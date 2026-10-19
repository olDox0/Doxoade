# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/doc_indexer.py
"""
DocIndexer v3.0 — Orquestrador Soberano de Indexação FTS5 & B-Tree (Thoth & Hades Engine).
Unifica a documentação HTML do CPython e os Datasets Canônicos em um único banco relacional + FTS5.
"""
from __future__ import annotations
import os
import sys
import json
import sqlite3
import re
import html as html_lib
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

RE_STRIP_BLOCKS = re.compile(
    r'<(?:script|style|nav|header|footer|svg)[^>]*>.*?</(?:script|style|nav|header|footer|svg)>',
    flags=re.DOTALL | re.IGNORECASE
)
RE_TAGS = re.compile(r'<[^>]+>')
RE_TITLE = re.compile(r'<title>(.*?)</title>', flags=re.DOTALL | re.IGNORECASE)
RE_SPACES = re.compile(r'\s+')
RE_CODE_BLOCK = re.compile(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', flags=re.DOTALL | re.IGNORECASE)
RE_PRE_BLOCK = re.compile(r'<pre[^>]*>(.*?)</pre>', flags=re.DOTALL | re.IGNORECASE)
RE_INLINE_CODE = re.compile(r'<code[^>]*>(.*?)</code>', flags=re.DOTALL | re.IGNORECASE)
RE_H1 = re.compile(r'<h1[^>]*>(.*?)</h1>', flags=re.DOTALL | re.IGNORECASE)
RE_H2 = re.compile(r'<h2[^>]*>(.*?)</h2>', flags=re.DOTALL | re.IGNORECASE)
RE_H3 = re.compile(r'<h3[^>]*>(.*?)</h3>', flags=re.DOTALL | re.IGNORECASE)
RE_P = re.compile(r'<p[^>]*>(.*?)</p>', flags=re.DOTALL | re.IGNORECASE)
RE_LI = re.compile(r'<li[^>]*>(.*?)</li>', flags=re.DOTALL | re.IGNORECASE)


class DocIndexer:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (Path.home() / ".doxoade" / "consult_docs_fts5.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.console = Console()

    def _get_db_connection(self, bulk_mode: bool = False) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=60.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA cache_size = -64000;")
        if bulk_mode:
            conn.execute("PRAGMA synchronous = OFF;")
        else:
            conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def init_db(self, drop_existing: bool = False):
        """Cria ou migra a arquitetura de duas camadas: docs (B-Tree) + docs_fts (FTS5)."""
        conn = self._get_db_connection(bulk_mode=False)
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.cursor()

            if drop_existing:
                conn.execute("DROP TABLE IF EXISTS docs_fts;")
                conn.execute("DROP TABLE IF EXISTS docs;")
                conn.execute("DROP TABLE IF EXISTS doc_metadata;")
            else:
                # Migração automática se tabelas antigas estiverem sem colunas canônicas
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='docs';")
                if cursor.fetchone():
                    cursor.execute("PRAGMA table_info(docs);")
                    cols = [r[1] for r in cursor.fetchall()]
                    if "path" not in cols or "content" not in cols:
                        conn.execute("DROP TABLE docs;")

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='docs_fts';")
                if cursor.fetchone():
                    cursor.execute("PRAGMA table_info(docs_fts);")
                    cols = [r[1] for r in cursor.fetchall()]
                    if "keywords" not in cols or "path" not in cols:
                        conn.execute("DROP TABLE docs_fts;")

            # 1. Tabela relacional permanente (chave primária 'path')
            conn.execute("""
                CREATE TABLE IF NOT EXISTS docs (
                    path TEXT PRIMARY KEY,
                    category TEXT,
                    title TEXT,
                    keywords TEXT,
                    content TEXT
                );
            """)

            # 2. Tabela virtual FTS5 com tokenizador porter unicode61
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                    path UNINDEXED,
                    title,
                    keywords,
                    content,
                    tokenize='porter unicode61'
                );
            """)

            # 3. Metadados de mtime dos arquivos HTML
            conn.execute("""
                CREATE TABLE IF NOT EXISTS doc_metadata (
                    path TEXT PRIMARY KEY,
                    last_modified REAL
                );
            """)

            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def find_python_docs(self) -> Optional[Path]:
        """Localiza o diretório oficial de documentação HTML do Python."""
        candidates = []
        py_prefix = Path(sys.base_prefix)
        candidates.append(py_prefix / "Doc" / "html")
        candidates.append(py_prefix / "share" / "doc" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "html")

        if os.name == 'nt':
            local_app = os.environ.get("LOCALAPPDATA", "")
            if local_app:
                candidates.append(
                    Path(local_app) / "Programs" / "Python" / f"Python{sys.version_info.major}{sys.version_info.minor}" / "Doc" / "html"
                )

        for c in candidates:
            if c.exists() and (c / "index.html").exists():
                return c
        return next((c for c in candidates if c.exists()), None)

    def extract_text_from_html(self, file_path: Path) -> Tuple[str, str, str]:
        raw_html = file_path.read_text(encoding="utf-8", errors="ignore")
        m_title = RE_TITLE.search(raw_html)
        title = html_lib.unescape(m_title.group(1).strip()) if m_title else file_path.stem
        clean = RE_STRIP_BLOCKS.sub(' ', raw_html)
        clean = RE_TAGS.sub(' ', clean)
        clean = html_lib.unescape(clean)
        clean = RE_SPACES.sub(' ', clean).strip()

        # Extrai palavras-chave do nome do arquivo e título
        stem = file_path.stem.lower()
        title_words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', title.lower())
        keywords = f"{stem} {' '.join(title_words[:10])}"

        return title, clean, keywords

    def html_to_markdown(self, raw_html: str, title_fallback: str = "Doc") -> str:
        m_title = RE_TITLE.search(raw_html)
        title = html_lib.unescape(m_title.group(1).strip()) if m_title else title_fallback

        body = self._isolate_sphinx_body(raw_html)
        text = RE_STRIP_BLOCKS.sub(' ', body)

        code_placeholders = {}
        def _save_code(m):
            token = f"@@CODEBLOCK_{len(code_placeholders)}@@"
            code_placeholders[token] = html_lib.unescape(m.group(1).strip())
            return f"\n\n{token}\n\n"

        text = RE_CODE_BLOCK.sub(_save_code, text)
        text = RE_PRE_BLOCK.sub(_save_code, text)
        text = RE_INLINE_CODE.sub(lambda m: f"`{html_lib.unescape(m.group(1).strip())}`", text)

        text = RE_H1.sub(lambda m: f"\n\n# {html_lib.unescape(m.group(1).strip())}\n\n", text)
        text = RE_H2.sub(lambda m: f"\n\n## {html_lib.unescape(m.group(1).strip())}\n\n", text)
        text = RE_H3.sub(lambda m: f"\n\n### {html_lib.unescape(m.group(1).strip())}\n\n", text)
        text = RE_LI.sub(lambda m: f"\n* {html_lib.unescape(m.group(1).strip())}", text)
        text = RE_P.sub(lambda m: f"\n\n{html_lib.unescape(m.group(1).strip())}\n\n", text)

        text = RE_TAGS.sub(' ', text)
        text = html_lib.unescape(text)

        for token, raw_code in code_placeholders.items():
            clean_code = RE_TAGS.sub('', raw_code)
            clean_code = html_lib.unescape(clean_code)
            text = text.replace(token, f"```python\n{clean_code}\n```")

        lines = [line.rstrip() for line in text.splitlines()]
        clean_text = "\n".join(lines)
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()
        return f"# 📖 {title}\n\n{clean_text}"

    def _isolate_sphinx_body(self, raw_html: str) -> str:
        """
        🛡️ [RIT-002 FIX v2] Isolamento por marcadores posicionais.
        Nota técnica (§5.1): regex lazy `(.*?)</div>` ceifa o body no primeiro
        div aninhado do Sphinx (highlight/section/admonition). Aqui nenhuma tag
        de fechamento é casada: o corte usa marcadores que só existem APÓS o body.
        """
        start_m = re.search(r'<div[^>]*role="main"[^>]*>', raw_html, re.IGNORECASE)
        if not start_m:
            start_m = re.search(r'<div[^>]*class="body"[^>]*>', raw_html, re.IGNORECASE)
        if not start_m:
            return raw_html
        body = raw_html[start_m.end():]

        low = body.lower()
        cuts = [low.find(m) for m in (
            '<div class="clearer"',
            '<div class="sphinxsidebar"',
            '<div role="navigation"',
            '<div class="footer"',
            '<footer',
        )]
        cuts = [i for i in cuts if i > 0]
        return body[:min(cuts)] if cuts else body

    def search(self, query: str, limit: int = 25) -> List[Tuple[str, str, str]]:
        """Busca textual no FTS5 com prefixos coringa (*)."""
        if not self.db_path.exists():
            return []

        clean_q = re.sub(r'[^\w\s]', ' ', query).strip()
        if not clean_q:
            return []

        tokens = clean_q.split()
        fts_query = " OR ".join([f'"{tok}"*' for tok in tokens])

        conn = self._get_db_connection(bulk_mode=False)
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

    def read_doc_as_markdown(self, path_or_query: str) -> Optional[str]:
        """
        Leitor Universal Inteligente:
        1. Busca exata por chave primária (0.1ms).
        2. Busca flexível por aproximação de path ou título (ex: 'json' acha 'python/cheatsheet/json').
        3. Fallback de arquivo HTML físico no disco.
        """
        clean_path = path_or_query.strip().strip("'\"")

        if self.db_path.exists():
            try:
                conn = self._get_db_connection(bulk_mode=False)
                # 1. Busca exata
                row = conn.execute(
                    "SELECT title, content FROM docs WHERE path = ? LIMIT 1;", (clean_path,)
                ).fetchone()

                # 2. Busca flexível se o usuário digitou apenas 'json' ou 'dataclass'
                if not row:
                    row = conn.execute(
                        "SELECT title, content FROM docs WHERE path LIKE ? OR title LIKE ? LIMIT 1;",
                        (f"%{clean_path}%", f"%{clean_path}%")
                    ).fetchone()

                conn.close()
                if row and row[1]:
                    title, content = row
                    if content.strip().startswith("#"):
                        return content
                    return f"# 📖 {title}\n\n{content}\n"
            except Exception:
                pass

        # Fallback de arquivo HTML no disco
        docs_dir = self.find_python_docs()
        target = Path(clean_path)
        if not target.is_absolute() and docs_dir:
            target = docs_dir / clean_path

        if target.exists() and target.is_file():
            raw_html = target.read_text(encoding="utf-8", errors="ignore")
            return self.html_to_markdown(raw_html, title_fallback=target.stem)

        return None

    def build_index(self, force: bool = False):
        """Indexação Unificada: CPython HTMLs + Datasets Canônicos em uma só passada."""
        self.console.print(f"[bold cyan]🗃️ [HADES] Inicializando Motor de Indexação Unificado...[/bold cyan]")
        self.init_db(drop_existing=force)

        # ── PARTIÇÃO 1: HTML DOCS CPYTHON ──
        docs_dir = self.find_python_docs()
        html_indexed = 0
        if docs_dir and docs_dir.exists():
            self.console.print(f"  [green]✔ Docs oficiais CPython localizados:[/green] [cyan]{docs_dir}[/cyan]")
            all_html = list(docs_dir.rglob("*.html"))

            conn = self._get_db_connection(bulk_mode=False)
            cursor = conn.cursor()
            cursor.execute("SELECT path, last_modified FROM doc_metadata;")
            existing_meta = dict(cursor.fetchall()) if not force else {}
            conn.close()

            pending_files: List[Tuple[Path, str, float]] = []
            for hf in all_html:
                rel = str(hf.relative_to(docs_dir)).replace("\\", "/")
                try:
                    mtime = hf.stat().st_mtime
                    if not force and rel in existing_meta and existing_meta[rel] == mtime:
                        continue
                    pending_files.append((hf, rel, mtime))
                except OSError:
                    continue

            if pending_files:
                self.console.print(f"  📚 Indexando [bold]{len(pending_files)}[/bold] arquivos HTML CPython...")
                db_conn = self._get_db_connection(bulk_mode=True)
                try:
                    batch_docs = []
                    batch_fts = []
                    batch_meta = []
                    batch_size = 100

                    with Progress(
                        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                        BarColumn(), TaskProgressColumn(), console=self.console
                    ) as progress:
                        task = progress.add_task("CPython HTMLs...", total=len(pending_files))

                        for fp, rel_path, mtime in pending_files:
                            title, text, kw = self.extract_text_from_html(fp)
                            raw_html = fp.read_text(encoding="utf-8", errors="ignore")
                            md_content = self.html_to_markdown(raw_html, title_fallback=title)

                            batch_docs.append((rel_path, "cpython_stdlib", title, kw, md_content))
                            batch_fts.append((rel_path, title, kw, text))
                            batch_meta.append((rel_path, mtime))

                            if len(batch_docs) >= batch_size:
                                self._commit_batch(db_conn, batch_docs, batch_fts, batch_meta)
                                html_indexed += len(batch_docs)
                                progress.update(task, advance=len(batch_docs))
                                batch_docs, batch_fts, batch_meta = [], [], []

                        if batch_docs:
                            self._commit_batch(db_conn, batch_docs, batch_fts, batch_meta)
                            html_indexed += len(batch_docs)
                            progress.update(task, advance=len(batch_docs))
                finally:
                    db_conn.close()
            else:
                self.console.print("  [dim green]✔ Partição HTML CPython já está atualizada.[/dim green]")
        else:
            self.console.print("  [yellow]⚠ Pasta de HTML Docs do CPython não encontrada no ambiente.[/yellow]")

        # ── PARTIÇÃO 2: DATASET CANÔNICO (CHEATSHEET) ──
        canonical_dir = Path.home() / ".doxoade" / "consult" / "canonical"
        cheatsheet_file = canonical_dir / "python_cheatsheet.jsonl"

        # Se o canônico ainda não foi gerado, roda o conversor automaticamente
        if not cheatsheet_file.exists():
            self.console.print("  [yellow]⚡ Gerando arquivo canônico do Cheatsheet automaticamente...[/yellow]")
            try:
                from .cheatsheet_converter import CheatsheetConverter
                CheatsheetConverter(canonical_dir).process_url()
            except Exception as e:
                self.console.print(f"  [red]✘ Erro ao gerar Cheatsheet: {e}[/red]")

        cheatsheet_indexed = 0
        if cheatsheet_file.exists():
            self.console.print(f"  📖 Ingerindo Cheatsheet Canônico: [cyan]{cheatsheet_file.name}[/cyan]...")
            db_conn = self._get_db_connection(bulk_mode=True)
            cursor = db_conn.cursor()

            try:
                db_conn.execute("BEGIN IMMEDIATE;")
                # Limpa partições antigas do cheatsheet antes de reinserir
                cursor.execute("DELETE FROM docs_fts WHERE path LIKE 'python/cheatsheet/%';")
                cursor.execute("DELETE FROM docs WHERE category = 'python_cheatsheet';")

                b_docs, b_fts = [], []
                with open(cheatsheet_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                r = json.loads(line)
                                path = r.get("path") or r.get("uid", "")
                                cat = r.get("category", "python_cheatsheet")
                                title = r.get("title", "")
                                kw = r.get("keywords", "")
                                content = r.get("content", "")

                                b_docs.append((path, cat, title, kw, content))
                                b_fts.append((path, title, kw, content))
                            except Exception:
                                continue

                if b_docs:
                    cursor.executemany("INSERT OR REPLACE INTO docs VALUES (?, ?, ?, ?, ?);", b_docs)
                    cursor.executemany("INSERT INTO docs_fts VALUES (?, ?, ?, ?);", b_fts)
                    cheatsheet_indexed = len(b_docs)

                db_conn.execute("COMMIT;")
            except Exception as e:
                db_conn.execute("ROLLBACK;")
                self.console.print(f"  [red]✘ Erro ao indexar Cheatsheet: {e}[/red]")
            finally:
                db_conn.close()

        # ── OTIMIZAÇÃO FINAL FTS5 ──
        self.console.print("  [dim cyan]⚡ Otimizando índices FTS5 no Hades...[/dim cyan]")
        conn = self._get_db_connection(bulk_mode=False)
        try:
            conn.execute("INSERT INTO docs_fts(docs_fts) VALUES('optimize');")
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM docs;")
            total_records = cursor.fetchone()[0]
        finally:
            conn.close()

        db_size_mb = self.db_path.stat().st_size / (1024 * 1024)
        self.console.print(f"\n[green bold]✔ [HADES] Base Unificada Concluída com Sucesso![/green bold]")
        self.console.print(f"  • CPython HTML Docs: [bold white]{html_indexed}[/bold white] adicionados")
        self.console.print(f"  • Cheatsheet Chunks:  [bold white]{cheatsheet_indexed}[/bold white] adicionados")
        self.console.print(f"  • Total no Banco:     [bold green]{total_records}[/bold green] documentos disponíveis")
        self.console.print(f"  • Tamanho no Disco:   [bold cyan]{db_size_mb:.2f} MB[/bold cyan]\n")

    def _commit_batch(self, conn: sqlite3.Connection, b_docs, b_fts, b_meta):
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE;")
        try:
            cursor.executemany("INSERT OR REPLACE INTO docs VALUES (?, ?, ?, ?, ?);", b_docs)
            cursor.executemany("INSERT INTO docs_fts VALUES (?, ?, ?, ?);", b_fts)
            cursor.executemany("INSERT OR REPLACE INTO doc_metadata VALUES (?, ?);", b_meta)
            cursor.execute("COMMIT;")
        except Exception:
            cursor.execute("ROLLBACK;")
            raise
