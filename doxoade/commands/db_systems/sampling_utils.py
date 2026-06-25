# doxoade/doxoade/commands/db_systems/sampling_utils.py
import sqlite3
# [DOX-UNUSED] import shutil
import os

class DataSampler:
    def __init__(self, src_path):
        self.src_path = src_path

    def create_gold_sample(self, dest_path, rows_limit=100):
        """Cria um clone do banco mas apenas com as primeiras X linhas de cada tabela."""
        src_conn = sqlite3.connect(self.src_path)
        src_curr = src_conn.cursor()
        
        # Cria banco novo
        if os.path.exists(dest_path): os.remove(dest_path)
        dest_conn = sqlite3.connect(dest_path)
        dest_curr = dest_conn.cursor()

        # Copia Schema
        src_curr.execute("SELECT sql, name FROM sqlite_master WHERE type='table';")
        for schema_sql, table_name in src_curr.fetchall():
            #if table_name == 'sqlite_sequence': continue
            if table_name.startswith('sqlite_'): continue
            dest_curr.execute(schema_sql)
            
            # Copia Dados Limitados
            src_curr.execute(f"SELECT * FROM {table_name} LIMIT {rows_limit}")
            rows = src_curr.fetchall()
            
            if rows:
                placeholders = ",".join(["?"] * len(rows[0]))
                dest_curr.executemany(f"INSERT INTO {table_name} VALUES ({placeholders})", rows)
        
        dest_conn.commit()
        src_conn.close()
        dest_conn.close()