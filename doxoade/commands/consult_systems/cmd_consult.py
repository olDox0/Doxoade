# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/cmd_consult.py
"""
⚡ ZEUS — Roteador CLI do Subsistema Doxoade Consult (V25.1 Hybrid Bridge Blindada).
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations
import click
import re
import sys
import os
from pathlib import Path
from typing import List, Tuple

# 🛡️ ADAPTADOR DE IMPORTAÇÃO UNIVERSAL (Hermes)
# Permite que o arquivo seja executado tanto via 'python -m' quanto diretamente pela bridge Lua.
try:
    from .consult_engine import ConsultEngine
    from .consult_renderer import ConsultRenderer
except ImportError:
    # Fallback para execução direta (script) ou bridge sem contexto de pacote
    _base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if _base_dir not in sys.path:
        sys.path.insert(0, _base_dir)
    from commands.consult_systems.consult_engine import ConsultEngine
    from commands.consult_systems.consult_renderer import ConsultRenderer

try:
    from doxoade.commands.telemetry_systems import ShadowMatrix as ShadowProfiler
except ImportError:
    try:
        from commands.telemetry_systems import ShadowMatrix as ShadowProfiler
    except ImportError:
        # Profiler Dummy (Fallback de Degradação Graciosa - Plano C)
        class ShadowProfiler:
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def render_hud(self): pass


def _escape_lua_str(s: str) -> str:
    """Escapa strings com segurança para serialização em tabelas Lua."""
    if not s:
        return ""
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace("\t", " ")
    )


def _format_modules_lua_table(query: str, results: List[Tuple[str, str]]) -> str:
    """Serializa resultados do pydoc.apropos em tabela Lua nativa para o Lite XL."""
    lines = [
        "return {",
        f'  query = "{_escape_lua_str(query)}",',
        f'  total = {len(results)},',
        "  results = {",
    ]
    for mod_name, desc in results:
        clean_desc = desc if desc else mod_name
        lines.append("    {")
        lines.append(f'      title = "{_escape_lua_str(mod_name)}",')
        lines.append(f'      path = "{_escape_lua_str(mod_name)}",')
        lines.append(f'      snippet = "{_escape_lua_str(clean_desc)}"')
        lines.append("    },")
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines)


def _format_modules_markdown(query: str, results: List[Tuple[str, str]]) -> str:
    """Serializa resultados em Markdown legível."""
    lines = [
        f"# 📚 Resultados da Busca: `{query}`",
        f"> 📊 **Encontrados:** `{len(results)}` módulos disponíveis",
        "---",
        "",
    ]
    for mod_name, desc in results:
        lines.append(f"### 📦 `{mod_name}`")
        if desc:
            lines.append(f"↳ {desc}\n")
    return "\n".join(lines)


@click.group("consult", help="📖 Doxoade Consult — Consultor offline de Python, módulos locais e fontes.")
@click.option("--source", "-s", is_flag=True, help="Exibe o código fonte do objeto, se disponível.")
@click.option("--raw", "-r", is_flag=True, help="Exibe a documentação em texto puro, sem formatação Rich.")
@click.option("--shadow-prof", "-P", is_flag=True, help="🦅 Ativa o Shadow Profiler para diagnosticar gargalos da execução.")
@click.pass_context
def consult_group(ctx, source, raw, shadow_prof):
    """Grupo de comandos de consulta offline."""
    ctx.obj = {
        "source": source,
        "raw": raw,
        "shadow_prof": shadow_prof,
    }
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@consult_group.command("doc", help="Consulta a documentação exata de um módulo, classe ou função.")
@click.argument("term", type=str)
@click.pass_context
def cmd_doc(ctx, term):
    """Busca a documentação exata de um tópico Python."""
    is_prof = ctx.obj.get("shadow_prof", False)
    with ShadowProfiler("consult_doc", enabled=is_prof) as profiler:
        engine = ConsultEngine()
        renderer = ConsultRenderer()
        obj = engine.resolve_object(term)
        if obj:
            doc_text = engine.get_docstring(obj)
            src_text = engine.get_source(obj) if ctx.obj.get("source") else None
            if ctx.obj.get("raw"):
                click.echo(doc_text)
                if src_text:
                    click.echo(f"\n{'='*75}\n{src_text}")
            else:
                renderer.render_doc(term, doc_text, src_text)
        else:
            results = engine.search_modules(term)
            if results:
                renderer.render_search_results(term, results)
            else:
                renderer.render_error(term, "Tópico não encontrado. Tente 'doxoade consult search --deep " + term + "'")
    if is_prof:
        profiler.render_hud()


@consult_group.command("search", help="Busca por palavra-chave nos resumos de módulos locais ou docs HTML.")
@click.argument("keyword", type=str)
@click.option("--deep", "-d", is_flag=True, help="Busca profunda na documentação HTML indexada (FTS5).")
@click.option("--md", is_flag=True, help="Emite o resultado diretamente em Markdown puro (para integração IDE).")
@click.option("--lua", is_flag=True, help="Emite o resultado em formato de tabela Lua nativa para a IDE.")
@click.option("--output", "-o", type=click.Path(dir_okay=False, writable=True), default=None, help="Grava o resultado diretamente no arquivo especificado em UTF-8.")
@click.pass_context
def cmd_search(ctx, keyword, deep, md, lua, output):
    """Busca híbrida inteligente: consulta índice FTS5 e módulos locais do venv."""
    is_prof = ctx.obj.get("shadow_prof", False)
    with ShadowProfiler("consult_search", enabled=is_prof) as profiler:
        engine = ConsultEngine()
        renderer = ConsultRenderer()

        # 1. Tenta consulta no índice FTS5
        fts_results = []
        db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"
        if db_path.exists():
            try:
                from .doc_indexer import DocIndexer
                indexer = DocIndexer(db_path)
                fts_results = indexer.search(keyword, limit=20)
            except Exception:
                fts_results = []

        # 2. Busca de módulos locais do Python/venv (pydoc apropos)
        mod_results = engine.search_modules(keyword)

        # 3. Emissão para a IDE Lite XL (Tabela Lua)
        if lua:
            lines = [
                "return {",
                f'  query = "{_escape_lua_str(keyword)}",',
                f'  total = {len(fts_results) if fts_results else len(mod_results)},',
                "  results = {"
            ]

            if fts_results:
                for path, title, snippet in fts_results:
                    clean_snip = re.sub(r'[\x02\x03]', '', str(snippet or title or ''))
                    lines.append("    {")
                    lines.append(f'      title = "{_escape_lua_str(str(title or path))}",')
                    lines.append(f'      path = "{_escape_lua_str(str(path))}",')
                    lines.append(f'      snippet = "{_escape_lua_str(clean_snip)}"')
                    lines.append("    },")
            else:
                for mod_name, desc in mod_results:
                    clean_desc = desc if desc else mod_name
                    lines.append("    {")
                    lines.append(f'      title = "{_escape_lua_str(mod_name)}",')
                    lines.append(f'      path = "{_escape_lua_str(mod_name)}",')
                    lines.append(f'      snippet = "{_escape_lua_str(clean_desc)}"')
                    lines.append("    },")

            lines.append("  }")
            lines.append("}")
            out_content = "\n".join(lines)

            if output:
                out_p = Path(output)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(out_content, encoding="utf-8")
            else:
                click.echo(out_content)
            return

        # 4. Emissão em Markdown (se solicitado)
        if md:
            if fts_results:
                from .doc_indexer import DocIndexer
                out_content = DocIndexer(db_path).generate_search_markdown(keyword, limit=20)
            else:
                out_content = _format_modules_markdown(keyword, mod_results)

            if output:
                out_p = Path(output)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(out_content, encoding="utf-8")
            else:
                click.echo(out_content)
            return

        # 5. Renderização visual no terminal (Rich)
        if deep and fts_results:
            renderer.render_deep_search_results(keyword, fts_results)
        elif mod_results:
            renderer.render_search_results(keyword, mod_results)
        elif fts_results:
            renderer.render_deep_search_results(keyword, fts_results)
        else:
            renderer.render_error(keyword, f"Nenhum resultado encontrado para '{keyword}'.")

    if is_prof:
        profiler.render_hud()


@consult_group.command("read", help="Converte e exibe um documento HTML ou docstring de módulo em Markdown puro.")
@click.argument("doc_path", type=str)
@click.option("--output", "-o", type=click.Path(dir_okay=False, writable=True), default=None, help="Grava o resultado diretamente no arquivo especificado em UTF-8.")
def cmd_read(doc_path, output):
    """Lê um arquivo HTML ou docstring do objeto e gera Markdown para a IDE."""
    md_content = None

    # 1. Tenta ler via indexador de HTML
    db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"
    if db_path.exists():
        try:
            from .doc_indexer import DocIndexer
            indexer = DocIndexer(db_path)
            md_content = indexer.read_doc_as_markdown(doc_path)
        except Exception:
            md_content = None

    # 2. Se não era HTML, tenta resolver como módulo ou objeto Python
    if not md_content:
        engine = ConsultEngine()
        obj = engine.resolve_object(doc_path)
        if obj:
            doc_text = engine.get_docstring(obj)
            src_text = engine.get_source(obj)
            md_content = f"# 📖 `{doc_path}`\n\n```python\n{doc_text}\n```\n"
            if src_text:
                md_content += f"\n## 💻 Código Fonte\n\n```python\n{src_text}\n```\n"

    if md_content:
        if output:
            out_p = Path(output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(md_content, encoding="utf-8")
        else:
            click.echo(md_content)
    else:
        click.secho(f"Documento ou módulo não localizado: {doc_path}", fg="red")


@consult_group.command("index", help="🗃️ Indexa a documentação HTML local do Python para busca profunda (FTS5).")
@click.option("--force", "-f", is_flag=True, help="Força a reindexação completa de todos os arquivos HTML.")
@click.pass_context
def cmd_index(ctx, force):
    is_prof = ctx.obj.get("shadow_prof", False)
    with ShadowProfiler("consult_index", enabled=is_prof) as profiler:
        from .doc_indexer import DocIndexer
        db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"
        indexer = DocIndexer(db_path)
        indexer.build_index(force=force)
    if is_prof:
        profiler.render_hud()


@consult_group.command("keywords", help="Lista as palavras-chave reservadas do Python.")
def cmd_keywords():
    import keyword
    renderer = ConsultRenderer()
    renderer.render_info("Palavras-chave do Python", ", ".join(keyword.kwlist))


@consult_group.command("symbols", help="Lista os símbolos especiais do Python.")
def cmd_symbols():
    import pydoc
    renderer = ConsultRenderer()
    try:
        symbols_text = pydoc.render_doc("symbols", renderer=pydoc.plaintext)
        renderer.render_doc("Símbolos Python", symbols_text)
    except Exception:
        renderer.render_error("symbols", "Não foi possível carregar a lista de símbolos via pydoc.")

@consult_group.command("ingest", help="📥 Indexa datasets educacionais (suporta caminho local ou URL).")
@click.argument("source", type=str, default="cheatsheet")
@click.option("--limit", "-l", type=int, default=0, help="Limita o número de registros (útil para testes).")
@click.pass_context
def cmd_ingest(ctx, source: str, limit: int):
    """Orquestrador Zeus para ingestão automática de conhecimento."""
    is_prof = ctx.obj.get("shadow_prof", False)
    
    # Presets de fallback (URLs públicas)
    PRESETS = {
        "cheatsheet": {
            "url": "https://raw.githubusercontent.com/gto76/python-cheatsheet/main/README.md",
            "name": "Python_Cheatsheet_MD",
        }
    }

    source_path = Path(source)
    
    # Roteamento Inteligente de Fonte
    if source in PRESETS:
        target_source = PRESETS[source]["url"]
        dataset_name = PRESETS[source]["name"]
    elif source.startswith("http"):
        target_source = source
        dataset_name = source.split("/")[-1].split("?")[0] or "custom_dataset"
    elif source_path.exists() and source_path.is_file():
        target_source = str(source_path.resolve())
        dataset_name = source_path.stem # Ex: "stack_edu_python"
    else:
        click.secho(f"❌ Fonte '{source}' não reconhecida. Use um preset, uma URL direta ou um caminho de arquivo local válido.", fg="red")
        return

    from .dataset_ingestor import DatasetIngestor
    from .doc_indexer import DocIndexer
    
    db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"
    
    # Garante que a tabela FTS5 existe
    indexer = DocIndexer(db_path)
    indexer.init_db()
    
    ingestor = DatasetIngestor(db_path)
    
    with ShadowProfiler("consult_ingest", enabled=is_prof) as profiler:
        ingestor.ingest(target_source, dataset_name, limit=limit)
        if is_prof:
            profiler.render_hud()
