import logging
import os
import platform
import shutil
import subprocess
import sys
import time

from sqlalchemy import MetaData, create_engine
from sqlalchemy.exc import SQLAlchemyError

import globalvars
from config import read_config
from utils import generate_secure_password

log = logging.getLogger("MYSQL_SETUP")

stmconfig = read_config()
server_ip = stmconfig['server_ip']
def create_default_config(mariadb_install_path, dbport):
    if platform.system() == "Windows":
        config_path = os.path.join(mariadb_install_path, 'my.ini')
        default_config = f"""
[mysqld]
datadir=\"./files/mdb/data/\"
basedir=\"./files/mdb/\"
port={dbport}
server-id=1
key_buffer_size=16M
max_allowed_packet=64M
wait_timeout=28800
interactive_timeout=28800
table_cache=64
sort_buffer_size=512K
net_buffer_length=8K
read_buffer_size=512K
read_rnd_buffer_size=512K
myisam_sort_buffer_size=8M
bind-address=0.0.0.0
expire_logs_days=7
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
log_error=\"./../../../logs/mariadb_error.log\"
general_log=1
general_log_file=\"./../../../logs/mariadb_general.log\"

"""
    else:  # Linux
        config_path = os.path.join(mariadb_install_path, 'my.cnf')
        default_config = f"""
[mysqld]
datadir=\"./files/mdb/data/\"
basedir=\"./files/mdb/\"
port={dbport}
server-id=1
key_buffer_size=16M
max_allowed_packet=64M
wait_timeout=28800
interactive_timeout=28800
table_cache=64
sort_buffer_size=512K
net_buffer_length=8K
read_buffer_size=512K
read_rnd_buffer_size=512K
myisam_sort_buffer_size=8M
bind-address=0.0.0.0
expire_logs_days=7
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
log_error=\"./../../../logs/mariadb_error.log\"
general_log=1
general_log_file=\"./../../../logs/mariadb_general.log\"

"""
    # Only create the config file if it does not already exist
    if not os.path.exists(config_path):
        with open(config_path, 'w') as config_file:
            config_file.write(default_config)
        log.info(f"Default configuration file created at {config_path}")
    else:
        log.error(f"Configuration file already exists at {config_path}")

def change_root_password(mariadb_install_path, password, dbport):
    sql_command = f"GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' IDENTIFIED BY '{password}' WITH GRANT OPTION;"
    if platform.system() == "Windows":
        mysql_path = os.path.join(mariadb_install_path, 'bin', 'mysql.exe')
    else:
        mysql_path = "files/mdb/bin/mariadb"  # Assuming 'mysql' is in the PATH on Linux

    try:
        subprocess.run([mysql_path, '-h', '127.0.0.1', '-P', f'{dbport}', '-u', 'root', '-e', sql_command], check=False)
        log.info("New root user added with local access only.")
    except subprocess.CalledProcessError as e:
        log.error(f"Failed to add new root user: {e}")
        exit(1)


def add_new_user_with_permissions(mariadb_install_path, database_name, username, password, root_password, dbport):
    # Generate a secure random password for the new user
    #print(f"Generated password for {username}: {password}")

    # SQL command to create the new user and grant permissions
    sql_commands = [
            f"CREATE USER '{username}'@'%' IDENTIFIED BY '{password}';",
            f"GRANT ALL PRIVILEGES ON {database_name}.* TO '{username}'@'%';",
            "CREATE DATABASE IF NOT EXISTS ClientConfigurationDB;",
            "CREATE DATABASE IF NOT EXISTS ContentDescriptionDB;",
            f"GRANT ALL PRIVILEGES ON ClientConfigurationDB.* TO '{username}'@'%';",
            f"GRANT ALL PRIVILEGES ON ContentDescriptionDB.* TO '{username}'@'%';",
            "FLUSH PRIVILEGES;"
    ]

    if platform.system() == "Windows":
        mysql_path = os.path.join(mariadb_install_path, 'bin', 'mysql.exe')
    else:
        mysql_path = "mysql"  # Assuming 'mysql' is in the PATH on Linux

    try:
        for sql_command in sql_commands:
            subprocess.run([mysql_path, '-h', '127.0.0.1', '-P', f'{dbport}', '-u', 'root', f'-p{root_password}', '-e', sql_command], check = False)
        log.info(f"User {username} created with permissions on {database_name}.")
    except subprocess.CalledProcessError as e:
        log.error(f"Failed to create user {username} or grant permissions: {e}")
        exit(1)

def initialize_mariadb(mariadb_install_path):
    if platform.system() == "Windows":
        try:
            log.info("Initializing MariaDB data directory...")
            # Construct paths using os.path.join and ensure backslashes are used
            install_db_path = os.path.join(mariadb_install_path, 'bin', 'mariadb-install-db.exe').replace('\\', '/')
            data_dir = 'files/mdb/data'.replace('\\', '/')

            # Ensure the data directory exists
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)

            # Use the constructed paths in the subprocess call
            subprocess.call([install_db_path, r'--datadir=files/mdb/data'])
            start_database(mariadb_install_path)
        except subprocess.CalledProcessError as e:
            log.error(f"Failed to initialize MariaDB on Windows: {e}")
            exit(1)
    else:  # Linux
        try:
            log.info("Initializing MariaDB data directory...")
            subprocess.call(['mariadb-install-db'])
            log.info("Initialization successful.")

        except subprocess.CalledProcessError as e:
            log.error(f"Failed to initialize MariaDB on Linux: {e}")
            exit(1)


def start_database(mariadb_install_path):
    if globalvars.stop_server:
        sys.exit(0)
    else:
        log.info("MariaDB data directory initialization successful.")
        daemon_start_path = os.path.join(mariadb_install_path, 'bin', 'mariadbd.exe').replace('\\', '/')
        globalvars.mariadb_process = subprocess.Popen([daemon_start_path, '--defaults-file=files/mdb/my.ini'])
        log.info("MariaDB Initialized.")
        time.sleep(2)  # Sleep for 2 seconds before creating the engine


def setup_mariadb(config):

    # Paths for the configuration files
    initialized_flag_path = config['configsdir'] + '/' + ".initialized"
    mariadb_install_path = "files/mdb/"

    dbport = config['database_port']
    dbhost = config['database_host']
    dbscheme = config['database']
    dbusername = config['database_username']
    dbpassword = config['database_password']

    # Check if .initialized exists, if it does that means this has already ran and we dont want to remake the database configs!
    if os.path.exists(initialized_flag_path):
        with open(initialized_flag_path, 'r') as file:
            content = file.read().strip()

        if content == '1':
            start_database(mariadb_install_path)
            return

        if config['use_builtin_mysql'].lower() == 'false':
            return
    elif not os.path.exists(initialized_flag_path) and config['use_builtin_mysql'].lower() == 'false':
        db_url = f"mysql+mysqlconnector://{dbusername}:{dbpassword}@{dbhost}:{dbport}/{dbscheme}"
        try:
            # Connect to the database
            engine = create_engine(db_url)
            conn = engine.connect()

            # Reflect the existing database
            metadata = MetaData()
            metadata.reflect(bind = engine)

            # Drop all tables in the database
            metadata.drop_all(engine)

            print("All tables have been dropped since .init file was not found.")
        except SQLAlchemyError as e:
            print(f"An error occurred: {e}")
            pass

    # this is a first run, just in case delete the data directory and my.ini so we can create new ones
    if os.path.exists('files/mdb/data'):
        shutil.rmtree('files/mdb/data')
        try:
            os.remove('files/mdb/my.ini')
        except:
            pass

    log.info("Deploying Built-in MySQL Database Software")

    create_default_config(mariadb_install_path, dbport)
    initialize_mariadb(mariadb_install_path)

    # Generate a secure random password for the new root user
    root_password = generate_secure_password()
    log.info(f"Generated root password: {root_password}")

    # Save the root password to a file
    with open("mysql_rootpassword.txt", "w") as password_file:
        password_file.write(root_password)
    log.info("Root password saved to ./mysql_rootpassword.txt")

    # change root user password to the generated password
    change_root_password(mariadb_install_path, root_password, dbport)

    add_new_user_with_permissions(mariadb_install_path, dbscheme, dbusername, dbpassword, root_password, dbport)

    with open(initialized_flag_path, 'w') as file:
        file.write('1')