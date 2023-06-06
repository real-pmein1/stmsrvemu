import os, struct, zlib struct, utilities
import dirs, globalvars

from Steam2.package import Package

def package_unpack(infilename, outpath) :

    if not os.path.exists(outpath) :
        os.makedirs(outpath)

    infile = open(infilename, "rb")
    package = infile.read()
    infile.close()

    header = package[-9:]

    (pkg_ver, compress_level, numfiles) = struct.unpack("<BLL", package[-9:])

    index = len(package) - (9 + 16)

    for i in range(numfiles) :

        (unpacked_size, packed_size, file_start, filename_len) = struct.unpack("<LLLL", package[index:index + 16])

        filename = package[index - filename_len:index - 1]

        (filepath, basename) = os.path.split(filename)

        index = index - (filename_len + 16)

        file = ""

        while packed_size > 0 :

            compressed_len = struct.unpack("<L", package[file_start:file_start + 4])[0]

            compressed_start = file_start + 4
            compressed_end   = compressed_start + compressed_len

            compressed_data = package[compressed_start:compressed_end]

            file = file + zlib.decompress(compressed_data)

            file_start = compressed_end
            packed_size = packed_size - compressed_len

        outsubpath = os.path.join(outpath, filepath)

        if not os.path.exists(outsubpath) :
            os.makedirs(outsubpath)

        outfullfilename = os.path.join(outpath, filename)

        outfile = open(outfullfilename, "wb")
        outfile.write(file)
        outfile.close()

        #print filename, "written"

def package_pack(directory, outfilename) :

    filenames = []

    for root, dirs, files in os.walk(directory) :
        for name in files :
            if directory != root[0:len(directory)] :
                print "ERROR!!!!!!"
                sys.exit()

            filename = os.path.join(root, name)
            filename = filename[len(directory):] # crop off the basepath part of the filename

            filenames.append(filename)

    #print filenames

    outfileoffset = 0

    datasection = ""
    indexsection = ""
    numberoffiles = 0

    for filename in filenames :

        infile = open(directory + filename, "rb")
        filedata = infile.read()
        infile.close()

        index = 0
        packedbytes = 0

        for i in range(0, len(filedata), 0x8000) :

            chunk = filedata[i:i + 0x8000]

            packedchunk = zlib.compress(chunk, 9)

            packedlen = len(packedchunk)

            datasection = datasection + struct.pack("<L", packedlen) + packedchunk

            packedbytes = packedbytes + packedlen

        indexsection = indexsection + filename + "\x00" + struct.pack("<LLLL", len(filedata), packedbytes, outfileoffset, len(filename) + 1)

        outfileoffset = len(datasection)

        numberoffiles = numberoffiles + 1

        #print filename

    fulloutfile = datasection + indexsection + struct.pack("<BLL", 0, 9, numberoffiles)

    outfile = open(outfilename, "wb")
    outfile.write(fulloutfile)
    outfile.close()

