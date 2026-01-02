# doxoade/tools/filesystem.py
import os
import sys
import toml
from pathlib import Path
from colorama import Fore

def _find_project_root(start_path='.'):
    """Encontra a raiz do projeto (pyproject.toml ou .git)."""
    current_path = Path(start_path).resolve()
    if (current_path / 'pyproject.toml').is_file(): return str(current_path)
    
    # Sobe até achar a raiz ou o topo
    search_path = current_path
    while search_path != search_path.parent:
        if (search_path / '.git').is_dir(): return str(search_path)
        search_path = search_path.parent
    return str(current_path)

def _get_project_config(logger, start_path='.'):
    """Lê configurações do pyproject.toml."""
    root_path = os.path.abspath(start_path)
    config = {'ignore': [], 'source_dir': '.'}
    config_path = os.path.join(root_path, 'pyproject.toml')
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                toml_data = toml.load(f)
                config.update(toml_data.get('tool', {}).get('doxoade', {}))
        except Exception as config_except:
            if logger:
                # Evita dependência circular com Logger aqui, apenas imprime se necessário ou ignora
                print(Fore.YELLOW + f"[Config] Aviso: Erro ao ler pyproject.toml: {config_except}")

    source_dir = config.get('source_dir', '.')
    search_path = os.path.join(root_path, source_dir)
    config['search_path_valid'] = os.path.isdir(search_path)
    
    config['root_path'] = root_path
    config['search_path'] = search_path
    return config

def _get_venv_python_executable(start_path='.'):
    """Localiza o interpretador Python do venv do projeto alvo."""
    # Garante que estamos olhando para o diretório onde o usuário está
    abs_start = os.path.abspath(start_path)
    
    # Procura venv na pasta atual ou acima
    venv_dir = os.path.join(abs_start, 'venv')
    if not os.path.exists(venv_dir):
        # Tenta achar a raiz se o usuário estiver em uma subpasta do projeto
        project_root = _find_project_root(abs_start)
        venv_dir = os.path.join(project_root, 'venv')

    exe_name = 'python.exe' if os.name == 'nt' else 'python'
    scripts_dir = 'Scripts' if os.name == 'nt' else 'bin'
    python_executable = os.path.join(venv_dir, scripts_dir, exe_name)
    
    if os.path.exists(python_executable):
        return os.path.abspath(python_executable)
        
    return None

def _is_path_ignored(file_path, project_path):
    """Verifica se um arquivo deve ser ignorado baseado na config."""
    config = _get_project_config(None, start_path=project_path)
    
    # Normalização robusta
    ignore_list = {p.strip('/\\').lower() for p in config.get('ignore', [])}
    ignore_list.update({'venv', '.git', '__pycache__', '.doxoade_cache', '.dox_agent_workspace'})
    
    try:
        rel_path = os.path.relpath(file_path, project_path)
    except ValueError:
        return True # Caminho inválido/fora da raiz
        
    parts = rel_path.replace('\\', '/').split('/')
    
    for part in parts:
        if part.lower() in ignore_list or (part.startswith('.') and part != '.'):
            return True
    return False

def collect_files_to_analyze(config, cmd_line_ignore=None):
    """Coleta arquivos .py respeitando ignores."""
    if cmd_line_ignore is None: cmd_line_ignore = []
    search_path = config.get('search_path', '.')
    
    # Normaliza padrões de ignore
    config_ignore = [p.strip('/\\').lower() for p in config.get('ignore', [])]
    cmd_line_ignore_list = [p.strip('/\\').lower() for p in list(cmd_line_ignore)]
    
    folders_to_ignore = set(config_ignore + cmd_line_ignore_list)
    folders_to_ignore.update(['venv', 'build', 'dist', '.git', '__pycache__', '.doxoade_cache', 'pytest_temp_dir', '.dox_agent_workspace'])

    files_to_check = []
    abs_search_path = os.path.abspath(search_path)

    for root, dirs, files in os.walk(abs_search_path, topdown=True):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in folders_to_ignore]
        
        rel_root = os.path.relpath(root, abs_search_path)
        if any(part.lower() in folders_to_ignore for part in rel_root.split(os.sep)):
            continue

        for file in files:
            if file.endswith('.py'):
                files_to_check.append(os.path.join(root, file))
                
    return files_to_check