
import struct
from steamemu.config import read_config
from storage_utilities import Storage
from index_utilities import readindexes
config = read_config()

def print_files_per_version(storagename):
    versions = {1, 2, 3}

    for version in versions:
        storage = Storage(storagename, "", version)
        storage.indexes, storage.filemodes = readindexes(storage.indexfile)

        print("Version:", version)
        for file_id in storage.indexes:
            print("File ID:", file_id)

        storage.close()
        print()

# Usage
storagename = "1"  # Replace with your storage name
print_files_per_version(storagename)