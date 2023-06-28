import steam, sys, getopt
def main(argv):
    print
    print "Steam Server Emulator Package Writer v1.0"
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
        print 'PkgWriter.exe -i <inputdir> -o <outputfile>.pkg'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'PkgWriter.exe -i <inputdir> -o <outputfile>.pkg'
            sys.exit()
        elif opt in ("-i", "--ifile"):
            inputfile = arg
        elif opt in ("-o", "--ofile"):
            outputfile = arg
    try:
        print "Processing..."
        stm_ui = steam.package_pack(inputfile + "\\", outputfile)
        print
        print("Written " + outputfile)
    except IOError:
        print 'PkgWriter.exe -i <inputdir> -o <outputfile>.pkg'
        sys.exit(2)


if __name__ == "__main__":
   main(sys.argv[1:])


