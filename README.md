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

## Architecture

TinyPG consists of several key components:

- **Binary Management**: Downloads and manages PostgreSQL binaries
- **Database Creation**: Creates isolated database instances  
- **Port Management**: Handles TCP port allocation
- **Context Managers**: Provides clean Python APIs
- **Configuration**: Flexible configuration management

## API Reference

Coming soon

## Development Status

TinyPG is currently only test and optimized for Linux development environments.

This currently focus on creating ephemeral PostgresSQL databases for test scenarios, but it could also be used
to use PostgresSQL as an "embedded" database just like you would use SQLite (except you get Postgres instead!).

I also have yet to publish it to PyPi. I created it initially to run python tests using postgres without having to install it and I have also used it to provide a local PostgresSQL database for a GUI app.

## License

MIT License - see LICENSE file for details.

## Acknowledgments

Based on [ephemeralpg](https://github.com/eradman/ephemeralpg) by Eric Radman.