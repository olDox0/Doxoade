import threading
import queue
import time
import os
import sqlite3
from pathlib import Path

class AlexandriaManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_engine()
        return cls._instance

    def _init_engine(self):
        self.queue = queue.Queue()
        from doxoade.core_database import DB_FILE
        self.lock_file = DB_FILE.parent / "alexandria.lock"
        self.stop_event = threading.Event()
        self.worker = threading.Thread(target=self._consumer, daemon=True)
        self.worker.start()

    def _consumer(self):
        """O único processo autorizado a escrever no banco."""
        from doxoade.core_database import get_db_connection
        while not self.stop_event.is_set():
            try:
                task = self.queue.get(timeout=1.0)
                if task is None: break
                
                query, params = task
                self._execute_with_lock(query, params)
                self.queue.task_done()
            except queue.Empty:
                continue

    def _execute_with_lock(self, query, params):
        """Aplica o file-based lock e executa o SQL."""
        try:
            # Criação do lock file (Opcional: SQLite já gerencia com WAL, 
            # mas este lock adiciona uma camada de formalidade do sistema)
            with open(self.lock_file, "w") as f:
                f.write(str(os.getpid()))
            
            from doxoade.core_database import get_db_connection
            conn = get_db_connection()
            conn.execute(query, params)
            conn.commit()
            conn.close()
        finally:
            if self.lock_file.exists():
                self.lock_file.unlink()

    def enqueue(self, query, params):
        self.queue.put((query, params))

# Interface pública
alexandria = AlexandriaManager()

def alexandria_lock(query, params):
    """Facade para os comandos enviarem escritas ao banco."""
    alexandria.enqueue(query, params)
