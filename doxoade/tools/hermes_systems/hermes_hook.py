# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_hook.py
"""
Hermes MetaPathFinder - Integração com VulcanMetaFinder.
Quando o Vulcan detectar Tier 3 (Python puro), redireciona para Hermes.
"""
import os
import sys
import time
import importlib.abc
import importlib.util
from pathlib import Path
import threading

from doxoade.tools.error_info import formated_traceback

_jit_stats = {'built': 0, 'skipped': 0, 'failed': 0}
_jit_lock = threading.Lock()
_jit_built = set()

# ═══════════════════════════════════════════════════════════════════════
# BLACKLIST DE SEGURANÇA (Anti-Recursão Infinita)
# ═══════════════════════════════════════════════════════════════════════
HERMES_BLACKLIST = {
    # Módulos do próprio Hermes (CRÍTICO!)
    'doxoade.commands.cmd_hermes',
    'doxoade.tools.hermes_systems',
    'doxoade.tools.hermes_systems.hermes_hook',
    'doxoade.tools.hermes_systems.hermes_loader',
    'doxoade.tools.hermes_systems.hermes_compress',
    'doxoade.tools.hermes_systems.hermes_scanner',
    'doxoade.tools.hermes_systems.hermes_dynamic_scanner',
    'doxoade.tools.hermes_systems.hermes_preprocessor',
    'doxoade.tools.hermes_systems.hermes_format',
    'doxoade.tools.hermes_systems.hermes_metrics',
    'doxoade.tools.hermes_systems.hermes_dict',
    'doxoade.tools.hermes_systems.hermes_dict.hermes_builder',
    
    # Módulos de infraestrutura crítica
    'doxoade.tools.aegis',
    'doxoade.tools.telemetry_tools',
    'doxoade.tools.alexandria',
    'doxoade.tools.filesystem',
    'doxoade.core_database',
    'doxoade.boot',
    'doxoade.rescue',
    'doxoade.__main__',
    'doxoade.tools.doxcolors',
    'doxoade.tools.error_info',

    # Módulos do Vulcan e Shadow
    'doxoade.tools.vulcan',
    'doxoade.tools.horus',
    'doxoade.tools.horus_scribe',
    
    'doxoade.commands.intelligence',
    'doxoade.commands.intelligence_systems',
    'doxoade.commands.intelligence_utils',
    
    # ✅ NOVO: Bibliotecas com lazy loading complexo (temporário)
#    'colorama',
#    'colorama.initialise',
#    'colorama.ansitowin32',
#    'colorama.ansi',
#    'colorama.winterm',
#    'colorama.win32',
#    'click',
#    'click.core',
#    'click.decorators',
#    'click.types',
#    'click._compat',
#    'click._winconsole',
#    'click.exceptions',
#    'click.globals',
#    'click.utils',
#    'click._utils',
#    'click.formatting',
#    'click.parser',
#    'click.termui',
}

HERMES_BLACKLIST_PREFIXES = (
    'doxoade.tools.hermes_systems',
    'doxoade.tools.aegis',
    'doxoade.tools.telemetry_tools',
    'doxoade.tools.alexandria',
    'doxoade.tools.vulcan',
    'doxoade.tools.horus',
    'colorama',  # ← ADICIONAR
    'click',     # ← ADICIONARclass HermesModuleLoader(importlib.abc.Loader):
)
_HERMES_FINDER_MARKER = True
_VERBOSE = os.environ.get('HERMES_VERBOSE') == '1'

def _log(msg: str):
    if _VERBOSE:
        sys.stderr.write(f'[HERMES] {msg}\n')

def _is_blacklisted(fullname: str) -> bool:
    """Verifica se um módulo está na blacklist."""
    if fullname in HERMES_BLACKLIST:
        return True
    if any(fullname.startswith(prefix) for prefix in HERMES_BLACKLIST_PREFIXES):
        return True
    return False

# ═══════════════════════════════════════════════════════════════════════
# HERMES LOADER (Executa o código descomprimido)
# ═══════════════════════════════════════════════════════════════════════
class HermesModuleLoader(importlib.abc.Loader):
    def __init__(self, hermes_path: Path, original_py_path: Path = None, package_name: str = None):
        self.hermes_path = hermes_path
        self.original_py_path = original_py_path
        self.package_name = package_name
        self._executed = False
    
    def create_module(self, spec):
        return None
    
    def exec_module(self, module):
        from doxoade.tools.aegis.aegis_core import nexus_exec
        try:
            from doxoade.tools.hermes_systems.hermes_loader import HermesLoader
            project_root = self.hermes_path.parent.parent.parent.parent
            loader = HermesLoader(str(project_root))
            
            # CARREGAMENTO ADAPTATIVO (Fase 3)
            file_size = self.hermes_path.stat().st_size
            code_obj = loader.decompress_to_code_adaptive(self.hermes_path, file_size)
            
            # Se retornou None, usa Python puro (fallback)
            if code_obj is None:
                if self.original_py_path and self.original_py_path.exists():
                    source = self._read_py_resilient(self.original_py_path)
                    module.__file__ = str(self.original_py_path)
                    self._setup_module_metadata(module)
                    code = compile(source, str(self.original_py_path), 'exec')
                    nexus_exec(code, module.__dict__)
                    return
                else:
                    raise ImportError(f"Hermes skipou módulo pequeno mas não há .py fallback: {self.hermes_path}")
            
            # Configura metadados
            self._setup_module_metadata(module)
            module.__file__ = str(self.hermes_path)
            
            # Execução Segura via Aegis
            nexus_exec(code_obj, module.__dict__)
            
        except Exception as e:
            # Fallback para .py original
            if (self.original_py_path
                    and self.original_py_path.exists()
                    and self.original_py_path.suffix == '.py'
                    and self.original_py_path.resolve() != self.hermes_path.resolve()):
                try:
                    source = self._read_py_resilient(self.original_py_path)
                    module.__file__ = str(self.original_py_path)
                    self._setup_module_metadata(module)
                    code = compile(source, str(self.original_py_path), 'exec')
                    nexus_exec(code, module.__dict__)
                    return
                except Exception as fallback_err:
                    raise ImportError(
                        f"Hermes falhou: {e} | Fallback .py também falhou: {fallback_err}"
                    ) from e
            else:
                raise ImportError(f"Falha crítica no Hermes Loader: {e}") from e
    
    def _setup_module_metadata(self, module):
        """Configura metadados do módulo."""
        if self.package_name:
            module.__package__ = self.package_name
        elif '.' in module.__name__:
            module.__package__ = module.__name__.rsplit('.', 1)[0]
        else:
            module.__package__ = module.__name__
        
        if self.original_py_path and self.original_py_path.name == '__init__.py':
            module.__path__ = [str(self.original_py_path.parent)]
        elif self.hermes_path.name.endswith('.__init__.hermes'):
            module.__path__ = [str(self.hermes_path.parent)]
    
    def _resolve_safe_py_path(self):
        """
        Resolve o caminho do .py original de forma SEGURA.
        NUNCA retorna um arquivo .hermes.
        """
        # 1. Verifica se original_py_path é válido e é .py
        if (self.original_py_path 
                and self.original_py_path.exists()
                and self.original_py_path.suffix == '.py'
                and not str(self.original_py_path).endswith('.hermes')):
            return self.original_py_path
        
        # 2. Tenta resolver pelo nome do módulo
        module_name = None
        hermes_stem = self.hermes_path.stem  # ex: doxoade.tools.command_metadata
        
        # 3. Constrói o path do .py a partir do project root
        project_root = self.hermes_path.parent.parent.parent.parent
        parts = hermes_stem.split('.')
        
        candidates = []
        
        # Path direto: doxoade/tools/command_metadata.py
        if len(parts) >= 2:
            direct_path = project_root / Path(*parts[:-1]) / f"{parts[-1]}.py"
            candidates.append(direct_path)
            
            # __init__.py: doxoade/tools/command_metadata/__init__.py
            init_path = project_root / Path(*parts) / '__init__.py'
            candidates.append(init_path)
        
        # Path com primeiro elemento como raiz
        if len(parts) >= 3:
            alt_path = project_root / parts[0] / Path(*parts[1:-1]) / f"{parts[-1]}.py"
            candidates.append(alt_path)
        
        for candidate in candidates:
            if (candidate.exists() 
                    and candidate.suffix == '.py'
                    and not str(candidate).endswith('.hermes')):
                return candidate
        
        # 4. Último recurso: busca global
        try:
            import importlib.machinery
            spec = importlib.machinery.PathFinder.find_spec(hermes_stem)
            if (spec and spec.origin 
                    and spec.origin.endswith('.py')
                    and not spec.origin.endswith('.hermes')):
                return Path(spec.origin)
        except Exception:
            pass
        
        return None

    def _set_module_metadata(self, module, py_path):
        """Configura metadados do módulo."""
        if self.package_name:
            module.__package__ = self.package_name
        elif '.' in module.__name__:
            module.__package__ = module.__name__.rsplit('.', 1)[0]
        else:
            module.__package__ = module.__name__
        
        if py_path.name == '__init__.py':
            module.__path__ = [str(py_path.parent)]

    @staticmethod
    def _read_py_resilient(path: Path) -> str:
        """Lê arquivo .py com encoding resiliente (anti-Unicode Plague)."""
        encodings = [
            ('utf-8', 'strict'),
            ('utf-8', 'replace'),
            ('latin-1', 'strict'),
            ('cp1252', 'strict'),
        ]
        last_error = None
        for encoding, errors in encodings:
            try:
                content = path.read_text(encoding=encoding, errors=errors)
                # Remove null bytes
                content = content.replace('\x00', '')
                return content
            except (UnicodeDecodeError, UnicodeError) as e:
                last_error = e
                continue
            except Exception:
                break
        
        try:
            raw = path.read_bytes()
            raw = raw.replace(b'\x00', b'')
            return raw.decode('utf-8', errors='replace')
        except Exception as e:
            raise UnicodeDecodeError('utf-8', b'', 0, 1, f'Falha em todos os encodings: {last_error}') from e

    def _resolve_original_py_path(self) -> 'Path | None':
        """
        Resolve o caminho do .py original de forma robusta.
        Evita retornar o .hermes por engano.
        """
        # 1. Tenta o original_py_path se for um .py válido
        if (self.original_py_path 
                and self.original_py_path.suffix == '.py'
                and self.original_py_path.exists()):
            return self.original_py_path
        
        # 2. Tenta resolver a partir do nome do módulo
        try:
            import importlib.machinery
            spec = importlib.machinery.PathFinder.find_spec(self.package_name or self.hermes_path.stem)
            if spec and spec.origin and spec.origin.endswith('.py'):
                return Path(spec.origin)
        except Exception:
            pass
        
        # 3. Tenta construir o path a partir do hermes_path
        # hermes: .doxoade/hermes/build/doxoade.tools.command_metadata.hermes
        # py: doxoade/tools/command_metadata.py
        try:
            hermes_stem = self.hermes_path.stem  # doxoade.tools.command_metadata
            parts = hermes_stem.split('.')
            if len(parts) >= 2:
                # Tenta vários paths possíveis
                project_root = self.hermes_path.parent.parent.parent.parent
                candidates = [
                    project_root / '/'.join(parts[:-1]) / f"{parts[-1]}.py",
                    project_root / '/'.join(parts) / '__init__.py',
                    project_root / parts[0] / 'tools' / parts[-1] / '__init__.py',
                ]
                for candidate in candidates:
                    if candidate.exists() and candidate.suffix == '.py':
                        return candidate
        except Exception:
            pass
        
        return None

    @staticmethod
    def _read_py_resilient(path: Path) -> str:
        """
        Lê arquivo .py com encoding resiliente (anti-Unicode Plague + Null Bytes).
        Tenta múltiplos encodings em ordem de prioridade:
          1. utf-8 (padrão Python 3)
          2. utf-8 com errors='replace' (substitui bytes inválidos por U+FFFD)
          3. latin-1 (sempre funciona, mapeia 1:1 bytes 0x00-0xFF)
          4. cp1252 (Windows Western European)
        
        FIX: Remove null bytes (\x00) que causam SyntaxError no compile().
        """
        encodings = [
            ('utf-8', 'strict'),
            ('utf-8', 'replace'),
            ('latin-1', 'strict'),
            ('cp1252', 'strict'),
        ]
        
        last_error = None
        for encoding, errors in encodings:
            try:
                content = path.read_text(encoding=encoding, errors=errors)
                # FIX CRÍTICO: Remove null bytes que quebram o compile()
                content = content.replace('\x00', '')
                return content
            except (UnicodeDecodeError, UnicodeError) as e:
                last_error = e
                continue
            except Exception:
                break
        
        # Último recurso: lê como bytes e decodifica com replace
        try:
            raw = path.read_bytes()
            # Remove null bytes antes de decodificar
            raw = raw.replace(b'\x00', b'')
            return raw.decode('utf-8', errors='replace')
        except Exception as e:
            raise UnicodeDecodeError('utf-8', b'', 0, 1, f'Falha em todos os encodings: {last_error}') from e

# ═══════════════════════════════════════════════════════════════════════
# GHOST BOOT + AUTO-BUILD (O coração do sistema)
# ═══════════════════════════════════════════════════════════════════════
def try_load_from_hermes(fullname: str, project_root: str):
    """Tenta carregar módulo via .hermes, com JIT automático."""
    if _is_blacklisted(fullname):
        return None
    
    root = Path(project_root).resolve()

    # [CRÍTICO] Import absoluto para evitar circularidade
    import doxoade.tools.hermes_systems.hermes_loader as hl
    loader = hl.HermesLoader(project_root)
    hermes_path = loader.find_hermes_for_module(fullname)

    if not hermes_path or not hermes_path.exists():
        lib_name = fullname.split('.')[0]
        lib_dir = root / '.doxoade' / 'hermes' / 'lib' / lib_name
        if lib_dir.exists():
            candidate = lib_dir / f"{fullname}.hermes"
            if candidate.exists():
                hermes_path = candidate

    if not hermes_path or not hermes_path.exists():
        return None

    parts = fullname.split('.')
    py_rel_path = Path(*parts).with_suffix('.py')
    py_path = root / py_rel_path

    if py_path.exists() and py_path.stat().st_mtime > hermes_path.stat().st_mtime:
        try:
            import doxoade.tools.hermes_systems.hermes_compress as hc
            compressor = hc.HermesCompressor(project_root)
            compressor.compress_file(py_path)
        except Exception:
            pass

    package_name = fullname.rsplit('.', 1)[0] if '.' in fullname else None
    module_loader = HermesModuleLoader(hermes_path, py_path if py_path.exists() else None, package_name)
    return importlib.util.spec_from_loader(fullname, module_loader, origin=str(hermes_path))

def _jit_build_with_optimize(fullname: str, py_path: Path, hermes_path: Path, reason: str):
    """JIT build com --optimize --dynamic aplicados automaticamente."""
    with _jit_lock:
        if fullname in _jit_built:
            _jit_stats['skipped'] += 1
            return
        _jit_built.add(fullname)
    
    try:
        import doxoade.tools.hermes_systems.hermes_compress as hc
        import doxoade.tools.hermes_systems.hermes_preprocessor as hp
        
        t0 = time.perf_counter()
        optimized, _ = hp.preprocess_for_hermes(py_path, str(py_path.parent))
        compressor = hc.HermesCompressor(str(py_path.parent))
        compressor.compress_file(py_path, optimized_content=optimized, use_dynamic_scan=True)
        
        elapsed_ms = (time.perf_counter() - t0) * 1000
        _jit_stats['built'] += 1
        
        if _VERBOSE:
            print(f"  ⚡ [HERMES-JIT] {fullname} → {hermes_path.name} ({elapsed_ms:.1f}ms, motivo: {reason})")
    except Exception as e:
        _jit_stats['failed'] += 1
        _jit_built.discard(fullname)
        if _VERBOSE:
            print(f"  ⚠ [HERMES-JIT] Falha em {fullname}: {e}")

def install(project_root: str):
    """Instala o HermesFinder no sys.meta_path."""
    for finder in sys.meta_path:
        if getattr(finder, '_HERMES_FINDER_MARKER', False):
            return
    try:
        hermes_finder = HermesFinder(project_root)
        sys.meta_path.insert(0, hermes_finder)  # ← CRÍTICO: insert(0) em vez de append()
    except Exception as e:
        formated_traceback(e, "hermes_hook - install")
        
    if _VERBOSE:
        print(f"\x1b[90m[HERMES] MetaPathFinder instalado no sys.meta_path[0]\x1b[0m")

def uninstall():
    """Remove o HermesFinder do sys.meta_path."""
    sys.meta_path[:] = [
        f for f in sys.meta_path
        if not getattr(f, '_HERMES_FINDER_MARKER', False)
    ]

class HermesFinder(importlib.abc.MetaPathFinder):
    """MetaPathFinder que intercepta imports e procura por .hermes."""
    _HERMES_FINDER_MARKER = True
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.dict_path = self.project_root / '.doxoade' / 'hermes' / 'master.dict'
        self.lib_hermes_dir = self.project_root / '.doxoade' / 'hermes' / 'lib'
        self._lib_cache: dict[str, dict[str, Path]] = {}
        self._path_cache: dict[str, Path] = {}
        
        # ═══════════════════════════════════════════════════════════════════
        # NOVO: Cache de módulos com .pyd disponível (Tier 1)
        # ═══════════════════════════════════════════════════════════════════
        self._pyd_cache: set[str] = set()
        self._build_pyd_index()
        
        self._scan_lib_dir()
    
    def _build_pyd_index(self):
        """
        Constrói índice em RAM de todos os .pyd disponíveis no bin/.
        Módulos com .pyd NÃO devem ser interceptados pelo Hermes.
        """
        bin_dir = self.project_root / '.doxoade' / 'vulcan' / 'bin'
        if not bin_dir.exists():
            return
        
        ext = '.pyd' if os.name == 'nt' else '.so'
        try:
            for pyd_file in bin_dir.glob(f'*{ext}'):
                # Extrai nome do módulo do filename
                # Ex: v_hermes_loader_38e018.pyd → hermes_loader
                stem = pyd_file.stem
                if stem.startswith('v_'):
                    # Remove prefixo 'v_' e sufixo '_hash'
                    parts = stem[2:].rsplit('_', 1)
                    if len(parts) == 2:
                        module_name = parts[0]
                        self._pyd_cache.add(module_name)
        except Exception:
            pass
    
    def _build_hermes_index(self):
        """
        Constrói índice em RAM de todos os .hermes disponíveis.
        Executado UMA VEZ no __init__, evita I/O repetido.
        """
        build_dir = self.project_root / '.doxoade' / 'hermes' / 'build'
        if not build_dir.exists():
            return
        
        try:
            for hermes_file in build_dir.glob('*.hermes'):
                # Extrai nome do módulo do filename
                # Ex: doxoade.tools.vulcan.forge.hermes → doxoade.tools.vulcan.forge
                module_name = hermes_file.stem
                self._hermes_index[module_name] = hermes_file
        except Exception:
            pass

    def _preload_build_cache(self):
        """Pré-carrega todos os .hermes do build/ em um dict O(1)."""
        build_dir = self.project_root / '.doxoade' / 'hermes' / 'build'
        if not build_dir.exists():
            return
        try:
            for f in build_dir.iterdir():
                if f.suffix == '.hermes':
                    # Converte nome do arquivo para nome do módulo
                    # doxoade.tools.vulcan.forge.hermes → doxoade.tools.vulcan.forge
                    module_name = f.stem
                    self._build_cache[module_name] = f
        except Exception:
            pass

    def _scan_lib_dir(self):
        """Varre .doxoade/hermes/lib/ e cacheia libs disponíveis."""
        if not self.lib_hermes_dir.exists():
            return
        for lib_dir in self.lib_hermes_dir.iterdir():
            if lib_dir.is_dir():
                lib_name = lib_dir.name
                hermes_files = {}
                for f in lib_dir.glob('*.hermes'):
                    module_name = f.stem
                    hermes_files[module_name] = f
                self._lib_cache[lib_name] = hermes_files
    
    def find_spec(self, fullname, path, target=None):
        # ═══════════════════════════════════════════════════════════════════
        # [CRÍTICO] Blacklist check (rápido)
        # ═══════════════════════════════════════════════════════════════════
        if _is_blacklisted(fullname):
            return None
        
        # ═══════════════════════════════════════════════════════════════════
        # OTIMIZAÇÃO: Se o módulo tem .pyd, NÃO intercepta
        # Deixa o VulcanMetaFinder carregar o binário nativo
        # ═══════════════════════════════════════════════════════════════════
        module_stem = fullname.split('.')[-1]
        if module_stem in self._pyd_cache:
            return None
        
        # ═══════════════════════════════════════════════════════════════════
        # [OTIMIZAÇÃO] Cache de paths (evita I/O repetido)
        # ═══════════════════════════════════════════════════════════════════
        if fullname in self._path_cache:
            hermes_path = self._path_cache[fullname]
        else:
            # 1. Tenta build/ (módulos do projeto)
            hermes_path = self._find_in_build(fullname)
            # 2. Tenta lib/ (libs de terceiros)
            if not hermes_path:
                hermes_path = self._find_in_lib(fullname)
            # 3. Cacheia o resultado (mesmo se None)
            self._path_cache[fullname] = hermes_path
        
        # ═══════════════════════════════════════════════════════════════════
        # [OTIMIZAÇÃO] Se não encontrou .hermes, retorna None imediatamente
        # ═══════════════════════════════════════════════════════════════════
        if not hermes_path:
            return None
        
        # ═══════════════════════════════════════════════════════════════════
        # [OTIMIZAÇÃO] Verifica staleness UMA VEZ só
        # ═══════════════════════════════════════════════════════════════════
        py_path = self._resolve_py_path_cached(fullname, path)
        if py_path and py_path.exists():
            if py_path.stat().st_mtime > hermes_path.stat().st_mtime:
                _log(f"⚠ {fullname}: .hermes desatualizado (use 'doxoade hermes build')")
        
        # ═══════════════════════════════════════════════════════════════════
        # Cria spec
        # ═══════════════════════════════════════════════════════════════════
        package_name = fullname.rsplit('.', 1)[0] if '.' in fullname else None
        spec = importlib.util.spec_from_loader(
            fullname,
            HermesModuleLoader(hermes_path, py_path, package_name),
            origin=str(hermes_path)
        )
        
        if py_path and py_path.name == '__init__.py':
            spec.submodule_search_locations = [str(py_path.parent)]
        
        _log(f"find_spec HIT: {fullname} ← {hermes_path.name}")
        return spec

    def _find_in_build(self, fullname: str) -> Path:
        """Procura .hermes em .doxoade/hermes/build/"""
        hermes_dir = self.project_root / '.doxoade' / 'hermes' / 'build'
        hermes_file = hermes_dir / f"{fullname}.hermes"
        return hermes_file if hermes_file.exists() else None

    def _find_in_lib(self, fullname: str) -> Path:
        """Procura .hermes em .doxoade/hermes/lib/<lib>/"""
        lib_name = fullname.split('.')[0]
        if lib_name not in self._lib_cache:
            return None
        hermes_files = self._lib_cache[lib_name]
        
        # 1. Busca direta pelo nome completo
        if fullname in hermes_files:
            return hermes_files[fullname]
        
        # 2. Para pacotes, busca __init__
        init_key = f"{fullname}.__init__"
        if init_key in hermes_files:
            return hermes_files[init_key]
        
        # 3. Para módulo raiz do pacote (ex: 'click' → 'click.__init__')
        if '.' not in fullname:
            init_key = f"{fullname}.__init__"
            if init_key in hermes_files:
                return hermes_files[init_key]
        
        # 4. Fallback: primeiro submódulo encontrado
        for key, path in sorted(hermes_files.items()):
            if key.startswith(fullname + '.'):
                return path
        
        return None

    def _resolve_py_path_cached(self, fullname, path):
        """Resolve o caminho do .py original com cache."""
        if not hasattr(self, '_py_path_cache'):
            self._py_path_cache = {}
        
        if fullname in self._py_path_cache:
            return self._py_path_cache[fullname]
        
        py_path = self._resolve_py_path(fullname, path)
        self._py_path_cache[fullname] = py_path
        return py_path

    def _resolve_py_path(self, fullname, path):
        """Resolve o caminho do .py original."""
        try:
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            if spec and spec.origin and spec.origin.endswith('.py'):
                return Path(spec.origin)
        except Exception:
            pass
        return None

    def _is_project_module(self, py_path: Path) -> bool:
        """Verifica se o módulo pertence ao projeto."""
        try:
            py_path.resolve().relative_to(self.project_root)
            return True
        except ValueError:
            return False

    def _jit_build(self, fullname: str, py_path: Path, hermes_path: Path):
        """JIT build com --optimize --dynamic."""
        with _jit_lock:
            if fullname in _jit_built:
                return
            _jit_built.add(fullname)
        
        try:
            import doxoade.tools.hermes_systems.hermes_compress as hc
            import doxoade.tools.hermes_systems.hermes_preprocessor as hp
            compressor = hc.HermesCompressor(str(self.project_root))
            optimized, _ = hp.preprocess_for_hermes(py_path)
            compressor.compress_file(py_path, optimized_content=optimized, use_dynamic_scan=True)
            
            if _VERBOSE:
                print(f"  ⚡ [HERMES-JIT] {fullname} → {hermes_path.name}")
        except Exception as e:
            _jit_built.discard(fullname)
            if _VERBOSE:
                print(f"  ⚠ [HERMES-JIT] Falha em {fullname}: {e}")
            formated_traceback(e, "hermes_hook - install")
