# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/doc_indexer.py
"""
DocIndexer v3.1 — Orquestrador Soberano de Indexação FTS5 & B-Tree (Thoth & Hades Engine).
Unifica a documentação HTML do CPython e os Datasets Canônicos em um único banco relacional + FTS5.

v3.1 (fixes):
- Pipeline _clean_cpython_markdown agora é efetivamente chamado no final de html_to_markdown.
- _fix_mojibake com strings Unicode escapadas (sem ambiguidade visual).
- RE_INLINE_CODE remove <span class="pre"> do Sphinx antes de envolver em backtick.
- Snippet de busca aumentado para 60 tokens (~30 palavras de contexto).
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


# ─── Limpeza pós-conversão HTML → Markdown (CPython/Sphinx) ───

# Mapa de mojibake UTF-8→CP1252. Usamos escapes Unicode para não depender
# da codificação do arquivo-fonte nem gerar ambiguidade visual.
# ─── Limpeza pós-conversão HTML → Markdown (CPython/Sphinx) ───

_MOJIBAKE_MAP = {
    "\u00e2\u20ac\u2122": "\u2019",
    "\u00e2\u20ac\u02dc": "\u2018",
    "\u00e2\u20ac\u0153": "\u201c",
    "\u00e2\u20ac\u009d": "\u201d",
    "\u00e2\u20ac\u201d": "\u2014",
    "\u00e2\u20ac\u201c": "\u2013",
    "\u00c2\u00b6": "\u00b6",
    "\u00c2\u00a7": "\u00a7",
    "\u00c2\u00a9": "\u00a9",
    "\u00c2\u00ae": "\u00ae",
    "\u00c2\u00b7": "\u00b7",
    "\u00e2\u20ac\u00a6": "\u2026",
    "\u00e2\u2030\u00a5": "\u2265",
    "\u00e2\u2030\u00a4": "\u2264",
    "\u00e2\u2030\u00a0": "\u2260",
}


def _fix_mojibake(text: str) -> str:
    for bad, good in _MOJIBAKE_MAP.items():
        text = text.replace(bad, good)
    return text


def _strip_sphinx_permalink_paragraphs(text: str) -> str:
    """Remove o ¶ de permalink que fica no fim de headers do Sphinx."""
    # Casa "¶" isolado no fim da linha (com espaços/tabs antes)
    return re.sub(r"[ \t]*\u00b6[ \t]*$", "", text, flags=re.MULTILINE)


def _strip_span_artifacts(text: str) -> str:
    """Remove espaços internos de inline code e colapsa espaços duplos fora de fences."""
    # 1) ` foo ` → `foo`  (espaços dentro do backtick)
    text = re.sub(r"`[ \t]+([^`\n]+?)[ \t]+`", r"`\1`", text)
    # 2) `` → ` (colapsa múltiplos backticks)
    text = re.sub(r"``([^`\n]+?)``", r"`\1`", text)
    # 3) Colapsa espaços duplos FORA de fences ``` ``` e fora de backticks
    #    Usa state machine: percorre linha por linha, rastreia se está em fence
    out_lines = []
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue
        # Colapsa [ \t]{2,} → " " mas preserva espaços internos de backticks
        # Para preservar `PyTypeObject` como token único, split por backtick
        parts = line.split("`")
        for i in range(len(parts)):
            if i % 2 == 0:
                parts[i] = re.sub(r"[ \t]{2,}", " ", parts[i])
        out_lines.append("`".join(parts))
    return "\n".join(out_lines)


def _ensure_header_spacing(text: str) -> str:
    """Garante \n\n antes e depois de cada header (#, ##, ###)."""
    # Colapsa \n\n+ antes do header em \n\n
    text = re.sub(r"\n{2,}(#{1,3}\s)", r"\n\n\1", text)
    # Colapsa \n\n+ depois do header em \n\n
    text = re.sub(r"(#{1,3}\s[^\n]+)\n{1,}", r"\1\n\n", text)
    # Colapsa \n\n+ em geral
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _clean_cpython_markdown(text: str) -> str:
    """Pipeline completo de limpeza para HTML do CPython."""
    text = _fix_mojibake(text)
    text = _strip_sphinx_permalink_paragraphs(text)
    text = _strip_span_artifacts(text)
    text = _ensure_header_spacing(text)
    return text.strip()


def _clean_inline_code(match: "re.Match") -> str:
    """Limpa o interior de <code>...</code>: remove <span>, tags residuais, unescape."""
    inner = match.group(1)
    inner = re.sub(r"<span[^>]*>(.*?)</span>", r"\1", inner, flags=re.DOTALL)
    inner = re.sub(r"<[^>]+>", "", inner)
    inner = html_lib.unescape(inner).strip()
    if not inner:
        return ""
    return f"`{inner}`"


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

            conn.execute("""
                CREATE TABLE IF NOT EXISTS docs (
                    path TEXT PRIMARY KEY,
                    category TEXT,
                    title TEXT,
                    keywords TEXT,
                    content TEXT
                );
            """)

            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                    path UNINDEXED,
                    title,
                    keywords,
                    content,
                    tokenize='porter unicode61'
                );
            """)

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
        candidates.append(
            py_prefix / "share" / "doc"
            / f"python{sys.version_info.major}.{sys.version_info.minor}" / "html"
        )
        if os.name == 'nt':
            local_app = os.environ.get("LOCALAPPDATA", "")
            if local_app:
                candidates.append(
                    Path(local_app) / "Programs" / "Python"
                    / f"Python{sys.version_info.major}{sys.version_info.minor}"
                    / "Doc" / "html"
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

        # Inline code com limpeza interna (remove <span class="pre">)
        text = RE_INLINE_CODE.sub(_clean_inline_code, text)

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

        # ─── PATCH: pipeline de limpeza pós-conversão ───
        clean_text = _clean_cpython_markdown(clean_text)

        return f"# 📖 {title}\n\n{clean_text}"

    def _isolate_sphinx_body(self, raw_html: str) -> str:
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
        if not query or not query.strip():
            return []

        clean_q = query.strip()
        conn = self._get_db_connection(bulk_mode=False)
        cursor = conn.cursor()

        # Filtro de ranking: prioriza conteúdo didático, penaliza índices
        # metadados e changelogs do CPython (que poluem o top-25 sem agregar).
        sql = """
            SELECT
                path,
                title,
                snippet(docs_fts, 3, '\x02', '\x03', '...', 60) as snippet
            FROM docs_fts
            WHERE docs_fts MATCH ?
            ORDER BY
                CASE
                    -- 🔴 Prioridade MÁXIMA: livros, PEPs, algoritmos, patterns, Typeshed
                    WHEN path LIKE 'python/peps/%'              THEN 0
                    WHEN path LIKE 'python/basic/%'             THEN 0
                    WHEN path LIKE 'python/algorithms/%'        THEN 0
                    WHEN path LIKE 'python/patterns/%'          THEN 0
                    WHEN path LIKE 'python/architecture/%'      THEN 0
                    WHEN path LIKE 'python/automation/%'        THEN 0
                    WHEN path LIKE 'python/typeshed/%'          THEN 1
                    WHEN path LIKE 'python/cheatsheet/%'        THEN 1
                    
                    -- 🟡 Prioridade MÉDIA: CPython tutorial, library, howto
                    WHEN path LIKE 'tutorial/%'                 THEN 2
                    WHEN path LIKE 'library/%'                  THEN 2
                    WHEN path LIKE 'howto/%'                    THEN 2
                    WHEN path LIKE 'reference/%'                THEN 3
                    WHEN path LIKE 'c-api/%'                    THEN 3
                    
                    -- ⚪ Prioridade BAIXA: metadados, índices, changelogs
                    WHEN path LIKE '%genindex%'                 THEN 9
                    WHEN path LIKE '%modindex%'                 THEN 9
                    WHEN path LIKE '%py-modindex%'              THEN 9
                    WHEN path LIKE '%contents.html%'            THEN 9
                    WHEN path LIKE 'whatsnew/%'                 THEN 9
                    WHEN path LIKE 'using/%'                    THEN 8
                    WHEN path LIKE 'faq/%'                      THEN 7
                    WHEN path LIKE 'about.html%'                THEN 9
                    WHEN path LIKE 'download.html%'             THEN 9
                    
                    -- Fallback: CPython misc (license, bugs, glossary, etc.)
                    ELSE 5
                END,
                rank
            LIMIT ?;
        """

        fts_query = clean_q
        if " " in clean_q and not any(c in clean_q for c in ('"', '*')):
            terms = [f'"{t}"' for t in clean_q.split() if t]
            fts_query = " ".join(terms)

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
        clean_path = path_or_query.strip().strip("'\"")

        if self.db_path.exists():
            try:
                conn = self._get_db_connection(bulk_mode=False)
                row = conn.execute(
                    "SELECT title, content FROM docs WHERE path = ? LIMIT 1;", (clean_path,)
                ).fetchone()

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

        docs_dir = self.find_python_docs()
        target = Path(clean_path)
        if not target.is_absolute() and docs_dir:
            target = docs_dir / clean_path

        if target.exists() and target.is_file():
            raw_html = target.read_text(encoding="utf-8", errors="ignore")
            return self.html_to_markdown(raw_html, title_fallback=target.stem)

        return None

    def build_index(self, force: bool = False):
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

        # ── PARTIÇÃO 2: DATASETS CANÔNICOS (*.jsonl) ──
        canonical_dir = Path.home() / ".doxoade" / "consult" / "canonical"
        canonical_dir.mkdir(parents=True, exist_ok=True)

        jsonl_files = sorted(canonical_dir.glob("*.jsonl"))
        total_canonical_records = 0

        if jsonl_files:
            db_conn = self._get_db_connection(bulk_mode=True)
            cursor = db_conn.cursor()

            try:
                db_conn.execute("BEGIN IMMEDIATE;")
                for jf in jsonl_files:
                    b_docs, b_fts = [], []
                    self.console.print(f"  📖 Ingerindo Acervo Canônico: [cyan]{jf.name}[/cyan]...")

                    with open(jf, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    r = json.loads(line)
                                    path = r.get("path") or r.get("uid", "")
                                    cat = r.get("category", jf.stem)
                                    title = r.get("title", "")
                                    kw = r.get("keywords", "")
                                    content = r.get("content", "")

                                    b_docs.append((path, cat, title, kw, content))
                                    b_fts.append((path, title, kw, content))
                                except Exception:
                                    continue

                    if b_docs:
                        cat_clean = b_docs[0][1]
                        cursor.execute("DELETE FROM docs_fts WHERE path IN (SELECT path FROM docs WHERE category = ?);", (cat_clean,))
                        cursor.execute("DELETE FROM docs WHERE category = ?;", (cat_clean,))

                        cursor.executemany("INSERT OR REPLACE INTO docs VALUES (?, ?, ?, ?, ?);", b_docs)
                        cursor.executemany("INSERT INTO docs_fts VALUES (?, ?, ?, ?);", b_fts)
                        total_canonical_records += len(b_docs)

                db_conn.execute("COMMIT;")
            except Exception as e:
                db_conn.execute("ROLLBACK;")
                self.console.print(f"  [red]✘ Erro ao indexar acervos canônicos: {e}[/red]")
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
        self.console.print(f"  • CPython HTML Docs:   [bold white]{html_indexed}[/bold white] adicionados")
        self.console.print(f"  • Acervos Canônicos:   [bold white]{total_canonical_records}[/bold white] adicionados")
        self.console.print(f"  • Total no Banco:       [bold green]{total_records}[/bold green] documentos disponíveis")
        self.console.print(f"  • Tamanho no Disco:     [bold cyan]{db_size_mb:.2f} MB[/bold cyan]\n")

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
