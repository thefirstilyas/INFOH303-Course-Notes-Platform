import os
import getpass
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# Points attribués par action — centralisés pour rester cohérents
# entre le script de chargement (load_data.py) et l'app Flask (web/app.py)
POINTS_PUBLICATION = 10
POINTS_EVALUATION  = 5

# connexion via socket Unix par défaut (auth peer, sans mot de passe)
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "/var/run/postgresql"),
    "dbname":   os.getenv("DB_NAME",     "infoh303"),
    "user":     os.getenv("DB_USER",     getpass.getuser()),
    "password": os.getenv("DB_PASSWORD", ""),
    "port":     os.getenv("DB_PORT",     "5432"),
}


def set_config(**kwargs):
    DB_CONFIG.update(kwargs)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def execute(query, params=None, fetch=None):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "all":
                    return cur.fetchall()
                return None
    finally:
        conn.close()


def execute_in(conn, query, params=None, fetch=None):
    # à utiliser à l'intérieur d'un bloc transaction(), pas seul
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall()
        return None


@contextmanager
def transaction():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
