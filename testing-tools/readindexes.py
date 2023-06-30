import os
import struct
import sys

def readindexes(filename):
    indexes = {}
    filemodes = {}

    if len(sys.argv) != 2:
        print("Incorrect number of arguments.")
        print("Usage: python readindexes.py <filename>")
        return

    if os.path.isfile(filename):
        f = open(filename, "rb")
        indexdata = f.read()
        f.close()

        indexptr = 0

        while indexptr < len(indexdata):
            (fileid, indexlen, filemode) = struct.unpack(">QQQ", indexdata[indexptr:indexptr + 24])

            if indexlen:
                indexes[fileid] = indexdata[indexptr + 24:indexptr + 24 + indexlen]
                filemodes[fileid] = filemode

            indexptr = indexptr + 24 + indexlen

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
        print("Usage: python readindexes.py <filename>")
    else:
        filename = sys.argv[1]
        readindexes(filename)
