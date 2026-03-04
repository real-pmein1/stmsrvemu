import logging
from datetime import datetime

import mariadb
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session

import globalvars
from config import get_config

log = logging.getLogger("CMSDB")

config = get_config()


def get_cms_db_config():
    """
    Returns the database connection string for the CMS database.
    If cms_usesamedb is 'true', uses the same server credentials as the main database
    but with the CMS database name.
    If cms_usesamedb is 'false', uses separate CMS database credentials.
    """
    cfg = get_config()

    if cfg.get('cms_usesamedb', '').lower() == 'true':
        # Use same server as main database but different database name
        db_user = cfg['database_username']
        db_pass = cfg['database_password']
        db_host = cfg['database_host']
        db_port = cfg['database_port']
        db_name = cfg['cms_dbname']
    else:
        # Use separate CMS database server
        db_user = cfg['cms_dbusername']
        db_pass = cfg['cms_dbpassword']
        db_host = cfg['cms_dbaddress']
        db_port = cfg['cms_dbport']
        db_name = cfg['cms_dbname']

    return {
        'user': db_user,
        'password': db_pass,
        'host': db_host,
        'port': int(db_port) if db_port else 3306,
        'database': db_name
    }


def get_cms_connection_string():
    """Returns SQLAlchemy connection string for CMS database."""
    cfg = get_cms_db_config()
    return f"mysql+pymysql://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['database']}"


class CMSDatabaseDriver:
    """
    Database driver for the CMS database.
    Can connect to either the same MariaDB server as the main database (with different db name)
    or a completely separate database server based on configuration.
    """
    _session_factory = None
    _engine = None

    def __init__(self):
        self.config = get_config()
        if CMSDatabaseDriver._engine is None:
            self.connect()

    def connect(self):
        """Establish connection to the CMS database."""
        try:
            connection_string = get_cms_connection_string()
            CMSDatabaseDriver._engine = create_engine(
                connection_string,
                pool_size=10,
                max_overflow=5,
                pool_timeout=5,
                pool_recycle=1300
            )
            CMSDatabaseDriver._session_factory = sessionmaker(bind=CMSDatabaseDriver._engine)
            log.info("Connected to CMS database successfully.")
        except Exception as e:
            log.error(f"Failed to connect to CMS database: {e}")
            raise

    @classmethod
    def get_session(cls):
        """Get a scoped session for the CMS database."""
        if cls._session_factory is None:
            raise Exception("CMS database connection not initialized.")
        return scoped_session(cls._session_factory)

    def get_mariadb_connection(self):
        """Get a direct mariadb connection for raw SQL operations."""
        cfg = get_cms_db_config()
        try:
            conn = mariadb.connect(
                user=cfg['user'],
                password=cfg['password'],
                host=cfg['host'],
                port=cfg['port'],
                database=cfg['database']
            )
            return conn
        except mariadb.Error as e:
            log.error(f"Error connecting to CMS MariaDB: {e}")
            raise

    def execute_query(self, query, params=None):
        """Execute a raw SQL query on the CMS database."""
        with CMSDatabaseDriver._engine.connect() as connection:
            if isinstance(query, str):
                query = text(query)
            result = connection.execute(query, params or {})
            connection.commit()
            return result


def get_theme_for_date(cddb_date):
    """
    Determines the appropriate theme based on the CDDB date.

    Args:
        cddb_date: datetime object representing the current CDDB date

    Returns:
        str: The theme name to use
    """
    # Define date ranges and their corresponding themes
    theme_ranges = [
        (datetime(2001, 1, 1), datetime(2002, 3, 15, 23, 59, 59), "2002_v1"),
        (datetime(2002, 3, 16), datetime(2002, 12, 31, 23, 59, 59), "2002_v2"),
        (datetime(2003, 1, 1), datetime(2003, 6, 28, 23, 59, 59), "2003_v1"),
        (datetime(2003, 6, 29), datetime(2004, 3, 25, 23, 59, 59), "2003_v2"),
        (datetime(2004, 3, 26), datetime(2004, 10, 20, 23, 59, 59), "2004"),
        (datetime(2004, 10, 21), datetime(2005, 3, 23, 23, 59, 59), "2005_v1"),
        (datetime(2005, 3, 24), datetime(2006, 1, 10, 23, 59, 59), "2005_v2"),
        (datetime(2006, 1, 11), datetime(2006, 9, 15, 23, 59, 59), "2006_v1"),
        (datetime(2006, 9, 16), datetime(2006, 12, 15, 23, 59, 59), "2006_v2"),
        (datetime(2006, 12, 16), datetime(2007, 3, 23, 23, 59, 59), "2007_v1"),
        (datetime(2007, 3, 24), datetime(2008, 3, 9, 23, 59, 59), "2007_v2"),
        (datetime(2008, 3, 10), datetime(2009, 11, 30, 23, 59, 59), "2008"),
        (datetime(2009, 12, 1), datetime(2010, 4, 26, 23, 59, 59), "2009"),
        (datetime(2010, 4, 27), datetime(2010, 7, 27, 23, 59, 59), "2010"),
        (datetime(2010, 7, 28), datetime(2012, 8, 14, 23, 59, 59), "2011"),
        (datetime(2012, 8, 15), datetime(2014, 9, 22, 23, 59, 59), "2012"),
    ]

    for start_date, end_date, theme in theme_ranges:
        if start_date <= cddb_date <= end_date:
            return theme

    # Default to latest theme if date is beyond defined ranges
    if cddb_date > datetime(2014, 9, 22):
        return "2012"

    # Default to earliest theme if date is before defined ranges
    return "2002_v1"


def update_cms_theme():
    """
    Updates the 'theme' and 'CDRDATE' settings in the CMS database settings table
    based on the current globalvars.CDDB_datetime value.

    The settings table has two columns: 'key' and 'value'.
    This function updates/inserts:
    - 'theme': The appropriate theme based on the date
    - 'CDRDATE': The date in '%m/%d/%Y' format (no time)
    """
    cfg = get_config()

    # Check if CMS is enabled
    if cfg.get('use_cms', '').lower() != 'true':
        log.debug("CMS is not enabled, skipping theme update.")
        return False

    # Check if CMS database is configured
    if not cfg.get('cms_dbname'):
        log.debug("CMS database name not configured, skipping theme update.")
        return False

    # Get the CDDB datetime
    if globalvars.CDDB_datetime is None:
        log.warning("CDDB_datetime is not set, cannot determine theme.")
        return False

    try:
        # Parse the CDDB datetime
        cddb_date = datetime.strptime(globalvars.CDDB_datetime, "%m/%d/%Y %H:%M:%S")

        # Determine the appropriate theme
        theme = get_theme_for_date(cddb_date)

        # Format the date for CDRDATE (no time, just date)
        cdr_date_str = cddb_date.strftime("%m/%d/%Y")

        # Get database connection configuration
        db_cfg = get_cms_db_config()

        # Connect and update the theme
        conn = mariadb.connect(
            user=db_cfg['user'],
            password=db_cfg['password'],
            host=db_cfg['host'],
            port=db_cfg['port'],
            database=db_cfg['database']
        )

        try:
            cur = conn.cursor()

            # Update the theme value in the settings table
            cur.execute(
                "UPDATE settings SET value = %s WHERE `key` = 'theme'",
                (theme,)
            )

            # If no row was updated, insert a new one
            if cur.rowcount == 0:
                cur.execute(
                    "INSERT INTO settings (`key`, value) VALUES ('theme', %s)",
                    (theme,)
                )

            # Update or insert the CDRDATE value in the settings table
            cur.execute(
                "UPDATE settings SET value = %s WHERE `key` = 'CDRDATE'",
                (cdr_date_str,)
            )

            # If no row was updated, insert a new one
            if cur.rowcount == 0:
                cur.execute(
                    "INSERT INTO settings (`key`, value) VALUES ('CDRDATE', %s)",
                    (cdr_date_str,)
                )

            conn.commit()
            log.info(f"CMS theme updated to '{theme}' and CDRDATE set to '{cdr_date_str}'")
            return True

        finally:
            conn.close()

    except mariadb.Error as e:
        log.error(f"Database error while updating CMS theme: {e}")
        return False
    except ValueError as e:
        log.error(f"Error parsing CDDB_datetime '{globalvars.CDDB_datetime}': {e}")
        return False
    except Exception as e:
        log.error(f"Unexpected error updating CMS theme: {e}")
        return False


def create_cms_database_driver():
    """Factory function to create a CMS database driver instance."""
    return CMSDatabaseDriver()
