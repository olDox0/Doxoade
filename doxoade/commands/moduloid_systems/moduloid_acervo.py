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
# [DOX-UNUSED] import traceback

from pathlib import Path
from datetime import datetime

# [DOX-UNUSED] from doxoade.tools.analysis import analyze_file_structure
from doxoade.tools.doxcolors import Fore, Style
from doxoade.commands.deepcheck_utils import DeepAnalyzer
from doxoade.commands.intelligence_systems.intelligence_utils import ChiefInsightVisitor
from doxoade.commands.mk_systems.mk_utils import open_in_notepadpp
# [DOX-UNUSED] from doxoade.commands.check import run_check_logic
from doxoade.commands.check_systems.check_io import CheckIO
from doxoade.commands.check_systems.check_state import CheckState
from doxoade.commands.check_systems.check_engine import run_audit_engine
from doxoade.commands.security_systems.maat_engine_integration import run_internal_security_audit
from doxoade.commands.init import _refactor_to_silo

from doxoade.core_database import get_db_connection, get_active_db_path, DB_FILE
from doxoade.tools.core_locator import CORE_ROOT

from doxoade.tools.alexandria.engine import alexandria_write
try:
    from rich.console import Console
    from rich.syntax import Syntax
    from rich.panel import Panel
    HAS_RICH = True
except ImportError:
    print('❌ Dependência faltando. Instalando rich...')
    HAS_RICH = False

# Configuração de Caminhos
ACERVO_BASE = CORE_ROOT / "data" / "acervo"
BRICKS_DIR = ACERVO_BASE / "bricks"
BRICKS_DIR.mkdir(parents=True, exist_ok=True)

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
    "consumer": "Processador de Fluxo (Output Sink)",
    "math":      "Cálculo Numérico/IA",
    "bridge":    "Conector Multilinguagem (Nativo)",
    "sqlite":    "Persistência em Banco de Dados",
    "pack":      "Compressão/Redução de Volume",
    "compress":  "Otimização de Armazenamento"
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
    "partition(":   "Índice de pivô (Inteiro)", # CONSERTADO: ADICIONADA VÍRGULA
    "asyncio.Queue":"Instância de Fila (Buffer)",
    "bytearray(":   "Buffer de Memória Bruta",
    "open(":        "Handle de Arquivo",
    "mergeSort(":   "Coleção Ordenada (Recursiva)" # Adicionado para o MergeSort
}

class AcervoEngine:
    def __init__(self):
        BRICKS_DIR.mkdir(parents=True, exist_ok=True)
        conn = get_db_connection()
        try:
            # Atualização da Tabela para métricas de qualidade
            alexandria_write('ALTER TABLE moduloid_acervo ADD COLUMN quality_score INTEGER DEFAULT 0;')
            alexandria_write('ALTER TABLE moduloid_acervo ADD COLUMN security_status TEXT DEFAULT "N/A";')
            alexandria_write('ALTER TABLE moduloid_acervo ADD COLUMN health_report TEXT;') # JSON com detalhes
        except Exception: pass # Colunas já existem
        
        # [AUTO-HEAL] Garante a tabela base
        try:
            alexandria_write('''
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
        """DNA do Moduloid: Inteligência de Relação e Qualidade."""
        try:
            content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(content)
            
            # 1. Identidade e Funções
            visitor = ChiefInsightVisitor(); visitor.visit(tree)
            funcs = [f['name'] for f in visitor.stats['functions']]
            
            # 2. Nuances de IO (In/Out)
            in_n, out_n = self._extract_io_nuances(tree)
            
            # 3. GERAÇÃO SEMÂNTICA (O Fim do 'Moduloid.')
            doc = ast.get_docstring(tree)
            if not doc:
                tags = set()
                # Varre o nome das funções e o nome do arquivo em busca de significado
                for termo in (funcs + [Path(file_path).stem]):
                    for key, label in TAXONOMIA_OPERACIONAL.items():
                        if key in termo.lower():
                            tags.add(label)
                
                # Constrói uma descrição baseada no que foi achado
                if tags:
                    doc = "Capacidades: " + " | ".join(sorted(tags))
                else:
                    doc = "Módulo funcional genérico."

            # 4. Auditoria de Qualidade
            score, sec_status, health = self._audit_quality(file_path)
            
            return {
                "name": Path(file_path).stem,
                "doc": doc + in_n + out_n, # Une Propósito + Contrato
                "capabilities": json.dumps(funcs),
                "score": score,
                "sec": sec_status,
                "health": json.dumps(health)
            }
        except Exception:
            return None

    def _extract_io_nuances(self, tree):
        """Dedução de IO por Linhagem: var -> origem (Padrão Maestro)."""
        ins, outs = set(), set()
        
        for node in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            analyzer = DeepAnalyzer()
            analyzer.visit(node)
            
            # 1. Mapa de Linhagem Local (Quem criou quem?)
            mapa_linhagem = {}
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            val_repr = ast.unparse(stmt.value)
                            # Verifica se o valor atribuído vem de uma relação conhecida
                            for pattern, label in DEDUCAO_POR_RELACAO.items():
                                if pattern in val_repr:
                                    mapa_linhagem[target.id] = label

            # 2. Entradas (Argumentos)
            for param, meta in analyzer.params.items():
                tipo = MAPA_DE_TIPOS.get(meta['type'], meta['type'])
                ins.add(f"{param}:{tipo}")

            # 3. Saídas (Retorno com rastreio de origem)
            if not analyzer.returns:
                outs.add("Procedimento (In-place)")
            else:
                for r in analyzer.returns:
                    val_id = r['value']
                    # Se o que está no return (ex: "item") estiver no nosso mapa de linhagem
                    if val_id in mapa_linhagem:
                        outs.add(mapa_linhagem[val_id])
                    else:
                        # Fallback para tipos básicos
                        outs.add(MAPA_DE_TIPOS.get(val_id, "Dado Processado"))

        in_str = f" [In: {', '.join(ins)}]" if ins else ""
        out_str = f" [Out: {' | '.join(outs)}]"
        return in_str, out_str

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
        except Exception as e:
            import sys as _dox_sys, os as _dox_os
            from traceback import print_tb as exc_trace
            exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
            f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_n = exc_tb.tb_lineno
            exc_trace(exc_tb)
            print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _analyze_brick\033[0m")
            print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
            return None

    def refresh_acervo(self, force=False):
        """Sincronização Diferencial: Velocidade Industrial."""
        click.secho("[*] Iniciando Smart Refresh (Diferencial)...", fg="cyan")
        conn = get_db_connection()
        conn.row_factory = __import__('sqlite3').Row
        
        # Mapeia estado atual do banco {nome: ultima_atualizacao}
        db_state = {r['name']: r['last_updated'] for r in conn.execute("SELECT name, last_updated FROM moduloid_acervo").fetchall()}
        
        count_upd, count_skip = 0, 0
        
        for brick_file in BRICKS_DIR.glob("*.py"):
            name = brick_file.stem
            mtime = datetime.fromtimestamp(brick_file.stat().st_mtime).isoformat()
            
            # [MTIME-SHIELD] Só processa se o arquivo for mais novo que o registro ou se for 'force'
            if not force and name in db_state and db_state[name] >= mtime:
                count_skip += 1
                continue
            
            meta = self._analyze_brick(brick_file)
            if meta:
                alexandria_write('''
                    UPDATE moduloid_acervo 
                    SET docstring = ?, capabilities = ?, quality_score = ?, 
                        security_status = ?, health_report = ?, last_updated = ?
                    WHERE name = ?
                ''', (meta['doc'], meta['capabilities'], meta['score'], 
                      meta['sec'], meta['health'], mtime, name))
                click.echo(f"   {Fore.GREEN}↻{Style.RESET_ALL} {name} (Score: {meta['score']})")
                count_upd += 1
        
        conn.commit(); conn.close()
        click.secho(f"✅ Sincronia concluída. Atualizados: {count_upd} | Mantidos: {count_skip}", fg="green", bold=True)

    def _sanitize_source(self, file_path):
        """Limpeza Industrial: Prepara o código para o Estado de Ouro."""
        try:
            content = Path(file_path).read_text(encoding='utf-8', errors='ignore')
            lines = content.splitlines()
            # 1. Remove espaços à direita e 2. Filtra linhas vazias excessivas
            clean_lines = [line.rstrip() for line in lines]
            # 3. Garante uma única quebra de linha no final
            final_code = "\n".join(clean_lines).strip() + "\n"
            
            Path(file_path).write_text(final_code, encoding='utf-8')
            return True
        except Exception as e:
            click.echo(f"   [!] Aviso na sanitização: {e}")
            return False

    def save_to_acervo(self, file_path, category="custom", custom_name=None):
        """Salva o Moduloid aplicando a Limpeza Industrial (V40)."""
        file_path = Path(file_path)
        if not file_path.exists(): return click.secho("✘ Arquivo ausente.", fg="red")

        # [NOVO] Limpeza de Pré-Arquivamento
        click.echo(f"[*] Sanitizando Brick: {Fore.YELLOW}{file_path.name}{Style.RESET_ALL}...")
        self._sanitize_source(file_path)

        click.echo(f"[*] Analisando e Auditando: {Fore.CYAN}{file_path.name}{Style.RESET_ALL}...")
        meta = self._analyze_brick(file_path)
        if not meta: return click.secho("✘ Falha crítica na análise.", fg="red")

        final_name = custom_name if custom_name else meta['name']
        dest_path = BRICKS_DIR / f"{final_name}.py"
        
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT version FROM moduloid_acervo WHERE name = ?", (final_name,)).fetchone()
            version = (row[0] + 1) if row else 1
            
            # ═══════════════════════════════════════════════════════════
            #  [FIX-GOLD] Escrita Síncrona (Confirmação Imediata)
            #  Substitui alexandria_write (assíncrono) por conexão direta
            # ═══════════════════════════════════════════════════════════
            conn.execute('''
                INSERT OR REPLACE INTO moduloid_acervo 
                (name, category, filename, docstring, capabilities, version, last_updated, 
                 origin_project, quality_score, security_status, health_report)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (final_name, category, f"{final_name}.py", meta['doc'], meta['capabilities'], 
                  version, datetime.now().isoformat(), os.getcwd(), 
                  meta['score'], meta['sec'], meta['health']))
            conn.commit()  # ← Força commit imediato
            
            shutil.copy2(file_path, dest_path)
            click.secho(f"✅ Moduloid '{final_name}' imortalizado com Score: {meta['score']}", fg="green", bold=True)
        finally:
            conn.close()

    def show_health(self, name):
        """Necropsia de Score: Explica por que o Brick não é 100."""
        conn = get_db_connection()
        row = conn.execute("SELECT health_report, quality_score, security_status FROM moduloid_acervo WHERE name = ?", (name,)).fetchone()
        conn.close()

        if not row: return click.secho(f"✘ Moduloid '{name}' não encontrado.", fg="red")

        h = json.loads(row['health_report']) if row['health_report'] else {}
        click.secho(f"\n--- 🩺 DIAGNÓSTICO DE SAÚDE: {name} ---", fg="magenta", bold=True)
        click.echo(f"  Score Final: {row['quality_score']}/100 | Segurança: {row['security_status']}")
        click.echo(f"  {Style.DIM}─" * 40)
        
        if h.get('issues', 0) > 0:
            click.echo(f"  ⚠️  {Fore.YELLOW}{h['issues']} Avisos de Estilo{Style.RESET_ALL} (-{h['issues']*5} pontos)")
        if h.get('security_vulns', 0) > 0:
            click.echo(f"  🚨 {Fore.RED}{h['security_vulns']} Riscos de Segurança{Style.RESET_ALL} (-{h['security_vulns']*25} pontos)")
        if h.get('lines', 0) > 200:
            click.echo(f"  ⚖️  {Fore.RED}Arquivo Obeso: {h['lines']} linhas{Style.RESET_ALL} (-10 pontos)")
        
        if row['quality_score'] == 100:
            click.secho("\n  🏆 ESTADO DE OURO: Brick em conformidade total.", fg="green")
        else:
            click.echo(f"\n  💡 Dica: Use 'doxoade moduloid view {name}' para revisar o código.")


    def list_acervo(self, search=None, func_filter=None):
        """Lista o patrimônio com UI de Alta Visibilidade (V39)."""
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
        
        rows = conn.execute(query, params).fetchall()
        conn.close()

        if not rows:
            click.echo(Fore.YELLOW + "[-] Nada encontrado com esses critérios.")
            return

        click.secho(f"\n--- 🏛️  ACERVO DE MODULOIDS ({len(rows)} Bricks) ---", fg="cyan", bold=True)
        for r in rows:
            funcs = json.loads(r['capabilities'])
            score = r['quality_score']
            
            # Definição de Cores Dinâmicas
            color_score = Fore.GREEN if score >= 80 else Fore.YELLOW if score >= 50 else Fore.RED
            color_sec = Fore.GREEN if r['security_status'] == "VERIFICADO" else Fore.RED
            
            # --- CARD DO MODULOID ---
            click.echo(f"\n{Fore.GREEN}📦 {r['name']} {Fore.WHITE}(v{r['version']}) "
                       f"{color_score}[Score: {score}]{Style.RESET_ALL} "
                       f"{color_sec}[🛡️ {r['security_status']}]{Style.RESET_ALL}")
            
            # EXIBIÇÃO DA CATEGORIA (Destaque Magenta)
            click.echo(f"   {Fore.MAGENTA}🏷️  Categoria: {Style.BRIGHT}{r['category'].upper()}{Style.RESET_ALL}")

            if r['health_report']:
                h = json.loads(r['health_report'])
                click.echo(f"   {Style.DIM}⚖️ {h.get('size_kb')}KB | {h.get('lines')} linhas | ⚠️ {h.get('issues')} avisos")
            
            # Tratamento da Descrição e IO
            proposito = r['docstring'].split(" [In:")[0]
            click.echo(f"   {Fore.CYAN}Propósito: {Style.RESET_ALL}{proposito}")
            
            in_m = re.search(r"\[In: (.*?)\]", r['docstring'])
            if in_m: click.echo(f"       {Fore.LIGHTGREEN_EX}IN  ➔ {in_m.group(1)}{Style.RESET_ALL}")
            out_m = re.search(r"\[Out: (.*?)\]", r['docstring'])
            if out_m: click.echo(f"       {Fore.LIGHTRED_EX}OUT ➔ {out_m.group(1)}{Style.RESET_ALL}")
            
            # Funções Internas
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

    def view_brick_code(self, name):
        """Dossiê Técnico Total: Exibe metadados, saúde e código (V40)."""
        conn = get_db_connection()
        conn.row_factory = __import__('sqlite3').Row
        row = conn.execute("SELECT * FROM moduloid_acervo WHERE name = ?", (name,)).fetchone()
        conn.close()

        if not row: return click.secho(f"✘ Moduloid '{name}' não encontrado.", fg="red")

        file_path = BRICKS_DIR / row['filename']
        code = file_path.read_text(encoding='utf-8', errors='ignore')
        h = json.loads(row['health_report']) if row['health_report'] else {}

        if HAS_RICH:
            console = Console()
            # --- 1. CABEÇALHO DO DOSSIÊ ---
            click.secho(f"\n--- 📑 DOSSIÊ TÉCNICO: {name.upper()} (v{row['version']}) ---", fg="cyan", bold=True)
            
            # Badges de Status
            score = row['quality_score']
            color_score = "green" if score >= 80 else "yellow" if score >= 50 else "red"
            sec_color = "green" if row['security_status'] == "VERIFICADO" else "red"
            
            from rich.columns import Columns
# [DOX-UNUSED]             from rich.text import Text
            
            badges = [
                Panel(f"[bold {color_score}]Score: {score}[/]", padding=(0, 2)),
                Panel(f"[bold {sec_color}]🛡️ {row['security_status']}[/]", padding=(0, 2)),
                Panel(f"[bold magenta]🏷️ {row['category'].upper()}[/]", padding=(0, 2))
            ]
            console.print(Columns(badges))

            # --- 2. METADADOS E IO ---
            click.echo(f"   {Fore.CYAN}Propósito:{Style.RESET_ALL} {row['docstring']}")
            click.echo(f"   {Fore.CYAN}Origem   :{Style.RESET_ALL} {Path(row['origin_project']).name}")
            click.echo(f"   {Fore.CYAN}Métricas :{Style.RESET_ALL} {h.get('size_kb')}KB | {h.get('lines')} linhas")
            
            # --- 3. CÓDIGO FONTE ---
            syntax = Syntax(code, "python", theme="monokai", line_numbers=True, word_wrap=True)
            panel = Panel(syntax, title=f"[bold white]📄 {row['filename']}[/]", border_style="blue")
            console.print(panel)
        else:
            click.echo(code) # Fallback simples

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
    
@moduloid_group.command('view')
@click.argument('name')
def moduloid_view(name):
    """Visualiza o código-fonte de um brick no acervo."""
    AcervoEngine().view_brick_code(name)
    
@moduloid_group.command('health')
@click.argument('name')
def moduloid_health(name):
    """Explica o Score de qualidade de um brick."""
    AcervoEngine().show_health(name)
    
def get_active_acervo_base():
    from doxoade.tools.filesystem import _find_project_root
    try:
        root = _find_project_root(os.getcwd())
        local_acervo = Path(root) / "data" / "acervo"
        
        # Se a pasta data/ existir, usamos o acervo local
        if (Path(root) / "data").is_dir():
            return local_acervo
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        from traceback import print_tb as exc_trace
        exc_obj, exc_tb = _dox_sys.exc_info()
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        exc_trace(exc_tb)
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: get_active_acervo_base\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        pass
    return Path.home() / ".doxoade" / "acervo"

ACERVO_BASE = get_active_acervo_base()
BRICKS_DIR = ACERVO_BASE / "bricks"
DB_FILE = get_active_db_path()
