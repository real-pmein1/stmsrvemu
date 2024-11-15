import struct
import binascii

from Steam import tools
from Steam.impsocket import impsocket

def get_fileservers(contentserver, app, ver, numservers) :
    s = impsocket()
    s.connect(contentserver)
    s.send(b"\x00\x00\x00\x02")
    s.recv(1)

    command = b"\x00\x00\x01" + bytes(struct.pack(">LLHL", app, ver, numservers, 5)) + b"\xff\xff\xff\xff\xff\xff\xff\xff"
    s.send_withlen(command)
    reply = s.recv_withlen()
    s.close()

    numadds = struct.unpack(">H", reply[:2])[0]
    #print(numadds)

    addresses = []
    for i in range(numadds) :
        if i == 0 : #TEMP FIX FOR MULTI SERVER NOT WORKING
            start = i * 16 + 2
            serverid = struct.unpack(">L", reply[start:start+4])[0]
            server1 = tools.decodeip(reply[start+4:start+10])
            server2 = tools.decodeip(reply[start+10:start+16])

            addresses.append((serverid, server1, server2))

    return addresses