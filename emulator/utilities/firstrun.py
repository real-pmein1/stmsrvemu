import os
import logging
import subprocess
import sys
import re
import hashlib
import globalvars
import time
from config import save_config_value, get_config
from utilities.database.setup_mariadb import start_database
from utils import generate_secure_password, generate_password

log = logging.getLogger("init")
configs = get_config()
admin_credentials = {"username": "", "password": ""}


def get_client_config_path():
    """Return the client_config.ini path based on runtime (frozen vs source)."""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
        target_dir = os.path.join(base_dir, "tools")
    else:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        target_dir = os.path.join(base_dir, "py39_tools", "user_tool")

    os.makedirs(target_dir, exist_ok=True)
    return os.path.join(target_dir, "client_config.ini")


def ensure_peer_password(config_values: dict) -> str:
    """Ensure a peer password exists, generating and persisting one if needed."""
    peer_password = (config_values or {}).get("peer_password") or ""
    if peer_password:
        globalvars.peer_password = peer_password
        return peer_password

    peer_password = generate_password()
    save_config_value("peer_password", peer_password)

    # Keep in-memory config and globals in sync for subsequent use.
    try:
        config_values["peer_password"] = peer_password
    except Exception:
        pass
    globalvars.peer_password = peer_password

    log.info("Generated new peer_password and saved to emulator.ini")
    return peer_password


def write_client_config(admin_username: str = "", admin_password: str = ""):
    """Create client_config.ini for the Remote Admin Tool with current settings."""
    current_config = get_config() or {}

    server_ip = current_config.get("server_ip") or ""
    admin_port = current_config.get("admin_server_port") or ""
    peer_password = ensure_peer_password(current_config)

    client_config_path = get_client_config_path()
    content_lines = [
        "[config]",
        f"adminserverip={server_ip}",
        f"adminserverport={admin_port}",
        f"adminusername={admin_username}",
        f"adminpassword={admin_password}",
        f"peer_password={peer_password}",
        "",
    ]

    try:
        with open(client_config_path, "w", encoding="utf-8") as client_config_file:
            client_config_file.write("\n".join(content_lines))
        log.info(f"client_config.ini written to {client_config_path}")
    except Exception as exc:
        log.error(f"Failed to write client_config.ini to {client_config_path}: {exc}")


def restart_script():
    log.info("Restarting Server...")

    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # For compiled executables
        os.execv(globalvars.ORIGINAL_PYTHON_EXECUTABLE, [globalvars.ORIGINAL_PYTHON_EXECUTABLE] + globalvars.ORIGINAL_CMD_ARGS[1:])
    else:
        # For scripts run from source
        # If the script is run with a specific Python interpreter, use that
        subprocess.call([globalvars.ORIGINAL_PYTHON_EXECUTABLE] + globalvars.ORIGINAL_CMD_ARGS)
        sys.exit(0)  # Exit parent process after child completes

def check_initialization():
    log.info("Server not initialized. Running setup...")
    time.sleep(1)
    prompt_setup_server()


DEFAULT_ADMIN_RIGHTS = 8191  # all permissions from servers/permissions.py


def create_admin_user_sql_file(username: str, password: str, rights: int = DEFAULT_ADMIN_RIGHTS):
    """Create or append to a SQL file for admin user insertion.

    Generates or appends to a SQL file at files/sql/admin_user.sql that will be
    executed when the database engine loads SQL files on startup.
    Supports adding multiple admin users before server start.
    """
    # Generate salt and password hash
    salt = os.urandom(8).hex()
    pw_hash = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

    # Escape single quotes in username for SQL safety
    escaped_username = username.replace("'", "''")

    # Ensure the directory exists
    sql_dir = os.path.join('files', 'sql')
    os.makedirs(sql_dir, exist_ok=True)

    sql_file_path = os.path.join(sql_dir, 'admin_user.sql')

    # Check if file already exists
    file_exists = os.path.exists(sql_file_path)

    if file_exists:
        # Append only the INSERT statement for additional users
        insert_sql = f"""
-- Additional admin user
INSERT INTO admin_users_record (Username, PWHash, PWSeed, Rights)
VALUES ('{escaped_username}', '{pw_hash}', '{salt}', {rights});
"""
        with open(sql_file_path, 'a', encoding='utf-8') as f:
            f.write(insert_sql)

        print(f"Admin user '{username}' appended to: {sql_file_path}")
    else:
        # Create the SQL content with table creation for first user
        sql_content = f"""-- Admin user creation script (auto-generated)
-- This file will be automatically deleted after execution

CREATE TABLE IF NOT EXISTS admin_users_record (
    UniqueID INT AUTO_INCREMENT PRIMARY KEY,
    Username VARCHAR(60) NOT NULL UNIQUE,
    PWHash VARCHAR(64) NOT NULL,
    PWSeed VARCHAR(256),
    Rights INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO admin_users_record (Username, PWHash, PWSeed, Rights)
VALUES ('{escaped_username}', '{pw_hash}', '{salt}', {rights});
"""
        with open(sql_file_path, 'w', encoding='utf-8') as f:
            f.write(sql_content)

        print(f"Admin user SQL file created at: {sql_file_path}")

    print(f"Admin user '{username}' will be added when the server starts.")


def create_admin_user(username: str, password: str, rights: int = DEFAULT_ADMIN_RIGHTS):
    """Create an admin user by generating a SQL file.

    The SQL file will be placed in files/sql/admin_user.sql and will be
    executed when the database engine loads SQL files on startup.
    """
    # Create SQL file instead of inserting directly
    create_admin_user_sql_file(username, password, rights)


def prompt_create_admin():
    global admin_credentials
    print("")
    print("-----------Create Administration User-----------")
    print("")

    while True:
        username = input("Enter admin username: ").strip()
        if not username:
            print("Username cannot be empty.")
            continue

        password = input("Enter admin password: ").strip()
        if not password:
            print("Password cannot be empty.")
            continue

        confirm_password = input("Confirm admin password: ").strip()
        if password != confirm_password:
            print("Passwords do not match.")
            continue

        try:
            create_admin_user(username, password)
            admin_credentials["username"] = username
            admin_credentials["password"] = password
            print("")
            print("Administration user created successfully!")
            break
        except Exception as e:
            print(f"Error creating admin user: {e}")
            break

    prompt_startover()

def prompt_startover():
    global admin_credentials
    print("")
    print("Would you like to:")
    print("1.) Start over")
    print("2.) Create Administration User for Remote Administration Tool")
    print("3.) Continue launching the server")
    choice = input("Enter your choice (1/2/3): ").strip()

    if choice == "1":
        # Delete admin_user.sql if it exists when starting over
        sql_file_path = os.path.join('files', 'sql', 'admin_user.sql')
        if os.path.exists(sql_file_path):
            try:
                os.remove(sql_file_path)
                print(f"Deleted existing admin user SQL file: {sql_file_path}")
            except Exception as e:
                print(f"Warning: Could not delete admin user SQL file: {e}")
        admin_credentials = {"username": "", "password": ""}
        prompt_setup_server()
    elif choice == "2":
        prompt_create_admin()
    elif choice == "3":
        write_client_config(admin_credentials.get("username", ""), admin_credentials.get("password", ""))
        directory = os.path.join(".", configs['configsdir'])
        os.makedirs(directory, exist_ok=True)  # Ensure the directory exists
        initialized_flag_path = os.path.join(directory, '.initialized')

        # Create an empty .initialized file
        with open(initialized_flag_path, 'w') as file:
            pass  # Just create the file, no need to write anything
        restart_script()
    else:
        print("Invalid choice. Please enter 1, 2, or 3.")
        prompt_startover()  # Re-prompt the user if the input is invalid.

def prompt_setup_server():
    actualhost = ''
    is_linux = sys.platform.startswith('linux')

    print("")
    print("")
    print("-----------First Run Server Initialization & Setup-----------")
    print("")
    print("Please select the database you wish to use:")

    if is_linux:
        print("1.) External MariaDB database")
        print("Enter your choice (default 1): ", end = "")
        choice = input().strip() or "1"
        if choice != "1":
            print("Invalid choice, defaulting to 1.) External MariaDB database")
            choice = "1"
        # On Linux, choice "1" means external database
        use_external = True
    else:
        print("1.) Built-in MariaDB database")
        print("2.) External MariaDB database")
        print("Enter your choice (default 1): ", end = "")
        choice = input().strip() or "1"
        if choice not in ["1", "2"]:
            print("Invalid choice, defaulting to 1.) Built-in MySQL database")
            choice = "1"
            save_config_value('use_builtin_mysql', 'true')
        use_external = (choice == "2")

    if use_external:
        print("")
        print("Please enter the IP address or domain name of the external MySQL database: ", end = "")
        dbhost = input().strip() or "127.0.0.1"
        save_config_value('database_host', dbhost)
        save_config_value('use_builtin_mysql', 'false')
        actualhost = dbhost
    else:
        save_config_value('database_host', configs['server_ip'])
        save_config_value('use_builtin_mysql', 'true')
        actualhost = configs['server_ip']

    if use_external:
        print("")
        print("Please enter the database port (default 3306): ", end = "")
    else:
        print("")
        print("Please select a port for the database (default 3306): ", end = "")
    dbport = input().strip() or "3306"
    try:
        int_test = int(dbport)
        save_config_value('database_port', dbport)
    except ValueError:
        print(f"Invalid port number. Defaulting to 3306.")
        save_config_value('database_port', "3306" )
        dbport = "3306"

    # Get database username
    if use_external:
        print("")
        dbusername = input("Please enter the database username: ").strip()
    else:
        print("")
        dbusername = input("Please select a database username (leave blank for default: stmserver): ").strip()
    if not dbusername:
        dbusername = "stmserver"
    # save the new config to emulator.ini
    save_config_value('database_username', dbusername)

    # Get password for database user
    if use_external:
        print("")
        dbpassword = input("Please enter the database password: ").strip()
        if not dbpassword:
            dbpassword = "stmserver"
            print(f"No password provided, defaulting to stmserver")
    else:
        print("")
        dbpassword = input("Create the desired password for the database user (leave blank for default: autogenerated): ").strip()
        if not dbpassword:
            dbpassword = generate_secure_password(8)
            log.info(f"Autogenerated password: {dbpassword}")
    save_config_value('database_password', dbpassword)

    # Get the name of the database
    print("")
    dbscheme = input("Please enter the name of the database you would like the server to use (leave blank for default: stmserver): ").strip()
    if not dbscheme:
        dbscheme = "stmserver"
    save_config_value('database', dbscheme)
    print("")
    log.info("Configurations Saved..")
    # Example usage
    update_php_database_config('files/webserver/webroot/include/global.php',
                               host=f'{actualhost}:{int_test}',
                               dbname=f'{dbscheme}',
                               username=f'{dbusername}',
                               password=f'{dbpassword}')

    prompt_startover()


def update_php_database_config(file_path, host, dbname, username, password):
    # Normalize the file path for cross-platform compatibility
    file_path = os.path.normpath(file_path)

    # Define regex patterns for each variable with inline comments to match the PHP structure
    patterns = {
            'host':    r"\$host\s*=\s*'([^']*)';\s*// Your database domain/ip",
            'dbname':  r"\$dbname\s*=\s*'([^']*)';\s*// Your database name",
            'username':r"\$username\s*=\s*'([^']*)';\s*// Your database username",
            'password':r"\$password\s*=\s*'([^']*)';\s*// Your database password"
    }

    # Define replacement templates based on the parameter values
    replacements = {
            'host':    f"$host = '{host}'; // Your database domain/ip",
            'dbname':  f"$dbname = '{dbname}'; // Your database name",
            'username':f"$username = '{username}'; // Your database username",
            'password':f"$password = '{password}'; // Your database password"
    }

    # Read the file content
    try:
        with open(file_path, 'r') as file:
            file_content = file.read()
    except FileNotFoundError:
        log.warning(f"{file_path} Not found, Steam Community not configured")
        time.sleep(1)
        return
    except Exception as e:
        log.error(f"Failed to read file: {e}")
        return

    # Track whether any modifications are made
    modified = False

    # Check each variable and replace if there's a mismatch
    for var_name, pattern in patterns.items():
        match = re.search(pattern, file_content)

        if match:
            current_value = match.group(1)
            new_value = locals()[var_name]
            # Only replace if the values don't match
            if current_value != new_value:
                #print(f"[INFO] Updating {var_name} from '{current_value}' to '{new_value}'")
                file_content = re.sub(pattern, replacements[var_name], file_content)
                modified = True
        else:
            log.warning(f"Pattern for {var_name} not found in file.")

    # If modifications were made, rewrite the file with updated content
    if modified:
        try:
            with open(file_path, 'w') as file:
                file.write(file_content)
            log.info("Community global.php file updated successfully with new configurations.")
            time.sleep(1)
        except Exception as e:
            log.error(f"Failed to write to file: {e}")
    else:
        log.info("No changes were necessary; file remains unmodified.")

