"""Helpers for working with PostgreSQL extensions.

TinyPG ships with the same portable PostgreSQL builds that power the
``pg-embed`` project. Those archives bundle more than sixty standard extensions
and this module provides the discovery and installation helpers that surface
them to application code.

The :class:`ExtensionSpec` dataclass is a normalized representation of the
``CREATE EXTENSION`` command that TinyPG understands. It accepts either strings,
mapping objects, or :class:`ExtensionManifest` instances and renders safe SQL
using psycopg2 composables::

    from tinypg import database, ExtensionSpec

    with database(extensions=["pgcrypto", ExtensionSpec(name="pg_trgm")]):
        ...  # both extensions are installed before yielding the DSN

Two convenience helpers make it easy to inspect the bundled catalog at runtime:

``list_available_extensions()``
    Returns a dictionary of :class:`ExtensionManifest` objects keyed by name.

``get_available_extension(name)``
    Looks up a single :class:`ExtensionManifest` by name and returns ``None`` if
    the extension is not shipped with the selected PostgreSQL version.

TinyPG currently exposes the extensions provided by the upstream PostgreSQL
distribution. Third-party projects such as ``pgvector``, ``pg_tle``, or
``pgmq`` are not yet packaged with TinyPG, but future releases will allow
registering custom manifests so those ecosystems can be supported.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, Union


@dataclass(frozen=True)
class ExtensionSpec:
    """Normalized description of a PostgreSQL extension."""

    name: str
    schema: Optional[str] = None
    version: Optional[str] = None
    cascade: bool = False

    @classmethod
    def from_value(cls, value: "ExtensionInput") -> "ExtensionSpec":
        """Create an :class:`ExtensionSpec` from user input."""

        if isinstance(value, cls):
            return value

        if isinstance(value, ExtensionManifest):
            return value.to_spec()

        if isinstance(value, str):
            return cls(name=value)

        if isinstance(value, dict):
            if "name" not in value or not value["name"]:
                raise ValueError("Extension specification requires a non-empty 'name'.")

            return cls(
                name=value["name"],
                schema=value.get("schema"),
                version=value.get("version"),
                cascade=bool(value.get("cascade", False)),
            )

        raise TypeError(
            "Extension specification must be a string, mapping, or ExtensionSpec instance."
        )

    def to_sql(self):
        """Render a safe ``CREATE EXTENSION`` SQL statement."""

        from psycopg2 import sql

        statement = sql.SQL("CREATE EXTENSION IF NOT EXISTS {}").format(
            sql.Identifier(self.name)
        )

        if self.schema:
            statement += sql.SQL(" SCHEMA {}").format(sql.Identifier(self.schema))

        if self.version:
            statement += sql.SQL(" VERSION {}").format(sql.Literal(self.version))

        if self.cascade:
            statement += sql.SQL(" CASCADE")

        return statement


@dataclass(frozen=True)
class ExtensionManifest:
    """Metadata about an available PostgreSQL extension."""

    name: str
    default_version: Optional[str] = None
    comment: Optional[str] = None
    relocatable: Optional[bool] = None
    requires: Tuple[str, ...] = ()
    control_path: Optional[Path] = None
    sql_directory: Optional[Path] = None
    library_path: Optional[Path] = None
    available_versions: Tuple[str, ...] = ()
    schema: Optional[str] = None

    def to_spec(
        self,
        *,
        version: Optional[str] = None,
        schema: Optional[str] = None,
        cascade: bool = False,
    ) -> ExtensionSpec:
        """Create an :class:`ExtensionSpec` targeting this manifest."""

        return ExtensionSpec(
            name=self.name,
            schema=schema or self.schema,
            version=version or self.default_version,
            cascade=cascade,
        )


ExtensionInput = Union[ExtensionManifest, ExtensionSpec, str, Dict[str, object]]


def list_available_extensions(
    version: Optional[str] = None,
) -> Dict[str, ExtensionManifest]:
    """Return manifests for extensions available in the bundled binaries."""

    from .binaries import PostgreSQLBinaries

    return PostgreSQLBinaries.list_extension_manifests(version=version)


def get_available_extension(
    name: str, version: Optional[str] = None
) -> Optional[ExtensionManifest]:
    """Return the manifest for ``name`` if the extension is bundled."""

    from .binaries import PostgreSQLBinaries

    return PostgreSQLBinaries.get_extension_manifest(name=name, version=version)


__all__ = [
    "ExtensionInput",
    "ExtensionManifest",
    "ExtensionSpec",
    "get_available_extension",
    "list_available_extensions",
]
