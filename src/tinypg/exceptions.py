"""
TinyPG exception classes.
"""


class TinyPGError(Exception):
    """Base exception for TinyPG errors."""

    pass


class DatabaseStartError(TinyPGError):
    """Raised when database fails to start."""

    pass


class BinaryNotFoundError(TinyPGError):
    """Raised when PostgreSQL binaries are not available."""

    pass


class DownloadError(TinyPGError):
    """Raised when binary download fails."""

    pass


class DatabaseTimeoutError(TinyPGError):
    """Raised when database operations timeout."""

    pass


class ProcessError(TinyPGError):
    """Raised when subprocess operations fail."""

    pass


class InitDBError(TinyPGError):
    """Raised when database initialization fails."""

    pass
