import os
import sys
import threading
import logging
import subprocess
import mariadb
import time
import os
import zipfile
from datetime import datetime, timedelta
from sqlalchemy import TextClause, create_engine, delete, inspect, select, text
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from sqlalchemy.sql import Delete, Insert, Select, Update
from sqlalchemy_utils import create_database, database_exists
from sqlalchemy.exc import SQLAlchemyError, IntegrityError  # Make sure to import this at the top

import globalvars
from .base_dbdriver import Base, ExecutedSQLFile

log = logging.getLogger("SQLEngine")

# from tqdm import tqdm
sql_execution_done_flag = False

class DatabaseDriver():
    _session_factory = None

    def __init__(self):
        super().__init__()
        self.engine = None
        self.lock = threading.Lock()
        self.current_connection = None
        self.metadata = Base.metadata
        if DatabaseDriver._session_factory is None:
            self.connect()

        self.config = globalvars.config

    def connect(self, connection_string):
        connection_string = get_db_config()

        if globalvars.config['use_builtin_mysql'].lower() == "true":
            if globalvars.mariadb_initialized:
                self.real_connect(connection_string)
                return
            start_time = datetime.now()
            # Wait for the specific readiness line
            while True:
                elapsed_time = (datetime.now() - start_time).total_seconds()
                if elapsed_time > 60:
                    log.error("MariaDB initialization is taking too long. Please consult your logs/mariadb_error.log for details and contact support in the Discord channel.")
                    break

                try:
                    with open('logs/mariadb_error.log', 'r') as log_file:
                        lines = log_file.readlines()
                        last_lines = lines[-10:]  # Get the last 10 lines of the log
                        mariadb_port = globalvars.config['database_port']

                        # Check for the readiness message in the last 5 lines
                        for line in last_lines:
                            if f"Version: '11.4.2-MariaDB-log'  socket: ''  port: {mariadb_port}  mariadb.org binary distribution" in line:
                                globalvars.mariadb_initialized = True
                                log.info("MariaDB server is ready.")
                                self.real_connect(connection_string)
                                return
                except Exception as log_error:
                    log.error(f"Error while reading the log file: {log_error}")
                time.sleep(3)

        else:
            globalvars.mariadb_initialized = True
            self.real_connect(connection_string)

    def real_connect(self, connection_string):
        self.engine = create_engine(connection_string,
                                    pool_size = 65,
                                    max_overflow = 55,
                                    pool_timeout = 5,
                                    pool_recycle = 1300
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
                log.debug(f"File {filename} has already been executed. Skipping.")
                return

        log.info(f"Executing {sql_file}.")
        try:
            if sql_file == "files/sql/ContentDescriptionDB.sql" or sql_file == "files/sql/ClientConfigurationDB.sql":

                if sql_file == "files/sql/ClientConfigurationDB.sql":
                    database_schema = "ClientConfigurationDB"
                else:
                    database_schema = "ContentDescriptionDB"

                config = globalvars.config
                with Session(self.engine) as session:
                    # Check if file has already been processed
                    filename = os.path.basename(sql_file)
                    existing_file = session.query(ExecutedSQLFile).filter_by(filename = filename).first()
                    if existing_file:
                        log.debug(f"File {filename} has already been executed. Skipping.")
                        return
                    if os.path.isfile("files/mdb/bin/mariadb.exe"):
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

                        # these need to be \\, not /, else import fails
                        import_cddb = subprocess.Popen(f"files\\mdb\\bin\\mariadb.exe -u {config['database_username']} -p{config['database_password']} -h {config['database_host']} -P {config['database_port']} --skip-ssl {database_schema} < files\\sql\\{database_schema}.sql", shell=True)
                        import_cddb.wait()

                        log.debug(f"Successfully executed statement.")

                        log.info(f"Finished executing {sql_file}.")
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
                            log.debug(f"Successfully executed statement.")
                        except SQLAlchemyError as e:
                            log.error(f"Error executing statement starting with: {statement[:100]}...\nError: {e}")
                            break  # Stop on error to help narrow down issues

                else:
                    log.info(f"Finished executing {sql_file}.")

                # Record the executed file
                with Session(self.engine) as session:
                    executed_file = ExecutedSQLFile(filename = filename)
                    session.add(executed_file)
                    session.commit()

        except Exception as e:
            log.error(f"Error processing {sql_file}: {e}")
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

    def disconnect(self):
        if self.current_connection:
            self.current_connection.close()
            self.current_connection = None
        if self.engine:
            self.engine.dispose()

    def get_current_connection(self):
       # with self.lock:
        if self.current_connection is None or self.current_connection.closed:
            self.current_connection = self.engine.connect()
        return self.current_connection

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