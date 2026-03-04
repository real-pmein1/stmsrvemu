"""
Client for querying Steam content servers.

This module provides functions for querying Steam content servers
to get file server information for content downloads.
"""

import struct
import binascii

from utilities.clientsocket import ClientSocket as impsocket


def get_fileservers(contentserver, app, ver, numservers):
    """
    Query a content server to get a list of file servers for an app.

    Args:
        contentserver: Tuple of (host, port) for the content server
        app: Application ID
        ver: Application version
        numservers: Number of servers to request

    Returns:
        List of tuples: (serverid, server1_address, server2_address)
        where each address is a (ip, port) tuple
    """
    s = impsocket()
    s.connect(contentserver)
    s.send(b"\x00\x00\x00\x02")
    s.recv(1)

    command = b"\x00\x00\x01" + bytes(struct.pack(">LLHL", app, ver, numservers, 5)) + b"\xff\xff\xff\xff\xff\xff\xff\xff"
    s.send_withlen(command)
    reply = s.recv_withlen()
    s.close()

    numadds = struct.unpack(">H", reply[:2])[0]

    addresses = []
    for i in range(numadds):
        if i == 0:  # TEMP FIX FOR MULTI SERVER NOT WORKING
            from utils import decodeIP  # Import here to avoid circular import
            start = i * 16 + 2
            serverid = struct.unpack(">L", reply[start:start+4])[0]
            server1 = decodeIP(reply[start+4:start+10])
            server2 = decodeIP(reply[start+10:start+16])

            addresses.append((serverid, server1, server2))

    return addresses
