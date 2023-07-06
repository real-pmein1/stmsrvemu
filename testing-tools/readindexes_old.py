import os
import struct
import sys

def readindexes_old(filename):
    indexes = {}
    filemodes = {}

    if len(sys.argv) != 2:
        print("Incorrect number of arguments.")
        print("Usage: python readindexes_old.py <filename>")
        return

    if os.path.isfile(filename):
        f = open(filename, "rb")
        indexdata = f.read()
        f.close()

        indexptr = 0

        while indexptr < len(indexdata):
            (fileid, indexlen, filemode) = struct.unpack(">LLL", indexdata[indexptr:indexptr + 12])

            if indexlen:
                indexes[fileid] = indexdata[indexptr + 12:indexptr + 12 + indexlen]
                filemodes[fileid] = filemode

            indexptr = indexptr + 12 + indexlen

    # Save output variables to file
    output_filename = filename + ".output"
    output = {
        "filename": filename,
        "indexes": indexes,
        "filemodes": filemodes
    }
    with open(output_filename, "w") as output_file:
        output_file.write(str(output))

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Incorrect number of arguments.")
        print("Usage: python readindexes_old.py <filename>")
    else:
        filename = sys.argv[1]
        readindexes_old(filename)
