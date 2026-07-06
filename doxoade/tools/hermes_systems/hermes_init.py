# doxoade/tools/hermes_systems/hermes_init.py
"""
Hermes Init - Sistema de Bootstrap Acelerado
=============================================
Pré-compila e carrega módulos críticos do Doxoade como binários nativos.
Resolve o paradoxo do bootstrapper: o sistema de carregamento rápido
não pode usar a si mesmo para carregar.

Arquitetura:
  Fase 1: Bootstrap Nativo (módulos críticos → .pyd)
  Fase 2: Hermes Runtime (módulos usuário → .hermes)

Módulos críticos (blacklist):
  - doxoade.tools.hermes_systems.*
  - doxoade.tools.vulcan.*
  - doxoade.tools.aegis.*
  - doxoade.core_database
  - doxoade.boot
"""

import sys
import os
from pathlib import Path
from typing import List, Set

# Módulos que devem ser pré-compilados (carregados como .pyd)
CRITICAL_MODULES = {
    'doxoade.tools.hermes_systems',
    'doxoade.tools.vulcan',
    'doxoade.tools.aegis',
    'doxoade.core_database',
    'doxoade.boot',
    'doxoade.rescue',
}

def get_critical_modules() -> Set[str]:
    """Retorna lista de módulos críticos que precisam de bootstrap nativo."""
    return CRITICAL_MODULES.copy()

def is_critical_module(module_name: str) -> bool:
    """Verifica se um módulo é crítico (precisa de bootstrap nativo)."""
    return any(
        module_name.startswith(critical)
        for critical in CRITICAL_MODULES
    )

def find_native_binary(module_name: str, project_root: Path) -> Path | None:
    """
    Localiza o binário nativo (.pyd/.so) para um módulo crítico.
    Usa o mesmo esquema de hash do VulcanMetaFinder.
    """
    import hashlib
    
    # Converte nome do módulo para path do arquivo
    module_path = module_name.replace('.', os.sep) + '.py'
    source_path = project_root / module_path
    
    if not source_path.exists():
        return None
    
    # Calcula hash do conteúdo (mesmo esquema do Vulcan)
    try:
        content = source_path.read_text(encoding='utf-8', errors='ignore').replace('\r\n', '\n')
        path_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:6]
    except Exception:
        path_hash = "000000"
    
    # Busca binário no diretório bin/
    bin_dir = project_root / '.doxoade' / 'vulcan' / 'bin'
    ext = '.pyd' if os.name == 'nt' else '.so'
    
    # Tenta vários padrões de nome
    candidates = [
        f'v_{source_path.stem}_{path_hash}{ext}',
        f'v_{source_path.stem}{ext}',
        f'v_{module_name.replace(".", "__")}_{path_hash}{ext}',
    ]
    
    for candidate in candidates:
        binary_path = bin_dir / candidate
        if binary_path.exists():
            return binary_path
    
    return None

def load_native_module(module_name: str, binary_path: Path) -> bool:
    """
    Carrega um módulo crítico diretamente do binário nativo.
    Retorna True se sucesso, False se falha.
    """
    import importlib.util
    
    try:
        # Cria spec diretamente do binário (sem MetaPathFinder)
        spec = importlib.util.spec_from_file_location(
            module_name,
            str(binary_path)
        )
        
        if not spec or not spec.loader:
            return False
        
        # Carrega o módulo
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        return True
    except Exception as e:
        if os.environ.get('HERMES_VERBOSE') == '1':
            print(f"[HERMES-INIT] Falha ao carregar {module_name}: {e}")
        return False

def bootstrap_critical_modules(project_root: Path) -> dict:
    """
    Fase 1: Bootstrap Nativo
    Carrega todos os módulos críticos como binários nativos.
    
    Retorna:
        dict com estatísticas:
        - 'loaded': número de módulos carregados com sucesso
        - 'failed': número de módulos que falharam
        - 'fallback': número de módulos que usaram fallback .py
    """
    stats = {
        'loaded': 0,
        'failed': 0,
        'fallback': 0,
        'modules': [],
    }
    
    # Itera sobre todos os módulos críticos
    for critical_prefix in CRITICAL_MODULES:
        # Busca todos os módulos que começam com este prefixo
        for module_name in list(sys.modules.keys()):
            if not module_name.startswith(critical_prefix):
                continue
            
            # Já está carregado?
            if module_name in sys.modules:
                continue
            
            # Tenta carregar como binário nativo
            binary_path = find_native_binary(module_name, project_root)
            
            if binary_path:
                success = load_native_module(module_name, binary_path)
                if success:
                    stats['loaded'] += 1
                    stats['modules'].append({
                        'name': module_name,
                        'type': 'native',
                        'path': str(binary_path),
                    })
                    if os.environ.get('HERMES_VERBOSE') == '1':
                        print(f"[HERMES-INIT] ✔ {module_name} (native)")
                else:
                    stats['failed'] += 1
                    stats['modules'].append({
                        'name': module_name,
                        'type': 'failed',
                        'error': 'load_failed',
                    })
            else:
                # Fallback: deixa o Python carregar normalmente
                stats['fallback'] += 1
                stats['modules'].append({
                    'name': module_name,
                    'type': 'fallback',
                    'reason': 'no_binary',
                })
    
    return stats

def compile_critical_modules(project_root: Path, force: bool = False) -> dict:
    """
    Pré-compila todos os módulos críticos usando Vulcan.
    
    Args:
        project_root: Raiz do projeto
        force: Se True, recompila mesmo se .pyd já existir
    
    Returns:
        dict com estatísticas de compilação
    """
    stats = {
        'compiled': 0,
        'skipped': 0,
        'failed': 0,
        'modules': [],
    }
    
    # Importa o Vulcan (só funciona se já estiver carregado)
    try:
        from doxoade.tools.vulcan.compiler import VulcanCompiler
        from doxoade.tools.vulcan.environment import VulcanEnvironment
    except ImportError:
        if os.environ.get('HERMES_VERBOSE') == '1':
            print("[HERMES-INIT] ⚠ Vulcan não disponível, pulando compilação")
        return stats
    
    # Cria ambiente Vulcan
    env = VulcanEnvironment(str(project_root))
    compiler = VulcanCompiler(env)
    
    # Compila cada módulo crítico
    for critical_prefix in CRITICAL_MODULES:
        # Busca todos os .py que começam com este prefixo
        module_path = critical_prefix.replace('.', os.sep)
        source_dir = project_root / module_path
        
        if not source_dir.exists():
            continue
        
        # Compila todos os .py no diretório
        for py_file in source_dir.rglob('*.py'):
            if py_file.name.startswith('__'):
                continue
            
            # Verifica se já existe .pyd atualizado
            binary_path = find_native_binary(
                py_file.stem,
                project_root
            )
            
            if binary_path and not force:
                # Verifica se .pyd é mais recente que .py
                if py_file.stat().st_mtime < binary_path.stat().st_mtime:
                    stats['skipped'] += 1
                    continue
            
            # Compila o módulo
            try:
                success = compiler.compile_module(str(py_file))
                if success:
                    stats['compiled'] += 1
                    stats['modules'].append({
                        'name': py_file.stem,
                        'type': 'compiled',
                        'path': str(py_file),
                    })
                else:
                    stats['failed'] += 1
                    stats['modules'].append({
                        'name': py_file.stem,
                        'type': 'failed',
                        'error': 'compile_failed',
                    })
            except Exception as e:
                stats['failed'] += 1
                stats['modules'].append({
                    'name': py_file.stem,
                    'type': 'failed',
                    'error': str(e),
                })
    
    return stats

def init_hermes_bootstrap(project_root: Path, compile_if_missing: bool = True) -> dict:
    """
    Inicializa o sistema Hermes Init (bootstrap acelerado).
    
    Args:
        project_root: Raiz do projeto
        compile_if_missing: Se True, compila módulos críticos se .pyd não existir
    
    Returns:
        dict com estatísticas completas do bootstrap
    """
    stats = {
        'bootstrap': None,
        'compile': None,
        'total_time_ms': 0,
    }
    
    import time
    start = time.perf_counter()
    
    # Fase 1: Bootstrap Nativo
    stats['bootstrap'] = bootstrap_critical_modules(project_root)
    
    # Fase 2: Compilação (se necessário)
    if compile_if_missing and stats['bootstrap']['fallback'] > 0:
        stats['compile'] = compile_critical_modules(project_root, force=False)
    
    # Calcula tempo total
    stats['total_time_ms'] = (time.perf_counter() - start) * 1000
    
    return stats

if __name__ == '__main__':
    # Teste standalone
    import sys
    project_root = Path.cwd()
    
    print("[HERMES-INIT] Iniciando bootstrap acelerado...")
    stats = init_hermes_bootstrap(project_root, compile_if_missing=False)
    
    print(f"\n[HERMES-INIT] Estatísticas:")
    print(f"  Módulos carregados (native): {stats['bootstrap']['loaded']}")
    print(f"  Módulos com fallback (.py): {stats['bootstrap']['fallback']}")
    print(f"  Módulos que falharam: {stats['bootstrap']['failed']}")
    print(f"  Tempo total: {stats['total_time_ms']:.2f}ms")