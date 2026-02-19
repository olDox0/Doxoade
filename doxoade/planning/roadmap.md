### ROADMAP

# 🗺️ Doxoade Roadmap: Rumo à v100

## Fase 1: Domínio do Silício (Atual)
- [ ] Concluir vetorização SIMD para o motor DRY (Clones).
- [ ] Vulcanizar o `DetailedAnalysisVisitor` para mapeamento de impacto instantâneo.

# Secundario
- [ ] **padronização de cache**: Seguindo o PASC 8.20 onde recomenda-se centralizar estes já que doxoade tem três pastas distindas com estes dados.
´´´


(venv) C:\Users\olDox222\Documents\A20251122\DOSSIER\Altonomo\Projetos_E_Programas\Projeto OADE\doxoade>doxoade search ".doxoade/" -c --full --commits
[05:06:28] Executando search...
╔═══ Nexus Search: '.doxoade/' ═══╗

[Código & Docs]
 [.PY] doxoade\commands\search_systems\search_utils.py:106
         104:     cmd = [
         105:         'git', 'grep', '-n', '-i', '-e', query, commit_hash,
      >  106:         '--', '*.py', '*.md', ':(exclude).doxoade/*'
         107:     ]
         108:     try:
 [.MD] doxoade\docs\Internals\vol19_deepcheck_nexus.md:50
          48:
          49: ## 5. Gestão de Snapshots e Comparação Histórica
      >   50: O sistema agora possui memória de longo prazo residindo em `.doxoade/deepcheck_snapshots/`.
          51: *   **Snapshot Local (`-cj`):** Compara o código atual com o último estado salvo, gerando um **Delta Semântico** (Ex: "O score subiu +15 após a refatoração").
          52: *   **Snapshot Git (`-cg`):** Baixa versões históricas (HEAD, Hashes, Branches) e realiza uma autópsia comparativa instantânea para detectar a **Erosão Funcional**.
 [.MD] doxoade\docs\Internals\vol1_arquitetura.md:39
          37: │
          38: ├── database.py             # [PERSISTÊNCIA] Camada de Dados.
      >   39: │                             - Gerencia o SQLite (~/.doxoade/doxoade.db).
          40: │                             - Executa migrações de schema automáticas.
          41: │
 [.MD] doxoade\docs\Internals\vol1_arquitetura.md:103
         101: ## 5. Persistência (Memória Sapiens)
         102:
      >  103: O estado do sistema reside em `~/.doxoade/doxoade.db` (SQLite).
         104:
         105: **Tabelas Críticas:**
 [.PY] doxoade\tools\optimizer.py:16
          14: class VulcanOptimizer:
          15:     def __init__(self):
      >   16:         self.bin_dir = Path(".doxoade/bin")
          17:         self.bin_dir.mkdir(parents=True, exist_ok=True)
          18:         self.registry = {} # {func_name: module_path}
 [.PY] doxoade\tools\vulcan\core.py:14
          12:     def __init__(self):
          13:         self.enabled = False # Opcional por padrão
      >   14:         self.registry_path = Path(".doxoade/vulcan/registry.json")
          15:         self.optimized_dir = Path(".doxoade/vulcan/bin")
          16:         self.blacklist = set() # Funções que falharam na validação
 [.PY] doxoade\tools\vulcan\core.py:15
          13:         self.enabled = False # Opcional por padrão
          14:         self.registry_path = Path(".doxoade/vulcan/registry.json")
      >   15:         self.optimized_dir = Path(".doxoade/vulcan/bin")
          16:         self.blacklist = set() # Funções que falharam na validação
          17:
 [.PY] doxoade\tools\vulcan\diagnostic.py:28
          26:             "compiler": compiler_ok,
          27:             "cython": cython_ok,
      >   28:             "foundry": self._check_directory(".doxoade/vulcan/foundry"),
          29:             "disk_space": self._check_disk_free()
          30:         }
 [.PY] tests\vulcan_sandbox\verify_bitwise.py:25
          23:
          24:     # 2. Carregamento do Metal (Vulcano)
      >   25:     bin_path = os.path.abspath(".doxoade/vulcan/bin/v_test_forge.pyd")
          26:     spec = importlib.util.spec_from_file_location("v_test_forge", bin_path)
          27:     v_mod = importlib.util.module_from_spec(spec)
 [.PY] tests\vulcan_sandbox\verify_ignition.py:19
          17:
          18:     # 2. Carregamento Dinâmico do Binário Vulcano
      >   19:     bin_path = os.path.abspath(".doxoade/vulcan/bin/v_test_forge.pyd")
          20:     spec = importlib.util.spec_from_file_location("v_test_forge", bin_path)
          21:     v_module = importlib.util.module_from_spec(spec)
[search] Tempo total: 5.610s

(venv) C:\Users\olDox222\Documents\A20251122\DOSSIER\Altonomo\Projetos_E_Programas\Projeto OADE\doxoade>

´´´

- [ ] **Revisar search**: Revisar search_systems.
´´´

(venv) C:\Users\olDox222\Documents\A20251122\DOSSIER\Altonomo\Projetos_E_Programas\Projeto OADE\doxoade>doxoade diff doxoade\commands\search.py
[05:02:40] Executando diff...
--- Diferenças em 'doxoade/commands/search.py' vs HEAD ---
     - | -- a/doxoade/commands/search.py
     + | ++ b/doxoade/commands/search.py
Mudanças perto da linha 1
       | # -*- coding: utf-8 -*-
     - | """
     - | Nexus Search v4.1 - Chief Gold Edition.
     - | Otimizado para busca linear em stream e filtragem de ruído.
     - | Conformidade: MPoT-7, PASC-6.
     - | """
     - | from os import walk
     - | from pathlib import Path
     - | from click import command, argument, option, echo, pass_context
     + | # doxoade/commands/search.py (v90.0 Modular Gold)
     + | import os
     + | import click
       | from colorama import Fore, Style
     - |
     - | from ..shared_tools import _get_project_config, ExecutionLogger
     - | from .search_systems.search_utils import extract_function_block, search_git_history_content, get_code_from_commit, extract_block_from_git
     - |
     - | # ============================================================================
     - | # FASE 1: MOTORES DE BUSCA (LÓGICA PURA)
     - | # ============================================================================
     - |
     - | def _search_in_commits(query: str, limit: int) -> list:
     - |     """Busca em mensagens de commit via Git (Aegis Protocol)."""
     - |     if not query:
     - |         return []
     - |
     - |     from subprocess import run # PASC-6.1: Lazy Import
     - |     try:
     - |         cmd = ['git', 'log', f'--grep={query}', '--oneline', '--no-merges', f'-n{limit}']
     - |         # shell=False garante segurança; # nosec silencia o Bandit revisado
     - |         result = run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=False) # nosec
     - |
     - |         if result.returncode != 0:
     - |             return []
     - |
     - |         matches = []
     - |         for line in result.stdout.splitlines():
     - |             if not line.strip(): continue
     - |             parts = line.split(' ', 1)
     - |             if len(parts) == 2:
     - |                 matches.append({'hash': parts[0], 'message': parts[1]})
     - |         return matches
     - |     except Exception:
     - |         return []
     - |
     - | def _is_searchable(file_path: Path) -> bool:
     - |     """Filtro de integridade para arquivos de busca (MPoT-17)."""
     - |     SKIP_EXTS = {'.lock', '.bin', '.db', '.pyc', '.log'}
     - |     ALLOWED_EXTS = {'.py', '.md', '.txt', '.json', '.dox', '.toml'}
     + | # [DOX-UNUSED] from pathlib import Path
     + | from ..shared_tools import ExecutionLogger, _find_project_root
     + | from .search_systems.search_state import SearchState
     + | from .search_systems.search_engine import run_search_engine
     + | from .search_systems.search_utils import render_search_results
     + |
     + | @click.command('search')
     + | @click.argument('query', required=False, default="")
     + | @click.option('--code', '-c', is_flag=True, help="Busca no código/docs")
     + | @click.option('--full', '-f', is_flag=True, help="Exibe a função inteira")
     + | @click.option('--commits', is_flag=True, help="Busca no histórico Git")
     + | @click.option('--here', '-H', is_flag=True, help="Filtra resultados deste diretório")
     + | @click.option('--specify-commit', '-sc', help="Busca código em commit específico")
     + | @click.option('--incidents', '-i', is_flag=True, help="Busca incidentes ativos")
     + | @click.option('--timeline', '-t', is_flag=True, help="Busca na timeline Chronos")
     + | @click.option('--limit', '-n', default=20, help="Limite de resultados")
     + | @click.pass_context
     + | def search(ctx, query, **kwargs):
     + |     """🔍 Busca Nexus v4.7.1: Modularidade e Aceleração Vulcano."""
     + |     root = _find_project_root(os.getcwd())
     + |     search_q = query if query else ("%" if kwargs.get('here') else "")
       |
     - |     if file_path.suffix in SKIP_EXTS or file_path.name == "arvore.txt":
     - |         return False
     - |     return file_path.suffix in ALLOWED_EXTS
     - |
     - | def _search_in_code_stream(project_root: Path, query: str, limit: int) -> list:
     - |     """
     - |     Motor de Busca Linear via Stream (Gargalo 4 Fix).
     - |     MPoT-5: Contrato de validação de entrada implementado.
     - |     """
     - |     if not project_root.exists() or not query:
     - |         return []
     - |
     - |     matches = []
     - |     query_lower = query.lower()
     - |     QUARANTINE = {
     - |         'venv', '.git', '__pycache__', 'build', 'dist',
     - |         '.doxoade_cache', '.doxoade', '.pytest_cache' # Adicionado .doxoade
     - |     }
     - |
     - |     for root, dirs, filenames in walk(project_root):
     - |         # Filtro de Pastas (Isolamento de Processamento)
     - |         dirs[:] = [d for d in dirs if d not in QUARANTINE]
     - |
     - |         for filename in filenames:
     - |             file_path = Path(root) / filename
     - |             if not _is_searchable(file_path):
     - |                 continue
     - |
     - |             try:
     - |                 # Busca via Stream para RAM constante (PASC-6.4)
     - |                 with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
     - |                     for i, line in enumerate(f, 1):
     - |                         if query_lower in line.lower():
     - |                             matches.append({
     - |                                 'file': str(file_path.relative_to(project_root)),
     - |                                 'line': i,
     - |                                 'text': line.strip(),
     - |                                 'type': file_path.suffix
     - |                             })
     - |                             if len(matches) >= limit:
     - |                                 return matches
     - |             except (OSError, UnicodeDecodeError):
     - |                 continue
     - |     return matches
     - |
     - | # ============================================================================
     - | # FASE 2: RENDERIZADORES ESPECIALISTAS (MPoT-4)
     - | # ============================================================================
     + |     if not search_q and not kwargs.get('here'):
     + |         click.echo(Fore.RED + "Erro: Forneça um termo de busca ou use --here.")
     + |         return
       |
     - | def _render_timeline(results: list):
     - |     """Renderiza histórico Chronos (MPoT-4)."""
     - |     if not results: return
     - |     echo(f"{Fore.MAGENTA}{Style.BRIGHT}\n╔═══ Timeline (Chronos) ═══╗")
     - |     for t in results:
     - |         status = f"{Fore.GREEN}✔" if t['exit_code'] == 0 else f"{Fore.RED}✘"
     - |         echo(f" {status} {Fore.WHITE}{t['timestamp'][:19]} | {Fore.CYAN}{t['full_line']}")
     - |         echo(f"    {Style.DIM}Em: {t['dir']}{Style.RESET_ALL}")
     + |     state = SearchState(root=root, query=search_q, limit=kwargs.get('limit'), is_full_mode=kwargs.get('full'))
       |
     - | def _render_database(db: dict):
     - |     """Renderiza Dívida Técnica e Gênese (MPoT-4)."""
     - |     if db.get('incidents'):
     - |         echo(f"{Fore.RED}{Style.BRIGHT}\n╔═══ Incidentes Ativos (Dívida Técnica) ═══╗")
     - |         for inc in db['incidents']:
     - |             echo(f"{Fore.YELLOW}[{inc['category']}] {Fore.WHITE}{inc['message']}")
     - |             echo(f"  Em: {inc['file']}:{inc['line']}")
     - |
     - |     if db.get('solutions'):
     - |         echo(f"{Fore.GREEN}{Style.BRIGHT}\n╔═══ Soluções Históricas (Gênese) ═══╗")
     - |         for sol in db['solutions']:
     - |             echo(f"{Fore.WHITE}{sol['message']}")
     - |             echo(f"  {Fore.CYAN}Arquivo:{Style.RESET_ALL} {sol['file']}")
     + |     with ExecutionLogger('search', root, ctx.params):
     + |         ctx_tag = f" em {os.path.basename(os.getcwd())}" if kwargs.get('here') else ""
     + |         click.echo(f"{Fore.CYAN}{Style.BRIGHT}╔═══ Nexus Search: '{query}'{ctx_tag} ═══╗{Style.RESET_ALL}")
       |
     - | def _render_code_matches(matches: list):
     - |     """Renderiza resultados de código (MPoT-4)."""
     - |     if not matches: return
     - |     echo(f"{Fore.CYAN}{Style.BRIGHT}\n[Código & Docs]")
     - |     for m in matches:
     - |         is_doc = m['type'] in ['.md', '.txt', '.dox']
     - |         color = Fore.MAGENTA if is_doc else Fore.BLUE
     - |         label = "DOC" if is_doc else "CODE"
     - |         echo(f"{color}[{label}] {m['file']}:{m['line']}{Style.RESET_ALL}")
     - |         echo(f"    > {Style.BRIGHT}{m['text']}{Style.RESET_ALL}")
     - |
     - | # ============================================================================
     - | # FASE 3: ORQUESTRADOR E SQL
     - | # ============================================================================
     - |
     - | @command('search')
     - | @argument('query')
     - | @option('--code', '-c', is_flag=True, help='Busca no código/docs')
     - | @option('--full', '-f', is_flag=True, help='Exibe a função inteira (detecção por indentação)')
     - | @option('--commits', is_flag=True, help='Busca em mensagens e conteúdo histórico')
     - | @option('--specify-commit', '-sc', help='Busca o código dentro de um commit específico')
     - | @option('--incidents', '-i', is_flag=True, help='Busca incidentes')
     - | @option('--timeline', '-t', is_flag=True, help='Busca na timeline')
     - | @option('--limit', '-n', default=20, help='Limite (Padrão: 20)')
     - | @pass_context
     - | def search(ctx, query, code, full, commits, incidents, timeline, specify_commit, limit):
     - |     """Busca Nexus v4.3: Viagem no tempo e recuperação de código."""
     - |     if not query:
     - |         raise ValueError("Contrato Violado: Query de busca é obrigatória.")
     - |
     - |     config = _get_project_config(None)
     - |     root = Path(config['root_path'])
     - |
     - |     with ExecutionLogger('search', str(root), ctx.params):
     - |         echo(f"{Fore.CYAN}{Style.BRIGHT}╔═══ Nexus Search: '{query}' ═══╗{Style.RESET_ALL}")
     - |
     - |         # 1. Busca Local (Código)
     - |         if code or (not any([code, commits, incidents, timeline])):
     - |             matches = _search_in_code_stream(root, query, limit)
     - |             if matches:
     - |                 echo(f"{Fore.CYAN}{Style.BRIGHT}\n[Código & Docs]")
     - |                 for m in matches:
     - |                     color = Fore.MAGENTA if m['type'] in ['.md', '.txt'] else Fore.BLUE
     - |                     echo(f"{color}[{m['type'].upper()}] {m['file']}:{m['line']}{Style.RESET_ALL}")
     - |
     - |                     if full and m['type'] == '.py':
     - |                         block = extract_function_block(str(root / m['file']), m['line'])
     - |                         echo(f"{Style.DIM}{block}{Style.RESET_ALL}\n")
     - |                     else:
     - |                         echo(f"    > {m['text']}")
     - |
     - |         # 2. Busca em Commits (Mensagens + Conteúdo Histórico)
     - |         if commits:
     - |             # Busca em mensagens (o que já tínhamos)
     - |             msg_matches = _search_in_commits(query, limit)
     - |             # Busca no conteúdo (Pickaxe Search)
     - |             content_matches = search_git_history_content(query, limit)
     - |
     - |             if msg_matches or content_matches:
     - |                 echo(f"{Fore.YELLOW}{Style.BRIGHT}\n[Linhagem Git / Histórico]")
     - |                 seen_hashes = set()
     - |                 for m in msg_matches + content_matches:
     - |                     if m['hash'] not in seen_hashes:
     - |                         echo(f" {Fore.MAGENTA}{m['hash']}{Fore.WHITE}: {m.get('message') or m.get('msg')}")
     - |                         seen_hashes.add(m['hash'])
     - |
     - |         # 3. Busca em Commits especifico
     - |         if specify_commit:
     - |             echo(f"{Fore.YELLOW}⏳ Consultando snapshot do commit: {specify_commit}...{Style.RESET_ALL}")
     - |             results = get_code_from_commit(specify_commit, query)
     - |
     - |             if not results:
     - |                 echo(f"   {Fore.RED}Nenhuma ocorrência encontrada nesse commit.{Style.RESET_ALL}")
     - |
     - |             for r in results:
     - |                 echo(f"{Fore.BLUE}[HISTORIC] {r['file']}:{r['line']}{Style.RESET_ALL}")
     - |                 if full:
     - |                     # EXTRAÇÃO INTEGRAL: Agora com indentação industrial
     - |                     block = extract_block_from_git(specify_commit, r['file'], r['line'])
     - |                     # Formatação Gold: indenta o bloco histórico para contrastar com o atual
     - |                     lines = block.splitlines()
     - |                     for line in lines:
     - |                         echo(f"      {Style.DIM}{line}{Style.RESET_ALL}")
     - |                     echo("")
     - |                 else:
     - |                     echo(f"    > {r['text']}")
     + |         # 1. Modo Arqueólogo JIT (Snapshots Históricos)
     + |         if kwargs.get('specify_commit'):
     + |             _handle_historic_search(state, kwargs['specify_commit'])
       |             return
     + |
     + |         # 2. Configuração de Filtros (PASC-8.7)
     + |         filters = kwargs
     + |         is_default = not any([kwargs.get('code'), kwargs.get('commits'),
     + |                              kwargs.get('incidents'), kwargs.get('timeline')])
       |
     - |         # 1. Fontes de Dados (Busca Lógica)
     - |         all_off = not any([code, commits, incidents, timeline])
     + |         filters['run_code'] = kwargs.get('code') or is_default
     + |         filters['run_db'] = kwargs.get('incidents') or is_default or kwargs.get('here')
     + |         filters['run_time'] = kwargs.get('timeline') or is_default or kwargs.get('here')
       |
     - |         if incidents or all_off:
     - |             _render_database(_search_in_database(query, limit))
     + |         # 3. Execução (Buffer-Scan Vulcan se disponível)
     + |         run_search_engine(state, filters)
       |
     - |         if timeline or all_off:
     - |             _render_timeline(_search_in_timeline(query, limit))
     + |         # 4. Despacho Visual
     + |         render_search_results(state)
       |
     - | def _search_in_database(query: str, limit: int) -> dict:
     - |     """Busca SQL com contrato de segurança (MPoT-5)."""
     - |     from ..database import get_db_connection
     - |     from sqlite3 import Row
     + | def _handle_historic_search(state, commit):
     + |     """Handler de Arqueologia: Busca cirúrgica em snapshots do Git."""
     + |     from .search_systems.search_utils import get_code_from_commit, extract_block_from_git
       |
     - |     results = {'incidents': [], 'solutions': []}
     - |     conn = get_db_connection()
     - |     conn.row_factory = Row
     - |     sql_wildcard = f"%{query}%"
     - |     try:
     - |         cursor = conn.cursor()
     - |         cursor.execute("SELECT * FROM open_incidents WHERE message LIKE ? OR file_path LIKE ? LIMIT ?", (sql_wildcard, sql_wildcard, limit))
     - |         for row in cursor.fetchall():
     - |             results['incidents'].append({'file': row['file_path'], 'line': row['line'], 'message': row['message'], 'category': row['category']})
     - |
     - |         cursor.execute("SELECT * FROM solutions WHERE message LIKE ? OR file_path LIKE ? LIMIT ?", (sql_wildcard, sql_wildcard, limit))
     - |         for row in cursor.fetchall():
     - |             results['solutions'].append({'file': row['file_path'], 'message': row['message']})
     - |     finally:
     - |         conn.close()
     - |     return results
     - |
     - | def _search_in_timeline(query: str, limit: int) -> list:
     - |     """Busca Timeline com contrato de segurança (MPoT-5)."""
     - |     from ..database import get_db_connection
     - |     from sqlite3 import Row
     - |
     - |     results = []
     - |     conn = get_db_connection()
     - |     conn.row_factory = Row
     - |     sql_wildcard = f"%{query}%"
     - |     try:
     - |         cursor = conn.cursor()
     - |         # Validação de integridade de esquema
     - |         cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_history'")
     - |         if not cursor.fetchone(): return []
     - |
     - |         cursor.execute("SELECT * FROM command_history WHERE full_command_line LIKE ? ORDER BY id DESC LIMIT ?", (sql_wildcard, limit))
     - |         for row in cursor.fetchall():
     - |             results.append({'full_line': row['full_command_line'], 'dir': row['working_dir'], 'timestamp': row['timestamp'], 'exit_code': row['exit_code']})
     - |     finally:
     - |         conn.close()
     - |     return results
     + |     click.echo(f"{Fore.YELLOW}⏳ Consultando snapshot do commit: {commit}...{Style.RESET_ALL}")
     + |     results = get_code_from_commit(commit, state.query)
     + |
     + |     for r in results:
     + |         click.echo(f"{Fore.BLUE}[HISTORIC] {r['file']}:{r['line']}{Style.RESET_ALL}")
     + |         if state.is_full_mode:
     + |             block = extract_block_from_git(commit, r['file'], r['line'])
     + |             click.echo(f"{Style.DIM}{block}{Style.RESET_ALL}\n")
     + |         else:
     + |             click.echo(f"    > {r['text']}")
[diff] Tempo total: 1.187s


´´´


## Fase 2: Expansão de Plugin (Próxima)
- [ ] Implementar a `Plugin API` permitindo que usuários adicionem sondas nativas.
- [ ] Criar o repositório central de plugins `doxoade-hub`.

## Fase 3: Consciência Global
- [ ] **Sapiens Sync**: Sincronização de templates de aprendizado entre diferentes projetos via Git.

---

