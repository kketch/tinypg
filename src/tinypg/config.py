"""TinyPG configuration management."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional


def _default_cache_dir() -> Path:
    """Compute the default cache directory for downloaded PostgreSQL binaries."""

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        # When running as root prefer a shared location so that unprivileged
        # helper processes can still access the binaries.
        return Path(tempfile.gettempdir()) / "tinypg"

    return Path.home() / ".tinypg"


class TinyPGConfig:
    """Global configuration for TinyPG."""

    # Default PostgreSQL version
    default_version: str = "15"

    # Cache directory for PostgreSQL binaries
    cache_dir: Path = _default_cache_dir()

    # Automatic cleanup of databases
    auto_cleanup: bool = True

    # Default timeout for database cleanup (seconds)
    default_timeout: int = 60

    # PostgreSQL download base URL
    postgresql_download_base: str = "https://ftp.postgresql.org/pub/source"

    # System temp directory override
    system_temp_dir: Optional[str] = None

    # Runtime user/group used when dropping privileges for PostgreSQL helpers
    runtime_user: Optional[str] = None
    runtime_group: Optional[str] = None

    @classmethod
    def set_cache_dir(cls, path: Path) -> None:
        """Set the directory for caching PostgreSQL binaries."""
        cls.cache_dir = Path(path)
        cls.cache_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def set_default_version(cls, version: str) -> None:
        """Set the default PostgreSQL version to use."""
        cls.default_version = version

    @classmethod
    def get_temp_dir(cls) -> Path:
        """Get the system temporary directory."""
        if cls.system_temp_dir:
            return Path(cls.system_temp_dir)
        return Path(os.environ.get("TMPDIR", "/tmp"))

    @classmethod
    def get_cache_dir(cls) -> Path:
        """Get the cache directory, creating it if necessary."""
        cls.cache_dir.mkdir(parents=True, exist_ok=True)
        cls.cache_dir.chmod(0o755)
        cls._migrate_legacy_cache()
        return cls.cache_dir

    @classmethod
    def set_runtime_identity(cls, user: str, group: Optional[str] = None) -> None:
        """Configure the user/group used to run PostgreSQL helpers."""

        cls.runtime_user = user
        cls.runtime_group = group

    @classmethod
    def _migrate_legacy_cache(cls) -> None:
        """Copy binaries from the legacy cache directory if necessary."""

        legacy_dir = Path.home() / ".tinypg"

        if legacy_dir == cls.cache_dir or not legacy_dir.exists():
            return

        try:
            for entry in legacy_dir.iterdir():
                destination = cls.cache_dir / entry.name

                if destination.exists():
                    continue

                if entry.is_dir():
                    shutil.copytree(entry, destination, dirs_exist_ok=True)
                else:
                    shutil.copy2(entry, destination)
        except OSError:
            # Migration is best-effort; fallback to downloading if copying fails.
            pass
