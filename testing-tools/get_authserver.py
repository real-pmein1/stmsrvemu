import sys

def steam_get_authserver(dirserver, namehash):
    s = ImpSocket()
    s.connect(dirserver)
    s.send("\x00\x00\x00\x02")
    s.recv(1)
    s.send_withlen("\x00" + namehash)
    reply = s.recv_withlen()
    s.close()

    numadds = struct.unpack(">H", reply[:2])[0]

    addresses = []
    for i in range(numadds):
        start = i * 6 + 2
        server = decodeIP(reply[start:start+6])

        addresses.append(server)

    print addresses

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Invalid number of arguments. Usage: python get_auth_servers.py <directory address:port> <namehash>")
    else:
        directory = sys.argv[1]
        namehash = sys.argv[2]

        if not directory or not namehash:
            print("Invalid arguments. Please provide a non-empty directory address:port and namehash.")
        else:
            auth_servers = steam_get_authserver(directory, namehash)
            print("Auth Servers:", auth_servers)
