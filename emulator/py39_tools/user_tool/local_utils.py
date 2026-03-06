#!/usr/bin/env python3
"""
Local utility functions for the Remote Administration Tool.

This module provides common helper functions needed by the admin tool
without depending on the main server's utils.py or config.py, which
would require emulator.ini to be present.
"""

import os
import struct


def decodeIP(ipport_str):
    """Decode a 6-byte packed IP:port structure into IP string and port integer.

    Args:
        ipport_str: 6 bytes containing IP (4 bytes, little-endian octets) + port (2 bytes, little-endian)

    Returns:
        Tuple of (ip_string, port_int)
    """
    (oct1, oct2, oct3, oct4, port) = struct.unpack("<BBBBH", ipport_str)
    ip = "%d.%d.%d.%d" % (oct1, oct2, oct3, oct4)
    return ip, port


def encodeIP(ip_port):
    """Encode an IP string and port into a 6-byte packed structure.

    Args:
        ip_port: Tuple of (ip_string, port_int)

    Returns:
        6 bytes containing packed IP and port
    """
    ip, port = ip_port
    if isinstance(port, str):
        port = int(port)
    if isinstance(ip, str):
        ip = ip.encode("latin-1")
    octets = ip.split(b".")
    packed_string = struct.pack("<BBBBH", int(octets[0]), int(octets[1]), int(octets[2]), int(octets[3]), port)
    return packed_string


def clear_console():
    """Clear the console screen in a cross-platform manner."""
    os.system('cls' if os.name in ('nt', 'dos') else 'clear')
