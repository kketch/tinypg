"""Context manager interfaces for TinyPG."""

import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncContextManager, ContextManager, List, Optional

from .core import AsyncEphemeralDB, EphemeralDB


@contextmanager
def database(
    port: Optional[int] = None,
    timeout: int = 60,
    postgres_args: Optional[List[str]] = None,
    version: str = None,
    keep_data: bool = False,
) -> ContextManager[str]:
    """Yield a temporary PostgreSQL database URI.

    Args:
        port: TCP port for the database. When ``None`` a free port is
            allocated automatically.
        timeout: Seconds before the database is stopped automatically. Use
            ``0`` to keep it running indefinitely.
        postgres_args: Extra arguments passed to the ``postgres`` server
            process.
        version: PostgreSQL version identifier. Defaults to the
            ``tinypg.config.TinyPGConfig`` value when ``None``.
        keep_data: When ``True`` the data directory is preserved after the
            database stops. Useful for debugging failed test runs.

    Yields:
        str: PostgreSQL connection URI for the running database instance.

    Example:
        ```python
        import psycopg2
        import tinypg

        with tinypg.database() as uri:
            conn = psycopg2.connect(uri)
            conn.close()
        ```
    """
    db = EphemeralDB(
        port=port,
        cleanup_timeout=timeout,
        postgres_args=postgres_args,
        version=version,
        keep_data=keep_data,
    )

    try:
        uri = db.start()
        yield uri
    finally:
        db.stop()


@asynccontextmanager
async def async_database(
    port: Optional[int] = None,
    timeout: int = 60,
    postgres_args: Optional[List[str]] = None,
    version: str = None,
    keep_data: bool = False,
) -> AsyncContextManager[str]:
    """Asynchronously yield a temporary PostgreSQL database URI.

    Args:
        port: TCP port for the database. When ``None`` a free port is
            allocated automatically.
        timeout: Seconds before the database is stopped automatically. Use
            ``0`` to keep it running indefinitely.
        postgres_args: Extra arguments passed to the ``postgres`` server
            process.
        version: PostgreSQL version identifier. Defaults to the
            ``tinypg.config.TinyPGConfig`` value when ``None``.
        keep_data: When ``True`` the data directory is preserved after the
            database stops. Useful for debugging failed test runs.

    Yields:
        str: PostgreSQL connection URI for the running database instance.

    Example:
        ```python
        import asyncpg
        import tinypg

        async with tinypg.async_database() as uri:
            conn = await asyncpg.connect(uri)
            await conn.close()
        ```
    """
    db = AsyncEphemeralDB(
        port=port,
        cleanup_timeout=timeout,
        postgres_args=postgres_args,
        version=version,
        keep_data=keep_data,
    )

    try:
        uri = await db.start()
        yield uri
    finally:
        await db.stop()


@contextmanager
def database_pool(
    pool_size: int = 5,
    timeout: int = 60,
    version: str = None,
    base_port: Optional[int] = None,
) -> ContextManager[List[str]]:
    """Create a pool of independent PostgreSQL databases.

    Args:
        pool_size: Number of database instances to start.
        timeout: Seconds before each database is stopped automatically. Use
            ``0`` to disable automatic cleanup.
        version: PostgreSQL version identifier. Defaults to the
            ``tinypg.config.TinyPGConfig`` value when ``None``.
        base_port: Base port number. When provided, ports are allocated as
            ``base_port + i``.

    Yields:
        list[str]: Connection URIs for the running databases.

    Example:
        ```python
        import psycopg2
        import tinypg

        with tinypg.database_pool(3) as uris:
            connections = [psycopg2.connect(uri) for uri in uris]
            for conn in connections:
                conn.close()
        ```
    """
    databases = []
    uris = []

    try:
        for i in range(pool_size):
            port = None if base_port is None else base_port + i

            db = EphemeralDB(
                port=port,
                cleanup_timeout=timeout,
                version=version,
            )

            uri = db.start()
            databases.append(db)
            uris.append(uri)

        yield uris

    finally:
        # Clean up all databases
        for db in databases:
            try:
                db.stop()
            except Exception:
                # Continue cleaning up other databases even if one fails
                pass


@asynccontextmanager
async def async_database_pool(
    pool_size: int = 5,
    timeout: int = 60,
    version: str = None,
    base_port: Optional[int] = None,
) -> AsyncContextManager[List[str]]:
    """Asynchronously create a pool of independent PostgreSQL databases.

    Args:
        pool_size: Number of database instances to start.
        timeout: Seconds before each database is stopped automatically. Use
            ``0`` to disable automatic cleanup.
        version: PostgreSQL version identifier. Defaults to the
            ``tinypg.config.TinyPGConfig`` value when ``None``.
        base_port: Base port number. When provided, ports are allocated as
            ``base_port + i``.

    Yields:
        list[str]: Connection URIs for the running databases.

    Example:
        ```python
        import asyncpg
        import tinypg

        async with tinypg.async_database_pool(3) as uris:
            connections = await asyncio.gather(
                *(asyncpg.connect(uri) for uri in uris)
            )
            await asyncio.gather(*(conn.close() for conn in connections))
        ```
    """
    databases = []
    uris = []

    try:
        # Start all databases concurrently
        tasks = []
        for i in range(pool_size):
            port = None if base_port is None else base_port + i

            db = AsyncEphemeralDB(
                port=port,
                cleanup_timeout=timeout,
                version=version,
            )

            databases.append(db)
            tasks.append(db.start())

        # Wait for all databases to start
        uris = await asyncio.gather(*tasks)
        yield uris

    finally:
        # Clean up all databases concurrently
        if databases:
            cleanup_tasks = [db.stop() for db in databases]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
