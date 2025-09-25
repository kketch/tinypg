"""
TinyPG configuration management.
"""

import os
from pathlib import Path
from typing import Optional


class TinyPGConfig:
    """Global configuration for TinyPG."""

    # Default PostgreSQL version
    default_version: str = "15"

    # Cache directory for PostgreSQL binaries
    cache_dir: Path = Path.home() / ".tinypg"

    # Automatic cleanup of databases
    auto_cleanup: bool = True

    # Default timeout for database cleanup (seconds)
    default_timeout: int = 60

    # PostgreSQL download base URL
    postgresql_download_base: str = "https://ftp.postgresql.org/pub/source"

    # System temp directory override
    system_temp_dir: Optional[str] = None

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
        return cls.cache_dir
