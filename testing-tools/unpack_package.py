import os
import struct
import sys
import zlib

def package_unpack(infilename, outpath):
    if not os.path.exists(outpath):
        os.makedirs(outpath)

    infile = open(infilename, "rb")
    package = infile.read()
    infile.close()

    header = package[-9:]

    (pkg_ver, compress_level, numfiles) = struct.unpack("<BLL", package[-9:])

    index = len(package) - (9 + 16)

    for i in range(numfiles):
        (unpacked_size, packed_size, file_start, filename_len) = struct.unpack("<LLLL", package[index:index + 16])

        filename = package[index - filename_len:index - 1]

        (filepath, basename) = os.path.split(filename)

        index = index - (filename_len + 16)

        file = ""

        while packed_size > 0:
            compressed_len = struct.unpack("<L", package[file_start:file_start + 4])[0]

            compressed_start = file_start + 4
            compressed_end = compressed_start + compressed_len

            compressed_data = package[compressed_start:compressed_end]

            file = file + zlib.decompress(compressed_data)

            file_start = compressed_end
            packed_size = packed_size - compressed_len

        outsubpath = os.path.join(outpath, filepath)

        if not os.path.exists(outsubpath):
            os.makedirs(outsubpath)

        outfullfilename = os.path.join(outpath, filename)

        outfile = open(outfullfilename, "wb")
        outfile.write(file)
        outfile.close()

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Incorrect number of arguments.")
        print("Usage: python package_unpack.py <infilename> <outpath>")
    else:
        infilename = sys.argv[1]
        outpath = sys.argv[2]
        package_unpack(infilename, outpath)

        # Save output variables to file
        #output_filename = infilename + ".output"
        #output = {
        #    "infilename": infilename,
        #    "outpath": outpath
        #}
        with open(output_filename, "w") as output_file:
            output_file.write(str(output))
