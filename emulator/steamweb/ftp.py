# TODO Eventually create a system for the user to get an appid/depotid generated from the server to ensure that the specific user is the only one who can edit/change their own specific applications/depots

import logging
import os
import shutil
import xml.etree.ElementTree as ET
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
import config


configs = config.get_config()


class CustomFTPHandler(FTPHandler):

    def log(self, message):
        """
        Logs a message, sanitizing it to avoid UnicodeEncodeErrors.
        """
        try:
            # Attempt to log the message normally
            super().log(message)
        except UnicodeEncodeError:
            # Sanitize the message by replacing problematic characters
            sanitized_message = message.encode('utf-8', errors = 'replace').decode('utf-8')
            super().log(sanitized_message)

    def on_connect(self):
        self.log(f"Connected from {self.remote_ip}:{self.remote_port}")

    def on_disconnect(self):
        # Log disconnections
        self.log(f"Disconnected from {self.remote_ip}:{self.remote_port}")

    def on_login(self, username):
        # Log successful logins
        self.log(f"User {username} logged in")

    def on_login_failed(self, username, password):
        # Log failed login attempts
        self.log(f"Failed login attempt with username: {username}")

    def ftp_CLNT(self, line):
        # If the client sends a "CLNT" command, log it
        client_info = line.split(' ', 1)[1] if ' ' in line else 'Unknown client'
        self.log(f"Client information: {client_info}")

    def on_file_received(self, file_path):
        # Log the received file
        self.log(f"File received: {file_path}")
        filename = os.path.basename(file_path)
        extension = os.path.splitext(filename)[1].lower()

        # Define directories
        temp_directory = os.path.join("files", "temp")
        customblob_directory = os.path.join("files", "custom")
        sdkstorages_directory = configs['steam2sdkdir']

        # Ensure directories exist
        for directory in (temp_directory, customblob_directory, sdkstorages_directory):
            os.makedirs(directory, exist_ok = True)

        # Move the file to the temp directory first
        temp_path = os.path.join(temp_directory, filename)
        try:
            shutil.move(file_path, temp_path)
            self.log(f"Moved file to temp directory: {temp_path}")
        except Exception as e:
            self.log(f"Error moving file to temp directory: {e}")
            self.respond("550 File transfer failed due to server error.")
            return

        # Handle file based on extension
        try:
            if extension == '.xml':
                # Handle 'ContentDescriptionDB.xml' specifically
                if filename.lower() == 'contentdescriptiondb.xml':
                    # Parse the XML to find the first AppId
                    try:
                        tree = ET.parse(temp_path)
                        root = tree.getroot()
                        app_record = root.find('.//AppRecord')
                        if app_record is None or 'AppId' not in app_record.attrib:
                            raise ValueError("No AppId found in ContentDescriptionDB.xml")
                        first_app_id = app_record.attrib['AppId']

                        # Rename the XML file based on the first AppId
                        new_filename = f"{first_app_id}.xml"
                        new_path = os.path.join(customblob_directory, new_filename)
                        self.log(f"Renaming ContentDescriptionDB.xml to {new_filename}")

                        # Replace the existing XML file if it exists
                        shutil.move(temp_path, new_path)
                        self.log(f"Moved XML file to {new_path}")

                    except Exception as e:
                        self.log(f"Error processing ContentDescriptionDB.xml: {e}")
                        self.respond("550 File transfer failed due to server error.")
                        os.remove(temp_path)  # Clean up temp file
                        return
                else:
                    # Move other XML files to the customblob_directory without renaming
                    new_path = os.path.join(customblob_directory, filename)
                    shutil.move(temp_path, new_path)
                    self.log(f"Moved XML file to {new_path}")

            elif extension in {'.dat', '.blob'}:
                new_path = os.path.join(sdkstorages_directory, filename)

                # Check if the file already exists
                if os.path.exists(new_path):
                    self.log(f"File already exists: {new_path}")
                    self.respond("550 File transfer failed due to server error.")
                    os.remove(temp_path)  # Clean up temp file
                    return

                # Move the file to the sdkstorages_directory
                shutil.move(temp_path, new_path)
                self.log(f"Moved {extension} file to {new_path}")

            else:
                # Reject non-SDK related files
                self.log(f"User tried to upload a non-SDK related file: {filename}")
                self.respond("550 File transfer failed due to server error.")
                os.remove(temp_path)  # Clean up temp file
                return

        except Exception as e:
            self.log(f"Error processing file {filename}: {e}")
            self.respond("550 File transfer failed due to server error.")
            os.remove(temp_path)  # Clean up temp file
            return


def create_ftp_server(directory, anonymous_directory, address="0.0.0.0", port=21):
    # Setup logging
    logger = logging.getLogger('pyftpdlib')
    #logger.setLevel(logging.INFO)

    # Log to console
    #console_handler = logging.StreamHandler()
    #console_handler.setLevel(logging.INFO)
    #logger.addHandler(console_handler)

    # Log to file
    os.makedirs('logs', exist_ok=True)
    file_handler = logging.FileHandler('logs/pyftpdlib.log')
    #file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    # Instantiate a dummy authorizer for managing 'virtual' users
    authorizer = DummyAuthorizer()
    # Load accounts from 'ftpaccounts.txt'
    try:
        with open('ftpaccounts.txt', 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and lines starting with '#' or ';'
                if not line or line.startswith('#') or line.startswith(';'):
                    continue

                # Split the line into username, password, and permission parts
                try:
                    username, password, perm_string = line.split(':', 2)

                    # Ignore anything after a semicolon in the perm_string (e.g., comments)
                    perm_string = perm_string.split(';', 1)[0].strip()

                    # Translate the provided permissions to pyftpdlib format
                    perm = ''
                    if 'r' in perm_string:
                        perm += 'elr'  # List and retrieve files
                    if 'w' in perm_string:
                        perm += 'adfmw'  # Allow uploading, appending, and creating directories
                    if 'd' in perm_string:
                        perm += 'd'  # Allow deleting files and directories
                    if 'u' in perm_string:
                        perm += 'w'  # Allow storing (uploading) files but no listing

                    # Set user's home directory
                    homedir = os.path.join(directory, username)
                    os.makedirs(homedir, exist_ok = True)
                    # Add user with the specified permissions
                    authorizer.add_user(username, password, homedir = homedir, perm = perm)
                except ValueError:
                    print(f"Invalid line in ftpaccounts.txt: {line}")
    except FileNotFoundError:
        # Create the 'ftpaccounts.txt' file with commented-out examples
        with open('ftpaccounts.txt', 'w') as f:
            f.write(
                    "# Example of ftpaccounts.txt file\n"
                    "# Each line follows the format: username:password:permissions\n"
                    "# Permissions can include:\n"
                    "#   r - read (list and retrieve files)\n"
                    "#   w - write (upload files, create directories)\n"
                    "#   d - delete (delete files and directories)\n"
                    "#   u - upload-only (store files but cannot list)\n"
                    "# Comments and empty lines are ignored\n"
                    "# Example entries:\n"
                    "# user1:password1:rw; This user can read and write files\n"
                    "# user2:password2:r; Read-only user\n"
                    "# user3:password3:rwd; Read, write, and delete permissions\n"
                    "# user4:password4:u; Upload-only user\n"
            )
        print("Created 'ftpaccounts.txt' with example entries. Please edit it to add your FTP user accounts.")

    # Add anonymous user with restricted access to a specific directory
    os.makedirs(anonymous_directory, exist_ok=True)
    authorizer.add_anonymous(anonymous_directory, perm='elr')  # Adjust 'perm' as needed

    # Instantiate FTP handler class
    handler = CustomFTPHandler
    handler.authorizer = authorizer

    # Enable logging of all commands and responses
    handler.log_prefix = '[%(username)s] %(remote_ip)s:%(remote_port)s - '  # Prefix for log entries

    # Create FTP server and start serving
    server = FTPServer((address, port), handler)
    print(f"Starting FTP server on {address}:{port}")
    server.serve_forever()

# Usage example
"""if __name__ == "__main__":
    create_ftp_server("files/ftproot", "files/beta1_ftp")"""