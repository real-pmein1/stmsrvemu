import os
import re
import shutil
import zipfile
import argparse
import subprocess
from collections import defaultdict
import xml.etree.ElementTree as ET

import logging

# Set up logging to errors.txt
logging.basicConfig(filename='errors.txt', level=logging.ERROR, format='%(asctime)s %(levelname)s:%(message)s')

def parse_filename(filename):
    # Regex to match the filename pattern
    pattern = r'^(\d+)_(\d+)(?:_(\w+)_(\w+))?\.(blob|dat)$'
    match = re.match(pattern, filename)
    if match:
        depotid = int(match.group(1))
        version = int(match.group(2))
        small_checksum = match.group(3)
        large_checksum = match.group(4)
        ext = match.group(5)
        return {
            'depotid': depotid,
            'version': version,
            'small_checksum': small_checksum,
            'large_checksum': large_checksum,
            'ext': ext,
            'filename': filename
        }
    else:
        return None

def get_version_ranges(versions):
    """
    Given a sorted list of versions, returns a list of tuples representing contiguous version ranges.
    """
    ranges = []
    start = prev = versions[0]
    for version in versions[1:]:
        if version == prev + 1:
            prev = version
        else:
            ranges.append((start, prev))
            start = prev = version
    ranges.append((start, prev))
    return ranges

def parse_content_description_record(xml_file):
    """
    Parses the ContentDescriptionRecord.xml file and returns a mapping of depotid to app name.
    """
    depotid_to_name = {}
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        for app_record in root.findall('./AllAppsRecord/AppRecord'):
            app_id = app_record.find('AppId')
            name = app_record.find('Name')
            if app_id is not None and name is not None:
                depotid = int(app_id.text)
                depot_name = name.text
                depotid_to_name[depotid] = depot_name
    except Exception as e:
        logging.error(f"Error parsing {xml_file}: {str(e)}")
    return depotid_to_name


def move_processed_depot_files(depotid):
    """
    Move all files with the specified depotid and matching checksums
    to the 'processed_files' folder.
    """
    small_checksum = "00000000"
    large_checksum = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    processed_dir = os.path.abspath('processed_files')
    os.makedirs(processed_dir, exist_ok = True)

    for file in os.listdir('.'):
        if file.startswith(f"{depotid}_") and small_checksum in file and large_checksum in file:
            shutil.move(file, processed_dir)
            print(f"Moved '{file}' to 'processed_files'")

def validate_depot_versions(depotid):
    """
    Validates the versions of the .blob files in ./processed_files against
    the .manifest files in ./output/Manifests for the given depotid.
    Logs missing versions in errors.txt.
    """
    processed_dir = os.path.abspath('processed_files')
    manifest_dir = os.path.join('output', 'Manifests')

    # Get the versions from the .blob filenames in processed_files
    blob_versions = set()
    for file in os.listdir(processed_dir):
        if file.startswith(f"{depotid}_") and file.endswith('.blob'):
            version = int(file.split('_')[1])
            blob_versions.add(version)

    # Get the versions from the .manifest filenames in output/Manifests
    manifest_versions = set()
    for file in os.listdir(manifest_dir):
        if file.startswith(f"{depotid}_") and file.endswith('.manifest'):
            version = int(file.split('_')[1].split('.')[0])
            manifest_versions.add(version)

    # Compare the two sets and log missing versions
    missing_versions = blob_versions - manifest_versions
    if missing_versions:
        with open('errors.txt', 'a') as error_log:
            for version in sorted(missing_versions):
                error_log.write(f"DepotID {depotid}, Version {version} is in sdk depots but is missing from output manifests\n")
                return missing_versions
    return []


def main():
    # Initialize the argument parser
    parser = argparse.ArgumentParser(description = 'Process depot files.')

    # Add optional arguments for datdir and zipout
    parser.add_argument('-datdir', help = 'Directory for .dat files', default = './')
    parser.add_argument('-zipout', help = 'Directory for zip output', default = './zip_output')
    parser.add_argument('-validate', action = 'store_true', help = 'Validate the processed .blob files against .manifest files')
    parser.add_argument('-endonerror', choices = ['true', 'false'], default = 'false', help = 'Pause and decide to continue or stop if validation fails. Default is false.')
    parser.add_argument('-v3storages2', action = 'store_true', help = 'Puts the files in their corresponding part 2 v3 storage/manifest dirs in the zip')

    # Parse the arguments
    args = parser.parse_args()

    # Set datdir to the provided value or default to './'
    datdir = args.datdir
    if not datdir:
        datdir = './'

    datdir = os.path.abspath(datdir)

    # Set zip_output to the provided value or default to './zip_output'
    zip_output = args.zipout

    # Create directories if they don't exist
    os.makedirs(datdir, exist_ok = True)
    os.makedirs(zip_output, exist_ok = True)

    # Rest of your processing logic...
    print(f"Using datdir: {datdir}")
    print(f"Using zip_output: {zip_output}")

    # Create zip output directory if it does not exist
    os.makedirs(zip_output, exist_ok = True)

    # Parse ContentDescriptionRecord.xml
    content_desc_file = 'ContentDescriptionDB.xml'
    depotid_to_name = {}
    if os.path.isfile(content_desc_file):
        depotid_to_name = parse_content_description_record(content_desc_file)
    else:
        logging.warning(f"{content_desc_file} not found. Zip filenames will not include app names.")

    # Get all the .blob and .dat files in the current directory
    files = [f for f in os.listdir('.') if f.endswith('.blob') or f.endswith('.dat')]
    file_infos = []

    for f in files:
        info = parse_filename(f)
        if info:
            file_infos.append(info)
        else:
            print(f"Filename {f} does not match the expected pattern.")

    # Organize files by depotid
    depot_files = defaultdict(list)
    for info in file_infos:
        depotid = info['depotid']
        depot_files[depotid].append(info)

    # For each depotid, find the highest version number
    for depotid in sorted(depot_files.keys()):
        try:
            # Get all versions for this depotid
            versions = defaultdict(list)
            version_numbers = set()
            for info in depot_files[depotid]:
                versions[info['version']].append(info)
                version_numbers.add(info['version'])

            # Detect missing versions
            version_numbers = sorted(version_numbers)
            min_version = version_numbers[0]
            max_version = version_numbers[-1]
            full_version_set = set(range(min_version, max_version + 1))
            missing_versions = sorted(full_version_set - set(version_numbers))

            # Identify version ranges
            version_ranges = get_version_ranges(version_numbers)

            # Format version ranges for the zip filename
            version_ranges_str = ','.join(f'V{start}-V{end}' if start != end else f'V{start}' for start, end in version_ranges)

            # Record missing versions if any
            if missing_versions:
                with open('missing_versions.txt', 'a') as mv_file:
                    mv_file.write(f"DepotID {depotid} missing versions: {missing_versions}\n")

            # Get the highest version number
            highest_version = max(versions.keys())
            highest_version_files = versions[highest_version]

            # Find the blob file with the highest version
            blob_file = None
            for info in highest_version_files:
                if info['ext'] == 'blob':
                    blob_file = info['filename']
                    break

            if not blob_file:
                print(f"No blob file found for depotid {depotid} version {highest_version}")
                continue

            # Prepare arguments for the processing script
            blob_path = os.path.abspath(blob_file)

            # For the processing script, the datdir needs to contain all .dat files
            # So we need to collect all .dat files for this depotid
            # dat_files = [info['filename'] for info in depot_files[depotid] if info['ext'] == 'dat']

            # Prepare the output directory
            output_dir = os.path.abspath('./output')
            # Clear the output directory
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir)
            os.makedirs(output_dir)

            # Run the processing script
            print(f"Processing depotid {depotid} version {highest_version}")
            # Convert datdir and output_dir to absolute paths

            cmd = ['python', 'processor_script.py', blob_path, '-d', datdir, '-o', output_dir, '-m']

            # Start the subprocess with the correct working directory
            process = subprocess.Popen(
                    cmd,
                    stdout = subprocess.PIPE,
                    stderr = subprocess.PIPE,
                    text = True,
                    cwd = os.getcwd()  # Ensures the working directory is the current directory
            )

            # Forward the stdout and stderr to the console as they are received
            stdout_lines = []
            stderr_lines = []

            # Capture stdout and print to console
            for stdout_line in iter(process.stdout.readline, ""):
                print(stdout_line, end = "")
                stdout_lines.append(stdout_line)

            # Capture stderr and print to console
            for stderr_line in iter(process.stderr.readline, ""):
                print(stderr_line, end = "")
                stderr_lines.append(stderr_line)

            # Close the streams
            process.stdout.close()
            process.stderr.close()

            # Wait for the process to complete
            exit_code = process.wait()

            # Check if the process failed
            if exit_code != 0:
                # Log the error
                error_message = f"Error processing depotid {depotid}: {''.join(stderr_lines)}"
                logging.error(error_message)

                # Append to failed_depots.txt
                with open('failed_depots.txt', 'a') as fd_file:
                    fd_file.write(f"{depotid}\n")

                # Check if the user wants to continue or stop
                if args.endonerror == 'true':
                    while True:
                        user_input = input(f"Error processing depotid {depotid}. Do you want to continue? (y/n): ").strip().lower()
                        if user_input == 'n':
                            print("Exiting script as per user request.")
                            return  # Exit the script
                        elif user_input == 'y':
                            print("Continuing execution as per user request.")
                            break
                        else:
                            print("Invalid input.")

                continue  # Move on to the next depotid

            # Call the function to move the processed files with the matching depotid and checksums
            move_processed_depot_files(depotid)

            # After processing, create Storages and Manifests folders in output
            if args.v3storages2:
                storages_dir = os.path.join(output_dir, 'v3storages2')
                manifests_dir = os.path.join(output_dir, 'v3manifests2')
            else:
                storages_dir = os.path.join(output_dir, 'storages')
                manifests_dir = os.path.join(output_dir, 'manifests')

            if not os.path.exists(storages_dir):
                os.makedirs(storages_dir)
            if not os.path.exists(manifests_dir):
                os.makedirs(manifests_dir)

            # Move .manifest files to Manifests, others to Storages
            for f in os.listdir(output_dir):
                f_path = os.path.join(output_dir, f)
                if os.path.isfile(f_path):
                    if f.endswith('.manifest'):
                        shutil.move(f_path, manifests_dir)
                    else:
                        shutil.move(f_path, storages_dir)

            # Validate each depot's versions in processed_files against output/Manifests
            if args.validate:
                validation_failed = False
                missing_versions_by_depot = {}  # To keep track of depots with missing versions

                for depotid_loop in sorted(depot_files.keys()):
                    missing_versions = validate_depot_versions(depotid_loop)
                    if missing_versions:
                        validation_failed = True
                        missing_versions_by_depot[depotid_loop] = missing_versions

                if validation_failed:
                    print("Validation failed. Missing versions logged in errors.txt.")

                    # Display the missing versions
                    for depotid_loop, missing_versions in missing_versions_by_depot.items():
                        print(f"DepotID {depotid_loop} is missing versions: {', '.join(map(str, missing_versions))}")

                    # Check if the user wants to continue or stop
                    if args.endonerror == 'true':
                        while True:
                            user_input = input("Validation failed. Do you want to continue? (y/n): ").strip().lower()
                            if user_input == 'n':
                                print("Exiting script as per user request.")
                                return  # Exit the script
                            elif user_input == 'y':
                                print("Continuing execution as per user request.")
                                break
                            else:
                                print("Invalid input.")
                else:
                    print("Validation passed.")

            # Prepare the zip filename
            app_name = depotid_to_name.get(depotid, '')
            sanitized_app_name = ''.join(c for c in app_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
            manifest_versions = set()
            for file in os.listdir(manifests_dir):
                if file.startswith(f"{depotid}_") and file.endswith('.manifest'):
                    version = int(file.split('_')[1].split('.')[0])
                    manifest_versions.add(version)

            if manifest_versions:
                min_version = min(manifest_versions)
                max_version = max(manifest_versions)
                if min_version == max_version:
                    version_ranges_str = f"v{min_version}"
                else:
                    version_ranges_str = f"v{min_version}-{max_version}"
            else:
                print("No manifest versions found.")

            if app_name:
                zip_filename = f"[{depotid}] {sanitized_app_name} ({version_ranges_str}).zip"
            else:
                zip_filename = f"{depotid} ({version_ranges_str}).zip"

            zip_output_dir = os.path.abspath(args.zipout)
            zip_filepath = os.path.join(zip_output_dir, zip_filename)
            if not os.path.exists(zip_output_dir):
                os.makedirs(zip_output_dir)

            # Zip the contents of the output directory
            # Create the zip file without compression (store only)
            with zipfile.ZipFile(zip_filepath, 'w', compression = zipfile.ZIP_STORED) as zip_file:
                for root, dirs, files in os.walk(output_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        archive_name = os.path.relpath(file_path, start = output_dir)
                        zip_file.write(file_path, archive_name)

            # Delete the files in Manifests and Storages
            shutil.rmtree(storages_dir)
            shutil.rmtree(manifests_dir)

            print(f"Created zip file {zip_filepath} for depotid {depotid}")

            # Move on to the next depotid

        except Exception as e:
            # Log the exception
            error_message = f"Exception processing depotid {depotid}: {str(e)}"
            logging.error(error_message)
            # Append to failed_depots.txt
            with open('failed_depots.txt', 'a') as fd_file:
                fd_file.write(f"{depotid}\n")
            continue  # Move on to the next depotid

if __name__ == '__main__':
    main()