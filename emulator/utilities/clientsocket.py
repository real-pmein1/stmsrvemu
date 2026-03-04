"""
Client-side socket wrapper for Steam protocol communication.

This module provides a simplified socket class for client applications,
specifically designed for downloading content from Steam file servers.
Unlike the server-side ImpSocket, this class doesn't include rate limiting,
blacklists, or other server-specific features.
"""

import binascii
import logging
import socket
import struct

log = logging.getLogger("ClientSocket")


class ClientSocket:
    """
    Simplified socket class for client-side Steam protocol communication.

    This is a client-focused socket wrapper that provides:
    - Basic socket operations (connect, send, recv, close)
    - Length-prefixed message support (send_withlen, recv_withlen)
    - Reliable full-message receiving (recv_all)
    - Connection tracking for error handling

    Unlike the server-side ImpSocket, this class:
    - Does not implement blacklist/whitelist management
    - Does not implement rate limiting
    - Does not track bandwidth statistics
    - Focuses on simplicity for client applications
    """

    def __init__(self, sock=None):
        """
        Initialize a new client socket.

        Args:
            sock: Optional existing socket to wrap. If None, creates a new TCP socket.
        """
        if sock is None:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.s = sock
        self.address = None

    def accept(self):
        """
        Accept an incoming connection.

        Returns:
            Tuple of (ClientSocket, address) for the new connection.
        """
        (returnedsocket, address) = self.s.accept()
        newsocket = ClientSocket(returnedsocket)
        newsocket.address = address
        return newsocket, address

    def bind(self, address):
        """
        Bind the socket to an address.

        Args:
            address: Tuple of (host, port) to bind to.
        """
        self.address = address
        self.s.bind(address)

    def connect(self, address):
        """
        Connect to a remote address.

        Args:
            address: Tuple of (host, port) to connect to.
        """
        self.address = address
        self.s.connect(address)

    def track_broken_connection(self, ip: str):
        """
        Track and log a broken connection for potential retry logic.

        Args:
            ip: The IP address of the broken connection.
        """
        log.warning(f"Broken connection to {ip}")

    def close(self):
        """Close the socket."""
        self.s.close()

    def listen(self, connections):
        """
        Start listening for incoming connections.

        Args:
            connections: Maximum number of queued connections.
        """
        self.s.listen(connections)

    def send(self, data, to_log=True):
        """
        Send data over the socket.

        Args:
            data: Bytes to send.
            to_log: Whether to log the operation (unused, for API compatibility).

        Returns:
            Number of bytes sent.
        """
        sentbytes = self.s.send(data)
        return sentbytes

    def sendto(self, data, address, to_log=True):
        """
        Send data to a specific address (UDP).

        Args:
            data: Bytes to send.
            address: Destination (host, port) tuple.
            to_log: Whether to log the operation (unused, for API compatibility).

        Returns:
            Number of bytes sent.
        """
        sentbytes = self.s.sendto(data, address)
        return sentbytes

    def send_withlen(self, data, to_log=True):
        """
        Send data with a 4-byte big-endian length prefix.

        This is the standard Steam protocol format for length-prefixed messages.

        Args:
            data: Bytes to send.
            to_log: Whether to log the operation (unused, for API compatibility).

        Raises:
            RuntimeError: If the connection is broken during send.
        """
        lengthstr = struct.pack(">L", len(data))
        totaldata = lengthstr + data
        totalsent = 0
        while totalsent < len(totaldata):
            sent = self.send(totaldata[totalsent:], False)
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent = totalsent + sent

    def recv(self, length, to_log=True):
        """
        Receive up to length bytes from the socket.

        Args:
            length: Maximum number of bytes to receive.
            to_log: Whether to log the operation (unused, for API compatibility).

        Returns:
            Received bytes.
        """
        data = self.s.recv(length)
        return data

    def recvfrom(self, length, to_log=True):
        """
        Receive data from the socket (UDP style).

        Args:
            length: Maximum number of bytes to receive.
            to_log: Whether to log the operation (unused, for API compatibility).

        Returns:
            Tuple of (data, address).
        """
        (data, address) = self.s.recvfrom(length)
        return (data, address)

    def recv_all(self, length, to_log=True):
        """
        Receive exactly length bytes from the socket.

        Blocks until all requested bytes are received or the connection is broken.

        Args:
            length: Exact number of bytes to receive.
            to_log: Whether to log the operation (unused, for API compatibility).

        Returns:
            Received bytes, or -1 on error.
        """
        data = b""
        while len(data) < length:
            chunk = self.recv(length - len(data), False)
            if chunk == -1:
                return -1
            if chunk == b'':
                self.track_broken_connection(str(self.address[0]) if self.address else "unknown")
            data = data + chunk
        return data

    def recv_withlen(self, to_log=True):
        """
        Receive a length-prefixed message.

        Reads a 4-byte big-endian length prefix, then reads that many bytes.

        Args:
            to_log: Whether to log the operation (unused, for API compatibility).

        Returns:
            The received message bytes, or a dummy response on error.
        """
        lengthstr = self.recv(4, False)
        if lengthstr == -1:
            return -1
        if len(lengthstr) != 4:
            return b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # DUMMY RETURN FOR FILESERVER
        else:
            length = struct.unpack(">L", lengthstr)[0]
            data = self.recv_all(length, False)
            return data

    def getsockname(self):
        """
        Get the local address of the socket.

        Returns:
            Tuple of (host, port) for the local end.
        """
        return self.s.getsockname()

    def settimeout(self, timeout):
        """
        Set a timeout on blocking socket operations.

        Args:
            timeout: Timeout in seconds, or None for blocking mode.
        """
        self.s.settimeout(timeout)


# Alias for backward compatibility with Steam/impsocket.py imports
impsocket = ClientSocket
