"""
TinyPG: Ephemeral PostgreSQL databases for Python development and testing.

Based on ephemeralpg by Eric Radman, reimplemented in pure Python.
"""

from .core import EphemeralDB, AsyncEphemeralDB
from .context import database, async_database, database_pool
from .config import TinyPGConfig
from .exceptions import (
    TinyPGError,
    DatabaseStartError,
    BinaryNotFoundError,
    DownloadError,
    DatabaseTimeoutError,
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