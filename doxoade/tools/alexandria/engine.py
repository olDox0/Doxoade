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

    def _worker(self):
        # A Mágica do Lazy Import para não engatilhar loop circular
        from doxoade.core_database import DB_FILE
        
        conn = sqlite3.connect(str(DB_FILE), timeout=30)
        cursor = conn.cursor()
        while True:
            try:
                task = self.queue.get(timeout=self._idle_timeout)
                if task is None: break
                query, params = task
                cursor.execute(query, params)
                conn.commit()
                self.queue.task_done()
            except queue.Empty:
                break
        conn.close()

alexandria = AlexandriaEngine()

def alexandria_write(query, params=()):
    alexandria.enqueue(query, params)
