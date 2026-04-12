# doxoade/commands/install.py
import traceback
import sys
import subprocess
import os
import json
import click
import ast
from packaging.requirements import Requirement
# [DOX-UNUSED] from importlib.metadata import PackageNotFoundError
from importlib import metadata
from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import ExecutionLogger, _get_venv_python_executable, _get_project_config

def _run_pip_command(venv_python, command, env=None):
    """Executa um comando pip e transmite a saída em tempo real."""
    try:
        full_command = [venv_python, '-m', 'pip'] + command
        subprocess.run(full_command, check=True, encoding='utf-8', env=env)
        return True
    except subprocess.CalledProcessError:
        click.echo(Fore.RED + "\nO comando pip falhou. Veja os detalhes do erro acima.")
        return False
    except FileNotFoundError:
        click.echo(Fore.RED + "Erro: O executável do pip ou do Python não foi encontrado no venv.")
        return False

def _get_installed_version(package_name):
    """Verifica se um pacote está instalado e retorna sua versão."""
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None

def _update_requirements(package_name, version=None):
    """(Versão Corrigida) Adiciona ou remove um pacote do requirements.txt de forma segura."""
    req_file = 'requirements.txt'
    try:
        lines = []
        if os.path.exists(req_file):
            with open(req_file, 'r', encoding='utf-8') as f:
                # Lê as linhas e remove quebras de linha extras
                lines = [line.strip() for line in f if line.strip()]
        normalized_package_name = package_name.lower().replace('_', '-')
        
        # Remove qualquer linha existente para este pacote
        lines = [
            line for line in lines 
            if not line.lower().replace('_', '-').startswith(normalized_package_name)
        ]
        # Adiciona a nova linha se uma versão foi fornecida
        if version:
            lines.append(f"{package_name}=={version}")
        # Escreve o arquivo de volta, garantindo que cada entrada tenha sua própria linha
        with open(req_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(sorted(lines)))
            f.write("\n") # Garante uma linha em branco no final do arquivo (boa prática)
        return True
    except IOError:
        return False

# LÓGICA MOVIDA DO OPTIMIZE.PY
def _find_unused_packages(logger, python_executable, debug=False):
    """Compara pacotes instalados com os importados. (Lógica do optimize)"""
    config = _get_project_config(logger)
    if not config.get('search_path_valid'): return None
    search_path = config.get('search_path')
    
# Dentro da função _find_unused_packages em install.py
    _PROBE_SCRIPT = """
import json
from importlib import metadata
results = {"package_deps": {}, "module_map": {}}
try:
    for dist in metadata.distributions():
        pkg_name = dist.metadata['name'].lower().replace('_', '-')
        try:
            # Pega as dependências do pacote
            results["package_deps"][pkg_name] = [
                req for req in (dist.requires or []) if 'extra == ' not in req
            ]
            
            # Mapeia o pacote para os módulos que ele fornece
            provided_modules = set()
            # Tenta ler o top_level.txt para descobrir os módulos
            top_level = dist.read_text('top_level.txt')
            if top_level:
                provided_modules.update(t.lower().replace('-', '_') for t in top_level.strip().split())
            
            # Adiciona o próprio nome do pacote como um módulo possível
            provided_modules.add(pkg_name.replace('-', '_')) 
            results["module_map"][pkg_name] = sorted(list(provided_modules))
        except Exception:
            # Ignora erros em pacotes individuais (ex: metadados corrompidos)
            continue
except Exception:
    # Ignora erro geral, apenas retorna o que conseguiu coletar
    pass
print(json.dumps(results))
"""
    try:
        # 1. Coletar imports do código-fonte
        imported_modules = set()
        folders_to_ignore = {'venv', '.git', '__pycache__', 'build', 'dist'}
        config_ignore = {item.strip('/\\') for item in config.get('ignore', [])}
        folders_to_ignore.update(config_ignore)
        for root, dirs, files in os.walk(search_path, topdown=True):
            dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            tree = ast.parse(f.read(), filename=file_path)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names: imported_modules.add(alias.name.split('.')[0].lower())
                            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                                imported_modules.add(node.module.split('.')[0].lower())
                    except Exception:
                        continue
        
        # 2. Executar Sonda e processar
        result = subprocess.run([python_executable, '-c', _PROBE_SCRIPT], capture_output=True, text=True, check=True, encoding='utf-8')
        probe_results = json.loads(result.stdout)
        
        package_deps_map_raw = probe_results.get("package_deps", {})
        package_deps_map = {}
        for pkg, raw_deps in package_deps_map_raw.items():
            parsed_deps = []
            for req_str in raw_deps:
                try:
                    parsed_deps.append(Requirement(req_str).name.lower().replace('_', '-'))
                except Exception:
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
        all_installed_packages = set(package_deps_map.keys())
        essential_packages = {'pip', 'setuptools', 'wheel', 'doxoade', 'packaging', 'importlib-metadata'}
        
        unused = sorted(list(all_installed_packages - fully_used_packages - essential_packages))
        return unused
        
    except Exception as e:
        logger.add_finding('ERROR', f"Falha ao analisar dependências: {e}", details=traceback.format_exc())
        return None

@click.command('install')
@click.pass_context
@click.argument('packages', nargs=-1)
@click.option('--uninstall', is_flag=True, help="Desinstala um pacote e o remove do requirements.txt.")
@click.option('--optimize', is_flag=True, help="Procura e remove pacotes não utilizados.")
@click.option('--wheel', '-w', is_flag=True, help="Força uso de wheels (binários). Se falhar, compila com otimização máxima de CPU.")
def install(ctx, packages, uninstall, optimize, wheel):
    """Gerencia dependências: instala, desinstala, sincroniza ou otimiza."""
    arguments = ctx.params
    with ExecutionLogger('install', '.', arguments) as logger:
        venv_python = _get_venv_python_executable()
        if not venv_python:
            msg = "Ambiente virtual 'venv' não encontrado ou inválido."
            logger.add_finding("CRITICAL", msg, category="VENV")
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)
            
        # ... [MANTENHA OS BLOCOS DE MODO OPTIMIZE, UNINSTALL E SINCRONIZAÇÃO INTACTOS AQUI] ...

        # MODO DE INSTALAÇÃO
        click.echo(Fore.CYAN + f"--- Instalando pacote(s): {', '.join(packages)} ---")
        for package_name in packages:
            installed_version = _get_installed_version(package_name)
            if installed_version:
                click.echo(Fore.YELLOW + f"[AVISO] Pacote '{package_name}' já está instalado (versão {installed_version}).")
        
        # --- LÓGICA DO --WHEEL / COMPILAÇÃO DE ALTA PERFORMANCE ---
        pip_args = ['install'] + list(packages)
        success = False
        
        if wheel:
            click.secho("  [WHEEL] Priorizando a busca estrita por binários pré-compilados (.whl)...", fg="yellow")
            # Tentativa 1: Forçar SÓ arquivos wheel
            success = _run_pip_command(venv_python, pip_args + ['--only-binary', ':all:'])
            
            if not success:
                click.secho("\n  [COMPILADOR] Binário não encontrado para sua plataforma.", fg="magenta", bold=True)
                click.secho("  [COMPILADOR] Ativando Vulcan CPU Engine para compilação Nível Máximo...", fg="cyan")
                
                custom_env = os.environ.copy()
                
                # Invoca a inteligência do Vulcan
                try:
                    # NOTA: Ajuste o caminho do import caso o cpu_flags.py esteja em outra subpasta.
                    # Ex: from doxoade.tools.cpu_flags import simd_compile_flags
                    from doxoade.cpu_flags import simd_compile_flags 
                    
                    base_flags = " ".join(simd_compile_flags())
                    click.secho(f"  [VULCAN DETECT] Flags otimizadas geradas: {base_flags}", fg="green")
                except ImportError:
                    # Fallback de segurança genérico se o Vulcan não for alcançado
                    base_flags = "/O2" if os.name == "nt" else "-O3"
                    click.secho("  [VULCAN] Módulo cpu_flags inacessível. Usando fallback genérico.", fg="yellow")

                # Injeta otimizações matemáticas extremas que o PIP adora para libs cientificas (Numpy/Pandas/C++)
                if os.name == "nt":
                    final_flags = f"{base_flags} /fp:fast"
                else:
                    final_flags = f"{base_flags} -fPIC -ffast-math"

                custom_env["CFLAGS"] = final_flags
                custom_env["CXXFLAGS"] = final_flags
                
                # Tentativa 2: Permite compilar a partir do source, mas usando as flags injetadas
                success = _run_pip_command(venv_python, pip_args, env=custom_env)
        else:
            # Comportamento Padrão
            success = _run_pip_command(venv_python, pip_args)

        if not success:
            logger.add_finding("ERROR", "Falha na instalação via pip.", category="PIP")
            return
            
        # --- ATUALIZANDO REQUIREMENTS E VERIFICAÇÃO ---
        click.echo(Fore.CYAN + "\n--- Atualizando requirements.txt ---")
        for package_name in packages:
            new_version = _get_installed_version(package_name)
            if new_version:
                if _update_requirements(package_name, new_version):
                    click.echo(Fore.GREEN + f"'{package_name}=={new_version}' salvo em requirements.txt.")
                    logger.add_finding("INFO", f"Pacote '{package_name}=={new_version}' salvo.", category="REQUIREMENTS")
                else:
                    click.echo(Fore.RED + f"Erro ao salvar '{package_name}' no requirements.txt.")
            else:
                click.echo(Fore.YELLOW + f"Não foi possível determinar a versão de '{package_name}' para salvar.")
                
        # VERIFICAÇÃO DE VERSÃO
        from importlib.metadata import version, PackageNotFoundError
        for pkg in packages:
            try:
                # Remove especificadores de versão (ex: 'pandas==2.0' -> 'pandas')
                clean_name = pkg.split('=')[0].split('<')[0].split('>')[0]
                installed_ver = version(clean_name)
                click.echo(Fore.CYAN + f"   > Verificado: {clean_name} v{installed_ver} instalado.")
            except PackageNotFoundError:
                click.echo(Fore.YELLOW + f"   [AVISO] {clean_name} instalado, mas metadados não encontrados.")