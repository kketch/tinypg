"""
[![Klv1Zcx.md.png](https://iili.io/Klv1Zcx.md.png)](https://freeimage.host/i/Klv1Zcx)

TinyPG: Ephemeral PostgreSQL databases for Python development and testing.

TinyPG provides a clean Python API for creating temporary PostgreSQL databases for development and testing. It's designed to be self-contained and work without requiring system-wide PostgreSQL installation.

## Features

- **Pure Python**: Takes care of downloading portable postgresql binaries for you
- **Fast startup**: Fast database initialization
- **Development-focused**: Perfect for writing python integrations tests against postgres without having to configure it in your environment
- **Good dev UX**: Context managers and pytest fixtures & works seamlessly with your existing code (SQLAlchemy, async ...)
- **(Optional) Supports compiling postgres from sources**: if you're not comfortable pulling prebuilt binaries from the internet

## Installation

You can install TinyPG from PyPI using your preferred Python packaging tool:

```bash
# Using pip
pip install tinypg

# Using uv
uv pip install tinypg
```

The package provides optional extras for asynchronous drivers and development
tooling. For example, to install the async dependencies with uv:

```bash
uv pip install "tinypg[async]"
```

## Quick Start

```python
import tinypg

# Simple usage with context manager
with tinypg.database() as db_uri:
    import psycopg2
    conn = psycopg2.connect(db_uri)
    # Use database...
# Database automatically cleaned up

# Advanced usage
db = tinypg.EphemeralDB(port=5433, cleanup_timeout=300)
uri = db.start()
try:
    # Use database...
    pass
finally:
    db.stop()
```

## Requirements

- Python 3.8+
- PostgreSQL source compilation tools (if binaries need to be built)

## Github repository

TinyPG's github repository is available there:
[Github repository](https://github.com/kketch/tinypg)

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
