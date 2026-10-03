import socket
from typing import Tuple

class DynamicPortAllocator:
    """WK-07: Verify --port 0 / printed-port behavior and collision handling."""
    @staticmethod
    def allocate_port() -> Tuple[socket.socket, int]:
        """Binds to port 0 to let the OS dynamically assign an open port safely."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        # Do not close it here, return it so the caller owns the lease and prevents collision
        allocated_port = sock.getsockname()[1]
        return sock, allocated_port
