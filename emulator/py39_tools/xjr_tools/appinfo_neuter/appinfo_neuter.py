import os
import chardet
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# Paths
emulator_ini_path = "emulator.ini"
mod_pkg_directory = "files/mod_pkg"

def detect_encoding(file_path):
    """Detects the encoding of a file."""
    with open(file_path, "rb") as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        return result['encoding']

def read_ip_from_ini(file_path, key):
    """Reads the IP (LAN or Public) from the emulator.ini file, ignoring comments and extra spaces."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                if line.startswith(key + "="):
                    ip_part = line.split(key + "=", 1)[1]
                    ip = ip_part.split(";")[0].strip()
                    return ip
    except FileNotFoundError:
        print(f"{Fore.RED}Error: {file_path} not found.")
    except Exception as e:
        print(f"{Fore.RED}Error reading {file_path}: {e}")
    return None

def replace_url_in_vdf(file_path, new_ip, old_ips):
    """Replaces the StorefrontCDNURL in the appinfo.vdf file, including previously neutered URLs."""
    target_urls = [f"http://{ip}" for ip in old_ips]
    target_urls.append("http://cdn.store.steampowered.com")  # Add the original URL to targets
    replacement_url = f"http://{new_ip}"
    
    try:
        encoding = detect_encoding(file_path)
        print(f"{Fore.YELLOW}Detected encoding for {file_path}: {encoding}")

        with open(file_path, "rb") as file:  # Open file in binary mode to preserve LF line endings
            content = file.read().decode(encoding)

        for target_url in target_urls:
            content = content.replace(target_url, replacement_url)

        with open(file_path, "wb") as file:  # Open file in binary mode to write
            file.write(content.replace("\r\n", "\n").encode(encoding))  # Ensure UNIX LF

        print(f"{Fore.GREEN}Updated {file_path} with IP: {new_ip}.")
    except FileNotFoundError:
        print(f"{Fore.RED}Error: {file_path} not found.")
    except Exception as e:
        print(f"{Fore.RED}Error updating {file_path}: {e}")

def find_vdf_files(directory):
    """Finds all files named appinfo.vdf in the given directory and its subdirectories."""
    vdf_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file == "appinfo.vdf":
                vdf_files.append(os.path.join(root, file))
    return vdf_files

def main():
    print("This tool replaces the ""http://cdn.store.steampowered.com"" URL in any appinfo.vdf files")
    print("you place in the mod_pkg directory. Replacing the CDN URL in the appinfo.vdf files allows")
    print("the gamedetailsheaders (background screenshots) to work when hosted from your Apache server.")
    print("")
    print(f"{Fore.CYAN}Choose the IP type for replacement:")
    print(f"{Fore.CYAN}1. LAN IP (server_ip) hosting localy")
    print(f"{Fore.CYAN}2. External IP (public_ip) hosting publicly")
    
    choice = input(f"{Fore.CYAN}Enter 1 or 2: ").strip()
    if choice not in {"1", "2"}:
        print(f"{Fore.RED}Invalid choice. Exiting.")
        return
    
    ip_key = "server_ip" if choice == "1" else "public_ip"
    new_ip = read_ip_from_ini(emulator_ini_path, ip_key)
    if not new_ip:
        print(f"{Fore.RED}Failed to retrieve {ip_key} from emulator.ini.")
        return
    
    lan_ip = read_ip_from_ini(emulator_ini_path, "server_ip") or ""
    public_ip = read_ip_from_ini(emulator_ini_path, "public_ip") or ""
    old_ips = [lan_ip, public_ip]
    
    vdf_files = find_vdf_files(mod_pkg_directory)
    if not vdf_files:
        print(f"{Fore.RED}No appinfo.vdf files found in {mod_pkg_directory}.")
        return
    
    for vdf_file in vdf_files:
        replace_url_in_vdf(vdf_file, new_ip, old_ips)

if __name__ == "__main__":
    main()
    input("Press Enter to exit...")
