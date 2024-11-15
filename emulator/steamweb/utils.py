import errno
import zipfile
import os
import shutil

import os
import shutil

import globalvars


def replace_file_in_zip(zip_path, target_file_path, file_to_replace_path):
    """
    Replace a specific file within a ZIP archive (e.g., an installer application holding files as a ZIP).

    :param zip_path: Path to the ZIP archive or executable with embedded ZIP structure.
    :param target_file_path: Path of the file to replace inside the archive (relative path within the ZIP).
    :param file_to_replace_path: Path to the new file that will replace the existing one.
    """
    # Create a temporary directory to extract the contents
    temp_dir = "temp_zip_contents"

    # Ensure the temporary directory is empty
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    # Extract the contents of the ZIP to the temporary directory
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)

    # Replace the target file with the new file
    target_file_full_path = os.path.join(temp_dir, target_file_path)
    if os.path.exists(target_file_full_path):
        os.remove(target_file_full_path)
        shutil.copy(file_to_replace_path, target_file_full_path)
        print(f"Replaced {target_file_path} in the archive.")
    else:
        print(f"{target_file_path} not found in the archive.")
        shutil.rmtree(temp_dir)  # Clean up and exit early
        return

    # Write the updated contents back into the original ZIP file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)  # Keep relative path
                zip_ref.write(file_path, arcname)

    # Clean up the temporary directory
    shutil.rmtree(temp_dir)
    print(f"Updated {zip_path} with the replaced file.")


def copy_appropriate_installer():
    """
    Copy the appropriate installer to LAN and WAN based on the global variables.
    """
    from config import get_config
    config = get_config()
    web_root = config['web_root']
    installers_path = os.path.join(web_root, 'installers')
    lan_installer_path = os.path.join(web_root, 'downloads/steaminstall_lan.exe')
    wan_installer_path = os.path.join(web_root, 'downloads/steaminstall_wan.exe')
    download_path = os.path.join(web_root, 'downloads')
    try:
        os.makedirs(download_path)
    except OSError as e:
        if e.errno != errno.EEXIST:  # Ignore if the directory already exists
            raise
    # Determine the correct installer to copy
    if globalvars.record_ver == 0 and globalvars.steam_ver == 0:
        source_installer = os.path.join(installers_path, 'setup_v0_b1.exe')
    elif globalvars.record_ver == 0 and globalvars.steam_ver == 1:
        source_installer = os.path.join(installers_path, 'setup_v1_b1.exe')
    elif globalvars.record_ver == 1 and globalvars.steam_ver == 0:
        source_installer = os.path.join(installers_path, 'SteamInstall_b2_2003-01-14.exe')
    elif globalvars.record_ver == 2 and globalvars.steam_ver == 1:
        source_installer = os.path.join(installers_path, 'SteamInstall_cz_2003-11-11.exe')
    elif globalvars.record_ver == 2 and globalvars.steam_ver == 2 and globalvars.steamui_ver == 5:
        source_installer = os.path.join(installers_path, 'SteamInstall_2003-12-19.exe')
    elif globalvars.record_ver == 3:
        source_installer = os.path.join(installers_path, 'SteamInstall_2004.exe')
    else:
        raise ValueError("No matching installer configuration found for the given global variables.")

    # Copy the installer to LAN and WAN paths
    shutil.copy(source_installer, lan_installer_path)
    shutil.copy(source_installer, wan_installer_path)
    print(f"Copied {source_installer} to {lan_installer_path} and {wan_installer_path}")

# Example usage
"""if __name__ == "__main__":
    zip_path = "path_to_installer.exe"  # Installer executable containing ZIP structure
    target_file_path = "path_within_zip/steam.exe"  # Relative path within the ZIP to replace
    file_to_replace_path = "path_to_new_steam.exe"  # Path to the new file

    replace_file_in_zip(zip_path, target_file_path, file_to_replace_path)"""