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
from typing import List, Tuple, Dict, Type

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


@consult_group.command("search", help="Busca unificada por palavra-chave no FTS5.")
@click.argument("keyword", type=str)
@click.option("--deep", "-d", is_flag=True, help="Compatibilidade legada (busca profunda ativada por padrão).")
@click.option("--md", is_flag=True, help="Emite o resultado diretamente em Markdown puro para a IDE.")
@click.option("--lua", is_flag=True, help="Emite o resultado em formato de tabela Lua nativa para a IDE.")
@click.option("--output", "-o", type=click.Path(dir_okay=False, writable=True), default=None, help="Grava a saída em arquivo UTF-8.")
@click.pass_context
def cmd_search(ctx, keyword, deep, md, lua, output):
    is_prof = ctx.obj.get("shadow_prof", False)
    with ShadowProfiler("consult_search", enabled=is_prof) as profiler:
        from .doc_indexer import DocIndexer
        renderer = ConsultRenderer()

        indexer = DocIndexer()
        fts_results = indexer.search(keyword, limit=25)

        # Emissão nativa para o Doxly/Lite XL
        if lua:
            lines = [
                "return {",
                f'  query = "{_escape_lua_str(keyword)}",',
                f'  total = {len(fts_results)},',
                "  results = {"
            ]
            for path, title, snippet in fts_results:
                clean_snip = re.sub(r'[\x02\x03]', '', str(snippet or title or '')).replace("\r", "").replace("\n", " ")
                lines.append("    {")
                lines.append(f'      title = "{_escape_lua_str(str(title or path))}",')
                lines.append(f'      path = "{_escape_lua_str(str(path))}",')
                lines.append(f'      snippet = "{_escape_lua_str(clean_snip)}"')
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

        if md:
            lines = [
                f"# 🔍 Doxoade Consult — Resultados: `{keyword}`",
                f"> 📊 **Encontrados:** `{len(fts_results)}` documentos relevantes",
                "---",
                ""
            ]
            for path, title, snippet in fts_results:
                clean_snip = snippet.replace("\x02", "**`").replace("\x03", "`**").replace("\r", "")
                lines.append(f"### 📄 {title}")
                lines.append(f"↳ `{path}`\n")
                lines.append(f"> {clean_snip}\n")
                lines.append("---\n")
            out_content = "\n".join(lines)
            if output:
                out_p = Path(output)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(out_content, encoding="utf-8")
            else:
                click.echo(out_content)
            return

        if fts_results:
            renderer.render_deep_search_results(keyword, fts_results)
        else:
            renderer.render_error(keyword, f"Nenhum resultado encontrado para '{keyword}'.")

    if is_prof:
        profiler.render_hud()


@consult_group.command("read", help="Exibe o conteúdo integral de um documento pelo path.")
@click.argument("doc_path", type=str)
@click.option("--output", "-o", type=click.Path(dir_okay=False, writable=True), default=None, help="Grava o resultado diretamente em arquivo UTF-8.")
def cmd_read(doc_path, output):
    from .doc_indexer import DocIndexer
    indexer = DocIndexer()
    md_content = indexer.read_doc_as_markdown(doc_path)

    if md_content:
        if output:
            out_p = Path(output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(md_content, encoding="utf-8")
        else:
            click.echo(md_content)
    else:
        click.secho(f"Documento não localizado no banco: {doc_path}", fg="red")


@consult_group.command("index", help="🗃️ Indexa e unifica todas as fontes de documentação (CPython + Cheatsheet).")
@click.option("--force", "-f", is_flag=True, help="Força a reconstrução total da base unificada.")
@click.pass_context
def cmd_index(ctx, force):
    is_prof = ctx.obj.get("shadow_prof", False)
    with ShadowProfiler("consult_index", enabled=is_prof) as profiler:
        from .doc_indexer import DocIndexer
        indexer = DocIndexer()
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

# ─── REGISTRY DE CONVERTERS ─────────────────────────────────────────────
# Mapeamento central de presets → classes de converter canônico.
# Cada converter deve retornar um Path de arquivo .jsonl em
# ~/.doxoade/consult/canonical/ que será ingerido pelo CanonicalDB.
def _get_converter_registry() -> Dict[str, str]:
    return {
        "cheatsheet":     "doxoade.commands.consult_systems.cheatsheet_converter:CheatsheetConverter",
        "byte_of_python": "doxoade.commands.consult_systems.converters.byte_of_python_converter:ByteOfPythonConverter",
        "30days":         "doxoade.commands.consult_systems.converters.thirty_days_converter:ThirtyDaysConverter",
        "py4e":           "doxoade.commands.consult_systems.converters.py4e_converter:Py4eConverter",
        "the_algorithms": "doxoade.commands.consult_systems.converters.the_algorithms_converter:TheAlgorithmsConverter",
        "automate":       "doxoade.commands.consult_systems.converters.automate_boring_stuff_converter:AutomateBoringStuffConverter",
        "peps":           "doxoade.commands.consult_systems.converters.peps_converter:PepsConverter",
        "cosmic":         "doxoade.commands.consult_systems.converters.cosmic_python_converter:CosmicPythonConverter",
        "patterns":       "doxoade.commands.consult_systems.converters.design_patterns_converter:DesignPatternsConverter",
        "typeshed":       "doxoade.commands.consult_systems.converters.typeshed_converter:TypeshedConverter",
        "automation":     "doxoade.commands.consult_systems.converters.click_rich_pytest_converter:ClickRichPytestConverter",
        "git":            "doxoade.commands.consult_systems.converters.git_github_converter:GitGithubConverter",
        "30seconds":      "doxoade.commands.consult_systems.converters.thirty_seconds_converter:ThirtySecondsConverter",
        "ecosystem":      "doxoade.commands.consult_systems.converters.devdocs_bridge_converter:DevDocsBridgeConverter",
    }

def _resolve_converter(name: str):
    """Importa o converter só no momento do uso."""
    from importlib import import_module
    path = _get_converter_registry()[name]
    mod_path, cls_name = path.split(":")
    mod = import_module(mod_path)
    return getattr(mod, cls_name)


def _ingest_one(name: str, converter) -> int:
    from .canonical_db import CanonicalDB
    click.secho(f"\n▶ [{name}] Executando converter...", fg="cyan", bold=True)
    try:
        canonical_file = converter.convert()
    except Exception as e:
        click.secho(f"  ✖ [{name}] Falha no converter: {e}", fg="red")
        return 0
    if not canonical_file or not canonical_file.exists():
        click.secho(f"  ✖ [{name}] Converter não produziu arquivo canônico.", fg="red")
        return 0
    db = CanonicalDB()
    count = db.ingest_jsonl(canonical_file)
    click.secho(f"  ✔ [{name}] {count} registros indexados no Hades.", fg="green")
    return count


@consult_group.command("ingest", help="📥 Indexa datasets canônicos normalizados.")
@click.argument("source", type=str, default="cheatsheet")
@click.option("--limit", "-l", type=int, default=0,
              help="Limita o nº de registros por fonte (0 = sem limite).")
@click.pass_context
def cmd_ingest(ctx, source: str, limit: int):
    is_prof = ctx.obj.get("shadow_prof", False) if ctx.obj else False
    registry = _get_converter_registry()

    if source == "all":
        targets = list(registry.keys())
    elif source in registry:
        targets = [source]
    else:
        available = ", ".join(sorted(registry.keys())) + ", all"
        click.secho(
            f"❌ Fonte '{source}' não reconhecida.\n"
            f"   Opções: {available}",
            fg="red"
        )
        return

    total = 0
    with ShadowProfiler("consult_ingest", enabled=is_prof) as profiler:
        for name in targets:
            try:
                converter = _resolve_converter(name)()
            except Exception as e:
                click.secho(f"  ✖ [{name}] Falha no import: {e}", fg="red")
                continue
            total += _ingest_one(name, converter)
        click.secho(
            f"\n✔ [HADES] Ingestão concluída: {total} registros totais "
            f"de {len(targets)} fonte(s).",
            fg="green", bold=True
        )
    if is_prof:
        profiler.render_hud()
