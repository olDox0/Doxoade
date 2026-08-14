# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/blacklist.py
"""
Hermes Blacklist Central — Fonte única de verdade para módulos protegidos.
"""
from pathlib import Path
from typing import Set
import json
import os

# Blacklist hardcoded (sempre ativa)
HARDCODED_BLACKLIST = {
    # Módulos críticos que NUNCA devem ser comprimidos
    '__main__',
    'doxoade.rescue',
    'doxoade.chronos',
    'doxoade.__main__',
    'doxoade.cli',
    'doxoade.boot',
    # Ferramentas
    'doxoade.tools.alexandria',
    'doxoade.tools.doxcolors',
    'doxoade.tools.error_info',
    'doxoade.tools.filesystem',
    'doxoade.tools.ganesha_systems',
    'doxoade.tools.ganesha_systems.ganesha_advisor',
    'doxoade.tools.ganesha_systems.ganesha_advisor_standalone',
    'doxoade.tools.git',
    'doxoade.tools.git_utils',
    'doxoade.tools.horus_scribe',
    # Hermes internals (evitar recursão)
    'doxoade.tools.hermes_systems',
    'doxoade.tools.hermes_systems.hbc6_audit',
    'doxoade.tools.hermes_systems.hbc6_meta_finder',
    'doxoade.tools.hermes_systems.hermes_compress',
    'doxoade.tools.hermes_systems.hermes_compress_hbc5',
    'doxoade.tools.hermes_systems.hermes_compress_hbc6',
    'doxoade.tools.hermes_systems.hermes_decoder_vector',
    'doxoade.tools.hermes_systems.hermes_diagnostic',
    'doxoade.tools.hermes_systems.hermes_dict',
    'doxoade.tools.hermes_systems.hermes_dict.hermes_builder',
    'doxoade.tools.hermes_systems.hermes_dynamic_scanner',
    'doxoade.tools.hermes_systems.hermes_format',
    'doxoade.tools.hermes_systems.hermes_hook',
    'doxoade.tools.hermes_systems.hermes_hook_v2',
    'doxoade.tools.hermes_systems.hermes_init',
    'doxoade.tools.hermes_systems.hermes_loader',
    'doxoade.tools.hermes_systems.hermes_metrics',
    'doxoade.tools.hermes_systems.hermes_payload',
    'doxoade.tools.hermes_systems.hermes_preprocessor',
    'doxoade.tools.hermes_systems.hermes_scanner',
    'doxoade.tools.hermes_systems.native',
    # Vulcan (compilador nativo)
    'doxoade.tools.vulcan',
    'doxoade.tools.vulcan.meta_finder',
    # Aegis (segurança)
    'doxoade.tools.aegis',
    # Database
    'doxoade.core_database',
    'doxoade.tools.db_utils',
    # Telemetria
    'doxoade.tools.telemetry_tools',
    'doxoade.tools.horus',
    # Comandos
    'doxoade.commands.check',
    'doxoade.commands.cmd_hermes',
    'doxoade.commands.db',
    'doxoade.commands.git_branch',
    'doxoade.commands.refactor',
    'doxoade.commands.save',
    'doxoade.commands.intelligence',
    'doxoade.commands.intelligence_systems',
    'doxoade.commands.intelligence_utils',
}

# Prefixos que também são bloqueados
HARDCODED_BLACKLIST_PREFIXES = (
    'doxoade.tools.hermes_systems.',
    'doxoade.tools.vulcan.',
    'doxoade.tools.aegis.',
    'doxoade.tools.horus',
)

def sync_blacklist_defaults(project_root: Path) -> int:
    """
    Garante que a blacklist persistente tenha todos os defaults.
    Retorna o número de novos módulos adicionados.
    """
    current = load_persistent_blacklist(project_root)
    added = 0
    
    for module in HARDCODED_BLACKLIST:
        if module not in current:
            current.add(module)
            added += 1
    
    if added > 0:
        # ✅ ORDEM CORRETA: (project_root, modules)
        save_persistent_blacklist(project_root, current)
    
    return added

def is_path_blacklisted(file_path: str | Path, project_root: Path = None) -> bool:
    """
    Verifica se um arquivo está na blacklist.
    Aceita paths absolutos ou relativos.
    """
    if project_root is None:
        project_root = Path.cwd().resolve()
    
    try:
        p = Path(file_path).resolve()
        rel = p.relative_to(project_root)
        
        # Bloqueia extensões binárias sempre
        if p.suffix.lower() in {'.pyd', '.so', '.dll', '.exe', '.o', '.hbc6', '.hermes'}:
            return True
        
        # Converte para module name
        if p.suffix == '.py':
            module_name = str(rel.with_suffix('')).replace(os.sep, '.')
            return is_blacklisted(module_name, project_root)
        
        # Para outros arquivos, verifica se está em diretório blacklisted
        for part in rel.parts:
            if part in {'.doxoade', 'venv', '.venv', '__pycache__', 'node_modules'}:
                return True
        
        return False
        
    except (ValueError, AttributeError):
        return False

def get_blacklist_file(project_root: Path) -> Path:
    """Retorna o caminho do arquivo de blacklist persistente."""
    return project_root / '.doxoade' / 'hermes' / 'blacklist.json'


def load_persistent_blacklist(project_root: Path) -> Set[str]:
    """Carrega blacklist do disco (fail-graceful)."""
    blacklist_file = get_blacklist_file(project_root)
    if not blacklist_file.exists():
        return set()
    
    try:
        data = json.loads(blacklist_file.read_text(encoding='utf-8'))
        return set(data.get('modules', []))
    except Exception:
        return set()


def save_persistent_blacklist(project_root: Path, modules: Set[str]):
    """Salva blacklist no disco."""
    blacklist_file = get_blacklist_file(project_root)
    blacklist_file.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        'version': 1,
        'modules': sorted(modules),
    }
    
    tmp = blacklist_file.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(blacklist_file)


def get_unified_blacklist(project_root: Path) -> Set[str]:
    """Retorna blacklist unificada (hardcoded + persistente)."""
    blacklist = set(HARDCODED_BLACKLIST)
    blacklist.update(load_persistent_blacklist(project_root))
    return blacklist


def is_blacklisted(module_name: str, project_root: Path = None) -> bool:
    """Verifica se um módulo está na blacklist unificada."""
    if project_root:
        blacklist = get_unified_blacklist(project_root)
    else:
        blacklist = HARDCODED_BLACKLIST
    
    # Match exato
    if module_name in blacklist:
        return True
    
    # Match por prefixo
    if any(module_name.startswith(prefix) for prefix in HARDCODED_BLACKLIST_PREFIXES):
        return True
    
    return False


def add_to_blacklist(module_name: str, project_root: Path):
    """Adiciona módulo à blacklist persistente."""
    blacklist = load_persistent_blacklist(project_root)
    blacklist.add(module_name)
    save_persistent_blacklist(project_root, blacklist)


def remove_from_blacklist(module_name: str, project_root: Path):
    """Remove módulo da blacklist persistente."""
    blacklist = load_persistent_blacklist(project_root)
    blacklist.discard(module_name)
    save_persistent_blacklist(project_root, blacklist)
    