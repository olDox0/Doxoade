#atualizado em 2025/10/07-Versão 32.0. Primeiro plugin extraído para a arquitetura v2.0.
import click
import os
import sys
import subprocess
import json
import ast
from colorama import Style
#from importlib import metadata
#from pathlib import Path
from colorama import Fore

# Mude esta linha de import:
from ..shared_tools import ExecutionLogger, _get_venv_python_executable

#adicionado em 2025/10/05-Versão 29.0. Tem como função analisar e remover dependências não utilizadas de um ambiente virtual.
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
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}"); sys.exit(1)
        
        unused_packages = _find_unused_packages(path, python_executable, logger)

        if not unused_packages:
            click.echo(Fore.GREEN + "\n[OK] Nenhuma dependência órfã encontrada. Seu ambiente está limpo!")
            return

        click.echo(Fore.YELLOW + "\nOs seguintes pacotes parecem estar instalados mas não são utilizados no seu código-fonte:")
        for pkg in unused_packages:
            click.echo(f"  - {pkg}")
        
        logger.add_finding('info', f"Encontrados {len(unused_packages)} pacotes não utilizados.", details=", ".join(unused_packages))

        if dry_run:
            click.echo(Fore.CYAN + "\nModo 'dry-run' ativado. Nenhuma alteração será feita.")
            return

        if force or click.confirm(Fore.RED + "\nVocê deseja desinstalar TODOS estes pacotes do seu venv?", abort=True):
            click.echo(Fore.CYAN + "\nIniciando a limpeza...")
            cmd = [python_executable, '-m', 'pip', 'uninstall', '-y'] + unused_packages
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode == 0:
                click.echo(Fore.GREEN + "\n[OK] Pacotes desinstalados com sucesso!")
                logger.add_finding('info', f"{len(unused_packages)} pacotes desinstalados com sucesso.")
            else:
                click.echo(Fore.RED + "\n[ERRO] Falha ao desinstalar um ou mais pacotes.")
                click.echo(Fore.WHITE + Style.DIM + result.stderr)
                logger.add_finding('error', "Falha no processo de desinstalação via pip.", details=result.stderr)
                sys.exit(1)

#atualizado em 2025/10/06-Versão 30.0. Tem como função encontrar pacotes não utilizados. Melhoria: A lógica agora constrói uma árvore de dependências completa, tornando a análise "dependency-aware" e corrigindo a falha em identificar dependências transitivas.
def _find_unused_packages(project_path, python_executable, logger):
    """Compara pacotes instalados com os importados, respeitando a árvore de dependências, e retorna os não utilizados."""
    
    _PROBE_SCRIPT = """
import json
from importlib import metadata

results = {"packages": {}, "dependencies": {}}
for dist in metadata.distributions():
    pkg_name = dist.metadata['name'].lower().replace('_', '-')
    results["packages"][pkg_name] = [req.split(' ')[0].lower() for req in (dist.requires or [])]
    
    provided_modules = set()
    top_level = dist.read_text('top_level.txt')
    if top_level:
        provided_modules.update(t.lower() for t in top_level.strip().split())
    provided_modules.add(pkg_name.replace('-', '_'))
    results["dependencies"][pkg_name] = sorted(list(provided_modules))

print(json.dumps(results))
"""
    try:
        # 1. Obter módulos importados pelo código do usuário
        imported_modules = set()
        # ... (a lógica de caminhar pela AST para encontrar imports permanece a mesma de antes) ...
        folders_to_ignore = {'venv', '.git', '__pycache__'}
        for root, dirs, files in os.walk(project_path, topdown=True):
            dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            tree = ast.parse(f.read(), filename=file_path)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    imported_modules.add(alias.name.split('.')[0].lower())
                            elif isinstance(node, ast.ImportFrom):
                                if node.module:
                                    imported_modules.add(node.module.split('.')[0].lower())
                    except Exception: continue

        # 2. Executar a sonda para obter o mapa de pacotes e suas dependências
        result = subprocess.run([python_executable, '-c', _PROBE_SCRIPT], capture_output=True, text=True, check=True, encoding='utf-8')
        probe_results = json.loads(result.stdout)
        dependency_tree = probe_results["dependencies"]
        package_deps = probe_results["packages"]

        # 3. Determinar os pacotes DIRETAMENTE utilizados
        directly_used = set()
        for pkg_name, provided_modules in dependency_tree.items():
            if not set(provided_modules).isdisjoint(imported_modules):
                directly_used.add(pkg_name)

        # 4. Resolver a árvore de dependências completa
        fully_used = set(directly_used)
        to_process = list(directly_used)
        while to_process:
            current_pkg = to_process.pop()
            for dep in package_deps.get(current_pkg, []):
                if dep not in fully_used:
                    fully_used.add(dep)
                    to_process.append(dep)

        # 5. Comparação final
        all_installed = set(package_deps.keys())
        essential = {'pip', 'setuptools', 'wheel', 'doxoade'}
        fully_used.update(essential)

        unused = sorted(list(all_installed - fully_used))
        return unused
        
    except Exception as e:
        logger.add_finding('error', f"Falha ao analisar dependências: {e}")
        return []
