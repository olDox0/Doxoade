# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/doc_indexer.py
"""
🗃️ HADES — Indexador de Documentação HTML Local (Python 3.x Docs).
Arquitetura STRAP: Streaming, Assíncrono, Pitstop (Resumível) e Backpressure.
Otimizado com Fast-Path Regex Engine e Sentinelas Seguras FTS5.
"""
import sys
import sqlite3
import re
import json
import asyncio
from pathlib import Path
from typing import List, Tuple, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Regex compiladas para performance máxima em nível de C
RE_STRIP_TAGS = re.compile(r'<(script|style|nav|header|footer|svg).*?</\1>', flags=re.DOTALL | re.IGNORECASE)
RE_HTML_TAGS = re.compile(r'<[^>]+>')
RE_TITLE = re.compile(r'<title>(.*?)</title>', flags=re.DOTALL | re.IGNORECASE)
RE_WHITESPACE = re.compile(r'\s+')


class DocIndexer:
    """Indexador de documentação com persistência FTS5 de alta performance."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.console = Console()
        self.state_file = db_path.parent / "strap_index_state.json"
        self.processed_files = set()
        self._load_state()

    def _load_state(self):
        """🛑 PITSTOP: Carrega o estado anterior para garantir idempotência."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.processed_files = set(state.get("processed", []))
            except Exception:
                self.processed_files = set()

    def _save_state(self):
        """🛑 PITSTOP: Salva o estado atual para resumo seguro."""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump({"processed": list(self.processed_files)}, f)
        except Exception:
            pass

    def _get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def init_db(self):
        """Garante a estrutura necessária no banco de dados SQLite FTS5."""
        conn = self._get_db_connection()
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                path UNINDEXED,
                title,
                content,
                tokenize='porter unicode61'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS doc_metadata (
                path TEXT PRIMARY KEY,
                last_modified REAL
            )
        """)
        conn.commit()
        conn.close()

    def find_python_docs(self) -> Optional[Path]:
        """Localiza a raiz dos arquivos HTML da documentação instalada."""
        base_prefix = Path(sys.base_prefix)
        candidates = [
            base_prefix / "Doc" / "html",
            base_prefix / "share" / "doc" / "python3" / "html",
            base_prefix / "share" / "doc" / "python3.12" / "html",
            base_prefix.parent / "Doc" / "html",
        ]
        for cand in candidates:
            if cand.exists() and (cand / "index.html").exists():
                return cand
        return None

    def extract_text_from_html(self, html_path: Path) -> Tuple[str, str]:
        """
        Extrai título e texto legível via Fast-Path Regex.
        Bypassa o overhead de charset_normalizer/BeautifulSoup.
        """
        try:
            raw_html = html_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return html_path.name, ""

        title_m = RE_TITLE.search(raw_html)
        if title_m:
            title = RE_WHITESPACE.sub(' ', RE_HTML_TAGS.sub('', title_m.group(1))).strip()
        else:
            title = html_path.stem

        clean = RE_STRIP_TAGS.sub('', raw_html)
        text = RE_HTML_TAGS.sub(' ', clean)
        text = RE_WHITESPACE.sub(' ', text).strip()

        return title, text

    async def _worker_extract(self, file_queue: asyncio.Queue, data_queue: asyncio.Queue, docs_dir: Path):
        """Worker assíncrono para extração I/O com alta taxa de transferência."""
        while True:
            item = await file_queue.get()
            if item is None:
                file_queue.task_done()
                break

            html_file = item
            rel_path = str(html_file.relative_to(docs_dir)).replace("\\", "/")
            try:
                mtime = html_file.stat().st_mtime
                title, text = await asyncio.to_thread(self.extract_text_from_html, html_file)
                await data_queue.put((rel_path, title, text, mtime))
            except Exception:
                pass
            finally:
                file_queue.task_done()

    async def _writer_consumer(self, data_queue: asyncio.Queue, progress, task_id, total_files: int):
        """Consumidor SQLite com escrita transacional em lote."""
        conn = self._get_db_connection()
        conn.execute("PRAGMA synchronous = OFF")  # Velocidade máxima de ingestão
        batch_size = 100
        batch = []
        processed_count = 0

        try:
            while True:
                item = await data_queue.get()
                if item is None:
                    if batch:
                        self._flush_batch(conn, batch)
                        processed_count += len(batch)
                        progress.update(task_id, advance=len(batch))
                        self._save_state()
                    data_queue.task_done()
                    break

                batch.append(item)
                if len(batch) >= batch_size:
                    self._flush_batch(conn, batch)
                    processed_count += len(batch)
                    progress.update(task_id, advance=len(batch))
                    self._save_state()
                    batch.clear()

                data_queue.task_done()
        finally:
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.close()

        return processed_count

    def _flush_batch(self, conn: sqlite3.Connection, batch: List[Tuple[str, str, str, float]]):
        """Grava o lote em uma única transação atômica."""
        paths_to_delete = [(item[0],) for item in batch]
        fts_data = [(item[0], item[1], item[2]) for item in batch]
        meta_data = [(item[0], item[3]) for item in batch]

        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        cursor.executemany("DELETE FROM docs_fts WHERE path = ?", paths_to_delete)
        cursor.executemany("INSERT INTO docs_fts (path, title, content) VALUES (?, ?, ?)", fts_data)
        cursor.executemany("INSERT OR REPLACE INTO doc_metadata (path, last_modified) VALUES (?, ?)", meta_data)
        conn.commit()

        for item in batch:
            self.processed_files.add(item[0])

    async def build_index_async(self, docs_dir: Path, html_files: List[Path]):
        """Orquestra o pipeline STRAP com balanceamento de carga real."""
        self.init_db()

        conn = self._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT path, last_modified FROM doc_metadata")
        existing_meta = dict(cursor.fetchall())
        conn.close()

        pending_files = []
        for f in html_files:
            rel = str(f.relative_to(docs_dir)).replace("\\", "/")
            if rel in existing_meta and rel in self.processed_files:
                try:
                    if f.stat().st_mtime == existing_meta[rel]:
                        continue
                except OSError:
                    pass
            pending_files.append(f)

        if not pending_files:
            self.console.print("[green bold]✔ Toda a documentação já está indexada e atualizada![/green bold]")
            return

        file_queue = asyncio.Queue(maxsize=150)
        data_queue = asyncio.Queue(maxsize=100)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("Indexando docs (STRAP Engine)...", total=len(pending_files))

            num_workers = 6
            workers = [
                asyncio.create_task(self._worker_extract(file_queue, data_queue, docs_dir))
                for _ in range(num_workers)
            ]

            writer = asyncio.create_task(self._writer_consumer(data_queue, progress, task, len(pending_files)))

            for f in pending_files:
                await file_queue.put(f)

            await file_queue.join()
            for _ in range(num_workers):
                await file_queue.put(None)
            await asyncio.gather(*workers)

            await data_queue.put(None)
            processed_count = await writer

        self._save_state()
        self.console.print(f"[green bold]✔ Indexação STRAP concluída com sucesso![/green bold]")
        self.console.print(f"[dim]💡 {processed_count} arquivos novos/atualizados indexados.[/dim]")
        self.console.print("[dim]💡 Use 'doxoade consult search --deep <termo>' para buscar.[/dim]")

    def build_index(self):
        """Ponto de entrada do comando index."""
        docs_dir = self.find_python_docs()
        if not docs_dir:
            self.console.print("[red]❌ Diretório de documentação do Python não encontrado.[/red]")
            return

        self.console.print(f"[green]✔ Docs do Python encontrados em:[/green] {docs_dir}")
        html_files = list(docs_dir.rglob("*.html"))
        self.console.print(f"[cyan]📚 {len(html_files)} arquivos HTML encontrados. Disparando STRAP Fast-Path...[/cyan]")
        try:
            asyncio.run(self.build_index_async(docs_dir, html_files))
        except KeyboardInterrupt:
            self.console.print("\n[yellow]⚠ Indexação interrompida (Pitstop acionado).[/yellow]")
            self._save_state()
        except Exception as e:
            self.console.print(f"\n[red]❌ Erro na indexação: {e}[/red]")
            self._save_state()

    def search(self, keyword: str, limit: int = 15) -> List[Tuple[str, str, str]]:
        """
        🔍 Busca textual profunda no FTS5 otimizada com Memory-Mapped I/O.
        Garante resposta sub-segundo sem contenção de lock.
        """
        if not self.db_path.exists():
            return []

        clean_keyword = re.sub(r'[^\w\s]', '', keyword).strip()
        if not clean_keyword:
            return []

        fts_query = " NEAR ".join(clean_keyword.split())

        # Conexão rápida em modo leitura com MMAP ativado
        db_uri = f"{self.db_path.resolve().as_uri()}?mode=ro"
        try:
            conn = sqlite3.connect(db_uri, uri=True, timeout=5.0)
        except Exception:
            # Fallback seguro caso o driver local não suporte URI
            conn = sqlite3.connect(str(self.db_path), timeout=5.0)

        # Otimizações de leitura em RAM
        conn.execute("PRAGMA query_only = ON")
        conn.execute("PRAGMA mmap_size = 67108864")  # 64MB MMAP
        conn.execute("PRAGMA cache_size = -8000")   # 8MB Cache

        cursor = conn.cursor()
        results = []

        sql = """
            SELECT 
                path, 
                title, 
                snippet(docs_fts, 2, '\x02', '\x03', '...', 25) as snippet
            FROM docs_fts
            WHERE docs_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """

        try:
            cursor.execute(sql, (fts_query, limit))
            results = cursor.fetchall()
        except sqlite3.OperationalError:
            try:
                tokens = " OR ".join(clean_keyword.split())
                cursor.execute(sql, (tokens, limit))
                results = cursor.fetchall()
            except Exception:
                results = []
        finally:
            conn.close()

        return results
