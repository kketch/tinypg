"""
Basic tests for TinyPG functionality.
"""

import psycopg2
import pytest

import tinypg
from tinypg import EphemeralDB


def test_port_manager():
    """Test port management utilities."""
    from tinypg.port_manager import get_free_port, is_port_available

    # Get a free port
    port = get_free_port()
    assert isinstance(port, int)
    assert 1024 <= port <= 65535

    # Port should be available
    assert is_port_available(port)


def test_ephemeral_db_basic():
    """Test basic EphemeralDB functionality."""
    db = EphemeralDB(cleanup_timeout=0)  # Disable auto-cleanup for testing

    try:
        # Start database
        uri = db.start()
        assert uri.startswith("postgresql://")
        assert db.is_running()

        # Get connection info
        info = db.get_connection_info()
        assert "uri" in info
        assert "database" in info
        assert info["database"] == "postgres"

    finally:
        db.stop()
        assert not db.is_running()


def test_context_manager():
    """Test context manager interface."""
    with tinypg.database(timeout=0) as uri:
        assert uri.startswith("postgresql://")

        # Connect and test database functionality
        conn = psycopg2.connect(uri)

        # Execute a simple query
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            assert result[0] == 1

        conn.close()


def test_sql_execution():
    """Test SQL execution functionality."""
    db = EphemeralDB(cleanup_timeout=0)

    try:
        db.start()

        # Execute some SQL
        db.execute_sql("CREATE TABLE test_table (id INT, name TEXT)")
        db.execute_sql("INSERT INTO test_table VALUES (1, 'test')")

        # Verify data exists using connection
        uri = db.get_connection_info()["uri"]
        conn = psycopg2.connect(uri)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM test_table")
            count = cur.fetchone()[0]
            assert count == 1

            cur.execute("SELECT * FROM test_table")
            row = cur.fetchone()
            assert row == (1, "test")

        conn.close()

    finally:
        db.stop()


@pytest.mark.asyncio
async def test_async_database():
    """Test async database functionality."""
    from tinypg import AsyncEphemeralDB

    db = AsyncEphemeralDB(cleanup_timeout=0)

    try:
        uri = await db.start()
        assert uri.startswith("postgresql://")

        # Test async SQL execution
        await db.execute_sql("CREATE TABLE async_test (id INT)")
        await db.execute_sql("INSERT INTO async_test VALUES (42)")

    finally:
        await db.stop()


def test_database_pool():
    """Test database pool functionality."""
    with tinypg.database_pool(pool_size=2, timeout=0) as uris:
        assert len(uris) == 2
        assert all(uri.startswith("postgresql://") for uri in uris)

        # Test that each database is independent
        for i, uri in enumerate(uris):
            conn = psycopg2.connect(uri)
            with conn.cursor() as cur:
                cur.execute(f"CREATE TABLE pool_test_{i} (id INT)")
                cur.execute(f"INSERT INTO pool_test_{i} VALUES ({i})")
            conn.close()
