"""Tests covering TinyPG extension discovery and installation."""

import psycopg2
from psycopg2 import sql

from tinypg import (
    EphemeralDB,
    ExtensionManifest,
    ExtensionSpec,
    get_available_extension,
    list_available_extensions,
)


def test_extension_installation_on_startup():
    """Extensions requested at construction are installed automatically."""

    db = EphemeralDB(cleanup_timeout=0, extensions=["pgcrypto"])

    conn = None

    try:
        db.start()
        conn = psycopg2.connect(db.get_connection_info()["uri"])

        with conn.cursor() as cur:
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'pgcrypto'")
            assert cur.fetchone()[0] == "pgcrypto"
    finally:
        if conn is not None:
            conn.close()
        db.stop()


def test_extension_installation_after_start():
    """Extensions can be installed after the database started."""

    db = EphemeralDB(cleanup_timeout=0)

    conn = None

    try:
        db.start()
        manifest = get_available_extension("pgcrypto")
        assert isinstance(manifest, ExtensionManifest)

        db.create_extension(manifest)

        conn = psycopg2.connect(db.get_connection_info()["uri"])

        with conn.cursor() as cur:
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'pgcrypto'")
            assert cur.fetchone()[0] == "pgcrypto"
    finally:
        if conn is not None:
            conn.close()
        db.stop()


def test_extension_spec_sql_composition_is_safe():
    """Extension specifications produce safely quoted SQL statements."""

    spec = ExtensionSpec(
        name='pgcrypto"; DROP SCHEMA public; --',
        schema="dangerous schema",
        version="1.2.3'; DROP TABLE pg_catalog.pg_class; --",
        cascade=True,
    )

    statement = spec.to_sql()

    expected = sql.SQL("CREATE EXTENSION IF NOT EXISTS {}").format(
        sql.Identifier('pgcrypto"; DROP SCHEMA public; --')
    )
    expected += sql.SQL(" SCHEMA {}").format(sql.Identifier("dangerous schema"))
    expected += sql.SQL(" VERSION {}").format(
        sql.Literal("1.2.3'; DROP TABLE pg_catalog.pg_class; --")
    )
    expected += sql.SQL(" CASCADE")

    assert repr(statement) == repr(expected)
    assert isinstance(statement, sql.Composed)


def test_list_available_extensions_discovers_pgcrypto():
    """Bundled binaries include common extensions such as pgcrypto."""

    manifests = list_available_extensions()
    assert "pgcrypto" in manifests

    manifest = manifests["pgcrypto"]
    assert manifest.default_version is not None
    assert manifest.library_path is None or manifest.library_path.exists()
    assert "pgcrypto" in manifest.control_path.name


def test_get_available_extension_returns_manifest():
    """Manifests can be fetched individually by name."""

    manifest = get_available_extension("pgcrypto")
    assert isinstance(manifest, ExtensionManifest)
    assert "pgcrypto" in manifest.available_versions or manifest.default_version
