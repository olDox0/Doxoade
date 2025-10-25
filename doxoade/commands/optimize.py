# DEV.V10-20251022. >>>
# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 13.0(Fnc).
# Descrição: ARQUITETURA FINAL. Implementa a lógica de "Tradução" explícita (módulo -> pacote),
# conforme a diretriz do usuário, resolvendo o bug de falsos positivos de forma definitiva.

import click, os, sys, subprocess, json, ast, traceback
from colorama import Style, Fore
from packaging.requirements import Requirement

# --- Imports Corretos e Finais de shared_tools ---
from ..shared_tools import (
    ExecutionLogger, 
    _get_venv_python_executable, 
    _get_project_config
)

@click.command('optimize')
@click.option('--dry-run', is_flag=True, help="Apenas analisa e relata...")
@click.option('--force', is_flag=True, help="Desinstala pacotes não utilizados...")
@click.option('--debug', is_flag=True, help="Ativa a saída de depuração...")
@click.pass_context
def optimize(ctx, dry_run, force, debug):
    """Analisa o venv em busca de pacotes instalados mas não utilizados."""
    arguments = {k: v for k, v in locals().items() if k != 'ctx'}
    path = '.'
    with ExecutionLogger('optimize', path, arguments) as logger:
        click.echo(Fore.CYAN + "--- [OPTIMIZE] Analisando dependências não utilizadas ---")
        
        python_executable = _get_venv_python_executable()
        if not python_executable:
            logger.add_finding('CRITICAL', "Ambiente virtual 'venv' não encontrado para análise.")
            click.echo(Fore.RED + "[ERRO] Ambiente virtual 'venv' não encontrado."); sys.exit(1)
        
        # A chamada foi simplificada, a função agora tem menos argumentos.
        unused_packages = _find_unused_packages(logger, python_executable, debug)

        if unused_packages is None:
            click.echo(Fore.RED + "[ERRO] A análise falhou. Verifique o log para mais detalhes.")
            sys.exit(1)

        if not unused_packages:
            click.echo(Fore.GREEN + "\n[OK] Nenhuma dependência órfã encontrada. Seu ambiente está limpo!")
            return

        click.echo(Fore.YELLOW + "\nOs seguintes pacotes parecem ser instalados mas não são utilizados no seu código-fonte:")
        for pkg in unused_packages:
            click.echo(f"  - {pkg}")

        if dry_run:
            click.echo(Fore.CYAN + "\nModo 'dry-run' ativado. Nenhuma alteração será feita.")
            return

        if force or click.confirm(Fore.RED + "\nVocê deseja desinstalar TODOS estes pacotes do seu venv?", abort=True):
            return

        click.echo(Fore.YELLOW + "\nOs seguintes pacotes parecem ser instalados mas não são utilizados no seu código-fonte:")
        for pkg in unused_packages:
            click.echo(f"  - {pkg}")

        if dry_run:
            return

        if force or click.confirm(Fore.RED + "\nVocê deseja desinstalar TODOS estes pacotes do seu venv?", abort=True):
            click.echo(Fore.CYAN + "\nIniciando a limpeza...")
            cmd = [python_executable, '-m', 'pip', 'uninstall', '-y'] + unused_packages
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode == 0:
                click.echo(Fore.GREEN + "\n[OK] Pacotes desinstalados com sucesso!")
                logger.add_finding('INFO', f"{len(unused_packages)} pacotes desinstalados com sucesso.")
            else:
                click.echo(Fore.RED + "\n[ERRO] Falha ao desinstalar um ou mais pacotes.")
                click.echo(Fore.WHITE + Style.DIM + result.stderr)
                logger.add_finding('ERROR', "Falha no processo de desinstalação via pip.", details=result.stderr)
                sys.exit(1)

def _find_unused_packages(logger, python_executable, debug=False):
    """Compara pacotes instalados com os importados, com parsing no lado do cliente."""
    
    config = _get_project_config(logger)
    if not config.get('search_path_valid'):
        return None
    search_path = config.get('search_path')
    
    click.echo(Fore.CYAN + f"   > Analisando código-fonte em: '{search_path}'")
    
    _PROBE_SCRIPT = """
import json
from importlib import metadata
results = {"package_deps": {}, "module_map": {}}
try:
    for dist in metadata.distributions():
        pkg_name = dist.metadata['name'].lower().replace('_', '-')
        try:
            results["package_deps"][pkg_name] = [req for req in (dist.requires or []) if 'extra == ' not in req]
            provided_modules = set()
            top_level = dist.read_text('top_level.txt')
            if top_level:
                provided_modules.update(t.lower().replace('-', '_') for t in top_level.strip().split())
            provided_modules.add(pkg_name.replace('-', '_')) 
            results["module_map"][pkg_name] = sorted(list(provided_modules))
        except Exception:
            continue
except Exception:
    pass
print(json.dumps(results))
"""
    try:
        # --- 1. Coletar TODOS os imports do código-fonte ---
        imported_modules = set()
        folders_to_ignore = {'venv', '.git', '__pycache__', 'build', 'dist'}
        config_ignore = [item.strip('/') for item in config.get('ignore', [])]
        folders_to_ignore.update(item.lower() for item in config_ignore)

        for root, dirs, files in os.walk(search_path, topdown=True):
            dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        tree = ast.parse(content, filename=file_path)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    imported_modules.add(alias.name.split('.')[0].lower())
                            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                                imported_modules.add(node.module.split('.')[0].lower())
                    except (SyntaxError, IOError) as e:
                        logger.add_finding('WARNING', f"Não foi possível analisar o arquivo: {file_path}", details=str(e))
                        continue

        if debug:
            click.echo(Fore.CYAN + "\n[DEBUG] Módulos importados encontrados no código-fonte:")
            click.echo(str(sorted(list(imported_modules))))

        # --- 2. Executar a Sonda e Processar os Dados "Inteligentemente" ---
        result = subprocess.run([python_executable, '-c', _PROBE_SCRIPT], capture_output=True, text=True, check=True, encoding='utf-8')
        probe_results = json.loads(result.stdout)
        
        package_deps_map_raw = probe_results.get("package_deps", {})
        package_deps_map = {}
        for pkg, raw_deps in package_deps_map_raw.items():
            parsed_deps = []
            for req_str in raw_deps:
                try:
                    parsed_deps.append(Requirement(req_str).name.lower().replace('_', '-'))
                except:
                    pass
            package_deps_map[pkg] = parsed_deps
        
        package_to_modules_map = probe_results.get("module_map", {})

        # --- ETAPA 3: O Tradutor (A Correção Chave) ---
        module_to_package_translator = {}
        for pkg_name, provided_modules in package_to_modules_map.items():
            for module in provided_modules:
                module_to_package_translator[module] = pkg_name

        # --- ETAPA 4: Traduzir os `imports` para `pacotes` ---
        directly_used_packages = set()
        for imported_mod in imported_modules:
            if imported_mod in module_to_package_translator:
                directly_used_packages.add(module_to_package_translator[imported_mod])
        
        if debug:
            click.echo(Fore.CYAN + "\n[DEBUG] Pacotes diretamente utilizados (Após Tradução):")
            click.echo(str(sorted(list(directly_used_packages))))

        # --- ETAPA 5: Resolução de Dependências (agora com dados corretos) ---
        packages_to_keep = set(config.get('keep', []))
        initial_seed_packages = directly_used_packages | packages_to_keep

        fully_used_packages = set(initial_seed_packages)
        to_process = list(initial_seed_packages)
        
        while to_process:
            current_pkg = to_process.pop()
            for dep in package_deps_map.get(current_pkg, []):
                if dep not in fully_used_packages:
                    fully_used_packages.add(dep)
                    to_process.append(dep)

        if debug:
            click.echo(Fore.CYAN + "\n[DEBUG] Pacotes em uso após resolver dependências:")
            click.echo(str(sorted(list(fully_used_packages))))

        # --- ETAPA 6: Comparação Final ---
        all_installed_packages = set(package_deps_map.keys())
        essential_packages = {'pip', 'setuptools', 'wheel', 'doxoade', 'packaging', 'importlib-metadata'}
        
        unused = sorted(list(all_installed_packages - fully_used_packages - essential_packages))
        return unused
        
    except Exception as e:
        logger.add_finding('ERROR', f"Falha ao analisar dependências: {e}", details=traceback.format_exc())
        return None