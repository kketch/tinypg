
![logo](https://iili.io/Klv1Zcx.md.png)

# TinyPG

A Python package for creating ephemeral PostgreSQL databases, inspired by [ephemeralpg](https://github.com/eradman/ephemeralpg).

## Overview

TinyPG provides a clean Python API for creating temporary PostgreSQL databases for development and testing. It's designed to be self-contained and work without requiring system-wide PostgreSQL installation.

**Currently only tested on linux & osx. Does not work on Windows yet.**

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

# Install the built-in pgcrypto extension and use it immediately
with tinypg.database(extensions=["pgcrypto"]) as db_uri:
    import psycopg2
    conn = psycopg2.connect(db_uri)
    with conn.cursor() as cur:
        cur.execute("SELECT encode(digest('hello', 'sha256'), 'hex')")
        print(cur.fetchone()[0])  # -> SHA-256 hash
    conn.close()

# Discover which extensions ship with the bundled PostgreSQL binaries
from tinypg import get_available_extension, list_available_extensions

available = list_available_extensions()
pgcrypto_manifest = get_available_extension("pgcrypto")

assert "pgcrypto" in available
assert pgcrypto_manifest is not None
assert pgcrypto_manifest.default_version is not None

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

## Bundled PostgreSQL extensions

TinyPG downloads the same portable PostgreSQL builds that ship with the
`pg-embed` project and exposes metadata about every extension included with the
distribution. Use :func:`tinypg.list_available_extensions` or
:func:`tinypg.get_available_extension` to inspect this catalog at runtime. The
default PostgreSQL 15 bundle currently includes the following extensions:

| Extension | Default version | Available versions |
| --- | --- | --- |
| `adminpack` | 2.1 | 1.0, 1.0--1.1, 1.1--2.0, 2.0--2.1 |
| `amcheck` | 1.3 | 1.0, 1.0--1.1, 1.1--1.2, 1.2--1.3 |
| `autoinc` | 1.0 | 1.0 |
| `bloom` | 1.0 | 1.0 |
| `bool_plperl` | 1.0 | 1.0 |
| `bool_plperlu` | 1.0 | 1.0 |
| `btree_gin` | 1.3 | 1.0, 1.0--1.1, 1.1--1.2, 1.2--1.3 |
| `btree_gist` | 1.7 | 1.0--1.1, 1.1--1.2, 1.2, 1.2--1.3, 1.3--1.4, 1.4--1.5, 1.5--1.6, 1.6--1.7 |
| `citext` | 1.6 | 1.0--1.1, 1.1--1.2, 1.2--1.3, 1.3--1.4, 1.4, 1.4--1.5, 1.5--1.6 |
| `cube` | 1.5 | 1.0--1.1, 1.1--1.2, 1.2, 1.2--1.3, 1.3--1.4, 1.4--1.5 |
| `dblink` | 1.2 | 1.0--1.1, 1.1--1.2, 1.2 |
| `dict_int` | 1.0 | 1.0 |
| `dict_xsyn` | 1.0 | 1.0 |
| `earthdistance` | 1.1 | 1.0--1.1, 1.1 |
| `file_fdw` | 1.0 | 1.0 |
| `fuzzystrmatch` | 1.1 | 1.0--1.1, 1.1 |
| `hstore` | 1.8 | 1.1--1.2, 1.2--1.3, 1.3--1.4, 1.4, 1.4--1.5, 1.5--1.6, 1.6--1.7, 1.7--1.8 |
| `hstore_plperl` | 1.0 | 1.0 |
| `hstore_plperlu` | 1.0 | 1.0 |
| `hstore_plpython3u` | 1.0 | 1.0 |
| `insert_username` | 1.0 | 1.0 |
| `intagg` | 1.1 | 1.0--1.1, 1.1 |
| `intarray` | 1.5 | 1.0--1.1, 1.1--1.2, 1.2, 1.2--1.3, 1.3--1.4, 1.4--1.5 |
| `isn` | 1.2 | 1.0--1.1, 1.1, 1.1--1.2 |
| `jsonb_plperl` | 1.0 | 1.0 |
| `jsonb_plperlu` | 1.0 | 1.0 |
| `jsonb_plpython3u` | 1.0 | 1.0 |
| `lo` | 1.1 | 1.0--1.1, 1.1 |
| `ltree` | 1.2 | 1.0--1.1, 1.1, 1.1--1.2 |
| `ltree_plpython3u` | 1.0 | 1.0 |
| `moddatetime` | 1.0 | 1.0 |
| `old_snapshot` | 1.0 | 1.0 |
| `pageinspect` | 1.11 | 1.0--1.1, 1.1--1.2, 1.10--1.11, 1.2--1.3, 1.3--1.4, 1.4--1.5, 1.5, 1.5--1.6, 1.6--1.7, 1.7--1.8, 1.8--1.9, 1.9--1.10 |
| `pg_buffercache` | 1.3 | 1.0--1.1, 1.1--1.2, 1.2, 1.2--1.3 |
| `pg_freespacemap` | 1.2 | 1.0--1.1, 1.1, 1.1--1.2 |
| `pg_prewarm` | 1.2 | 1.0--1.1, 1.1, 1.1--1.2 |
| `pg_stat_statements` | 1.10 | 1.0--1.1, 1.1--1.2, 1.2--1.3, 1.3--1.4, 1.4, 1.4--1.5, 1.5--1.6, 1.6--1.7, 1.7--1.8, 1.8--1.9, 1.9--1.10 |
| `pg_surgery` | 1.0 | 1.0 |
| `pg_trgm` | 1.6 | 1.0--1.1, 1.1--1.2, 1.2--1.3, 1.3, 1.3--1.4, 1.4--1.5, 1.5--1.6 |
| `pg_visibility` | 1.2 | 1.0--1.1, 1.1, 1.1--1.2 |
| `pg_walinspect` | 1.0 | 1.0 |
| `pgcrypto` | 1.3 | 1.0--1.1, 1.1--1.2, 1.2--1.3, 1.3 |
| `pgrowlocks` | 1.2 | 1.0--1.1, 1.1--1.2, 1.2 |
| `pgstattuple` | 1.5 | 1.0--1.1, 1.1--1.2, 1.2--1.3, 1.3--1.4, 1.4, 1.4--1.5 |
| `plperl` | 1.0 | 1.0 |
| `plperlu` | 1.0 | 1.0 |
| `plpgsql` | 1.0 | 1.0 |
| `plpython3u` | 1.0 | 1.0 |
| `pltcl` | 1.0 | 1.0 |
| `pltclu` | 1.0 | 1.0 |
| `postgres_fdw` | 1.1 | 1.0, 1.0--1.1 |
| `refint` | 1.0 | 1.0 |
| `seg` | 1.4 | 1.0--1.1, 1.1, 1.1--1.2, 1.2--1.3, 1.3--1.4 |
| `sslinfo` | 1.2 | 1.0--1.1, 1.1--1.2, 1.2 |
| `tablefunc` | 1.0 | 1.0 |
| `tcn` | 1.0 | 1.0 |
| `tsm_system_rows` | 1.0 | 1.0 |
| `tsm_system_time` | 1.0 | 1.0 |
| `unaccent` | 1.1 | 1.0--1.1, 1.1 |
| `uuid-ossp` | 1.1 | 1.0--1.1, 1.1 |
| `xml2` | 1.1 | 1.0--1.1, 1.1 |

Third-party extensions such as `pgvector`, `pg_tle`, or `pgmq` are not packaged
with the official binaries yet. Adding additional
extension in the future could be possible so these ecosystems can be supported once the
project provides a portable installation workflow for them.

### Can I use other postgres extensions?

Not yet no. It's possible but it isn't supported yet.

At the moment the portable PostgreSQL builds bundled with TinyPG do not expose
the `pg_config` utility that PGXN requires, so the helper exits with a clear
error explaining that third-party compilation is not yet possible. This script
still serves as a reference point for the command sequence and will succeed once
the toolchain includes `pg_config` in a future release.

Building extensions requires a standard C compiler toolchain, development
headers, and network access to fetch dependency archives. These prerequisites
are available on most Linux distributions. This process is currently unsupported
as the trimmed down postgres distribution tinypg uses does not have pg_config 
or postgres dev headers avaialble.

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
