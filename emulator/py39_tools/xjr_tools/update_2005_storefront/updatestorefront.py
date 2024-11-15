import os
import shutil
import subprocess
import sys

# Define paths relative to the script's location
destination = os.path.join(os.path.dirname(sys.executable), "files", "webserver", "webroot", "protected")
client_blob = os.path.join(destination, "clientregistry.blob")
content_desc = os.path.join(destination, "ContentDescriptionRecord.xml")

# Check if a file was dragged onto the executable; if not, show instructions
if len(sys.argv) < 2:
    print("Usage Instructions:\n")
    print("1. Drag a ClientRegistry.blob you want the storefront's content to reflect onto this executable.")
    print("2. The program will automatically copy the ClientRegistry.blob to the appropriate location,")
    print("   convert it to XML for use with the 2005 storefront, and clean up temporary files.")
    print("")
    print("   NOTE: Using the ClientRegistry.blob from your Steam client folder after logging into an account")
    print("   will make the storefront be in parity with the Steam Emulator's CDR. You will need to do this")
    print("   everytime you change the Steam version in the emulator.")
    input("\nPress Enter to exit...")
    sys.exit()

# Delete ContentDescriptionRecord.xml if it exists
if os.path.exists(content_desc):
    os.remove(content_desc)

# Get the path of the dragged file
file_to_copy = sys.argv[1]
shutil.copy(file_to_copy, destination)

# Run CDR2XML_vb.exe in the destination directory
os.chdir(destination)
subprocess.run(["CDR2XML_vb.exe"])

# Delete clientregistry.blob if it exists
if os.path.exists(client_blob):
    os.remove(client_blob)

# Pause the script to emulate "pause" in a batch file
input("Press Enter to exit...")
