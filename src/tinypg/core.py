"""
Core ephemeral database implementation.
"""

import asyncio
import getpass
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from .binaries import PostgreSQLBinaries
from .config import TinyPGConfig
from .exceptions import (
    DatabaseStartError,
    DatabaseTimeoutError,
    InitDBError,
    ProcessError,
)
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
        """
        self.port = port
        self.cleanup_timeout = cleanup_timeout
        self.postgres_args = postgres_args or []
        self.version = version or TinyPGConfig.default_version
        self.keep_data = keep_data

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

            # Set up automatic cleanup
            if self.cleanup_timeout > 0:
                self._setup_cleanup()

            self._is_running = True

            # Cache connection info
            self._connection_info = self._build_connection_info()

            return self._connection_info["uri"]

        except Exception as e:
            # Clean up on failure
            self.stop()
            raise DatabaseStartError(f"Failed to start database: {e}")

    def stop(self) -> None:
        """Stop the database and clean up resources."""
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

    def execute_sql(self, sql: str) -> None:
        """Execute SQL directly on the database."""
        if not self._is_running:
            raise DatabaseStartError("Database is not running")

        import getpass

        import psycopg2

        try:
            user = getpass.getuser()

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
                cur.execute(sql)

            conn.close()

        except psycopg2.Error as e:
            raise ProcessError(f"Failed to execute SQL: {e}")

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

        # Data directory for this PostgreSQL version
        data_dir = temp_path / self.version

        try:
            # Run initdb
            initdb_path = PostgreSQLBinaries.get_binary_path("initdb", self.version)

            subprocess.run(
                [
                    str(initdb_path),
                    "--nosync",
                    "-D",
                    str(data_dir),
                    "-E",
                    "UNICODE",
                    "-A",
                    "trust",
                ],
                check=True,
                capture_output=True,
                cwd=temp_path,
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
            subprocess.run(
                [
                    str(pg_ctl_path),
                    "-W",  # Don't wait for server to start
                    "-o",
                    " ".join(server_opts),
                    "-s",  # Silent mode
                    "-D",
                    str(self._data_dir),
                    "-l",
                    str(log_file),
                    "start",
                ],
                check=True,
                capture_output=True,
            )

            # Give PostgreSQL more time to start, especially with persistent data
            time.sleep(0.5)

        except subprocess.CalledProcessError as e:
            raise DatabaseStartError(f"Failed to start PostgreSQL server: {e}")

    def _stop_postgres_server(self) -> None:
        """Stop the PostgreSQL server."""
        try:
            pg_ctl_path = PostgreSQLBinaries.get_binary_path("pg_ctl", self.version)
            env = self._get_pg_environment()

            subprocess.run(
                [str(pg_ctl_path), "-W", "-D", str(self._data_dir), "stop"],
                env=env,
                check=True,
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
        env = os.environ.copy()

        if self.port:
            env["PGPORT"] = str(self.port)

        if self._temp_dir:
            env["PGHOST"] = self._temp_dir

        return env

    def _build_connection_info(self) -> Dict[str, Any]:
        """Build connection information dictionary."""
        user = getpass.getuser()

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

    async def execute_sql(self, sql: str) -> None:
        """Execute SQL asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, super().execute_sql, sql)

    async def __aenter__(self):
        """Async context manager entry."""
        return await self.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
