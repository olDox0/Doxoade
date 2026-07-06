# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_hook_v2.py
"""
Hermes Hook v2 - MetaPathFinder & Loader (C-Native Fast Path)
=============================================================
O "Pulo do Gato" contra o Memory Wall e o Import Machinery do Python.

Arquitetura:
  1. Intercepta o import (MetaPathFinder).
  2. Localiza o arquivo .hermes (HBC5) no build dir.
  3. Chama o hermes_bridge.pyd (C-Native SSE 4.2).
  4. O C-bridge parseia o HBC5, expande os tokens branchless e 
     retorna um PyCodeObject pronto.
  5. Injeta o Code Object no sys.modules via nexus_exec() seguro.

Ganhos esperados:
  - Bypass do compile() (Economia de ~10ms por módulo)
  - Bypass do import_loader Python (Economia de ~31ms por módulo)
  - Bypass do reverse_tokens em Python (Economia de ~0.4ms)
"""
import os
import sys
import importlib.abc
import importlib.machinery
import importlib.util
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# BLACKLIST DE SEGURANÇA (Anti-Recursão e Bootstrap)
# ═══════════════════════════════════════════════════════════════════════════════
# Módulos que NUNCA devem ser interceptados pelo Hermes v2.
# Se o hook tentar carregar o próprio motor C ou o Vulcan usando o motor C,
# o sistema entra em colapso por dependência circular.
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
    'doxoade.tools.filesystem',
    'doxoade.tools.doxcolors',
    'doxoade.tools.error_info',
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

_VERBOSE = os.environ.get('HERMES_VERBOSE') == '1'

def _log(msg: str):
    if _VERBOSE:
        sys.stderr.write(f'[HERMES-V2] {msg}\n')

def _is_blacklisted(fullname: str) -> bool:
    if fullname in HERMES_BLACKLIST_V2:
        return True
    return any(fullname.startswith(prefix) for prefix in HERMES_BLACKLIST_PREFIXES_V2)


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
        c_code_obj = self._try_c_bridge()
        
        if c_code_obj is not None:
            _log(f"✔ [C-BRIDGE] {self.fullname} carregado via Motor Nativo (Zero-Compile)")
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
        self._python_fallback(module)

    def _try_c_bridge(self):
        """Tenta carregar o módulo via hermes_bridge.pyd (C-Native)."""
        try:
            # Importa o motor C. Se não estiver compilado, lança ImportError.
            from doxoade.tools.hermes_systems.native import hermes_bridge
            
            # Chama a função C: load_module(hermes_path, global_dict_path)
            # O C faz o parse HBC5, mmap, expansão branchless e retorna o PyCodeObject.
            code_obj = hermes_bridge.load_module(
                str(self.hermes_path), 
                str(self.global_dict_path)
            )
            return code_obj
        except ImportError:
            _log("Motor C (hermes_bridge) não encontrado. Usando fallback.")
            return None
        except Exception as e:
            _log(f"Erro no Motor C: {e}")
            return None

    def _python_fallback(self, module):
        """Fallback para o Hermes Loader original (Python) ou compile() nativo."""
        if not self.original_py_path or not self.original_py_path.exists():
            raise ImportError(f"Hermes V2: Falha no C-Bridge e .py original não encontrado para {self.fullname}")
        
        try:
            # Tenta o loader Python do Hermes v1 (se existir e estiver funcional)
            from doxoade.tools.hermes_systems.hermes_loader import HermesLoader
            loader = HermesLoader(str(self.hermes_path.parent.parent.parent.parent))
            code_obj = loader.decompress_to_code(self.hermes_path)
            if code_obj:
                from doxoade.tools.aegis.aegis_core import nexus_exec
                nexus_exec(code_obj, module.__dict__)
                return
        except Exception:
            pass # Se o Hermes v1 falhar, vamos para o compile() puro

        # Último recurso: Lê o .py original e compila (O comportamento padrão do Python)
        source = self.original_py_path.read_text(encoding='utf-8')
        code = compile(source, str(self.original_py_path), 'exec', optimize=2)
        from doxoade.tools.aegis.aegis_core import nexus_exec
        nexus_exec(code, module.__dict__)


# ═══════════════════════════════════════════════════════════════════════════════
# O FINDER v2 (O Radar de Interceptação)
# ═══════════════════════════════════════════════════════════════════════════════
class HermesFinderV2(importlib.abc.MetaPathFinder):
    """
    Intercepta sys.meta_path para procurar arquivos .hermes (HBC5).
    """
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.hermes_build_dir = self.root / '.doxoade' / 'hermes' / 'build'
        self.global_dict_path = self.root / '.doxoade' / 'hermes' / 'master.dict'
        
        # Cache em RAM para evitar I/O de disco no find_spec (O(1) lookup)
        self._hermes_index = {}
        self._build_index()

    def _build_index(self):
        """Varre o diretório build uma vez e mapeia module_name -> hermes_path."""
        if not self.hermes_build_dir.exists():
            return
        
        # O compressor salva como "doxoade.cli.hermes"
        for hermes_file in self.hermes_build_dir.rglob('*.hermes'):
            # Extrai o nome do módulo relativo ao build_dir
            rel_path = hermes_file.relative_to(self.hermes_build_dir)
            module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')
            self._hermes_index[module_name] = hermes_file

    def find_spec(self, fullname, path, target=None):
        # 1. Segurança (Blacklist)
        if _is_blacklisted(fullname):
            return None

        # 2. Verifica se o módulo foi comprimido no Hermes (O(1) Cache Hit)
        hermes_path = self._hermes_index.get(fullname)
        
        if not hermes_path or not hermes_path.exists():
            return None

        # 3. Tenta achar o .py original para metadados de traceback
        original_py_path = self.root / (fullname.replace('.', os.sep) + '.py')
        if not original_py_path.exists():
            original_py_path = None

        _log(f"🎯 [FINDER] Interceptado: {fullname} -> {hermes_path.name}")

        # 4. Cria o ModuleSpec com o nosso Loader V2
        loader = HermesLoaderV2(fullname, hermes_path, self.global_dict_path, original_py_path)
        spec = importlib.machinery.ModuleSpec(fullname, loader, origin=str(hermes_path))
        
        # Se for um pacote (tem __init__.py), configura o subpath
        if original_py_path and original_py_path.name == '__init__.py':
            spec.submodule_search_locations = [str(original_py_path.parent)]

        return spec


# ═══════════════════════════════════════════════════════════════════════════════
# API DE INSTALAÇÃO (Para o boot.py)
# ═══════════════════════════════════════════════════════════════════════════════
_FINDER_INSTANCE = None

def install(project_root: str):
    """
    Instala o Hermes Finder v2 no sys.meta_path.
    Deve ser chamado APÓS o VulcanMetaFinder e ShadowFinder.
    """
    global _FINDER_INSTANCE
    if _FINDER_INSTANCE is not None:
        return # Já instalado

    finder = HermesFinderV2(project_root)
    
    # Insere no meta_path. 
    # O Vulcan está no índice 0, Shadow no 1. Hermes vai para o 2.
    sys.meta_path.insert(2, finder)
    _FINDER_INSTANCE = finder
    _log(f"✔ [HOOK V2] Instalado no sys.meta_path. Index: {len(finder._hermes_index)} módulos.")

def uninstall():
    """Remove o hook do sys.meta_path."""
    global _FINDER_INSTANCE
    if _FINDER_INSTANCE in sys.meta_path:
        sys.meta_path.remove(_FINDER_INSTANCE)
    _FINDER_INSTANCE = None