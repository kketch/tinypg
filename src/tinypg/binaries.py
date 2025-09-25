"""
PostgreSQL binary management - download, install, and manage PostgreSQL binaries.
"""

import lzma
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import requests

from .config import TinyPGConfig
from .exceptions import BinaryNotFoundError, DownloadError, ProcessError


class PostgreSQLBinaries:
    """Manages PostgreSQL binary installation and versioning."""

    # PostgreSQL versions supported (from pg-embed)
    SUPPORTED_VERSIONS = {
        "17": "17.2.0",
        "16": "16.6.0",
        "15": "15.9.0",
        "14": "14.15.0",
        "13": "13.18.0",
        "12": "12.22.0",
        "11": "11.22.1",
        "10": "10.23.0",
    }

    # Maven repository base URL (same as pg-embed)
    MAVEN_BASE_URL = "https://repo1.maven.org/maven2/io/zonky/test/postgres"

    # Required binaries (only core server binaries, not client utilities)
    REQUIRED_BINARIES = ["initdb", "postgres", "pg_ctl"]

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or TinyPGConfig.get_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Detect platform
        self.os_name = self._detect_os()
        self.arch = self._detect_arch()

    def _detect_os(self) -> str:
        """Detect the operating system."""
        system = platform.system().lower()
        if system == "darwin":
            return "darwin"
        elif system == "windows":
            return "windows"
        elif system == "linux":
            # For simplicity, assume regular Linux (not Alpine)
            return "linux"
        else:
            raise DownloadError(f"Unsupported operating system: {system}")

    def _detect_arch(self) -> str:
        """Detect the CPU architecture."""
        machine = platform.machine().lower()
        if machine in ["x86_64", "amd64"]:
            return "amd64"
        elif machine in ["i386", "i686"]:
            return "i386"
        elif machine in ["armv7l", "armv7"]:
            return "arm32v7"
        elif machine in ["aarch64", "arm64"]:
            return "arm64v8"
        elif machine == "ppc64le":
            return "ppc64le"
        else:
            raise DownloadError(f"Unsupported architecture: {machine}")

    def _get_platform_string(self) -> str:
        """Get the platform string for binary downloads."""
        return f"{self.os_name}-{self.arch}"

    @classmethod
    def ensure_version(cls, version: str) -> Path:
        """
        Ensure PostgreSQL version is available, download if needed.

        Args:
            version: PostgreSQL version (e.g., "15")

        Returns:
            Path to the PostgreSQL installation directory

        Raises:
            BinaryNotFoundError: If version is not supported
            DownloadError: If download fails
        """
        manager = cls()

        if version not in cls.SUPPORTED_VERSIONS:
            raise BinaryNotFoundError(f"Unsupported PostgreSQL version: {version}")

        install_dir = manager._get_install_dir(version)

        # Check if already installed
        if manager._is_version_installed(version):
            return install_dir

        # Try to find system PostgreSQL first
        if manager._try_system_postgresql(version):
            return manager._get_system_postgresql_path()

        # Download and install
        return manager.download_postgresql(version)

    @classmethod
    def get_binary_path(cls, binary_name: str, version: str = None) -> Path:
        """
        Get path to a specific PostgreSQL binary.

        Args:
            binary_name: Name of binary (initdb, postgres, pg_ctl, etc.)
            version: PostgreSQL version (uses default if None)

        Returns:
            Path to the binary

        Raises:
            BinaryNotFoundError: If binary is not found
        """
        manager = cls()

        if version is None:
            version = TinyPGConfig.default_version

        # Check system installation first
        system_binary = shutil.which(binary_name)
        if system_binary and manager._verify_system_binary_version(
            system_binary, version
        ):
            return Path(system_binary)

        # Check our installation
        install_dir = manager._get_install_dir(version)
        binary_path = install_dir / "bin" / binary_name

        if binary_path.exists() and os.access(binary_path, os.X_OK):
            return binary_path

        raise BinaryNotFoundError(
            f"Binary {binary_name} not found for PostgreSQL {version}"
        )

    @classmethod
    def list_available_versions(cls) -> List[str]:
        """List locally available PostgreSQL versions."""
        manager = cls()
        versions = []

        for version in cls.SUPPORTED_VERSIONS:
            if manager._is_version_installed(version):
                versions.append(version)

        return versions

    def download_postgresql(self, version: str, force: bool = False) -> Path:
        """
        Download and install a specific PostgreSQL version.

        Args:
            version: PostgreSQL version to download
            force: Force re-download even if already exists

        Returns:
            Path to installation directory

        Raises:
            DownloadError: If download or installation fails
        """
        install_dir = self._get_install_dir(version)

        if install_dir.exists() and not force:
            return install_dir

        try:
            # Create temporary directory for download
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                print(
                    f"Downloading PostgreSQL {version} binary for {self._get_platform_string()}..."
                )
                jar_path = self._download_binary(version, temp_path)

                print(f"Extracting PostgreSQL {version}...")
                extracted_dir = self._extract_binary(jar_path, temp_path)

                print(f"Installing PostgreSQL {version}...")
                self._install_binary(extracted_dir, install_dir)

                # Verify installation
                self._verify_installation(install_dir)

                return install_dir

        except Exception as e:
            # Clean up failed installation
            if install_dir.exists():
                shutil.rmtree(install_dir, ignore_errors=True)
            raise DownloadError(f"Failed to install PostgreSQL {version}: {e}")

    def _download_binary(self, version: str, temp_dir: Path) -> Path:
        """Download prebuilt PostgreSQL binary from Maven repository."""
        full_version = self.SUPPORTED_VERSIONS[version]
        platform = self._get_platform_string()

        # Construct Maven download URL (same pattern as pg-embed)
        url = (
            f"{self.MAVEN_BASE_URL}/embedded-postgres-binaries-{platform}/"
            f"{full_version}/embedded-postgres-binaries-{platform}-{full_version}.jar"
        )

        try:
            response = requests.get(url, timeout=300, stream=True)
            response.raise_for_status()
        except requests.RequestException as e:
            raise DownloadError(
                f"Failed to download PostgreSQL {version} for {platform}: {e}"
            )

        jar_path = temp_dir / f"postgresql-{version}-{platform}.jar"
        with open(jar_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return jar_path

    def _extract_binary(self, jar_path: Path, temp_dir: Path) -> Path:
        """Extract PostgreSQL binary from JAR file."""
        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)

        # JAR files are ZIP archives
        with zipfile.ZipFile(jar_path, "r") as jar:
            # Find the .txz file inside the JAR
            txz_files = [name for name in jar.namelist() if name.endswith(".txz")]
            if not txz_files:
                raise DownloadError("No .txz file found in PostgreSQL JAR")

            txz_name = txz_files[0]
            jar.extract(txz_name, extract_dir)

        txz_path = extract_dir / txz_name
        return self._extract_txz(txz_path, extract_dir)

    def _extract_txz(self, txz_path: Path, extract_dir: Path) -> Path:
        """Extract .txz (tar.xz) file."""
        # Extract .txz to .tar first
        tar_path = txz_path.with_suffix("")  # Remove .xz, keeping .tar

        with lzma.open(txz_path, "rb") as xz_file:
            with open(tar_path, "wb") as tar_file:
                shutil.copyfileobj(xz_file, tar_file)

        # Extract tar file
        with tarfile.open(tar_path, "r") as tar:
            tar.extractall(extract_dir, filter="data")

        # The binaries are extracted directly into bin/, lib/, share/ directories
        # Check if we have the expected PostgreSQL structure
        expected_dirs = ["bin", "lib", "share"]
        found_dirs = [item.name for item in extract_dir.iterdir() if item.is_dir()]

        if all(dir_name in found_dirs for dir_name in expected_dirs):
            # The extract_dir itself contains the PostgreSQL installation
            return extract_dir

        # Fallback: look for a subdirectory with PostgreSQL structure
        for item in extract_dir.iterdir():
            if item.is_dir():
                item_dirs = [sub.name for sub in item.iterdir() if sub.is_dir()]
                if all(dir_name in item_dirs for dir_name in expected_dirs):
                    return item

        raise DownloadError(
            f"Could not find PostgreSQL installation structure. Found directories: {found_dirs}"
        )

    def _install_binary(self, extracted_dir: Path, install_dir: Path) -> None:
        """Install extracted PostgreSQL binary."""
        # Simply copy the extracted directory to the installation location
        if install_dir.exists():
            shutil.rmtree(install_dir)

        shutil.copytree(extracted_dir, install_dir)

        # Make binaries executable
        bin_dir = install_dir / "bin"
        if bin_dir.exists():
            for binary in bin_dir.iterdir():
                if binary.is_file():
                    binary.chmod(0o755)

    def _get_install_dir(self, version: str) -> Path:
        """Get installation directory for a PostgreSQL version."""
        return self.cache_dir / f"postgresql-{version}"

    def _is_version_installed(self, version: str) -> bool:
        """Check if a PostgreSQL version is installed."""
        install_dir = self._get_install_dir(version)

        # Check if all required binaries exist
        for binary in self.REQUIRED_BINARIES:
            binary_path = install_dir / "bin" / binary
            if not (binary_path.exists() and os.access(binary_path, os.X_OK)):
                return False

        return True

    def _try_system_postgresql(self, version: str) -> bool:
        """Try to use system PostgreSQL installation."""
        try:
            # Check if initdb exists and get version
            initdb_path = shutil.which("initdb")
            if not initdb_path:
                return False

            result = subprocess.run(
                [initdb_path, "--version"], capture_output=True, text=True, check=True
            )

            # Parse version from output
            output = result.stdout.strip()
            if f"PostgreSQL) {version}." in output:
                return True

        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return False

    def _get_system_postgresql_path(self) -> Path:
        """Get system PostgreSQL installation path."""
        initdb_path = shutil.which("initdb")
        if initdb_path:
            # Return parent directory of bin
            return Path(initdb_path).parent.parent
        raise BinaryNotFoundError("System PostgreSQL not found")

    def _verify_system_binary_version(
        self, binary_path: str, expected_version: str
    ) -> bool:
        """Verify that a system binary matches the expected version."""
        try:
            result = subprocess.run(
                [binary_path, "--version"], capture_output=True, text=True, check=True
            )
            return f"PostgreSQL) {expected_version}." in result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _verify_installation(self, install_dir: Path) -> None:
        """Verify that PostgreSQL installation is complete."""
        bin_dir = install_dir / "bin"

        for binary in self.REQUIRED_BINARIES:
            binary_path = bin_dir / binary
            if not (binary_path.exists() and os.access(binary_path, os.X_OK)):
                raise BinaryNotFoundError(f"Binary {binary} not found in installation")

        print(f"PostgreSQL installation verified at {install_dir}")


# Legacy class for compatibility
class PostgreSQLBinaryManager(PostgreSQLBinaries):
    """Legacy compatibility class."""

    pass
