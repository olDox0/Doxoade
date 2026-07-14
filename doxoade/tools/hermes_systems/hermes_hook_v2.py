# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_hook_v2.py
"""
Hermes Hook v2.1 — Produção (C-Native Fast Path + Telemetria)
==============================================================
Arquitetura:
  1. Intercepta o import (MetaPathFinder).
  2. Localiza o arquivo .hbc6 no build dir.
  3. Chama o hermes_bridge.pyd (Motor C).
  4. O Motor C faz mmap, expansão HBC5 (HGD1) e DFS HBC6.
  5. Injeta o CodeObject no sys.modules via nexus_exec().
  6. Fallback para Python puro se o Motor C falhar.

Telemetria:
  - Métricas de cold start vs warm start.
  - Contagem de módulos carregados via Hermes vs Python puro.
  - Tempo médio de carregamento por módulo.
"""
import os
import sys
import time
import importlib.abc
import importlib.machinery
import importlib.util
from pathlib import Path
from typing import Dict, Optional

# ═══════════════════════════════════════════════════════════════════════════════
# BLACKLIST DE SEGURANÇA (Anti-Recursão e Bootstrap)
# ═══════════════════════════════════════════════════════════════════════════════
# Módulos que NUNCA devem ser interceptados pelo Hermes v2.
HERMES_BLACKLIST_V2 = {
    'doxoade.tools.hermes_systems',
    'doxoade.tools.hermes_systems.hermes_hook',
    'doxoade.tools.hermes_systems.hermes_hook_v2',
    'doxoade.tools.hermes_systems.hermes_loader',
    'doxoade.tools.hermes_systems.hermes_compress',
    'doxoade.tools.hermes_systems.native',
    'doxoade.tools.hermes_systems.native.hermes_bridge',
    'doxoade.tools.vulcan',
    'doxoade.tools.aegis',
    'doxoade.tools.telemetry_tools',
    'doxoade.tools.alexandria',
    'doxoade.core_database',
    'doxoade.boot',
    'doxoade.rescue',
    'doxoade.__main__',
}

HERMES_BLACKLIST_PREFIXES_V2 = (
    'doxoade.tools.hermes_systems',
    'doxoade.tools.vulcan',
    'doxoade.tools.aegis',
    'doxoade.tools.telemetry_tools',
)

# ═══════════════════════════════════════════════════════════════════════════════
# THRESHOLD DE PERFORMANCE (Evita overhead em módulos pequenos)
# ═══════════════════════════════════════════════════════════════════════════════
# Módulos menores que este threshold NÃO serão interceptados pelo Motor C
# (Python puro é mais rápido para arquivos pequenos)
MIN_FILE_SIZE_KB = 20.0

_VERBOSE = os.environ.get('HERMES_VERBOSE') == '1'

def _log(msg: str):
    if _VERBOSE:
        sys.stderr.write(f'[HERMES-V2] {msg}\n')

def _is_blacklisted(fullname: str) -> bool:
    if fullname in HERMES_BLACKLIST_V2:
        return True
    return any(fullname.startswith(prefix) for prefix in HERMES_BLACKLIST_PREFIXES_V2)

# ═══════════════════════════════════════════════════════════════════════════════
# TELEMETRIA DE PERFORMANCE (Singleton)
# ═══════════════════════════════════════════════════════════════════════════════
class HermesTelemetry:
    """Métricas de performance do Hermes v2."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.stats = {
                'hermes_loads': 0,
                'python_fallbacks': 0,
                'total_hermes_ms': 0.0,
                'total_python_ms': 0.0,
                'modules': []
            }
        return cls._instance
    
    def record_hermes_load(self, module_name: str, elapsed_ms: float):
        self.stats['hermes_loads'] += 1
        self.stats['total_hermes_ms'] += elapsed_ms
        self.stats['modules'].append({
            'name': module_name,
            'method': 'hermes',
            'time_ms': elapsed_ms
        })
    
    def record_python_fallback(self, module_name: str, elapsed_ms: float):
        self.stats['python_fallbacks'] += 1
        self.stats['total_python_ms'] += elapsed_ms
        self.stats['modules'].append({
            'name': module_name,
            'method': 'python',
            'time_ms': elapsed_ms
        })
    
    def get_report(self) -> Dict:
        total = self.stats['hermes_loads'] + self.stats['python_fallbacks']
        avg_hermes = self.stats['total_hermes_ms'] / max(1, self.stats['hermes_loads'])
        avg_python = self.stats['total_python_ms'] / max(1, self.stats['python_fallbacks'])
        
        return {
            'total_modules': total,
            'hermes_loads': self.stats['hermes_loads'],
            'python_fallbacks': self.stats['python_fallbacks'],
            'avg_hermes_ms': avg_hermes,
            'avg_python_ms': avg_python,
            'speedup': avg_python / max(0.001, avg_hermes)
        }

_telemetry = HermesTelemetry()

# ═══════════════════════════════════════════════════════════════════════════════
# O LOADER v2 (O Motor de Injeção C-Native)
# ═══════════════════════════════════════════════════════════════════════════════
class HermesLoaderV2(importlib.abc.Loader):
    """
    Loader que bypassa o compile() do Python.
    Usa o hermes_bridge (C) para gerar o PyCodeObject e executa direto.
    """
    def __init__(self, fullname: str, hermes_path: Path, global_dict_path: Path, original_py_path: Path = None):
        self.fullname = fullname
        self.hermes_path = hermes_path
        self.global_dict_path = global_dict_path
        self.original_py_path = original_py_path
    
    def create_module(self, spec):
        # Deixa o Python criar o objeto módulo padrão (sys.modules)
        return None 
    
    def exec_module(self, module):
        # 1. Configura Metadados Básicos (Obrigatório para o Python)
        module.__file__ = str(self.hermes_path)
        module.__loader__ = self
        if self.original_py_path:
            module.__file__ = str(self.original_py_path) # Para tracebacks apontarem para o .py
        
        # 2. TENTATIVA DE FAST PATH (C-Native SSE 4.2)
        t0 = time.perf_counter()
        c_code_obj = self._try_c_bridge()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        
        if c_code_obj is not None:
            _log(f"✔ [C-BRIDGE] {self.fullname} carregado via Motor Nativo ({elapsed_ms:.2f}ms)")
            _telemetry.record_hermes_load(self.fullname, elapsed_ms)
            
            # O C-Bridge retornou um PyCodeObject válido. 
            # O nexus_exec() aceita code objects diretamente.
            try:
                from doxoade.tools.aegis.aegis_core import nexus_exec
                nexus_exec(c_code_obj, module.__dict__)
                return
            except Exception as e:
                _log(f"✘ [C-BRIDGE] Falha na execução do code object: {e}")
                # Se falhar na execução, cai para o fallback Python
        
        # 3. FALLBACK (Python Puro / Hermes v1)
        _log(f"⚠ [FALLBACK] {self.fullname} usando loader Python padrão.")
        t0 = time.perf_counter()
        self._python_fallback(module)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        _telemetry.record_python_fallback(self.fullname, elapsed_ms)
    
    def _try_c_bridge(self):
        """Tenta carregar o módulo via hermes_bridge.pyd (C-Native)."""
        try:
            # Importa o motor C. Se não estiver compilado, lança ImportError.
            from doxoade.tools.hermes_systems.native import hermes_bridge
            
            # Chama a função C: load_module(hermes_path, global_dict_path)
            # O C faz o parse HBC6, mmap, expansão HBC5 (HGD1) e DFS HBC6.
            code_obj = hermes_bridge.load_module(
                str(self.hermes_path),
                str(self.global_dict_path)
            )
            return code_obj
        except Exception as e:
            _log(f"✘ [C-BRIDGE] Falha ao carregar {self.fullname}: {e}")
            return None
    
    def _python_fallback(self, module):
        """Fallback para o loader Python padrão (Hermes v1 ou compile())."""
        try:
            from doxoade.tools.hermes_systems.hermes_loader import HermesLoader
            project_root = self.hermes_path.parent.parent.parent.parent
            loader = HermesLoader(str(project_root))
            
            # Tenta carregar via Hermes v1 (HBC3/HBC4/HBC5)
            code_obj = loader.decompress_to_code(self.hermes_path)
            
            if code_obj is None:
                # Se não houver .hermes, usa o .py original
                if self.original_py_path and self.original_py_path.exists():
                    source = self.original_py_path.read_text(encoding='utf-8')
                    code_obj = compile(source, str(self.original_py_path), 'exec')
                else:
                    raise ImportError(f"Hermes skipou módulo mas não há .py fallback: {self.hermes_path}")
            
            # Executa o code object
            from doxoade.tools.aegis.aegis_core import nexus_exec
            nexus_exec(code_obj, module.__dict__)
        except Exception as e:
            _log(f"✘ [FALLBACK] Erro crítico no fallback Python: {e}")
            raise

# ═══════════════════════════════════════════════════════════════════════════════
# O FINDER v2 (MetaPathFinder)
# ═══════════════════════════════════════════════════════════════════════════════
class HermesFinderV2(importlib.abc.MetaPathFinder):
    """
    Intercepta imports e redireciona para o Hermes v2 (HBC6 + Motor C).
    """
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.build_dir = self.project_root / '.doxoade' / 'hermes' / 'build'
        self.global_dict_path = self.project_root / '.doxoade' / 'hermes' / 'master.bin'
        
        # Cache de módulos encontrados (O(1) lookup)
        self._module_cache: Dict[str, Path] = {}
        self._build_index()
    
    def _build_index(self):
        """Constrói índice de módulos .hbc6 disponíveis."""
        if not self.build_dir.exists():
            return
        
        for hbc6_file in self.build_dir.glob('*.hbc6'):
            # Extrai o nome do módulo do path
            # Ex: .doxoade/hermes/build/doxoade.tools.vulcan.compiler.hbc6
            module_name = hbc6_file.stem.replace('.hbc6', '')
            self._module_cache[module_name] = hbc6_file
    
    def find_spec(self, fullname, path, target=None):
        """Intercepta imports e redireciona para o Hermes v2."""
        # 1. Verifica blacklist
        if _is_blacklisted(fullname):
            return None
        
        # 2. Verifica se o módulo está no cache
        if fullname not in self._module_cache:
            return None
        
        hermes_path = self._module_cache[fullname]
        
        # 3. 🚀 SMART THRESHOLD: Bypass para módulos pequenos
        # Python puro é mais rápido para arquivos pequenos (< MIN_FILE_SIZE_KB)
        try:
            file_size_kb = hermes_path.stat().st_size / 1024
            if file_size_kb < MIN_FILE_SIZE_KB:
                _log(f"⚡ [THRESHOLD] {fullname} ({file_size_kb:.1f}KB) é pequeno. Usando Python puro.")
                return None
            
            # 4. Verifica se há compressão HBC5 (Flag 0x01)
            with open(hermes_path, 'rb') as f:
                header = f.read(6) # Magic(4) + Version(1) + Flags(1)
                if len(header) == 6:
                    flags = header[5]
                    if not (flags & 0x01): # FLAG_TOKENIZED_CONSTS não está setada
                        _log(f"⚡ [THRESHOLD] {fullname} não tem tokens HBC5. Usando Python puro.")
                        return None
        except Exception as e:
            _log(f"⚠ [THRESHOLD] Falha ao ler header de {fullname}: {e}. Prosseguindo com Motor C.")
        
        # 5. FAST PATH: Módulo grande e/ou tokenizado -> Usa Motor C
        original_py_path = self._resolve_py_path(fullname)
        
        loader = HermesLoaderV2(
            fullname=fullname,
            hermes_path=hermes_path,
            global_dict_path=self.global_dict_path,
            original_py_path=original_py_path
        )
        
        spec = importlib.machinery.ModuleSpec(
            name=fullname,
            loader=loader,
            origin=str(hermes_path),
            is_package=False
        )
        
        if original_py_path:
            spec.submodule_search_locations = [str(original_py_path.parent)]
        
        return spec
    
    def _resolve_py_path(self, fullname: str) -> Optional[Path]:
        """Resolve o path do .py original para fallback."""
        # Converte nome do módulo para path
        # Ex: doxoade.tools.vulcan.compiler -> doxoade/tools/vulcan/compiler.py
        module_path = fullname.replace('.', os.sep) + '.py'
        py_path = self.project_root / module_path
        
        if py_path.exists():
            return py_path
        
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# API PÚBLICA (Install / Uninstall)
# ═══════════════════════════════════════════════════════════════════════════════
_HERMES_FINDER_INSTANCE: Optional[HermesFinderV2] = None

def install(project_root: str):
    """Instala o Hermes v2 no sys.meta_path."""
    global _HERMES_FINDER_INSTANCE
    
    if _HERMES_FINDER_INSTANCE is not None:
        _log("Hermes v2 já está instalado.")
        return
    
    # Verifica se o Motor C está compilado
    try:
        from doxoade.tools.hermes_systems.native import hermes_bridge
        _log("Motor C (hermes_bridge.pyd) encontrado.")
    except ImportError:
        _log("✘ Motor C não encontrado. Compile com: doxoade hermes build-native")
        return
    
    # Cria o finder
    _HERMES_FINDER_INSTANCE = HermesFinderV2(project_root)
    
    # Insere no topo do sys.meta_path (prioridade máxima)
    sys.meta_path.insert(0, _HERMES_FINDER_INSTANCE)
    
    _log(f"✔ Hermes v2 instalado. Módulos disponíveis: {len(_HERMES_FINDER_INSTANCE._module_cache)}")

def uninstall():
    """Remove o Hermes v2 do sys.meta_path."""
    global _HERMES_FINDER_INSTANCE
    
    if _HERMES_FINDER_INSTANCE is None:
        return
    
    sys.meta_path.remove(_HERMES_FINDER_INSTANCE)
    _HERMES_FINDER_INSTANCE = None
    
    _log("Hermes v2 desinstalado.")

def get_telemetry_report() -> Dict:
    """Retorna o relatório de performance do Hermes v2."""
    return _telemetry.get_report()

def print_telemetry_report():
    """Imprime o relatório de performance no console."""
    from doxoade.tools.doxcolors import Fore, Style
    
    report = get_telemetry_report()
    
    print(f"\n{'═' * 70}")
    print(f"  📊 HERMES V2 TELEMETRY REPORT")
    print(f"{'═' * 70}")
    print(f"  Total de Módulos Carregados : {report['total_modules']}")
    print(f"  ├─ Via Motor C (HBC6)       : {Fore.GREEN}{report['hermes_loads']}{Style.RESET_ALL}")
    print(f"  └─ Fallback Python          : {Fore.YELLOW}{report['python_fallbacks']}{Style.RESET_ALL}")
    print(f"  ──────────────────────────────────────────────────────────")
    print(f"  Tempo Médio de Carregamento :")
    print(f"  ├─ Motor C (HBC6)           : {Fore.GREEN}{report['avg_hermes_ms']:.2f} ms{Style.RESET_ALL}")
    print(f"  └─ Python Puro              : {Fore.YELLOW}{report['avg_python_ms']:.2f} ms{Style.RESET_ALL}")
    print(f"  ──────────────────────────────────────────────────────────")
    print(f"  Speedup Médio               : {Fore.CYAN}{report['speedup']:.2f}×{Style.RESET_ALL}")
    print(f"{'═' * 70}\n")