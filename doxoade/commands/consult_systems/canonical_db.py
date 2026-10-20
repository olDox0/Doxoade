# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/canonical_db.py
"""
Hades Canonical Database Engine (Passo 2).
Tabela relacional B-Tree para leitura imediata (0.1ms) + FTS5 para busca textual.
"""
from __future__ import annotations
import os
import sys
import json
import sqlite3
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


class CanonicalDB:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (Path.home() / ".doxoade" / "consult_docs_fts5.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self, bulk: bool = False) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA cache_size = -64000;")
        if bulk:
            conn.execute("PRAGMA synchronous = OFF;")
        else:
            conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def init_schema(self):
        """Cria ou migra as tabelas relacional e virtual FTS5."""
        conn = self.get_connection(bulk=False)
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.cursor()

            # 1. Migração automática da tabela relacional 'docs' se estiver no schema antigo
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='docs';")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(docs);")
                cols = [r[1] for r in cursor.fetchall()]
                if "path" not in cols:
                    conn.execute("DROP TABLE docs;")

            # 2. Tabela relacional B-Tree Canônica (busca direta por 'path' em 0.1ms)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS docs (
                    path TEXT PRIMARY KEY,
                    category TEXT,
                    title TEXT,
                    keywords TEXT,
                    content TEXT
                );
            """)

            # 3. Migração automática do FTS5 se for o schema antigo da Fase 1
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='docs_fts';")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(docs_fts);")
                cols = [r[1] for r in cursor.fetchall()]
                if "keywords" not in cols or "path" not in cols:
                    conn.execute("DROP TABLE docs_fts;")

            # 4. Tabela FTS5 Canônica
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                    path UNINDEXED,
                    title,
                    keywords,
                    content,
                    tokenize='porter unicode61'
                );
            """)

            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def ingest_jsonl(self, jsonl_path: Path, category_filter: Optional[str] = None, limit: int = 0) -> int:
        """Ingere um dataset canônico com substituição limpa (idempotente)."""
        self.init_schema()
        conn = self.get_connection(bulk=True)
        cursor = conn.cursor()

        records: List[Dict[str, Any]] = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            count = 0
            for line in f:
                if limit and count >= limit:
                    break
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        continue

        if not records:
            conn.close()
            return 0

        target_category = category_filter or records[0].get("category", "")

        try:
            conn.execute("BEGIN IMMEDIATE;")

            # Limpa partições antigas da mesma categoria
            if target_category:
                cursor.execute("DELETE FROM docs_fts WHERE path IN (SELECT path FROM docs WHERE category = ?);", (target_category,))
                cursor.execute("DELETE FROM docs WHERE category = ?;", (target_category,))

            batch_docs = []
            batch_fts = []
            for r in records:
                path = r.get("path") or r.get("uid", "")
                cat = r.get("category", "")
                title = r.get("title", "")
                kw = r.get("keywords", "")
                content = r.get("content", "")

                batch_docs.append((path, cat, title, kw, content))
                batch_fts.append((path, title, kw, content))

            cursor.executemany("INSERT OR REPLACE INTO docs (path, category, title, keywords, content) VALUES (?, ?, ?, ?, ?);", batch_docs)
            cursor.executemany("INSERT INTO docs_fts (path, title, keywords, content) VALUES (?, ?, ?, ?);", batch_fts)

            conn.execute("COMMIT;")

            # Otimização FTS5
            conn.execute("INSERT INTO docs_fts(docs_fts) VALUES('optimize');")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

        return len(records)

    def get_document(self, path_or_uid: str) -> Optional[Dict[str, Any]]:
        """Leitura direta por B-Tree (execução em ~0.1ms)."""
        if not self.db_path.exists():
            return None
        conn = self.get_connection(bulk=False)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT path, category, title, keywords, content FROM docs WHERE path = ? LIMIT 1;", (path_or_uid,))
            row = cursor.fetchone()
            if row:
                return {
                    "path": row[0],
                    "uid": row[0],
                    "category": row[1],
                    "title": row[2],
                    "keywords": row[3],
                    "content": row[4]
                }
            return None
        finally:
            conn.close()

    def search(self, query: str, limit: int = 25) -> List[Tuple[str, str, str]]:
        """Busca textual no FTS5 tolerante a prefixos."""
        if not self.db_path.exists():
            return []

        clean_q = re.sub(r'[^\w\s]', ' ', query).strip()
        if not clean_q:
            return []

        tokens = clean_q.split()
        fts_query = " OR ".join([f'"{tok}"*' for tok in tokens])

        conn = self.get_connection(bulk=False)
        cursor = conn.cursor()

        sql = """
            SELECT 
                path,
                title,
                snippet(docs_fts, 3, '\x02', '\x03', '...', 18) as snippet
            FROM docs_fts
            WHERE docs_fts MATCH ?
            ORDER BY rank
            LIMIT ?;
        """
        try:
            cursor.execute(sql, (fts_query, limit))
            return cursor.fetchall()
        except sqlite3.OperationalError:
            try:
                cursor.execute(sql, (f'"{clean_q}"', limit))
                return cursor.fetchall()
            except Exception:
                return []
        finally:
            conn.close()


def run_ingest():
    canonical_file = Path.home() / ".doxoade" / "consult" / "canonical" / "python_cheatsheet.jsonl"
    if not canonical_file.exists():
        print(f"❌ Arquivo canônico não encontrado: {canonical_file}")
        sys.exit(1)

    print("[*] Ingerindo dataset canônico no Hades...")
    db = CanonicalDB()
    count = db.ingest_jsonl(canonical_file)
    print(f"✔ Sucesso: {count} registros indexados no banco relacional + FTS5!")


if __name__ == "__main__":
    run_ingest()
