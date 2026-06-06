# -*- coding: utf-8 -*-
# doxoade/commands/moduloid_systems/moduloid_acervo.py
""" Dicionário Taxonômico (Inspirado no Relatório Macrothon)
    Mapeia símbolos de código para Significado Operacional   """
import os
import re
import ast
import json
import click
import shutil
import traceback

from pathlib import Path
from datetime import datetime

from doxoade.tools.analysis import analyze_file_structure
from doxoade.tools.doxcolors import Fore, Style
from doxoade.database import get_db_connection

from doxoade.commands.deepcheck_utils import DeepAnalyzer
from doxoade.commands.intelligence_utils import ChiefInsightVisitor
from doxoade.commands.mk_systems.mk_utils import open_in_notepadpp

from doxoade.commands.check import run_check_logic
from doxoade.commands.check_systems.check_io import CheckIO
from doxoade.commands.check_systems.check_state import CheckState
from doxoade.commands.check_systems.check_engine import run_audit_engine

from doxoade.commands.security_systems.maat_engine_integration import run_internal_security_audit

from doxoade.commands.init import _refactor_to_silo

# Configuração de Caminhos
ACERVO_BASE = Path.home() / ".doxoade" / "acervo"
BRICKS_DIR = ACERVO_BASE / "bricks"
TAXONOMIA_OPERACIONAL = {
    "sort":     "Ordenação de Dados",
    "partition":"Divisão Estrutural (Divide & Conquer)",
    "read":     "Leitura de Fluxo (IO)",
    "write":    "Escrita de Fluxo (IO)",
    "json":     "Serialização de Dados (JSON)",
    "buffer":   "Gerenciamento de Memória Volátil",
    "hash":     "Cálculo de Integridade (Checksum)",
    "cache":    "Persistência Temporária",
    "search":   "Busca/Localização",
    "encrypt":  "Segurança/Criptografia",
    "token":    "Processamento de Texto (NLP)",
    "node":     "Estrutura de Grafo/Rede",
    "async":    "Fluxo Assíncrono (Não-Bloqueante)",
    "queue":    "Fila de Processamento (FIFO)",
    "put":      "Inserção em Buffer",
    "get":      "Extração de Buffer",
    "gather":   "Orquestração Paralela",
    "producer": "Gerador de Fluxo (Input Source)",
    "consumer": "Processador de Fluxo (Output Sink)"
}

MAPA_DE_TIPOS = {
    "list":  "Coleção Sequencial",
    "dict":  "Estrutura de Mapa (Key-Value)",
    "str":   "Fluxo de Texto",
    "int":   "Valor Numérico Inteiro",
    "float": "Valor de Ponto Flutuante",
    "Path":  "Referência de Arquivo",
    "bytes": "Bloco de Dados Binários",
    "bool":  "Sinalizador Lógico (Verdadeiro/Falso)",
    "Queue": "Fila de Mensagens (Buffer)",
    "None":  "Sem retorno (Procedimento)"
}

DEDUCAO_POR_RELACAO = {
    ".get(":        "Item extraído de Fila/Buffer",
    ".read(":       "Conteúdo lido de Fluxo",
    ".pop()":       "Elemento removido de Coleção",
    "json.load":    "Objeto estruturado (JSON)",
    "partition(":   "Índice de pivô (Inteiro)",
    "asyncio.Queue":"Instância de Fila (Buffer)",
    "bytearray(":   "Buffer de Memória Bruta",
    "open(":        "Handle de Arquivo"
}

class AcervoEngine:
    def __init__(self):
        BRICKS_DIR.mkdir(parents=True, exist_ok=True)
        conn = get_db_connection()
        try:
            # Atualização da Tabela para métricas de qualidade
            conn.execute('ALTER TABLE moduloid_acervo ADD COLUMN quality_score INTEGER DEFAULT 0;')
            conn.execute('ALTER TABLE moduloid_acervo ADD COLUMN security_status TEXT DEFAULT "N/A";')
            conn.execute('ALTER TABLE moduloid_acervo ADD COLUMN health_report TEXT;') # JSON com detalhes
        except Exception: pass # Colunas já existem
        
        # [AUTO-HEAL] Garante a tabela base
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS moduloid_acervo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT,
                    filename TEXT,
                    docstring TEXT,
                    capabilities TEXT,
                    version INTEGER DEFAULT 1,
                    last_updated DATETIME,
                    origin_project TEXT,
                    quality_score INTEGER DEFAULT 0,
                    security_status TEXT DEFAULT "N/A",
                    health_report TEXT
                );
            ''')
            conn.commit()
        except Exception: pass
        finally: conn.close()

    def build_system(self, module_names, build_dir="build"):
        """Monta um sistema funcional a partir de Moduloids do Acervo."""
        build_path = Path(os.getcwd()) / build_dir
        build_path.mkdir(exist_ok=True)
        
        click.secho(f"[*] Iniciando montagem do sistema em: '{build_dir}/'", fg="cyan")
        
        conn = get_db_connection()
        macrothon_flow = [] # Onde o fluxo será construído
        
        for name in module_names:
            row = conn.execute("SELECT filename FROM moduloid_acervo WHERE name = ?", (name,)).fetchone()
            if not row:
                click.secho(f"  [!] Módulo '{name}' não encontrado no acervo.", fg="yellow")
                continue
            
            # 1. Transplante do Brick
            src_file = BRICKS_DIR / row[0]
            dest_file = build_path / row[0]
            shutil.copy2(src_file, dest_file)
            click.echo(f"  {Fore.GREEN}✔{Style.RESET_ALL} Moduloid '{name}' injetado.")
            
            # 2. Refatoração para Autonomia
            content = dest_file.read_text(encoding='utf-8')
            dest_file.write_text(_refactor_to_silo(content))
            
            # 3. Adiciona ao fluxo do Macrothon
            macrothon_flow.append(name)
            
        conn.close()
        
        # 4. Geração do Blueprint (main.macrothon)
        if macrothon_flow:
            blueprint_path = build_path / "main.macrothon"
            flow_str = " -> ".join(macrothon_flow)
            blueprint_content = (
                f"# Blueprint gerado pelo Doxoade Build System\n"
                f"# Data: {datetime.now().isoformat()}\n\n"
                f"# Fluxo de Execução Sugerido:\n"
                f"FLOW: {flow_str}"
            )
            blueprint_path.write_text(blueprint_content)
            click.secho(f"✅ Blueprint 'main.macrothon' gerado em '{build_dir}/'.", fg="green", bold=True)
        else:
            click.secho("✘ Nenhum módulo válido para montar o sistema.", fg="red")

    def _classify_functions(self, funcs):
        """Algoritmo de Classificação Determinística baseado em Dicionário."""
        tags = set()
        for f in funcs:
            f_low = f.lower()
            for key, label in TAXONOMIA_OPERACIONAL.items():
                if key in f_low:
                    tags.add(label)
        return " | ".join(tags) if tags else "Módulo funcional genérico."

    def _analyze_brick(self, file_path):
        """Analisa o Moduloid com proteção contra RecursionError (MergeSort Fix)."""
        try:
            content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(content)
            
            visitor = ChiefInsightVisitor()
            visitor.visit(tree)
            
            funcs = [f['name'] for f in visitor.stats['functions']]
            
            # Tenta extrair IO, mas protege contra falhas no Deepcheck (Recursividade)
            try:
                in_n, out_n = self._extract_io_nuances(tree)
            except Exception as io_err:
                click.secho(f"   [!] Aviso de IO em {Path(file_path).name}: {io_err}", fg="yellow")
                in_n, out_n = " [In: ?]", " [Out: ?]"
            
            tags = set()
            for f in funcs:
                for key, label in TAXONOMIA_OPERACIONAL.items():
                    if key in f.lower(): tags.add(label)
            
            prop = (" | ".join(tags) if tags else "Moduloid.") + in_n + out_n
            
            # Executa Auditoria de Qualidade Corrigida
            score, sec, health = self._audit_quality(file_path)

            return {
                "doc": ast.get_docstring(tree) or prop,
                "capabilities": json.dumps(funcs),
                "name": Path(file_path).stem,
                "score": score, "sec": sec, "health": json.dumps(health)
            }
        except Exception:
            click.secho(f"\n❌ ERRO NA ANÁLISE AST ({Path(file_path).name})", fg="red")
            click.echo(traceback.format_exc())
            return None

    def _extract_io_nuances(self, tree):
        all_ins, all_outs = set(), set()
        for node in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            analyzer = DeepAnalyzer()
            analyzer.visit(node)
            for param, meta in analyzer.params.items():
                all_ins.add(f"{param}:{MAPA_DE_TIPOS.get(meta['type'], meta['type'])}")
            if not analyzer.returns:
                all_outs.add("Procedimento (In-place)")
            else:
                for r in analyzer.returns:
                    val = r['value']
                    trad = "Dado Processado"
                    for op, _, alvo in analyzer.flow_map:
                        if alvo == val:
                            for pat, lab in DEDUCAO_POR_RELACAO.items():
                                if pat in op: trad = lab; break
                    if val in ["True", "False"]: trad = "Sinalizador Lógico"
                    all_outs.add(trad)
        return f" [In: {', '.join(all_ins)}]" if all_ins else "", f" [Out: {' | '.join(all_outs)}]"

    def _analyze_brick(self, file_path):
        try:
            content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(content)
            visitor = ChiefInsightVisitor(); visitor.visit(tree)
            funcs = [f['name'] for f in visitor.stats['functions']]
            in_n, out_n = self._extract_io_nuances(tree)
            
            tags = set()
            for f in funcs:
                for key, label in TAXONOMIA_OPERACIONAL.items():
                    if key in f.lower(): tags.add(label)
            
            desc_auto = (" | ".join(tags) if tags else "Moduloid.") + in_n + out_n
            score, sec, health = self._audit_quality(file_path)

            return {
                "doc": ast.get_docstring(tree) or desc_auto,
                "capabilities": json.dumps(funcs),
                "name": Path(file_path).stem,
                "score": score, "sec": sec, "health": json.dumps(health)
            }
        except: return None

    def refresh_acervo(self):
        """Refresh Total: Força o banco a espelhar a qualidade atual do disco."""
        click.secho("[*] Sincronizando Qualidade e Score do Acervo...", fg="cyan")
        conn = get_db_connection()
        count = 0
        
        # Sincroniza via arquivo físico para garantir que tudo no cofre seja auditado
        for brick_file in BRICKS_DIR.glob("*.py"):
            meta = self._analyze_brick(brick_file)
            if meta:
                conn.execute('''
                    UPDATE moduloid_acervo 
                    SET docstring = ?, capabilities = ?, quality_score = ?, 
                        security_status = ?, health_report = ?, last_updated = ?
                    WHERE name = ?
                ''', (meta['doc'], meta['capabilities'], meta['score'], 
                      meta['sec'], meta['health'], datetime.now().isoformat(), meta['name']))
                click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} {meta['name']} -> Score: {meta['score']}")
                count += 1
        
        conn.commit()
        conn.close()
        click.secho(f"✅ Qualidade sincronizada para {count} Moduloids.", fg="green", bold=True)

    def save_to_acervo(self, file_path, category="custom", custom_name=None):
        """Salva ou atualiza um moduloid no cofre."""
        file_path = Path(file_path)
        if not file_path.exists():
            click.secho(f"✘ Arquivo não encontrado: {file_path}", fg="red")
            return

        click.echo(f"[*] Analisando Moduloid: {Fore.CYAN}{file_path.name}{Style.RESET_ALL}...")
        meta = self._analyze_brick(file_path)
        
        if not meta:
            click.secho("✘ Falha na análise AST do arquivo.", fg="red")
            return

        # Define o nome: Nome customizado ou o nome do arquivo
        final_name = custom_name if custom_name else meta['name']
        dest_filename = f"{final_name}.py"
        dest_path = BRICKS_DIR / dest_filename
        
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT version, origin_project FROM moduloid_acervo WHERE name = ?", (final_name,)).fetchone()
            
            if row:
                version = row[0] + 1
                action_msg = f"atualizado para v{version}"
            else:
                version = 1
                action_msg = "imortalizado (v1)"
            
            conn.execute('''
                INSERT OR REPLACE INTO moduloid_acervo 
                (name, category, filename, docstring, capabilities, version, last_updated, origin_project)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (final_name, category, dest_filename, meta['doc'], meta['capabilities'], 
                  version, datetime.now().isoformat(), os.getcwd()))
            
            shutil.copy2(file_path, dest_path)
            conn.commit()
            
            click.secho(f"✅ Moduloid '{final_name}' {action_msg} no acervo!", fg="green", bold=True)
        finally:
            conn.close()

    def list_acervo(self, search=None, func_filter=None):
        conn = get_db_connection()
        query = "SELECT * FROM moduloid_acervo"
        params = []
        if search or func_filter:
            query += " WHERE "
            if search:
                query += "(name LIKE ? OR category LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])
            if func_filter:
                if search: query += " AND "
                query += "capabilities LIKE ?"
                params.append(f"%{func_filter}%")
        
        rows = conn.execute(query, params).fetchall(); conn.close()
        if not rows:
            click.echo(Fore.YELLOW + "[-] Nada encontrado."); return

        click.secho(f"\n--- 🏛️  ACERVO DE MODULOIDS ({len(rows)} Bricks) ---", fg="cyan", bold=True)
        for r in rows:
            funcs = json.loads(r['capabilities'])
            score = r['quality_score']
            color_score = Fore.GREEN if score >= 80 else Fore.YELLOW if score >= 50 else Fore.RED
            color_sec = Fore.GREEN if r['security_status'] == "VERIFICADO" else Fore.RED
            
            click.echo(f"\n{Fore.GREEN}📦 {r['name']} {Fore.WHITE}(v{r['version']}) "
                       f"{color_score}[Score: {score}]{Style.RESET_ALL} "
                       f"{color_sec}[🛡️ {r['security_status']}]{Style.RESET_ALL}")
            
            if r['health_report']:
                h = json.loads(r['health_report'])
                click.echo(f"   {Style.DIM}⚖️ {h['size_kb']}KB | {h['lines']} linhas | ⚠️ {h['issues']} avisos")
            
            proposito = r['docstring'].split(" [In:")[0]
            click.echo(f"   {Fore.CYAN}Propósito: {Style.RESET_ALL}{proposito}")
            
            in_m = re.search(r"\[In: (.*?)\]", r['docstring'])
            if in_m: click.echo(f"       {Fore.LIGHTGREEN_EX}IN  ➔ {in_m.group(1)}{Style.RESET_ALL}")
            out_m = re.search(r"\[Out: (.*?)\]", r['docstring'])
            if out_m: click.echo(f"       {Fore.LIGHTRED_EX}OUT ➔ {out_m.group(1)}{Style.RESET_ALL}")
            
            funcs_fmt = [f"{Fore.YELLOW}{Style.BRIGHT}{f}{Style.RESET_ALL}" if func_filter and func_filter.lower() in f.lower() else f for f in funcs]
            click.echo(f"   {Fore.WHITE}ƒ {Style.DIM}{', '.join(funcs_fmt[:8])}")
        click.echo("")

    def pull_to_project(self, name, target_dir="utils", open_editor=False):
        """Transplanta um Moduloid do acervo para o projeto atual."""
        conn = get_db_connection()
        row = conn.execute("SELECT filename FROM moduloid_acervo WHERE name = ?", (name,)).fetchone()
        conn.close()

        if not row:
            click.secho(f"✘ Moduloid '{name}' não encontrado no acervo.", fg="red")
            return

        src = BRICKS_DIR / row[0]
        dest_dir = Path(os.getcwd()) / target_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / row[0]

        shutil.copy2(src, dest)
        
        # Ajuste de Silo (Importado do init.py logic)
        from doxoade.commands.init import _refactor_to_silo
        content = dest.read_text(encoding='utf-8')
        dest.write_text(_refactor_to_silo(content))

        click.secho(f"🚀 Moduloid '{name}' injetado com sucesso em {target_dir}/", fg="green")
        
        if open_editor:
            open_in_notepadpp([str(dest)])

    def _audit_quality(self, file_path):
        """Executa a bateria de testes usando o Estado Oficial do Doxoade."""
        try:
            # 1. Prepara o Gabinete de IO e Estado do Doxoade
            io_manager = CheckIO(str(file_path))
            state = CheckState(root=io_manager.project_root, target_path=io_manager.target_abs)
            
            # 2. Roda o Motor de Auditoria Real (Casa de Máquinas)
            run_audit_engine(state, io_manager, fast=True, no_cache=True)
            
            # 3. Auditoria de Segurança Aegis
            sec_findings = run_internal_security_audit(os.path.dirname(file_path), [str(file_path)])
            
            report = {
                "size_kb": round(os.path.getsize(file_path)/1024, 2),
                "lines": sum(1 for _ in open(file_path, 'rb')),
                "issues": len(state.findings),
                "security_vulns": len(sec_findings)
            }
            
            # Score Doxoade Chief-Gold
            score = 100 - (report["issues"] * 5) - (report["security_vulns"] * 25)
            if report["lines"] > 200: score -= 10
            
            return max(0, score), ("VERIFICADO" if report["security_vulns"] == 0 else "CRÍTICO"), report
        except Exception as e:
            click.secho(f"   [!] Falha no Diagnóstico de Qualidade: {e}", fg="red")
            return 0, "ERRO", {}


# CLI REGISTRY
@click.group('moduloid')
def moduloid_group():
    """🧩 Gestão de Moduloids e Acervo Técnico (Chief-Gold)."""
    pass

@moduloid_group.command('save')
@click.argument('path')
@click.option('--cat', default='custom', help='Categoria do modulo')
@click.option('--name', '-n', help='Nome customizado para o Moduloid no acervo')
def moduloid_save(path, cat, name):
    """Guarda um modulo no acervo central."""
    AcervoEngine().save_to_acervo(path, cat, custom_name=name)

@moduloid_group.command('list')
@click.option('--search', '-s', help='Buscar por nome ou categoria')
@click.option('--func', '-f', help='Buscar por nome de função interna')
def moduloid_list(search, func):
    """Lista o acervo. Ex: list --func partition"""
    AcervoEngine().list_acervo(search, func_filter=func)

@moduloid_group.command('pull')
@click.argument('name')
@click.option('--dir', 'target_dir', default='utils', help='Pasta de destino')
@click.option('--up', is_flag=True, help='Abre o arquivo no editor após o transplante')
def moduloid_pull(name, target_dir, up):
    """Transplanta um moduloid para o projeto atual."""
    AcervoEngine().pull_to_project(name, target_dir, open_editor=up)
    
@moduloid_group.command('refresh')
def moduloid_refresh():
    """Atualiza o acervo com as novas regras taxonômicas."""
    AcervoEngine().refresh_acervo()
    
@moduloid_group.command('build')
@click.argument('modules', nargs=-1, required=True)
@click.option('--dir', 'build_dir', default='build', help='Diretório de montagem do sistema.')
def moduloid_build(modules, build_dir):
    """Monta um sistema a partir de bricks do acervo para uso do Macrothon."""
    AcervoEngine().build_system(modules, build_dir)