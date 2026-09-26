# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/cmd_consult.py
"""
⚡ ZEUS — Roteador CLI do Subsistema Doxoade Consult.
Consome o ShadowMatrix oficial de telemetry_systems para telemetria temporal.
"""
import click
from .consult_engine import ConsultEngine
from .consult_renderer import ConsultRenderer

# 🛑 UNIFICAÇÃO: Conexão direta com o motor central do Doxoade
from doxoade.commands.telemetry_systems import ShadowMatrix as ShadowProfiler

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
        "shadow_prof": shadow_prof
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
@click.option("--deep", "-d", is_flag=True, help="Busca profunda na documentação HTML indexada (requer 'doxoade consult index').")
@click.pass_context
def cmd_search(ctx, keyword, deep):
    is_prof = ctx.obj.get("shadow_prof", False)
    with ShadowProfiler("consult_search", enabled=is_prof) as profiler:
        engine = ConsultEngine()
        renderer = ConsultRenderer()
        if deep:
            from .doc_indexer import DocIndexer
            from pathlib import Path
            db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"
            indexer = DocIndexer(db_path)
            results = indexer.search(keyword, limit=15)
            if results:
                renderer.render_deep_search_results(keyword, results)
            else:
                renderer.render_error(keyword, "Nenhum resultado na documentação HTML. Execute 'doxoade consult index' primeiro.")
        else:
            results = engine.search_modules(keyword)
            if results:
                renderer.render_search_results(keyword, results)
            else:
                renderer.render_error(keyword, "Nenhum módulo local encontrado. Tente 'doxoade consult search --deep " + keyword + "'.")

    if is_prof:
        profiler.render_hud()


@consult_group.command("index", help="🗃️ Indexa a documentação HTML local do Python para busca profunda (FTS5).")
@click.pass_context
def cmd_index(ctx):
    is_prof = ctx.obj.get("shadow_prof", False)
    with ShadowProfiler("consult_index", enabled=is_prof) as profiler:
        from .doc_indexer import DocIndexer
        from pathlib import Path
        db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"
        indexer = DocIndexer(db_path)
        indexer.build_index()

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
