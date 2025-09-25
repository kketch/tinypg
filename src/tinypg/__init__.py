"""
TinyPG: Ephemeral PostgreSQL databases for Python development and testing.

Based on ephemeralpg by Eric Radman, reimplemented in pure Python.
"""

from .config import TinyPGConfig
from .context import async_database, database, database_pool
from .core import AsyncEphemeralDB, EphemeralDB
from .exceptions import (
    BinaryNotFoundError,
    DatabaseStartError,
    DatabaseTimeoutError,
    DownloadError,
    TinyPGError,
)

__version__ = "0.1.0"

__all__ = [
    "EphemeralDB",
    "AsyncEphemeralDB",
    "database",
    "async_database",
    "database_pool",
    "TinyPGConfig",
    "TinyPGError",
    "DatabaseStartError",
    "BinaryNotFoundError",
    "DownloadError",
    "DatabaseTimeoutError",
    "__version__",
]
