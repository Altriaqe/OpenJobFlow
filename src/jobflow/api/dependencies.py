from jobflow.db.connection import connect_postgres


def get_connection():
    connection = connect_postgres()
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()
