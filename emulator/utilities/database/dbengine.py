import os
import sys
import threading
import logging
import subprocess
import shutil
from pathlib import Path
import mariadb
import time
import os
import zipfile
import psutil
from datetime import datetime, timedelta
from sqlalchemy import TextClause, create_engine, delete, inspect, select, text
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from sqlalchemy.sql import Delete, Insert, Select, Update
from sqlalchemy_utils import create_database, database_exists
from sqlalchemy.exc import SQLAlchemyError, IntegrityError  # Make sure to import this at the top

import sqlparse.engine.grouping
sqlparse.engine.grouping.MAX_GROUPING_DEPTH = None
sqlparse.engine.grouping.MAX_GROUPING_TOKENS = None

import globalvars
from .base_dbdriver import Base, ExecutedSQLFile

# Lazy logger initialization to ensure CustomLogger class is set first
_log = None

def get_log():
    global _log
    if _log is None:
        _log = logging.getLogger("SQLEngine")
    return _log


def find_mariadb_client():
    """Find the mariadb or mysql client executable on the system."""
    # Check for built-in mariadb first (Windows)
    if globalvars.IS_WINDOWS:
        builtin_path = os.path.join("files", "mdb", "bin", "mariadb.exe")
        if os.path.isfile(builtin_path):
            return builtin_path

    # Try to find mariadb or mysql in PATH
    for cmd in ['mariadb', 'mysql']:
        path = shutil.which(cmd)
        if path:
            return path

    # Common Linux locations to check
    common_paths = [
        '/usr/bin/mariadb',
        '/usr/bin/mysql',
        '/usr/local/bin/mariadb',
        '/usr/local/bin/mysql',
        '/usr/local/mariadb/bin/mariadb',
        '/usr/local/mysql/bin/mysql',
    ]

    for path in common_paths:
        if os.path.isfile(path):
            return path

    return None

# from tqdm import tqdm
sql_execution_done_flag = False

class DatabaseDriver():
    _session_factory = None

    def __init__(self):
        super().__init__()
        self.engine = None
        self.lock = threading.Lock()
        self.metadata = Base.metadata
        if DatabaseDriver._session_factory is None:
            self.connect()

        self.config = globalvars.config

    def connect(self, _unused_connection_string: str = ""):
        """
        Wait for the bundled MariaDB to finish booting, then create the
        SQLAlchemy engine.  We simply look for a
        ?[Note] ? mariadbd.exe: ready for connections.? line whose
        timestamp is *after* this function was entered.
        """
        connection_string = get_db_config()

        # ????????????????????????????????????????????????????????????????
        if globalvars.config['use_builtin_mysql'].lower() == "true":

            if globalvars.mariadb_initialized:          # fast exit
                self.real_connect(connection_string)
                return

            # If the process exists we still have to wait for its ?ready?
            # log-entry, so we no longer short-circuit here.

            start_dt   = globalvars.mariadb_launch_dt
            log_path   = Path('logs/mariadb_error.log')
            deadline   = start_dt + timedelta(seconds=60)
            last_pos   = 0                              # incremental tail

            while datetime.now() < deadline:
                try:
                    chunk = b''  # Initialize chunk before checking
                    if log_path.exists():
                        with log_path.open('rb') as lf:          # binary mode
                            lf.seek(last_pos)
                            chunk     = lf.read()                # new bytes
                            last_pos  = lf.tell()                # safe: no iterator

                    # Nothing new written yet?
                    if not chunk:
                        time.sleep(0.5)
                        continue

                    for raw_line in chunk.splitlines():
                        line = raw_line.decode('latin-1', errors='ignore')
                        if "ready for connections." not in line:
                            continue

                        try:
                            ts = datetime.strptime(line[:19],
                                                   "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            continue

                        if ts >= start_dt:
                            globalvars.mariadb_initialized = True
                            get_log().info("MariaDB ready @ %s.", ts, category="database")
                            self.real_connect(connection_string)
                            return

                except Exception as log_error:
                    get_log().error("Error reading MariaDB log: %s", log_error)

                time.sleep(0.5)  # light 2 Hz poll

            get_log().error(
                "MariaDB did not become ready within 60 s. "
                "Check %s for details.", log_path)
            return

        globalvars.mariadb_initialized = True  # external DB
        self.real_connect(connection_string)

    def real_connect(self, connection_string):
        self.engine = create_engine(connection_string,
                                    pool_size = 150,
                                    max_overflow = 200,
                                    pool_timeout = 15,
                                    pool_recycle = 1800,
                                    pool_use_lifo=True
                                    )
        if not database_exists(self.engine.url):
            create_database(self.engine.url)
        DatabaseDriver._session_factory = sessionmaker(bind = self.engine)
        self.create_missing_tables()

    @classmethod
    def get_session(cls):
        if cls._session_factory is None:
            raise Exception("Database connection not initialized.")
        return scoped_session(cls._session_factory)

    def create_missing_tables(self):
        # Create missing tables based on model definitions
        Base.metadata.create_all(self.engine, checkfirst=True)
        self.execute_sql_files_in_directory('files/sql/')

    def load_sql_file(self, sql_file, chunk_size = 250):
        config = globalvars.config
        filename = os.path.basename(sql_file)

        with Session(self.engine) as session:
            # Check if the file has already been processed
            existing_file = session.query(ExecutedSQLFile).filter_by(filename = filename).first()
            if existing_file:
                # Verify that expected tables actually exist for critical database SQL files
                needs_reexecution = False
                if filename == "ClientConfigurationDB.sql":
                    needs_reexecution = not self._table_exists_in_database("ClientConfigurationDB", "configurations")
                elif filename == "ContentDescriptionDB.sql":
                    needs_reexecution = not self._table_exists_in_database("ContentDescriptionDB", "filename")
                elif filename == "BetaContentDescriptionDB.sql":
                    needs_reexecution = not self._table_exists_in_database("BetaContentDescriptionDB", "filename")
                elif filename == "ProductInformationDB.sql":
                    needs_reexecution = not self._table_exists_in_database("ProductInformationDB", "applications")

                if needs_reexecution:
                    get_log().warning(f"File {filename} was marked as executed but expected tables are missing. Re-executing.")
                    session.delete(existing_file)
                    session.commit()
                else:
                    get_log().debug(f"File {filename} has already been executed. Skipping.")
                    return

        get_log().info(f"Executing {sql_file}.")
        try:
            if sql_file == "files/sql/ContentDescriptionDB.sql" or sql_file == "files/sql/ClientConfigurationDB.sql" or sql_file == "files/sql/ProductInformationDB.sql" or sql_file == "files/sql/BetaContentDescriptionDB.sql":

                if sql_file == "files/sql/ClientConfigurationDB.sql":
                    database_schema = "ClientConfigurationDB"
                elif sql_file == "files/sql/ContentDescriptionDB.sql":
                    database_schema = "ContentDescriptionDB"
                elif sql_file == "files/sql/BetaContentDescriptionDB.sql":
                    database_schema = "BetaContentDescriptionDB"
                else:
                    database_schema = "ProductInformationDB"

                config = globalvars.config
                with Session(self.engine) as session:
                    # Check if file has already been processed
                    filename = os.path.basename(sql_file)
                    existing_file = session.query(ExecutedSQLFile).filter_by(filename = filename).first()
                    if existing_file:
                        get_log().debug(f"File {filename} has already been executed. Skipping.")
                        return
                    if globalvars.IS_WINDOWS and os.path.isfile(os.path.join("files", "mdb", "bin", "mariadb.exe")):
                        # Connect to MariaDB Platform
                        try:
                            conn = mariadb.connect(
                                    user=config['database_username'],
                                    password=config['database_password'],
                                    host=config['database_host'],
                                    port=int(config['database_port'])
                            )
                        except mariadb.Error as e:
                            print(f"Error connecting to MariaDB Platform: {e}")
                            return
                        # Get Cursor
                        cur = conn.cursor()

                        cur.execute(f"DROP DATABASE IF EXISTS {database_schema}")
                        cur.execute(f"CREATE DATABASE IF NOT EXISTS {database_schema}")
                        conn.close()

                        mariadb_bin = os.path.join("files", "mdb", "bin", "mariadb.exe")
                        sql_path = os.path.join("files", "sql", f"{database_schema}.sql")
                        import_cmd = [
                            mariadb_bin,
                            f"-u{config['database_username']}",
                            f"-p{config['database_password']}",
                            f"-h{config['database_host']}",
                            f"-P{config['database_port']}",
                            "--skip-ssl",
                            database_schema,
                        ]
                        #with open(sql_path, "rb") as sql_file:
                        #    import_cddb = subprocess.Popen(import_cmd, stdin=sql_file)
                        #    import_cddb.wait()
                    else:
                        # Linux: Create the database first (same as Windows branch)
                        try:
                            conn = mariadb.connect(
                                    user=config['database_username'],
                                    password=config['database_password'],
                                    host=config['database_host'],
                                    port=int(config['database_port'])
                            )
                            cur = conn.cursor()
                            cur.execute(f"DROP DATABASE IF EXISTS {database_schema}")
                            cur.execute(f"CREATE DATABASE IF NOT EXISTS {database_schema}")
                            conn.close()
                        except mariadb.Error as e:
                            get_log().error(f"Error creating database {database_schema}: {e}")
                            return

                        mariadb_client = find_mariadb_client()
                        if not mariadb_client:
                            get_log().error("Could not find mariadb or mysql client. Please ensure MariaDB/MySQL client is installed and in PATH.")
                            return
                        import_cmd = [
                            mariadb_client,
                            f"-u{config['database_username']}",
                            f"-p{config['database_password']}",
                            f"-h{config['database_host']}",
                            f"-P{config['database_port']}",
                            database_schema,
                        ]
                        sql_path = os.path.join("files", "sql", f"{database_schema}.sql")
                    with open(sql_path, "rb") as sql_file_bin:
                        import_cddb = subprocess.Popen(import_cmd, stdin=sql_file_bin)
                        import_cddb.wait()

                    #get_log().debug(f"Successfully executed statement.")

                    get_log().info(f"Finished executing {sql_file}.")
                    executed_file = ExecutedSQLFile(filename = filename)
                    session.add(executed_file)
                    session.commit()
                    # os.remove(sql_file)
            else:
                # Read the SQL file and escape problematic characters
                with open(sql_file, 'r', encoding = 'latin-1') as file:
                    sql_commands = file.read()

                # Escape single quotes in HTML content
                sql_commands = sql_commands # .replace("'", "''")  # Escape single quotes

                # Split and execute statements individually
                sql_statements = self._split_sql_statements(sql_commands)

                # Execute statements individually
                for statement in sql_statements:
                    if statement.strip():
                        try:
                            with self.engine.connect() as connection:
                                raw_connection = connection.connection
                                cursor = raw_connection.cursor()
                                cursor.execute(statement)
                                raw_connection.commit()
                            #get_log().debug(f"Successfully executed statement.")
                        except SQLAlchemyError as e:
                            get_log().error(f"Error executing statement starting with: {statement[:100]}...\nError: {e}")
                            break  # Stop on error to help narrow down issues

                else:
                    get_log().info(f"Finished executing {sql_file}.")

                # Record the executed file
                with Session(self.engine) as session:
                    executed_file = ExecutedSQLFile(filename = filename)
                    session.add(executed_file)
                    session.commit()

                # Delete admin_user.sql after processing
                if filename == 'admin_user.sql':
                    try:
                        os.remove(sql_file)
                        get_log().info(f"Deleted {sql_file} after successful execution.")
                    except OSError as e:
                        get_log().warning(f"Failed to delete {sql_file}: {e}")

        except Exception as e:
            get_log().error(f"Error processing {sql_file}: {e}")
            return

    def _split_sql_statements(self, sql_commands):
        """
        Splits SQL commands, handling multi-line comments and strings.
        """
        import sqlparse
        parsed = sqlparse.parse(sql_commands)
        statements = []
        for statement in parsed:
            # Skip empty statements
            if statement and statement.tokens:
                statements.append(str(statement).strip())
        return statements

    def execute_sql_files_in_directory(self, directory):
        global sql_execution_done_flag
        if not sql_execution_done_flag:
            #cddb_sql_file_path = os.path.join(directory, )
            with Session(self.engine) as session:
                # Check if the file has already been processed
                existing_file = session.query(ExecutedSQLFile).filter_by(filename = 'ContentDescriptionDB.sql').first()

            if not existing_file:
                # Unzip the ContentDescriptionDB.zip file to the same directory
                zip_file_path = os.path.join(directory, 'ContentDescriptionDB.zip')
                if os.path.exists(zip_file_path):
                    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                        zip_ref.extractall(directory)
                    os.remove(zip_file_path)

            # Iterate over SQL files in the directory and load them
            for filename in os.listdir(directory):
                if filename.endswith('.sql'):
                    self.load_sql_file(os.path.join(directory, filename))

        sql_execution_done_flag = True

    def check_table_exists(self, table_name):
        inspector = inspect(self.engine)
        return table_name in inspector.get_table_names()

    def _table_exists_in_database(self, database_name, table_name):
        """Check if a specific table exists in a specific database."""
        try:
            config = globalvars.config
            conn = mariadb.connect(
                user=config['database_username'],
                password=config['database_password'],
                host=config['database_host'],
                port=int(config['database_port']),
                database=database_name
            )
            cur = conn.cursor()
            cur.execute(f"SHOW TABLES LIKE '{table_name}'")
            result = cur.fetchone()
            conn.close()
            return result is not None
        except Exception as e:
            get_log().debug(f"Error checking table {database_name}.{table_name}: {e}")
            return False

    def disconnect(self):
        if self.engine:
            self.engine.dispose()

    def execute_query(self, query, params = None):
        #with self.lock:
        with self.engine.connect() as connection:
            result = None
            if isinstance(query, (str, TextClause)):  # Check for TextClause along with str
                query = text(query) if isinstance(query, str) else query  # Handle raw SQL string
                try:
                    result = connection.execute(query, params or {}).fetchall()
                except Exception as e:
                    # Log the exception for debugging
                    raise TypeError(f"Query execution failed: {e}")

            elif isinstance(query, Select):
                result = connection.execute(query).fetchall()  # Handle SELECT queries
            elif isinstance(query, (Insert, Update, Delete)):
                result = connection.execute(query)  # Handle INSERT, UPDATE, DELETE
                connection.commit()  # Commit the transaction
                return result.rowcount  # Return the number of rows affected

            if result is not None:
                connection.commit()  # Commit the transaction
                return result
            else:
                raise TypeError("Unsupported query type")

    def insert_data(self, orm_class, data):
        # Access the table object associated with the ORM class
        table = orm_class.__table__
        # Create the insert statement
        ins = table.insert().values(**data)
        # Execute the query
        return self.execute_query(ins)

    def select_data(self, orm_class, where_clause = None):
        select_statement = select(orm_class)
        if where_clause is not None:
            select_statement = select_statement.where(where_clause)
        result = self.execute_query(select_statement)
        # Check if result is a list, if so, return it directly
        if isinstance(result, list):
            return result
        else:
            return result.fetchall()

    def update_data(self, orm_class, where_clause, new_values):
        table = orm_class.__table__
        upd = table.update().where(where_clause).values(**new_values)
        return self.execute_query(upd)

    def remove_data(self, orm_class, where_clause = None):
        delete_statement = delete(orm_class)
        if where_clause is not None:
            delete_statement = delete_statement.where(where_clause)
        return self.execute_query(delete_statement)

    def get_rows_by_date(self, orm_class, date_column, order = 'asc'):
        table = orm_class.__table__
        sel = select([table]).order_by(date_column if order == 'asc' else date_column.desc())
        return self.execute_query(sel)

    def get_next_available_id(self, table, id_column = 'UniqueID'):
        query = text(f"SELECT COALESCE(MAX({id_column}), 0) + 1 FROM {table.name}")
        result = self.execute_query(query)
        next_id = result[0][0]
        return int(next_id)

def get_db_config():
    config = globalvars.config
    return f"mysql+pymysql://{config['database_username']}:{config['database_password']}@{config['database_host']}:{config['database_port']}/{config['database']}"



class MySQLDriver(DatabaseDriver):
    def connect(self):
        super().connect(get_db_config())


def create_database_driver():
    return MySQLDriver()
