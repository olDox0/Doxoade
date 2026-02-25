# -*- coding: utf-8 -*-
# doxoade/tools/filesystem.py
import os
# [DOX-UNUSED] import sys
import toml
from pathlib import Path
# [DOX-UNUSED] from doxoade.tools.doxcolors import Fore

# Fonte Única da Verdade para Exclusões (OSL-17)
SYSTEM_IGNORES = {
    'venv', '.git', '__pycache__', 'build', 'dist', 
    '.doxoade', '.doxoade_cache', 'node_modules', 
    '.vscode', '.idea', 'pytest_temp_dir', '.dox_agent_workspace'
}

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

def _get_project_config(logger=None, start_path='.'):
    """
    Fonte Única da Verdade para Configuração (PASC 8.3).
    Garante que o retorno seja sempre uma tupla previsível.
    """
    root_path = _find_project_root(start_path)
    config = {'ignore': [], 'source_dir': '.', 'root_path': root_path}
    config_path = os.path.join(root_path, 'pyproject.toml')
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = toml.load(f)
                dox_config = data.get('tool', {}).get('doxoade', {})
                config.update(dox_config)
        except Exception as e:
            if logger: logger.add_finding("WARNING", f"Erro no TOML: {e}")

    # Normalização OSL: search_path é obrigatório e absoluto
    source_dir = config.get('source_dir', '.')
    config['search_path'] = os.path.abspath(os.path.join(root_path, source_dir))
    return config

def get_file_metadata(file_path: str):
    """
    Sincronizador de Unpack (Fix: expected 2).
    Sempre retorna exatamente (mtime: float, size: int).
    """
    try:
        st = os.stat(file_path)
        return float(st.st_mtime), int(st.st_size)
    except (OSError, FileNotFoundError):
        return 0.0, 0

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
    
def is_ignored(path: str, project_root: str, extra_patterns: set = None) -> bool:
    """Verifica se um caminho deve ser ignorado (PASC-8.17)."""
    try:
        rel_path = os.path.relpath(path, project_root).replace('\\', '/')
    except ValueError: return True
    
    parts = rel_path.lower().split('/')
    
    # Combina ignores do sistema com os customizados do usuário
    combined_ignores = SYSTEM_IGNORES.union(extra_patterns or set())
    
    # Se qualquer parte do caminho está na lista de proibidos, ignora
    return any(part in combined_ignores for part in parts)

def collect_project_files(search_path: str, project_root: str, extra_ignores: set = None):
    """
    Iterador Industrial de Arquivos (PASC-6.4).
    Otimiza o os.walk cortando diretórios ignorados na raiz da recursão.
    """
    combined_ignores = SYSTEM_IGNORES.union(extra_ignores or set())
    
    for root, dirs, files in os.walk(search_path, topdown=True):
        # Otimização Crítica: Modificar dirs in-place impede o walk de entrar nelas
        dirs[:] = [d for d in dirs if d.lower() not in combined_ignores and not d.startswith('.')]
        
        for file in files:
            if file.endswith('.py'):
                yield os.path.join(root, file)