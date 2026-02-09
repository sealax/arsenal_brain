import os
import psycopg


def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Put it in your .env and load it before running init_db.")
    return psycopg.connect(url)
