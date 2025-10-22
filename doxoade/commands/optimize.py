# DEV.V10-20251022. >>>
# doxoade/commands/optimize.py
# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 2.0(Fnc).
# Descrição: Corrige uma falha crítica de falsos positivos. A análise de imports agora percorre
# a AST inteira, detectando 'lazy imports' (imports dentro de funções), tornando a análise precisa.

import click
import os
import sys
import subprocess
import json
import ast
from colorama import Style, Fore

from ..shared_tools import ExecutionLogger, _get_venv_python_executable

@click.command('optimize')
@click.option('--dry-run', is_flag=True, help="Apenas analisa e relata, não oferece para desinstalar.")
@click.option('--force', is_flag=True, help="Desinstala pacotes não utilizados sem confirmação.")
@click.pass_context
def optimize(ctx, dry_run, force):
    """Analisa o venv em busca de pacotes instalados mas não utilizados e oferece para removê-los."""
    arguments = ctx.params
    path = '.'

    with ExecutionLogger('optimize', path, arguments) as logger:
        click.echo(Fore.CYAN + "--- [OPTIMIZE] Analisando dependências não utilizadas ---")
        
        python_executable = _get_venv_python_executable()
        if not python_executable:
            msg = "Ambiente virtual 'venv' não encontrado para análise."
            logger.add_finding('CRITICAL', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}"); sys.exit(1)
        
        unused_packages = _find_unused_packages(path, python_executable, logger)

        if not unused_packages:
            click.echo(Fore.GREEN + "\n[OK] Nenhuma dependência órfã encontrada. Seu ambiente está limpo!")
            return

        click.echo(Fore.YELLOW + "\nOs seguintes pacotes parecem estar instalados mas não são utilizados no seu código-fonte:")
        for pkg in unused_packages:
            click.echo(f"  - {pkg}")
        
        logger.add_finding('INFO', f"Encontrados {len(unused_packages)} pacotes não utilizados.", details=", ".join(unused_packages))

        if dry_run:
            click.echo(Fore.CYAN + "\nModo 'dry-run' ativado. Nenhuma alteração será feita.")
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

def _find_unused_packages(project_path, python_executable, logger):
    """Compara pacotes instalados com os importados, respeitando a árvore de dependências e lazy loading."""
    
    _PROBE_SCRIPT = """
import json
from importlib import metadata
results = {"packages": {}, "dependencies": {}}
try:
    for dist in metadata.distributions():
        pkg_name = dist.metadata['name'].lower().replace('_', '-')
        results["packages"][pkg_name] = [req.split(' ')[0].lower().replace('_', '-') for req in (dist.requires or []) if 'extra == ' not in req]
        
        provided_modules = set()
        # Mapeia o nome do pacote para os módulos que ele fornece (ex: 'beautifulsoup4' -> 'bs4')
        top_level = dist.read_text('top_level.txt')
        if top_level:
            provided_modules.update(t.lower().replace('-', '_') for t in top_level.strip().split())
        
        # Fallback: adiciona o próprio nome do pacote como um módulo provável
        provided_modules.add(pkg_name.replace('-', '_')) 
        results["dependencies"][pkg_name] = sorted(list(provided_modules))
except Exception:
    # Em caso de erro na sonda, retorna um dicionário vazio para não quebrar a análise.
    pass
print(json.dumps(results))
"""
    try:
        # --- Utilitário 1: Obter TODOS os módulos importados (incluindo lazy imports) ---
        imported_modules = set()
        folders_to_ignore = {'venv', '.git', '__pycache__', 'build', 'dist'}
        for root, dirs, files in os.walk(project_path, topdown=True):
            dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        tree = ast.parse(content, filename=file_path)
                        # A LÓGICA CORRETA: ast.walk percorre a árvore inteira, incluindo corpos de funções.
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    imported_modules.add(alias.name.split('.')[0].lower())
                            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                                imported_modules.add(node.module.split('.')[0].lower())
                    except Exception: 
                        continue

        # --- Utilitário 2: Executar a Sonda de Ambiente ---
        result = subprocess.run([python_executable, '-c', _PROBE_SCRIPT], capture_output=True, text=True, check=True, encoding='utf-8')
        probe_results = json.loads(result.stdout)
        package_to_modules_map = probe_results.get("dependencies", {})
        package_deps_map = probe_results.get("packages", {})

        # --- Utilitário 3: Resolver dependências ---
        directly_used_packages = set()
        for pkg_name, provided_modules in package_to_modules_map.items():
            # Se qualquer um dos módulos que um pacote fornece estiver na nossa lista de imports, o pacote é usado.
            if not imported_modules.isdisjoint(provided_modules):
                directly_used_packages.add(pkg_name)

        fully_used_packages = set(directly_used_packages)
        to_process = list(directly_used_packages)
        while to_process:
            current_pkg = to_process.pop()
            for dep in package_deps_map.get(current_pkg, []):
                if dep not in fully_used_packages:
                    fully_used_packages.add(dep)
                    to_process.append(dep)

        # --- Utilitário 4: Comparação Final ---
        all_installed_packages = set(package_deps_map.keys())
        essential_packages = {'pip', 'setuptools', 'wheel', 'doxoade', 'packaging', 'importlib-metadata'}
        
        unused = sorted(list(all_installed_packages - fully_used_packages - essential_packages))
        return unused
        
    except Exception as e:
        logger.add_finding('ERROR', f"Falha ao analisar dependências: {e}", details=traceback.format_exc())
        return []