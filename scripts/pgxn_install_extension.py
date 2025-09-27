#!/usr/bin/env python3
"""Install a PostgreSQL extension from PGXN for the bundled TinyPG binaries."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from tinypg.binaries import PostgreSQLBinaries
from tinypg.config import TinyPGConfig
from tinypg.exceptions import BinaryNotFoundError


def install_extension(extension: str, *, quiet: bool = False) -> int:
    """Run ``pgxn install`` for ``extension`` using TinyPG's ``pg_config``."""

    pgxn = shutil.which("pgxn")
    if pgxn is None:
        raise RuntimeError(
            "pgxn executable not found. Install pgxnclient (pip install pgxnclient)."
        )

    version = TinyPGConfig.default_version
    PostgreSQLBinaries.ensure_version(version)

    try:
        pg_config = PostgreSQLBinaries.get_binary_path("pg_config", version)
    except BinaryNotFoundError as exc:
        raise RuntimeError(
            "TinyPG's bundled PostgreSQL does not expose pg_config; third-party "
            "extensions cannot currently be compiled against it."
        ) from exc
    if pg_config is None:
        raise RuntimeError("Unable to locate pg_config from TinyPG binaries")

    cmd = [
        pgxn,
        "install",
        "--pg_config",
        str(pg_config),
        extension,
    ]

    completed = subprocess.run(
        cmd,
        stdout=subprocess.PIPE if quiet else None,
        stderr=subprocess.PIPE if quiet else None,
        text=True,
        check=False,
    )

    if quiet and completed.stdout:
        sys.stdout.write(completed.stdout)
    if quiet and completed.stderr:
        sys.stderr.write(completed.stderr)

    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "extension",
        metavar="EXTENSION",
        help="Name of the extension to install via pgxn",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress pgxn output until the command finishes",
    )
    args = parser.parse_args(argv)

    return install_extension(args.extension, quiet=args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
