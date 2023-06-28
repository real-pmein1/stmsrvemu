import steam, sys, getopt, zlib

def main(argv):
    print
    print "Steam Server Emulator CDR Writer v1.2"
    print "====================================="
    print
    print "Credits to: pmein1, Dormine"
    print
    print
    inputfile = ''
    outputfile = ''
    compress = 0
    try:
        opts, args = getopt.getopt(argv,"hi:o:c")
    except getopt.GetoptError:
        print("cmdline error")
        print 'BlobWriter.exe -i <inputfile>.py -o <outputfile>.bin [-c(ompress)]'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'BlobWriter.exe -i <inputfile>.py -o <outputfile>.bin [-c(ompress)]'
            sys.exit()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg
        elif opt in ("-c"):
            compress = 1

    execdict = {}
    try:
        print "Processing..."
        execfile(inputfile, execdict)
    except IOError:
        print 'BlobWriter.exe -i <inputfile>.py -o <outputfile>.bin [-c(ompress)]'
        sys.exit(2)

    blob = steam.blob_serialize(execdict["blob"])
    if compress == 1:
        blob = zlib.compress(blob[20:])
    f = open(outputfile, "wb")
    f.write(blob)
    f.close()
    print
    print("Written " + outputfile)

if __name__ == "__main__":
   main(sys.argv[1:])
