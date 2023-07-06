import sys

def steam_get_fileservers(contentserver, app, ver, numservers):
    command = "\x00\x00\x01" + struct.pack(">LLHL", app, ver, numservers, 0) + "\xff\xff\xff\xff\xff\xff\xff\xff"

    s = ImpSocket()
    s.connect(contentserver)
    s.send("\x00\x00\x00\x02")
    s.recv(1)
    s.send_withlen(command)
    reply = s.recv_withlen()

    s.close()

    numadds = struct.unpack(">H", reply[:2])[0]

    addresses = []
    for i in range(numadds):
        start = i * 16 + 2
        serverid = struct.unpack(">L", reply[start:start+4])[0]
        server1 = decodeIP(reply[start+4:start+10])
        server2 = decodeIP(reply[start+10:start+16])

        addresses.append((serverid, server1, server2))

    print addresses

if __name__ == '__main__':
    if len(sys.argv) != 5:
        print("Invalid number of arguments. Usage: python get_file_servers.py <contentserver ip:port> <appid> <app version> <number of servers to request>")
    else:
        contentserver = sys.argv[1]
        appid = int(sys.argv[2])
        appver = int(sys.argv[3])
        numservers = int(sys.argv[4])

        if not contentserver or not appid or not appver or not numservers:
            print("Invalid arguments. Please provide non-empty values for all arguments.")
        else:
            file_servers = steam_get_fileservers(contentserver, appid, appver, numservers)
            print("File Servers:", file_servers)
