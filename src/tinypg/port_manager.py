"""
Port management utilities - Python implementation of getsocket.c functionality.
"""

import socket
from typing import Optional


def get_free_port() -> int:
    """
    Get an unused TCP port.

    Python implementation of getsocket.c functionality.

    Returns:
        int: An available TCP port number
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Bind to port 0 to get an available port
        sock.bind(("0.0.0.0", 0))
        _, port = sock.getsockname()
        return port
    finally:
        sock.close()


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """
    Check if a port is available for binding.

    Args:
        port: Port number to check
        host: Host to check (default: 127.0.0.1)

    Returns:
        bool: True if port is available, False otherwise
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def find_port_in_range(
    start_port: int, end_port: int, host: str = "127.0.0.1"
) -> Optional[int]:
    """
    Find an available port in a given range.

    Args:
        start_port: Start of port range (inclusive)
        end_port: End of port range (inclusive)
        host: Host to check (default: 127.0.0.1)

    Returns:
        Optional[int]: Available port number, or None if no port is available
    """
    for port in range(start_port, end_port + 1):
        if is_port_available(port, host):
            return port
    return None
