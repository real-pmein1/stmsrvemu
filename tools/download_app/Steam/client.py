import struct

from Steam import tools
from Steam.impsocket import impsocket

def get_fileservers(contentserver, app, ver, numservers) :
    s = impsocket()
    s.connect(contentserver)
    s.send("\x00\x00\x00\x02")
    s.recv(1)

    command = "\x00\x00\x01" + struct.pack(">LLHL", app, ver, numservers, 5) + "\xff\xff\xff\xff\xff\xff\xff\xff"
    s.send_withlen(command)
    reply = s.recv_withlen()
    s.close()

    numadds = struct.unpack(">H", reply[:2])[0]

    addresses = []
    for i in range(numadds) :
        start = i * 16 + 2
        serverid = struct.unpack(">L", reply[start:start+4])[0]
        server1 = tools.decodeip(reply[start+4:start+10])
        server2 = tools.decodeip(reply[start+10:start+16])

        addresses.append((serverid, server1, server2))

    return addresses

def get_authserver(dirserver, namehash) :
    s = impsocket()
    s.connect(dirserver)
    s.send("\x00\x00\x00\x02")
    s.recv(1)
    s.send_withlen("\x00" + struct.pack("<L", namehash))
    reply = s.recv_withlen()
    s.close()

    numadds = struct.unpack(">H", reply[:2])[0]

    addresses = []
    for i in range(numadds) :
        start = i * 6 + 2
        server = tools.decodeip(reply[start:start+6])

        addresses.append(server)

    return addresses

def get_contentserver(dirserver) :
    s = impsocket()
    s.connect(dirserver)
    s.send("\x00\x00\x00\x02")
    s.recv(1)
    s.send_withlen("\x06")
    reply = s.recv_withlen()
    s.close()

    numadds = struct.unpack(">H", reply[:2])[0]

    addresses = []
    for i in range(numadds) :
        start = i * 6 + 2
        server = tools.decodeip(reply[start:start+6])

        addresses.append(server)

    return addresses

def get_configserver(dirserver) :
    s = impsocket()
    s.connect(dirserver)
    s.send("\x00\x00\x00\x02")
    s.recv(1)
    s.send_withlen("\x03")
    reply = s.recv_withlen()
    s.close()

    numadds = struct.unpack(">H", reply[:2])[0]

    addresses = []
    for i in range(numadds) :
        start = i * 6 + 2
        server = tools.decodeip(reply[start:start+6])

        addresses.append(server)

    return addresses
