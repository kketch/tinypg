
[![Klv1Zcx.md.png](https://iili.io/Klv1Zcx.md.png)](https://freeimage.host/i/Klv1Zcx)

# TinyPG

A Python package for creating ephemeral PostgreSQL databases, inspired by [ephemeralpg](https://github.com/eradman/ephemeralpg).

## Overview

TinyPG provides a clean Python API for creating temporary PostgreSQL databases for development and testing. It's designed to be self-contained and work without requiring system-wide PostgreSQL installation.

**Currently only tested on linux, but should work on OSX and Windows hopefully**

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

## Documentation / API Reference

TinyPG's documentation is available there:
[docs](https://python-tinypg.readthedocs.io/en/latest/)


## Architecture

TinyPG consists of several key components:

- **Binary Management**: Downloads and manages PostgreSQL binaries
- **Database Creation**: Creates isolated database instances  
- **Port Management**: Handles TCP port allocation
- **Context Managers**: Provides clean Python APIs
- **Configuration**: Flexible configuration management

## Development Status

TinyPG is currently only test and optimized for Linux development environments.

This currently focus on creating ephemeral PostgresSQL databases for test scenarios, but it could also be used
to use PostgresSQL as an "embedded" database just like you would use SQLite (except you get Postgres instead!).

TinyPG is currently primarily tested on Linux, but contributions that improve support on other platforms are welcome. The project started as a way to run PostgreSQL-backed test suites without installing Postgres globally and can also power local development environments that need an "embedded" PostgreSQL instance.

## License

MIT License - see LICENSE file for details.

## Acknowledgments

Based on [ephemeralpg](https://github.com/eradman/ephemeralpg) by Eric Radman.
