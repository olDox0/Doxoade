# doxoade/indexer/cache.py
"""
Cache Persistente para Índices de Código.

Responsabilidades:
- Salvar/carregar índice do disco (SQLite)
- Detectar mudanças nos arquivos via hash
- Invalidar cache quando necessário

Filosofia MPoT:
- Funções < 60 linhas
- Assertions em pontos críticos
- Fail loudly
"""

import sqlite3
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime


class IndexCache:
    """
    Cache persistente do índice usando SQLite.
    
    Exemplo:
        cache = IndexCache(Path.home() / '.doxoade' / 'cache')
        if cache.is_valid(files):
            index = cache.load()
        else:
            # Re-indexa
            cache.save(indexer, files)
    """
    
    def __init__(self, cache_dir: Path):
        """Inicializa o cache."""
        assert cache_dir, "cache_dir não pode estar vazio"
        
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / 'search_index.db'
        self._init_db()
    
    def _init_db(self) -> None:
        """Cria tabelas se não existirem."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Metadados de arquivos (checksums)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_metadata (
                file_path TEXT PRIMARY KEY,
                checksum TEXT NOT NULL,
                indexed_at TEXT NOT NULL
            )
        """)
        
        # Funções indexadas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS functions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                docstring TEXT
            )
        """)
        
        # Comentários
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                text TEXT NOT NULL
            )
        """)
        
        # Call graph
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                caller TEXT NOT NULL,
                callee TEXT NOT NULL,
                PRIMARY KEY (caller, callee)
            )
        """)
        
        # Índices para performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_func_name ON functions(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee)")
        
        conn.commit()
        conn.close()
    
    def is_valid(self, files: List[Path]) -> bool:
        """
        Verifica se o cache ainda é válido.
        
        Args:
            files: Lista de arquivos a verificar
        
        Returns:
            True se nenhum arquivo mudou desde última indexação
        """
        assert files, "Lista de arquivos não pode estar vazia"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for file_path in files:
                current_checksum = self._calculate_checksum(file_path)
                
                cursor.execute(
                    "SELECT checksum FROM file_metadata WHERE file_path = ?",
                    (str(file_path),)
                )
                row = cursor.fetchone()
                
                # Se arquivo não está no cache ou checksum mudou
                if not row or row[0] != current_checksum:
                    return False
            
            return True
        finally:
            conn.close()
    
    def save(self, indexer, files: List[Path]) -> None:
        """
        Salva o índice no cache.
        
        Args:
            indexer: CodeIndexer com dados
            files: Lista de arquivos indexados
        """
        assert indexer, "Indexer não pode ser None"
        assert files, "Lista de arquivos não pode estar vazia"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Limpa cache anterior
            cursor.execute("DELETE FROM file_metadata")
            cursor.execute("DELETE FROM functions")
            cursor.execute("DELETE FROM comments")
            cursor.execute("DELETE FROM calls")
            
            # Salva metadados
            now = datetime.now().isoformat()
            for file_path in files:
                checksum = self._calculate_checksum(file_path)
                cursor.execute(
                    "INSERT INTO file_metadata VALUES (?, ?, ?)",
                    (str(file_path), checksum, now)
                )
            
            # Salva índice
            self._save_functions(cursor, indexer.index['functions'])
            self._save_comments(cursor, indexer.index['comments'])
            self._save_calls(cursor, indexer.index['calls'])
            
            conn.commit()
        finally:
            conn.close()
    
    def load(self) -> Optional[Dict]:
        """
        Carrega índice do cache.
        
        Returns:
            Dicionário com índice ou None se vazio
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Verifica se há dados
            cursor.execute("SELECT COUNT(*) FROM functions")
            if cursor.fetchone()[0] == 0:
                return None
            
            index = {
                'functions': defaultdict(list),
                'comments': {},
                'calls': defaultdict(set),
                'docstrings': {}
            }
            
            self._load_functions(cursor, index)
            self._load_comments(cursor, index)
            self._load_calls(cursor, index)
            
            return index
        finally:
            conn.close()
    
    def _save_functions(self, cursor, functions: Dict) -> None:
        """Salva funções no cache."""
        for func_name, locations in functions.items():
            for loc in locations:
                cursor.execute(
                    "INSERT INTO functions (name, file_path, line_number, docstring) VALUES (?, ?, ?, ?)",
                    (func_name, loc['file'], loc['line'], loc['docstring'])
                )
    
    def _save_comments(self, cursor, comments: Dict) -> None:
        """Salva comentários no cache."""
        for file_path, comment_list in comments.items():
            for line_num, text in comment_list:
                cursor.execute(
                    "INSERT INTO comments (file_path, line_number, text) VALUES (?, ?, ?)",
                    (file_path, line_num, text)
                )
    
    def _save_calls(self, cursor, calls: Dict) -> None:
        """Salva call graph no cache."""
        for callee, callers in calls.items():
            for caller in callers:
                cursor.execute(
                    "INSERT INTO calls (caller, callee) VALUES (?, ?)",
                    (caller, callee)
                )
    
    def _load_functions(self, cursor, index: Dict) -> None:
        """Carrega funções do cache."""
        cursor.execute("SELECT name, file_path, line_number, docstring FROM functions")
        for name, file_path, line_num, docstring in cursor.fetchall():
            index['functions'][name].append({
                'file': file_path,
                'line': line_num,
                'name': name,
                'docstring': docstring
            })
            if docstring:
                index['docstrings'][name] = docstring
    
    def _load_comments(self, cursor, index: Dict) -> None:
        """Carrega comentários do cache."""
        cursor.execute("SELECT file_path, line_number, text FROM comments")
        for file_path, line_num, text in cursor.fetchall():
            if file_path not in index['comments']:
                index['comments'][file_path] = []
            index['comments'][file_path].append((line_num, text))
    
    def _load_calls(self, cursor, index: Dict) -> None:
        """Carrega call graph do cache."""
        cursor.execute("SELECT caller, callee FROM calls")
        for caller, callee in cursor.fetchall():
            index['calls'][callee].add(caller)
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calcula SHA256 de um arquivo."""
        assert file_path.exists(), f"Arquivo não existe: {file_path}"
        
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()