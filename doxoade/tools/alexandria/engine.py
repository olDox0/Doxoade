# doxoade\tools\alexandria\engine.py
import threading
import queue
import sqlite3

class AlexandriaEngine:
    def __init__(self):
        self.queue = queue.Queue()
        self._thread = None
        self._idle_timeout = 5.0 

    def enqueue(self, query, params):
        self.queue.put((query, params))
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._worker, daemon=True)
            self._thread.start()

    def _init_db_structure(self, cursor):
        """Garante a estrutura exata exigida pelo sistema de telemetria (v134+)."""
        # 1. Cria a tabela com a topologia moderna unificada
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operational_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subsystem TEXT,
                action TEXT,
                data TEXT,
                pid INTEGER,
                level TEXT,
                message TEXT,
                details TEXT
            )
        """)
        
        # 2. Sincroniza retrocompatibilidade se o banco físico já existia com colunas antigas
        colunas_modernas = [
            ("subsystem", "TEXT"),
            ("action", "TEXT"),
            ("data", "TEXT"),
            ("pid", "INTEGER")
        ]
        
        cursor.execute("PRAGMA table_info(operational_logs)")
        colunas_existentes = [info[1] for info in cursor.fetchall()]
        
        for nome_coluna, tipo_coluna in colunas_modernas:
            if nome_coluna not in colunas_existentes:
                try:
                    cursor.execute(f"ALTER TABLE operational_logs ADD COLUMN {nome_coluna} {tipo_coluna}")
                except sqlite3.OperationalError:
                    pass


    def _worker(self):
        from doxoade.tools.core_locator import GLOBAL_DB_FILE, GLOBAL_DATA_DIR
        from doxoade.core_database import DB_FILE, DB_DIR, get_db_connection
        import os
        
        GLOBAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        DB_DIR.mkdir(parents=True, exist_ok=True)
        # Garante a existência física do diretório da base
        os.makedirs(os.path.dirname(str(DB_FILE)), exist_ok=True)
        
        # Invoca a conexão oficial para garantir a Gênese do init_db()
#        conn_oficial = None
        conn_oficial = get_db_connection()
        conn_oficial.close()

        # Conexão paralela do Alexandria
        conn = sqlite3.connect(str(GLOBAL_DB_FILE), timeout=30)
        cursor = conn.cursor()
        
        # 🔴 CORREÇÃO: O Alexandria garante sua própria estrutura antes de trabalhar
        self._init_db_structure(cursor)
        
        try:
            cursor.execute("ALTER TABLE operational_logs ADD COLUMN subsystem TEXT")
            cursor.execute("ALTER TABLE operational_logs ADD COLUMN action TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass # Ignora se já existirem fisicamente

        
        # Força o SQLite a limpar cache de schemas antigos nesta conexão
        cursor.execute("PRAGMA writable_schema = ON;")
        cursor.execute("PRAGMA writable_schema = OFF;")
        
        while True:
            try:
                task = self.queue.get(timeout=self._idle_timeout)
                if task is None: 
                    break
                query, params = task
                
                # Tenta executar a query de log
                try:
                    cursor.execute(query, params)
                    conn.commit()
                except sqlite3.OperationalError as e:
                    # Se mesmo assim ele reclamar que a coluna não existe (bug de cache do SQLite)
                    if "no such column: subsystem" in str(e) or "has no column named subsystem" in str(e):
                        # Força uma reinicialização da conexão para limpar o estado
                        conn.close()
                        conn = sqlite3.connect(str(DB_FILE), timeout=30)
                        cursor = conn.cursor()
                        # Tenta reexecutar uma única vez com a nova conexão limpa
                        cursor.execute(query, params)
                        conn.commit()
                    else:
                        raise e # Repassa se for outro erro operacional
                        
                self.queue.task_done()
            except queue.Empty:
                break
            except Exception as e:
                # Captura qualquer erro residual para nunca travar ou inundar o terminal
                print(f"[-] Erro Alexandria Engine tratado: {e}")
                try:
                    self.queue.task_done()
                except ValueError:
                    pass
        conn.close()

alexandria = AlexandriaEngine()

def alexandria_write(query, params=()):
    alexandria.enqueue(query, params)
