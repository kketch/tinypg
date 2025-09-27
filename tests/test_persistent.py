"""Tests for the PersistentDB helper."""

import uuid

import psycopg2

import tinypg


def test_persistent_database(tmp_path):
    """PersistentDB should reuse the same data directory across restarts."""

    name = f"test-{uuid.uuid4().hex}"
    base_dir = tmp_path / "persistent"

    db = tinypg.PersistentDB(name=name, base_dir=base_dir)

    try:
        uri = db.start()
        conn = psycopg2.connect(uri)
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS persistent_test (id SERIAL PRIMARY KEY, value TEXT)"
            )
            cur.execute("INSERT INTO persistent_test (value) VALUES ('hello')")
        conn.commit()
        conn.close()
    finally:
        db.stop()

    db_reuse = tinypg.PersistentDB(name=name, base_dir=base_dir)

    try:
        uri = db_reuse.start()
        conn = psycopg2.connect(uri)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM persistent_test")
            (count,) = cur.fetchone()
        conn.close()
    finally:
        db_reuse.stop()

    assert count == 1
