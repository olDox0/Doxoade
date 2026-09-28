# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/cmd_consult.py
"""
⚡ ZEUS — Roteador CLI do Subsistema Doxoade Consult.
"""
import click
from pathlib import Path
from .consult_engine import ConsultEngine
from .consult_renderer import ConsultRenderer
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
@click.option("--md", is_flag=True, help="Emite o resultado diretamente em Markdown puro (para integração IDE).")
@click.option("--lua", is_flag=True, help="Emite o resultado em formato de tabela Lua nativa para a IDE.")
@click.option("--output", "-o", type=click.Path(dir_okay=False, writable=True), default=None, help="Grava o resultado diretamente no arquivo especificado em UTF-8.")
@click.pass_context
def cmd_search(ctx, keyword, deep, md, lua, output):
    is_prof = ctx.obj.get("shadow_prof", False)
    with ShadowProfiler("consult_search", enabled=is_prof) as profiler:
        engine = ConsultEngine()
        renderer = ConsultRenderer()
        if deep:
            from .doc_indexer import DocIndexer
            db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"
            indexer = DocIndexer(db_path)
            if lua:
                lua_table = indexer.generate_search_lua_table(keyword, limit=20)
                if output:
                    Path(output).write_text(lua_table, encoding="utf-8")
                else:
                    click.echo(lua_table)
                return
            if md:
                markdown_doc = indexer.generate_search_markdown(keyword, limit=20)
                if output:
                    Path(output).write_text(markdown_doc, encoding="utf-8")
                else:
                    click.echo(markdown_doc)
                return
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


@consult_group.command("read", help="Converte e exibe um documento HTML do Python em formato Markdown puro.")
@click.argument("doc_path", type=str)
@click.option("--output", "-o", type=click.Path(dir_okay=False, writable=True), default=None, help="Grava o resultado diretamente no arquivo especificado em UTF-8.")
def cmd_read(doc_path, output):
    """Lê um arquivo de doc e exibe em Markdown para a IDE."""
    from .doc_indexer import DocIndexer
    db_path = Path.home() / ".doxoade" / "consult_docs_fts5.db"
    indexer = DocIndexer(db_path)
    md_content = indexer.read_doc_as_markdown(doc_path)
    if md_content:
        if output:
            Path(output).write_text(md_content, encoding="utf-8")
        else:
            click.echo(md_content)
    else:
        click.secho(f"Documento não localizado: {doc_path}", fg="red")


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
