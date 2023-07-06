from __future__ import unicode_literals

import steam, ast, zlib, sys, getopt

def main(argv):
    print
    print "Steam Server Emulator CDR Reader v1.1"
    print "====================================="
    print
    print "Credits to: pmein1, Dormine"
    print
    print
    inputfile = ''
    outputfile = ''
    try:
        opts, args = getopt.getopt(argv,"hi:o:",["ifile=","ofile="])
    except getopt.GetoptError:
        print 'BlobReader.exe -i <inputfile>.bin -o <outputfile>.py'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'BlobReader.exe -i <inputfile>.bin -o <outputfile>.py'
            sys.exit()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg
    try:
        print "Processing..."
        f = open(inputfile, "rb")
    except IOError:
        print 'BlobReader.exe -i <inputfile>.bin -o <outputfile>.py'
        sys.exit(2)

    blob = f.read()
    f.close()

    if blob[0:2] == "\x01\x43":
        blob = zlib.decompress(blob[20:])

    blob2 = steam.blob_unserialize(blob)

    blob3 = steam.blob_dump(blob2)

    g = open(outputfile, "w")
    g.write("blob = ")
    g.write(blob3)
    g.close()
    print
    print("Written " + outputfile)

if __name__ == "__main__":
   main(sys.argv[1:])

