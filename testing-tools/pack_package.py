import os
import struct
import sys
import zlib

def package_pack(directory, outfilename):
    filenames = []

    for root, dirs, files in os.walk(directory):
        for name in files:
            if directory != root[0:len(directory)]:
                print("ERROR!!!!!!")
                sys.exit()

            filename = os.path.join(root, name)
            filename = filename[len(directory):]  # Crop off the basepath part of the filename

            filenames.append(filename)

    outfileoffset = 0

    datasection = ""
    indexsection = ""
    numberoffiles = 0

    for filename in filenames:
        infile = open(directory + filename, "rb")
        filedata = infile.read()
        infile.close()

        index = 0
        packedbytes = 0

        for i in range(0, len(filedata), 0x8000):
            chunk = filedata[i:i + 0x8000]

            packedchunk = zlib.compress(chunk, 9)

            packedlen = len(packedchunk)

            datasection = datasection + struct.pack("<L", packedlen) + packedchunk

            packedbytes = packedbytes + packedlen

        indexsection = indexsection + filename + "\x00" + struct.pack("<LLLL", len(filedata), packedbytes,
                                                                      outfileoffset, len(filename) + 1)

        outfileoffset = len(datasection)

        numberoffiles = numberoffiles + 1

    fulloutfile = datasection + indexsection + struct.pack("<BLL", 0, 9, numberoffiles)

    outfile = open(outfilename, "wb")
    outfile.write(fulloutfile)
    outfile.close()

    # Save output variables to file
    output_filename = outfilename + ".pkg"
    output = {
        "directory": directory,
        "outfilename": outfilename
    }
    with open(output_filename, "w") as output_file:
        output_file.write(str(output))

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Incorrect number of arguments.")
        print("Usage: python package_pack.py <directory> <outfilename>")
    else:
        directory = sys.argv[1]
        outfilename = sys.argv[2]
        package_pack(directory, outfilename)
