import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

conn = psycopg2.connect(user="postgres", host="localhost", port="5433", dbname="postgres")
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()
try:
    cursor.execute("CREATE DATABASE mopt;")
    print("Database 'mopt' created successfully.")
except psycopg2.errors.DuplicateDatabase:
    print("Database 'mopt' already exists.")
finally:
    cursor.close()
    conn.close()
