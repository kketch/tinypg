"""Using PostgreSQL extensions
=================================

This narrative guide expands on :mod:`tinypg.extensions` and walks through the
practical steps required to enable PostgreSQL extensions inside an ephemeral
database provisioned by TinyPG.

Declaring extensions
--------------------

You can request extensions when creating a database through any of TinyPG's
context managers or helpers. The ``extensions`` parameter accepts strings,
``ExtensionSpec`` instances, or :class:`tinypg.extensions.ExtensionManifest`
objects. The examples below demonstrate each option::

    import tinypg

    # Simple string input
    with tinypg.database(extensions=["pgcrypto"]):
        ...

    # Rich specification with cascade support
    from tinypg import ExtensionSpec

    spec = ExtensionSpec(name="pg_trgm", schema="public", cascade=True)
    with tinypg.database(extensions=[spec]):
        ...

    # Manifests can be turned into specs
    manifest = tinypg.get_available_extension("hstore")
    if manifest:
        with tinypg.database(extensions=[manifest]):
            ...

Discovering bundled extensions
-------------------------------

TinyPG parses the ``.control`` files that ship with the portable PostgreSQL
distribution during installation. The :func:`tinypg.list_available_extensions`
function returns a dictionary mapping extension names to
:class:`tinypg.extensions.ExtensionManifest` instances, each providing details
about default and upgradeable versions, dependencies, and associated SQL or
shared library files. Use it to present feature flags in your application or to
perform guard checks before requesting an installation.

Roadmap for additional ecosystems
---------------------------------

Only the extensions bundled with PostgreSQL itself are currently available.
Popular third-party projects such as ``pgvector``, ``pg_tle``, or ``pgmq``
require additional build steps and are not yet supported. The manifest APIs were
designed with these future workflows in mind, and TinyPG will grow the ability
to register custom manifests once the project offers a portable installation
story for community-maintained extensions.

Installing additional extensions with PGXN
------------------------------------------

Advanced users can experiment with third-party packages by compiling them
against the PostgreSQL toolchain that TinyPG downloads. The
``PostgreSQLBinaries.get_binary_path`` helper exposes the path to ``pg_config``,
which most build tools use to locate headers and libraries::

    from tinypg.binaries import PostgreSQLBinaries

    pg_config_path = PostgreSQLBinaries.get_binary_path("pg_config")

That path can be passed to command line installers such as
`PGXN <https://pgxn.github.io/>`_ by spawning a subprocess from Python. The
repository ships with a small helper that wires everything together::

    python scripts/pgxn_install_extension.py pgvector

Under the hood the script resolves TinyPG's ``pg_config`` executable and feeds
it to ``pgxn install``. You can mimic the behaviour manually if you prefer::

    import subprocess

    subprocess.run(
        [
            "pgxn",
            "install",
            "--pg_config",
            str(pg_config_path),
            "pgvector",
        ],
        check=True,
    )

The current TinyPG binaries mirror ``pg-embed``'s stripped-down toolchain and do
not ship ``pg_config`` yet. Running the helper therefore raises a descriptive
error instead of installing the requested extension. The command sequence is
still useful for future releases or for developers who rebuild PostgreSQL with
the full client utilities available.

The ``pgxn`` client supports ``--pg_config`` out of the box, but keep in mind
that it will modify the PostgreSQL installation referenced by that executable.
If you manage multiple TinyPG clusters simultaneously, install additional
extensions before the databases start or coordinate the installations carefully
to avoid races.

Building extensions typically requires a C compiler toolchain and standard
development headers. These are available on most Linux distributions and on
macOS with the Xcode command line tools. Windows support is not yet available
for TinyPG, and PGXN installations on that platform may require significant
manual setup.
"""
