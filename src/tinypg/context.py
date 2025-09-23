"""
Context manager interfaces for TinyPG.
"""

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
    """
    Context manager that yields a database URI.
    
    Args:
        port: TCP port for the database (auto-assigned if None)
        timeout: Seconds before automatic cleanup
        postgres_args: Additional arguments to pass to postgres server
        version: PostgreSQL version to use
        keep_data: Keep data directory after stopping
    
    Yields:
        str: PostgreSQL connection URI
    
    Example:
        with tinypg.database() as uri:
            conn = psycopg2.connect(uri)
            # Use database...
        # Database automatically cleaned up
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
    """
    Async context manager that yields a database URI.
    
    Args:
        port: TCP port for the database (auto-assigned if None)
        timeout: Seconds before automatic cleanup
        postgres_args: Additional arguments to pass to postgres server
        version: PostgreSQL version to use
        keep_data: Keep data directory after stopping
    
    Yields:
        str: PostgreSQL connection URI
    
    Example:
        async with tinypg.async_database() as uri:
            conn = await asyncpg.connect(uri)
            # Use database...
        # Database automatically cleaned up
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
    """
    Context manager that yields multiple database URIs.
    
    Args:
        pool_size: Number of databases to create
        timeout: Seconds before automatic cleanup
        version: PostgreSQL version to use
        base_port: Base port number (will use base_port, base_port+1, etc.)
    
    Yields:
        List[str]: List of PostgreSQL connection URIs
    
    Example:
        with tinypg.database_pool(3) as uris:
            # uris is a list of 3 database connection strings
            for uri in uris:
                conn = psycopg2.connect(uri)
                # Use each database...
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
    """
    Async context manager that yields multiple database URIs.
    
    Args:
        pool_size: Number of databases to create
        timeout: Seconds before automatic cleanup
        version: PostgreSQL version to use
        base_port: Base port number (will use base_port, base_port+1, etc.)
    
    Yields:
        List[str]: List of PostgreSQL connection URIs
    
    Example:
        async with tinypg.async_database_pool(3) as uris:
            # uris is a list of 3 database connection strings
            tasks = [asyncpg.connect(uri) for uri in uris]
            connections = await asyncio.gather(*tasks)
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