#!/usr/bin/env python3

import os
import sys
import argparse
from collections import defaultdict

def parse_filename(filename):
    """
    Parses the filename and extracts depotid and version.
    Expected filename format: <depotid>_<version>_<small checksum>_<big checksum>.blob
    """
    if not filename.endswith('.blob'):
        return None, None
    parts = filename[:-5].split('_')  # Remove '.blob' and split
    if len(parts) < 4:
        return None, None
    depotid = parts[0]
    version = parts[1]
    return depotid, version

def find_depotids_with_duplicate_versions(directory):
    """
    Iterates through .blob files in the given directory and finds depotids
    that have multiple files with the same version.
    """
    depot_versions = defaultdict(lambda: defaultdict(int))
    
    try:
        files = os.listdir(directory)
    except FileNotFoundError:
        print(f"Error: Directory '{directory}' does not exist.", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied to access '{directory}'.", file=sys.stderr)
        sys.exit(1)
    
    for file in files:
        if not file.endswith('.blob'):
            continue
        depotid, version = parse_filename(file)
        if depotid is None or version is None:
            # Skip files that do not match the expected pattern
            continue
        depot_versions[depotid][version] += 1
    
    # Collect depotids with any version count >1
    duplicate_depotids = []
    for depotid, versions in depot_versions.items():
        for version, count in versions.items():
            if count > 1:
                duplicate_depotids.append(depotid)
                break  # No need to check other versions for this depotid
    
    return duplicate_depotids

def main():
    parser = argparse.ArgumentParser(description="Find depotids with duplicate versions in .blob files.")
    parser.add_argument('directory', nargs='?', default='.', help="Path to the directory containing .blob files (default: current directory)")
    args = parser.parse_args()
    
    directory = args.directory
    duplicate_depotids = find_depotids_with_duplicate_versions(directory)
    
    if duplicate_depotids:
        print("DepotIDs with duplicate versions:")
        for depotid in sorted(duplicate_depotids):
            print(depotid)
    else:
        print("No depotIDs with duplicate versions found.")

if __name__ == "__main__":
    main()