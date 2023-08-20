import psycopg2


# Configuration for your RDS instance
DEFAULT_DB_ENDPOINT = "reshuffle-db.c2ivaryam5yw.eu-central-1.rds.amazonaws.com"
DEFAULT_USER = "postgres"
DEFAULT_PASSWORD = "qeuurdmtwkspfyto"
DEFAULT_DB_NAME = "reshuffle"


class DatabaseConnection:
    def __init__(self, host=DEFAULT_DB_ENDPOINT, user=DEFAULT_USER, password=DEFAULT_PASSWORD, db_name=DEFAULT_DB_NAME):
        self.host = host
        self.user = user
        self.password = password
        self.db_name = db_name
        self.connection = None

    def __enter__(self):
        connection_string = f"dbname={self.db_name} user={self.user} host={self.host} password={self.password}"
        self.connection = psycopg2.connect(connection_string)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()
    
    def get_cursor(self):
        if not self.connection:
            self.__enter__()
        return self.connection.cursor()
    
    def query(self, query):
        if not self.connection:
            raise ValueError("Database connection not established.")
        
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    
    def commit(self, query):
        if not self.connection:
            raise ValueError("Database connection not established.")
        
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            return self.connection.commit()
