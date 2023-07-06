import MySQLdb, logging
import steamemu.logger

from steamemu.config import read_config

config = read_config()
log = logging.getLogger("MysqlDriver")

class MySQLConnector(object):
    def __init__(self):
        self.host = config['mysqlhost']
        self.username = config['mysqlusername']
        self.password = config['mysqlpassword']
        self.database = config['mysqldatabase']
        self.conn = None

    def connect(self):
        self.conn = MySQLdb.connect(
            host=self.host,
            user=self.username,
            passwd=self.password,
            db=self.database,
            charset='utf8'
        )
        self.conn.autocommit(True)

    def disconnect(self):
        if self.conn:
            self.conn.close()

    def execute_query(self, query):
        cursor = self.conn.cursor()
        cursor.execute(query)
        cursor.close()

    def execute_query_with_result(self, query):
        cursor = self.conn.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        return result

    def insert_data(self, table, data):
        columns = ', '.join(data.keys())
        values = ', '.join(['%s'] * len(data))
        query = "INSERT INTO {} ({}) VALUES ({})".format(table, columns, values)
        cursor = self.conn.cursor()
        cursor.execute(query, tuple(data.values()))
        cursor.close()

    def update_data(self, table, data, condition):
        set_values = ', '.join(['{} = %s'.format(column) for column in data.keys()])
        query = "UPDATE {} SET {} WHERE {}".format(table, set_values, condition)
        cursor = self.conn.cursor()
        cursor.execute(query, tuple(data.values()))
        cursor.close()

    def delete_data(self, table, condition):
        query = "DELETE FROM {} WHERE {}".format(table, condition)
        cursor = self.conn.cursor()
        cursor.execute(query)
        cursor.close()

    def select_data(self, table, columns='*', condition=''):
        query = "SELECT {} FROM {} WHERE {}".format(columns, table, condition)
        return self.execute_query_with_result(query)
