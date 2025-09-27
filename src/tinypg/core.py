"""Core ephemeral database implementation."""

import asyncio
import getpass
import grp
import hashlib
import os
import pwd
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Union

if TYPE_CHECKING:
    from psycopg2.sql import Composable
from urllib.parse import quote

from .binaries import PostgreSQLBinaries
from .config import TinyPGConfig
from .exceptions import (
    DatabaseStartError,
    DatabaseTimeoutError,
    InitDBError,
    ProcessError,
)
from .extensions import ExtensionInput, ExtensionManifest, ExtensionSpec
from .port_manager import get_free_port


class EphemeralDB:
    """Manages a single ephemeral PostgreSQL database instance."""

    def __init__(
        self,
        port: Optional[int] = None,
        cleanup_timeout: int = 60,
        postgres_args: Optional[List[str]] = None,
        data_dir: Optional[Path] = None,
        version: str = None,
        keep_data: bool = False,
        extensions: Optional[Sequence[ExtensionInput]] = None,
    ) -> None:
        """
        Create an ephemeral PostgreSQL database.

        Args:
            port: TCP port for the database (auto-assigned if None)
            cleanup_timeout: Seconds before automatic cleanup (0 = no auto cleanup)
            postgres_args: Additional arguments to pass to postgres server
            data_dir: Custom data directory (temp dir if None)
            version: PostgreSQL version to use (uses default if None)
            keep_data: Keep data directory after stopping (for debugging)
            extensions: Extensions to install after the server starts. Items
                can be provided as strings (extension name), mappings with
                optional ``schema``, ``version`` and ``cascade`` keys, or
                :class:`tinypg.ExtensionSpec`/:class:`tinypg.ExtensionManifest`
                instances.
        """
        self.port = port
        self.cleanup_timeout = cleanup_timeout
        self.postgres_args = postgres_args or []
        self.version = version or TinyPGConfig.default_version
        self.keep_data = keep_data
        self._extensions = self._normalize_extensions(extensions)
        self._connection_user = getpass.getuser()

        # Determine the runtime user for PostgreSQL processes. When running as
        # root (as happens inside many CI environments) we drop privileges to a
        # less privileged user so that ``initdb`` and ``postgres`` accept the
        # invocation.
        self._runtime_uid = os.geteuid()
        self._runtime_gid = os.getegid()
        self._runtime_user = pwd.getpwuid(self._runtime_uid).pw_name
        self._runtime_group = grp.getgrgid(self._runtime_gid).gr_name
        self._drop_privileges = False

        if self._runtime_uid == 0:
            configured_user = (
                TinyPGConfig.runtime_user
                or os.environ.get("TINYPGRUNTIME_USER")
                or "nobody"
            )
            user_info = pwd.getpwnam(configured_user)
            self._runtime_uid = user_info.pw_uid
            self._runtime_user = user_info.pw_name

            configured_group = TinyPGConfig.runtime_group or os.environ.get(
                "TINYPGRUNTIME_GROUP"
            )
            if configured_group:
                group_info = grp.getgrnam(configured_group)
                self._runtime_gid = group_info.gr_gid
                self._runtime_group = group_info.gr_name
            else:
                self._runtime_gid = user_info.pw_gid
            self._runtime_group = grp.getgrgid(self._runtime_gid).gr_name

            self._drop_privileges = True

        # Ensure the cache directory is accessible when running helper
        # processes under a different user.
        self._ensure_runtime_access(TinyPGConfig.get_cache_dir())

        # Runtime state
        self._data_dir: Optional[Path] = data_dir
        self._temp_dir: Optional[str] = None
        self._process: Optional[subprocess.Popen] = None
        self._cleanup_process: Optional[subprocess.Popen] = None
        self._is_running = False
        self._connection_info: Optional[Dict[str, Any]] = None

        # Ensure PostgreSQL binaries are available
        PostgreSQLBinaries.ensure_version(self.version)

    def start(self) -> str:
        """
        Start the database and return connection URI.

        Returns:
            PostgreSQL connection URI

        Raises:
            DatabaseStartError: If database fails to start
        """
        if self._is_running:
            return self.get_connection_info()["uri"]

        try:
            # Initialize database if needed
            if self._data_dir is None:
                self._data_dir = self._initialize_database()

            # Assign port if needed
            if self.port is None:
                self.port = get_free_port()

            # Start PostgreSQL server
            self._start_postgres_server()

            self._is_running = True

            # Install requested extensions
            self._install_extensions()

            # Set up automatic cleanup
            if self.cleanup_timeout > 0:
                self._setup_cleanup()

            # Cache connection info
            self._connection_info = self._build_connection_info()

            return self._connection_info["uri"]

        except Exception as e:
            # Clean up on failure
            self._stop_impl()
            raise DatabaseStartError(f"Failed to start database: {e}")

    def stop(self) -> None:
        """Stop the database and clean up resources."""
        self._stop_impl()

    def _stop_impl(self) -> None:
        """Internal implementation of :meth:`stop`."""
        if not self._is_running:
            return

        try:
            # Stop cleanup process
            if self._cleanup_process:
                try:
                    self._cleanup_process.terminate()
                    self._cleanup_process.wait(timeout=5)
                except (subprocess.TimeoutExpired, ProcessLookupError):
                    pass
                self._cleanup_process = None

            # Stop PostgreSQL server
            if self._process:
                self._stop_postgres_server()

            # Clean up data directory
            if not self.keep_data and self._temp_dir:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                self._temp_dir = None

        finally:
            self._is_running = False
            self._process = None
            self._connection_info = None

    def is_running(self) -> bool:
        """Check if the database is currently running."""
        if not self._is_running:
            return False

        # Check if process is still alive
        if self._process and self._process.poll() is not None:
            self._is_running = False
            return False

        return True

    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get connection information.

        Returns:
            Dict with keys: host, port, database, user, uri
        """
        if not self._is_running:
            raise DatabaseStartError("Database is not running")

        if self._connection_info is None:
            self._connection_info = self._build_connection_info()

        return self._connection_info

    def execute_sql(self, statement: Union[str, "Composable"]) -> None:
        """Execute SQL directly on the database."""
        if not self._is_running:
            raise DatabaseStartError("Database is not running")

        import getpass

        import psycopg2

        try:
            user = self._connection_user

            # Connect to the postgres database
            if self.port:
                # Network connection
                conn = psycopg2.connect(
                    host="127.0.0.1", port=self.port, database="postgres", user=user
                )
            else:
                # Unix socket connection
                conn = psycopg2.connect(
                    host=self._temp_dir, database="postgres", user=user
                )

            conn.autocommit = True

            with conn.cursor() as cur:
                cur.execute(statement)

            conn.close()

        except psycopg2.Error as e:
            raise ProcessError(f"Failed to execute SQL: {e}")

    def install_extension(self, extension: ExtensionInput) -> None:
        """Install a PostgreSQL extension on the running database."""

        if not self._is_running:
            raise DatabaseStartError("Database is not running")

        spec = ExtensionSpec.from_value(extension)
        self.execute_sql(spec.to_sql())

    def create_extension(self, extension: ExtensionInput) -> None:
        """Alias for :meth:`install_extension` to mirror SQL semantics."""

        self.install_extension(extension)

    def install_extensions(self, extensions: Iterable[ExtensionInput]) -> None:
        """Install multiple PostgreSQL extensions on the running database."""

        for extension in extensions:
            self.install_extension(extension)

    def _normalize_extensions(
        self, extensions: Optional[Sequence[ExtensionInput]]
    ) -> List[ExtensionSpec]:
        """Normalize extension specifications provided by the user."""

        if not extensions:
            return []

        normalized: List[ExtensionSpec] = []

        for extension in extensions:
            normalized.append(ExtensionSpec.from_value(extension))

        return normalized

    def _build_command_environment(
        self, extra_env: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Create an environment mapping for PostgreSQL commands."""

        env = os.environ.copy()

        if self.port:
            env["PGPORT"] = str(self.port)

        if self._temp_dir:
            env["PGHOST"] = str(self._temp_dir)

        if self._drop_privileges:
            env.setdefault("HOME", str(self._temp_dir or self._data_dir or Path(".")))
            env["USER"] = self._runtime_user
            env["LOGNAME"] = self._runtime_user

        if extra_env:
            env.update(extra_env)

        return env

    def _run_command(
        self,
        args: Sequence[str],
        *,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = False,
        check: bool = True,
        timeout: Optional[float] = None,
    ) -> subprocess.CompletedProcess:
        """Run a PostgreSQL helper command, dropping privileges if required."""

        if env is None:
            env = self._build_command_environment()

        run_kwargs: Dict[str, Any] = {
            "cwd": cwd,
            "env": env,
            "check": check,
            "timeout": timeout,
        }

        if capture_output:
            run_kwargs["capture_output"] = True

        if self._drop_privileges:
            uid = self._runtime_uid
            gid = self._runtime_gid
            username = self._runtime_user

            def demote() -> None:
                try:
                    groups = os.getgrouplist(username, gid)
                except OSError:
                    groups = [gid]

                os.setgroups(groups)
                os.setgid(gid)
                os.setuid(uid)

            run_kwargs["preexec_fn"] = demote

        return subprocess.run(
            args, **{k: v for k, v in run_kwargs.items() if v is not None}
        )

    def _ensure_directory_owner(
        self, path: Path, mode: int = 0o700, *, create: bool = True
    ) -> None:
        """Ensure a directory exists with the correct ownership and mode."""

        if create:
            path.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            return

        os.chmod(path, mode)

        if self._drop_privileges:
            shutil.chown(path, self._runtime_uid, self._runtime_gid)

    def _ensure_runtime_access(self, path: Path) -> None:
        """Ensure the runtime PostgreSQL user can traverse the given path."""

        if not self._drop_privileges:
            return

        try:
            resolved = path.resolve()
        except FileNotFoundError:
            resolved = path

        temp_root = TinyPGConfig.get_temp_dir().resolve()

        if not resolved.is_relative_to(temp_root):
            return

        current = resolved

        while True:
            if current.exists():
                mode = current.stat().st_mode
                os.chmod(current, mode | 0o111)

            if current == temp_root or current.parent == current:
                break

            current = current.parent

    def load_sql_file(self, file_path: Path) -> None:
        """Load and execute SQL from a file."""
        if not file_path.exists():
            raise FileNotFoundError(f"SQL file not found: {file_path}")

        # Read SQL file and execute it
        with open(file_path, "r") as f:
            sql_content = f.read()

        self.execute_sql(sql_content)

    def _initialize_database(self) -> Path:
        """Initialize a new PostgreSQL database cluster."""
        # Create temporary directory
        self._temp_dir = tempfile.mkdtemp(prefix="tinypg.")
        temp_path = Path(self._temp_dir)

        # Ensure the PostgreSQL runtime user owns the temp directory so that
        # initdb can create the cluster even when the main process runs as
        # root.
        self._ensure_directory_owner(temp_path, create=False)

        # Data directory for this PostgreSQL version
        data_dir = temp_path / self.version

        try:
            # Run initdb
            initdb_path = PostgreSQLBinaries.get_binary_path("initdb", self.version)

            self._run_command(
                [
                    str(initdb_path),
                    "--nosync",
                    "-D",
                    str(data_dir),
                    "-E",
                    "UNICODE",
                    "-A",
                    "trust",
                    "-U",
                    self._connection_user,
                ],
                capture_output=True,
                cwd=temp_path,
                env=self._build_command_environment(),
            )

            # Configure PostgreSQL for ephemeral use
            self._configure_postgresql(data_dir)

            return data_dir

        except subprocess.CalledProcessError as e:
            raise InitDBError(f"Failed to initialize database: {e}")

    def _configure_postgresql(self, data_dir: Path) -> None:
        """Configure PostgreSQL for ephemeral use (based on pg_tmp.sh)."""
        config_file = data_dir / "postgresql.conf"

        # Additional configuration for ephemeral database
        config_additions = f"""
# TinyPG ephemeral database configuration
unix_socket_directories = '{self._temp_dir}'
listen_addresses = ''
shared_buffers = 12MB
fsync = off
synchronous_commit = off
full_page_writes = off
log_min_duration_statement = 0
log_connections = on
log_disconnections = on
"""

        with open(config_file, "a") as f:
            f.write(config_additions)

    def _install_extensions(self) -> None:
        """Install user-requested extensions on the running database."""

        if not self._extensions:
            return

        for extension in self._extensions:
            self.execute_sql(extension.to_sql())

    def _start_postgres_server(self) -> None:
        """Start the PostgreSQL server process."""
        try:
            pg_ctl_path = PostgreSQLBinaries.get_binary_path("pg_ctl", self.version)

            # Build server options
            server_opts = []
            if self.port:
                server_opts.extend(
                    ["-c", f"listen_addresses=*", "-c", f"port={self.port}"]
                )

            # Add user-provided options
            if self.postgres_args:
                server_opts.extend(self.postgres_args)

            # Log file
            log_file = self._data_dir / "postgres.log"

            # Start server
            self._run_command(
                [
                    str(pg_ctl_path),
                    "-w",  # Wait for server to become ready
                    "-o",
                    " ".join(server_opts),
                    "-s",  # Silent mode
                    "-D",
                    str(self._data_dir),
                    "-l",
                    str(log_file),
                    "start",
                ],
                capture_output=True,
                env=self._build_command_environment(),
            )

            # Give PostgreSQL a brief moment after pg_ctl reports success.
            time.sleep(0.1)

        except subprocess.CalledProcessError as e:
            raise DatabaseStartError(f"Failed to start PostgreSQL server: {e}")

    def _stop_postgres_server(self) -> None:
        """Stop the PostgreSQL server."""
        try:
            pg_ctl_path = PostgreSQLBinaries.get_binary_path("pg_ctl", self.version)

            self._run_command(
                [str(pg_ctl_path), "-w", "-D", str(self._data_dir), "stop"],
                env=self._build_command_environment(),
                capture_output=True,
                timeout=30,
            )

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            # Force kill if graceful shutdown fails
            if self._process:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()

    def _setup_cleanup(self) -> None:
        """Set up automatic cleanup process (like in pg_tmp.sh)."""
        # This mimics the background cleanup process in pg_tmp.sh
        # We could implement this as a separate thread or process
        pass

    def _get_pg_environment(self) -> Dict[str, str]:
        """Get environment variables for PostgreSQL commands."""

        return self._build_command_environment()

    def _build_connection_info(self) -> Dict[str, Any]:
        """Build connection information dictionary."""
        user = self._connection_user

        if self.port:
            # Network connection
            host = "127.0.0.1"
            uri = f"postgresql://{user}@{host}:{self.port}/postgres"
        else:
            # Unix socket connection
            host = self._temp_dir
            # URL-encode the socket path
            encoded_host = quote(host, safe="")
            uri = f"postgresql:///postgres?host={encoded_host}"

        return {
            "host": host,
            "port": self.port,
            "database": "postgres",
            "user": user,
            "uri": uri,
        }

    def __enter__(self):
        """Context manager entry."""
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


class AsyncEphemeralDB(EphemeralDB):
    """Async version of EphemeralDB for use with asyncio."""

    async def start(self) -> str:
        """Async version of start()."""
        # Run synchronous start in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, super().start)

    async def stop(self) -> None:
        """Async version of stop()."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, super().stop)

    async def execute_sql(self, statement: Union[str, "Composable"]) -> None:
        """Execute SQL asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, super().execute_sql, statement)

    async def install_extension(self, extension: ExtensionInput) -> None:
        """Install a PostgreSQL extension asynchronously."""

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, super().install_extension, extension)

    async def create_extension(self, extension: ExtensionInput) -> None:
        """Async alias for :meth:`install_extension`."""

        await self.install_extension(extension)

    async def install_extensions(self, extensions: Iterable[ExtensionInput]) -> None:
        """Install multiple PostgreSQL extensions asynchronously."""

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, super().install_extensions, extensions)

    async def __aenter__(self):
        """Async context manager entry."""
        return await self.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


class PersistentDB(EphemeralDB):
    """Manage a reusable PostgreSQL database for local development."""

    def __init__(
        self,
        name: str,
        *,
        base_dir: Optional[Path] = None,
        port: Optional[int] = None,
        postgres_args: Optional[List[str]] = None,
        version: str = None,
        extensions: Optional[Sequence[ExtensionInput]] = None,
    ) -> None:
        """
        Create (or reuse) a persistent PostgreSQL database instance.

        Args:
            name: Identifier used to group database files on disk.
            base_dir: Optional directory used to store persistent data. When
                omitted the database is stored inside ``TinyPGConfig``'s cache
                directory under ``persistent/<name>/<version>``.
            port: TCP port for the database (auto-assigned when ``None``).
            postgres_args: Additional arguments passed to the ``postgres``
                server process.
            version: PostgreSQL version identifier. Defaults to the
                ``tinypg.config.TinyPGConfig`` value when ``None``.
            extensions: Extensions to install after the server starts.
        """

        version = version or TinyPGConfig.default_version

        persistent_root = (
            Path(base_dir)
            if base_dir is not None
            else TinyPGConfig.get_cache_dir() / "persistent" / name
        )
        persistent_root.mkdir(parents=True, exist_ok=True)

        version_dir = persistent_root / version
        version_dir.mkdir(parents=True, exist_ok=True)
        data_dir_path = version_dir / "data"
        data_dir_exists = data_dir_path.exists()

        super().__init__(
            port=port,
            cleanup_timeout=0,
            postgres_args=postgres_args,
            data_dir=data_dir_path if data_dir_exists else None,
            version=version,
            keep_data=True,
            extensions=extensions,
        )

        self._name = name
        self._version_dir = version_dir
        self._data_dir_path = data_dir_path

        socket_root = TinyPGConfig.get_temp_dir() / "tinypg" / "sockets"
        socket_key = f"{name}-{version}-{persistent_root}"
        socket_id = hashlib.sha256(socket_key.encode("utf-8")).hexdigest()[:8]
        self._socket_dir = socket_root / socket_id

        self._ensure_directory_owner(self._socket_dir, mode=0o755)
        self._ensure_runtime_access(self._socket_dir)
        self._ensure_runtime_access(self._version_dir)
        # Ensure directories are owned by the runtime PostgreSQL user so that
        # subsequent invocations can reuse the data safely.
        self._ensure_directory_owner(persistent_root, mode=0o755, create=False)
        self._ensure_directory_owner(self._version_dir, mode=0o755, create=False)
        if data_dir_exists:
            self._ensure_directory_owner(self._data_dir_path, create=False)
            self._data_dir = self._data_dir_path

        self._temp_dir = str(self._socket_dir)

    def start(self) -> str:
        """Start the persistent database and return the connection URI."""

        # Ensure socket directory is always set to the persistent location.
        self._ensure_directory_owner(self._socket_dir, mode=0o755)
        self._temp_dir = str(self._socket_dir)
        self._ensure_existing_instance_stopped()
        return super().start()

    def _initialize_database(self) -> Path:
        """Initialize the persistent PostgreSQL database cluster."""

        data_dir = self._data_dir_path
        self._ensure_directory_owner(self._version_dir, mode=0o755)
        self._ensure_directory_owner(self._socket_dir, mode=0o755)
        self._temp_dir = str(self._socket_dir)

        pg_version_file = data_dir / "PG_VERSION"
        if pg_version_file.exists():
            self._ensure_directory_owner(data_dir, create=False)
            return data_dir

        if data_dir.exists():
            shutil.rmtree(data_dir)

        initdb_path = PostgreSQLBinaries.get_binary_path("initdb", self.version)

        self._run_command(
            [
                str(initdb_path),
                "-D",
                str(data_dir),
                "-E",
                "UNICODE",
                "-A",
                "trust",
                "-U",
                self._connection_user,
            ],
            capture_output=True,
            cwd=self._version_dir,
            env=self._build_command_environment(),
        )

        self._configure_postgresql(data_dir)
        self._ensure_directory_owner(data_dir, create=False)
        return data_dir

    def _ensure_existing_instance_stopped(self) -> None:
        """Stop any lingering PostgreSQL instance using this data directory."""

        if not self._data_dir_path.exists():
            return

        pid_file = self._data_dir_path / "postmaster.pid"

        if not pid_file.exists():
            return

        pg_ctl_path = PostgreSQLBinaries.get_binary_path("pg_ctl", self.version)

        try:
            self._run_command(
                [str(pg_ctl_path), "-w", "-D", str(self._data_dir_path), "stop"],
                capture_output=True,
                env=self._build_command_environment(),
            )
        except subprocess.CalledProcessError:
            try:
                pid_file.unlink(missing_ok=True)
            except OSError:
                pass

    def _configure_postgresql(self, data_dir: Path) -> None:
        """Configure PostgreSQL for persistent local usage."""

        config_file = data_dir / "postgresql.conf"
        config_additions = "\n".join(
            [
                "# TinyPG persistent database configuration",
                f"unix_socket_directories = '{self._socket_dir}'",
                "listen_addresses = 'localhost'",
            ]
        )

        with open(config_file, "a") as f:
            f.write(config_additions + "\n")
