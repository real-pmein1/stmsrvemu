import sys

def steam_download_package(fileserver, filename, outfilename):
    s = ImpSocket()
    s.connect(fileserver)
    s.send("\x00\x00\x00\x03")
    s.recv(1)
    message = struct.pack(">LLL", 0, 0, len(filename)) + filename + "\x00\x00\x00\x05"

    s.send_withlen(message)

    response = s.recv(8)

    datalen = struct.unpack(">LL", response)[0]

    f = open(outfilename, "wb")

    while datalen:
        reply = s.recv(datalen)
        datalen = datalen - len(reply)
        f.write(reply)

    f.close()
    s.close()

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Invalid number of arguments. Usage: python steam_download_package.py <fileserver ip:port> <package filename> <out filename>")
    else:
        fileserver = sys.argv[1]
        filename = sys.argv[2]
        outfilename = sys.argv[3]

        if not fileserver or not filename or not outfilename:
            print("Invalid arguments. Please provide non-empty values for all arguments.")
        else:
            steam_download_package(fileserver, filename, outfilename)
            print("Package downloaded successfully.")
