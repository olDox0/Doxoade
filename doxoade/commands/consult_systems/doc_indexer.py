# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/doc_indexer.py
"""
🗃️ HADES / POSEIDON — Indexador de Documentação HTML Local (Python Docs).
Arquitetura STRAP v2.3 Markdown Studio:
- Busca profunda FTS5 com geração de relatórios estruturados em Markdown (.md).
- Conversor Fast-Path de HTML do Python Docs para Markdown legível com código destacado.
- SQLite com isolation_level=None e suporte a --force (-f).
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations

import os
import sys
import sqlite3
import re
import html as html_lib
from pathlib import Path
from typing import List, Tuple, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Regex pré-compiladas de alta eficiência
RE_STRIP_BLOCKS = re.compile(
    r'<(?:script|style|nav|header|footer|svg)[^>]*>.*?</(?:script|style|nav|header|footer|svg)>',
    flags=re.DOTALL | re.IGNORECASE
)
RE_TAGS = re.compile(r'<[^>]+>')
RE_TITLE = re.compile(r'<title>(.*?)</title>', flags=re.DOTALL | re.IGNORECASE)
RE_SPACES = re.compile(r'\s+')

# Regex específicas para conversão de HTML em Markdown
RE_CODE_BLOCK = re.compile(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', flags=re.DOTALL | re.IGNORECASE)
RE_PRE_BLOCK = re.compile(r'<pre[^>]*>(.*?)</pre>', flags=re.DOTALL | re.IGNORECASE)
RE_INLINE_CODE = re.compile(r'<code[^>]*>(.*?)</code>', flags=re.DOTALL | re.IGNORECASE)
RE_H1 = re.compile(r'<h1[^>]*>(.*?)</h1>', flags=re.DOTALL | re.IGNORECASE)
RE_H2 = re.compile(r'<h2[^>]*>(.*?)</h2>', flags=re.DOTALL | re.IGNORECASE)
RE_H3 = re.compile(r'<h3[^>]*>(.*?)</h3>', flags=re.DOTALL | re.IGNORECASE)
RE_P = re.compile(r'<p[^>]*>(.*?)</p>', flags=re.DOTALL | re.IGNORECASE)
RE_LI = re.compile(r'<li[^>]*>(.*?)</li>', flags=re.DOTALL | re.IGNORECASE)


class DocIndexer:
    """Indexador e Renderizador Markdown de documentação Python offline."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.console = Console()

    def _get_db_connection(self, bulk_mode: bool = False) -> sqlite3.Connection:
        """Abre conexão com isolation_level=None para controle manual estrito."""
        conn = sqlite3.connect(str(self.db_path), timeout=60.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA cache_size = -64000")  # 64 MB em RAM
        if bulk_mode:
            conn.execute("PRAGMA synchronous = OFF")
        else:
            conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def init_db(self):
        """Inicializa as tabelas e índices FTS5."""
        conn = self._get_db_connection(bulk_mode=False)
        try:
            conn.execute("BEGIN IMMEDIATE")
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
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def find_python_docs(self) -> Optional[Path]:
        """Localiza o diretório raiz dos arquivos HTML instalados."""
        base_prefix = Path(sys.base_prefix)
        candidates = [
            base_prefix / "Doc" / "html",
            base_prefix / "share" / "doc" / "python3" / "html",
            base_prefix / "share" / "doc" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "html",
            base_prefix.parent / "Doc" / "html",
            Path.home() / ".doxoade" / "python_docs" / "html",
        ]
        for cand in candidates:
            if cand.exists() and (cand / "index.html").exists():
                return cand.resolve()
        return None

    def extract_text_from_html(self, html_path: Path) -> Tuple[str, str]:
        """Extrai título e texto puro decodificando entidades HTML."""
        try:
            raw_html = html_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return html_path.name, ""

        title_m = RE_TITLE.search(raw_html)
        if title_m:
            raw_title = RE_TAGS.sub('', title_m.group(1))
            title = RE_SPACES.sub(' ', html_lib.unescape(raw_title)).strip()
        else:
            title = html_path.stem

        clean = RE_STRIP_BLOCKS.sub(' ', raw_html)
        clean_tags = RE_TAGS.sub(' ', clean)
        clean_text = html_lib.unescape(clean_tags)
        text = RE_SPACES.sub(' ', clean_text).strip()
        return title, text

    def html_to_markdown(self, html_content: str, title_fallback: str = "Documentação") -> str:
        """Converte HTML oficial para Markdown técnico limpo com espaçamento tipográfico natural."""
        raw = html_content

        # 1. Isola o corpo principal do Sphinx (<div role="main"> ou <div class="body">)
        main_match = re.search(r'<div[^>]*role="main"[^>]*>(.*?)</div>\s*<div[^>]*class="clearer"', raw, flags=re.DOTALL | re.IGNORECASE)
        if not main_match:
            main_match = re.search(r'<div[^>]*class="body"[^>]*role="main"[^>]*>(.*?)</div>\s*</div>', raw, flags=re.DOTALL | re.IGNORECASE)
        if main_match:
            raw = main_match.group(1)

        # 2. Purga elementos de navegação, breadcrumbs e barras laterais
        raw = re.sub(r'<div[^>]*(?:class="[^"]*(?:related|sphinxsidebar|mobile-nav|header|footer)[^"]*"|role="navigation")[^>]*>.*?</div>', '', raw, flags=re.DOTALL | re.IGNORECASE)
        raw = RE_STRIP_BLOCKS.sub('', raw)

        title_m = RE_TITLE.search(html_content)
        page_title = html_lib.unescape(RE_TAGS.sub('', title_m.group(1))).strip() if title_m else title_fallback
        page_title = re.sub(r'\s*—\s*Python\s+[\d\.]+\s+documentation', '', page_title)

        # 3. Preserva blocos de código com sentinelas temporárias (SEM inserir espaços espúrios entre tags de código)
        code_blocks: List[str] = []
        def _save_code(m):
            # No código: remove tags substituindo por vazio '', não por espaço ' '
            code_text = html_lib.unescape(RE_TAGS.sub('', m.group(1))).strip()
            idx = len(code_blocks)
            code_blocks.append(code_text)
            return f"\n\n```python\n___DOX_CODE_BLOCK_{idx}___\n```\n\n"

        text = RE_CODE_BLOCK.sub(_save_code, raw)
        text = RE_PRE_BLOCK.sub(_save_code, text)

        # 4. Converte títulos e estrutura
        text = RE_H1.sub(lambda m: f"\n\n# {html_lib.unescape(RE_TAGS.sub('', m.group(1))).strip()}\n\n", text)
        text = RE_H2.sub(lambda m: f"\n\n## {html_lib.unescape(RE_TAGS.sub('', m.group(1))).strip()}\n\n", text)
        text = RE_H3.sub(lambda m: f"\n\n### {html_lib.unescape(RE_TAGS.sub('', m.group(1))).strip()}\n\n", text)
        text = RE_INLINE_CODE.sub(lambda m: f"`{html_lib.unescape(RE_TAGS.sub('', m.group(1))).strip()}`", text)
        text = RE_LI.sub(lambda m: f"\n* {html_lib.unescape(RE_TAGS.sub('', m.group(1))).strip()}", text)
        text = RE_P.sub(lambda m: f"\n\n{html_lib.unescape(RE_TAGS.sub(' ', m.group(1))).strip()}\n\n", text)

        # Remove tags remanescentes
        text = RE_TAGS.sub(' ', text)

        # Restaura os blocos de código
        for idx, block in enumerate(code_blocks):
            text = text.replace(f"___DOX_CODE_BLOCK_{idx}___", block)

        # 5. Higienização tipográfica: remove espaços espúrios antes de pontuações
        text = re.sub(r'[ \t]+([,.:;?!)\'\"\]])', r'\1', text)
        text = re.sub(r'([(\[\'\"‘“])[ \t]+', r'\1', text)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()

        md_output = [
            f"# {page_title}",
            "---",
            text
        ]
        return "\n".join(md_output)

    def search(self, query: str, limit: int = 15) -> List[Tuple[str, str, str]]:
        """Busca rápida no índice FTS5 com marcadores seguros."""
        self.init_db()
        conn = self._get_db_connection(bulk_mode=False)
        cursor = conn.cursor()

        clean_q = re.sub(r'[^\w\s]', ' ', query).strip()
        if not clean_q:
            conn.close()
            return []

        tokens = clean_q.split()
        fts_query = " ".join([f'"{tok}"*' for tok in tokens])

        sql = """
            SELECT 
                path,
                title,
                snippet(docs_fts, 2, '\x02', '\x03', '...', 18) as snippet
            FROM docs_fts
            WHERE docs_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        try:
            cursor.execute(sql, (fts_query, limit))
            results = [(row[0], row[1], row[2]) for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            try:
                cursor.execute(sql, (f'"{clean_q}"', limit))
                results = [(row[0], row[1], row[2]) for row in cursor.fetchall()]
            except Exception:
                results = []
        finally:
            conn.close()

        return results

    def generate_search_markdown(self, query: str, limit: int = 20) -> str:
        """Gera um dossiê completo de resultados formatado em Markdown para exibição no Doxly."""
        results = self.search(query, limit=limit)
        docs_dir = self.find_python_docs()
        docs_base_str = str(docs_dir) if docs_dir else "Docs Local"

        lines = [
            f"# 🔍 Doxoade Consult — Resultados: `{query}`",
            f"> 📂 **Base:** `{docs_base_str}`  ",
            f"> 📊 **Encontrados:** `{len(results)}` documentos relevantes  ",
            f"> 💡 **Dica:** *Pressione [Enter] sobre a linha de qualquer arquivo para ler a documentação completa neste painel.*",
            "",
            "---",
            ""
        ]

        if not results:
            lines.append("### ❌ Nenhum resultado localizado para a busca.")
            lines.append("Tente termos mais amplos (ex: `asyncio`, `json`, `socket`, `subprocess`).")
            return "\n".join(lines)

        MARK_START = "\x02"
        MARK_END = "\x03"

        for idx, (path, title, snippet) in enumerate(results, 1):
            clean_snippet = snippet.replace(MARK_START, "**`").replace(MARK_END, "`**")
            lines.append(f"### {idx}. 📄 {title}")
            lines.append(f"↳ `{path}`")
            lines.append("")
            lines.append(f"> {clean_snippet}")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def read_doc_as_markdown(self, rel_or_abs_path: str) -> Optional[str]:
        """Lê um arquivo HTML da documentação e o retorna formatado em Markdown."""
        docs_dir = self.find_python_docs()
        target = Path(rel_or_abs_path)
        if not target.is_absolute() and docs_dir:
            target = docs_dir / rel_or_abs_path

        if not target.exists() or not target.is_file():
            return None

        raw_html = target.read_text(encoding="utf-8", errors="ignore")
        return self.html_to_markdown(raw_html, title_fallback=target.stem)

    def build_index(self, force: bool = False):
        """Pipeline de indexação otimizado com suporte a reindexação forçada."""
        docs_dir = self.find_python_docs()
        if not docs_dir:
            self.console.print("[red bold]❌ Diretório de documentação do Python não encontrado.[/red bold]")
            return

        self.console.print(f"[green]✔ Docs do Python encontrados em:[/green] [cyan]{docs_dir}[/cyan]")
        self.init_db()

        if force:
            self.console.print("[yellow]🔄 Flag --force detectada: Limpando base de dados FTS5 para reindexação total...[/yellow]")
            conn = self._get_db_connection(bulk_mode=False)
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM docs_fts")
                conn.execute("DELETE FROM doc_metadata")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
            finally:
                conn.close()
            existing_meta = {}
        else:
            conn = self._get_db_connection(bulk_mode=False)
            cursor = conn.cursor()
            cursor.execute("SELECT path, last_modified FROM doc_metadata")
            existing_meta = dict(cursor.fetchall())
            conn.close()

        all_html = list(docs_dir.rglob("*.html"))
        pending_files: List[Tuple[Path, str, float]] = []

        for html_file in all_html:
            rel_path = str(html_file.relative_to(docs_dir)).replace("\\", "/")
            try:
                mtime = html_file.stat().st_mtime
                if not force and rel_path in existing_meta and existing_meta[rel_path] == mtime:
                    continue
                pending_files.append((html_file, rel_path, mtime))
            except OSError:
                continue

        if not pending_files:
            self.console.print("[green bold]✔ Toda a documentação já está indexada e atualizada![/green bold]")
            self.console.print("[dim]💡 Use 'doxoade consult index --force' para forçar a regeração completa.[/dim]")
            return

        self.console.print(f"[cyan]📚 Indexando [bold]{len(pending_files)}[/bold] arquivos HTML com Fast-Path FTS5...[/cyan]")

        db_conn = self._get_db_connection(bulk_mode=True)
        try:
            try:
                db_conn.execute("INSERT INTO docs_fts(docs_fts, rank) VALUES('automerge', 0);")
            except Exception:
                pass

            batch_size = 100
            current_batch: List[Tuple[str, str, str, float]] = []
            processed_count = 0

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("Indexando docs (STRAP Engine)...", total=len(pending_files))

                for file_path, rel_path, mtime in pending_files:
                    title, text = self.extract_text_from_html(file_path)
                    current_batch.append((rel_path, title, text, mtime))

                    if len(current_batch) >= batch_size:
                        self._write_batch(db_conn, current_batch)
                        processed_count += len(current_batch)
                        progress.update(task, advance=len(current_batch))
                        current_batch = []

                if current_batch:
                    self._write_batch(db_conn, current_batch)
                    processed_count += len(current_batch)
                    progress.update(task, advance=len(current_batch))

            self.console.print("[dim cyan]⚡ Otimizando segmentos do índice FTS5...[/dim cyan]")
            try:
                db_conn.execute("INSERT INTO docs_fts(docs_fts, rank) VALUES('automerge', 4);")
                db_conn.execute("INSERT INTO docs_fts(docs_fts) VALUES('optimize');")
            except Exception:
                pass

        finally:
            try:
                db_conn.execute("PRAGMA synchronous = NORMAL")
            except Exception:
                pass
            db_conn.close()

        self.console.print("[green bold]✔ Indexação concluída com sucesso![/green bold]")
        self.console.print(f"[dim]💡 {processed_count} arquivos processados e higienizados.[/dim]")
        self.console.print("[dim]💡 Use 'doxoade consult search --deep <termo>' para pesquisar.[/dim]\n")

    def generate_search_lua_table(self, query: str, limit: int = 20) -> str:
        """Gera uma tabela Lua soberana 100% compatível com a sintaxe do Lua 5.4 (UTF-8 limpo)."""
        results = self.search(query, limit=limit)

        def _to_lua_str(s: str) -> str:
            if not s:
                return '""'
            clean = s.replace("\0", "").replace("\r\n", "\n").replace("\r", "\n")
            clean = clean.replace("\\", "\\\\").replace('"', '\\"')
            clean = clean.replace("\n", "\\n").replace("\t", "\\t")
            return f'"{clean}"'

        lines = [
            "-- auto-generated by doxoade consult search",
            "return {",
            f"  query = {_to_lua_str(query)},",
            f"  total = {len(results)},",
            "  results = {",
        ]
        MARK_START = "\x02"
        MARK_END = "\x03"

        for path, title, snippet in results:
            clean_snippet = snippet.replace(MARK_START, "").replace(MARK_END, "")
            lines.append("    {")
            lines.append(f"      path = {_to_lua_str(path)},")
            lines.append(f"      title = {_to_lua_str(title)},")
            lines.append(f"      snippet = {_to_lua_str(clean_snippet)},")
            lines.append("    },")

        lines.append("  }")
        lines.append("}")
        return "\n".join(lines)

    def _write_batch(self, conn: sqlite3.Connection, batch: List[Tuple[str, str, str, float]]):
        paths_to_delete = [(item[0],) for item in batch]
        fts_data = [(item[0], item[1], item[2]) for item in batch]
        meta_data = [(item[0], item[3]) for item in batch]

        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            cursor.executemany("DELETE FROM docs_fts WHERE path = ?", paths_to_delete)
            cursor.executemany("INSERT INTO docs_fts (path, title, content) VALUES (?, ?, ?)", fts_data)
            cursor.executemany("INSERT OR REPLACE INTO doc_metadata (path, last_modified) VALUES (?, ?)", meta_data)
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise
