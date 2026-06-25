import sqlite3
from doxoade.core_database import get_db_connection

from doxoade.tools.alexandria.engine import alexandria_write
def executar_escrita():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Padrão 1: cursor.execute
    alexandria_write("INSERT INTO logs (msg) VALUES (?)", ("test",))
    # Padrão 2: conn.execute
    alexandria_write("UPDATE config SET val = 1")
    conn.commit()

def leitura_segura():
    conn = get_db_connection()
    # Padrão 3: conn.execute com select
    data = conn.execute("SELECT * FROM events").fetchall()
    return data
