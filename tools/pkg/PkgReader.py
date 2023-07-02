import steam, sys, getopt
def main(argv):
    print
    print "Steam Server Emulator Package Reader v1.0"
    print "========================================="
    print
    print "Credits to: pmein1, Dormine"
    print
    print
    inputfile = ''
    outputfile = ''
    try:
        opts, args = getopt.getopt(argv,"hi:o:",["ifile=","ofile="])
    except getopt.GetoptError:
        print 'PkgReader.exe -i <inputfile>.pkg -o <outputdir>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'PkgReader.exe -i <inputfile>.pkg -o <outputdir>'
            sys.exit()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg
    try:
        print "Processing..."
        steam.package_unpack(inputfile, outputfile)
        print
        print("Extracted " + inputfile + " to " + outputfile)
    except IOError:
        print 'PkgReader.exe -i <inputfile>.pkg -o <outputdir>'
        sys.exit(2)


if __name__ == "__main__":
   main(sys.argv[1:])
