# doxoade/tools/hermes_systems/hbc6_meta_finder.py
"""
HBC6 MetaPathFinder — Redirecionamento Transparente para Produção
"""
import sys
import time
import hashlib
import struct
import importlib.abc
import importlib.util
from pathlib import Path

_AUDIT_ENABLED = False
_auditor = None

def _get_auditor():
    global _AUDIT_ENABLED, _auditor
    if not _AUDIT_ENABLED:
        import os
        _AUDIT_ENABLED = os.environ.get("HERMES_HBC6_AUDIT", "0") == "1"
    if _AUDIT_ENABLED and _auditor is None:
        from doxoade.tools.hermes_systems.hbc6_audit import HBC6Auditor, HBC6Decision
        _auditor = HBC6Auditor.get_instance()
    return _auditor


class HBC6Finder(importlib.abc.MetaPathFinder):
    
    def __init__(self, project_root: str):  # ✅ CORRIGIDO: Faltavam os __
        self.root = Path(project_root).resolve()
        self.build_dir = self.root / '.doxoade' / 'hermes' / 'build'
        self._loader_instance = None
        self._path_hash_cache = {}  # ✅ NOVO: Cache de hash
        
        self._blacklist = {
            'doxoade.rescue',
            'doxoade.chronos',
            'doxoade.commands.cmd_hermes',
            'doxoade.commands',
            'doxoade.tools.hermes_systems',
            'doxoade.tools.hermes_systems.hermes_loader',
            'doxoade.tools.hermes_systems.hermes_compress_hbc6',
            'doxoade.tools.vulcan.meta_finder',
            'doxoade.tools.hermes_systems.hbc6_meta_finder',
            'doxoade.tools.hermes_systems.hermes_payload',
            'doxoade.tools.hermes_systems.hermes_init',
            'doxoade.tools.hermes_systems.hermes_hook',
            'doxoade.tools.hermes_systems.hermes_hook_v2',
            'doxoade.tools.hermes_systems.hermes_diagnostic',
            'doxoade.tools.hermes_systems.hermes_format',
            'doxoade.tools.hermes_systems.hermes_decoder_vector',
            'doxoade.tools.hermes_systems.native',
            'doxoade.tools.hermes_systems.hbc6_audit',
            '__main__',
            'doxoade.__main__',
            'doxoade.cli',
            'doxoade.boot',
            'doxoade.core_database',
            'doxoade.tools.db_utils',
            'doxoade.tools.filesystem',
            'doxoade.tools.aegis',
            'doxoade.tools.telemetry_tools',
            'doxoade.tools.git',
            'doxoade.tools.git_utils',
            'doxoade.tools.vulcan',
            'doxoade.commands.db',
            'doxoade.commands.git_branch',
            'doxoade.commands.save',
            'doxoade.commands.check',
            'doxoade.commands.refactor',
            'sys', 'os', 'builtins', 'importlib',
            '_frozen_importlib', '_frozen_importlib_external',
            'click', 'click.core', 'click.decorators',
            'doxoade.tools.ganesha_systems',
            'doxoade.tools.ganesha_systems.ganesha_advisor_standalone',
            'doxoade.tools.ganesha_systems.ganesha_advisor',
        }
        
        self._whitelist = {
            'doxoade.tools.hermes_systems.hermes_format',
            'doxoade.tools.hermes_systems.hermes_loader_hbc5',
            'doxoade.tools.hermes_systems.hermes_metrics',
            'doxoade.tools.hermes_systems.hermes_lab',
            'doxoade.tools.doxcolors',
            'doxoade.tools.compress_utils',
            'doxoade.tools.colors_command',
            'doxoade.commands.refactor_systems.refactor_syntax',
            'doxoade.commands.vulcan_cmd_lazy',
            'doxoade.commands.check_systems.fixer',
            'doxoade.commands.intelligence_utils',
            'doxoade.commands.ganesha_advisor_standalone',
        }
        
        self._available_modules = set()
        if self.build_dir.exists():
            for hbc6_file in self.build_dir.glob('*.hbc6'):
                stem = hbc6_file.stem
                if '_' in stem:
                    base_name = stem.rsplit('_', 1)[0]
                    self._available_modules.add(base_name)

    def _get_path_hash(self, py_path: Path) -> str:  # ✅ NOVO: Método que faltava
        """Calcula SHA-256 do conteúdo do .py (normalizado CRLF→LF)."""
        path_str = str(py_path)
        if path_str in self._path_hash_cache:
            return self._path_hash_cache[path_str]
        try:
            content = py_path.read_bytes().replace(b'\r\n', b'\n')
            h = hashlib.sha256(content).hexdigest()[:12]
        except Exception:
            h = "000000000000"
        self._path_hash_cache[path_str] = h
        return h

    def _get_hermes_loader(self):
        if self._loader_instance is None:
            from doxoade.tools.hermes_systems.hermes_loader import HermesLoader
            self._loader_instance = HermesLoader(str(self.root))
        return self._loader_instance

    def invalidate_caches(self):
        self._available_modules = set()
        self._path_hash_cache.clear()
        if self.build_dir.exists():
            for hbc6_file in self.build_dir.glob("*.hbc6"):
                stem = hbc6_file.stem
                if "_" in stem:
                    base_name = stem.rsplit("_", 1)[0]
                    self._available_modules.add(base_name)

    def _resolve_py_path(self, fullname, path=None):
        parts = fullname.split(".")
        if path:
            leaf = parts[-1]
            for base in path:
                base = Path(base)
                candidates = [
                    base / f"{leaf}.py",
                    base / leaf / "__init__.py",
                ]
                for cand in candidates:
                    if cand.is_file():
                        return cand.resolve()
        rel = Path(*parts)
        search_roots = [self.root]
        for p in sys.path:
            if not p:
                continue
            search_roots.append(Path(p))
        for base in search_roots:
            candidates = [
                base / rel.with_suffix(".py"),
                base / rel / "__init__.py",
            ]
            if len(parts) == 1:
                candidates.append(base / f"{fullname}.py")
            for cand in candidates:
                if cand.is_file():
                    return cand.resolve()
        return None

    def find_spec(self, fullname, path, target=None):
        if not fullname.startswith('doxoade'):
            if _AUDIT_ENABLED:
                from doxoade.tools.hermes_systems.hbc6_audit import HBC6Decision
                _get_auditor().record(fullname, HBC6Decision.SKIP_BUILTIN, "Não é namespace doxoade")
            return None

        if fullname in self._blacklist or any(fullname.startswith(b + '.') for b in self._blacklist):
            if _AUDIT_ENABLED:
                from doxoade.tools.hermes_systems.hbc6_audit import HBC6Decision
                _get_auditor().record(fullname, HBC6Decision.FALLBACK_BLACKLIST, "Módulo na blacklist Hermes")
            return None

        py_path = self._resolve_py_path(fullname)
        if py_path is None:
            return None

        t0 = time.perf_counter_ns()
        file_hash = self._get_path_hash(py_path)
        hbc6_path = self.build_dir / f"{fullname.replace('.', '_')}_{file_hash[:12]}.hbc6"

        if not hbc6_path.exists():
            if _AUDIT_ENABLED:
                elapsed = (time.perf_counter_ns() - t0) / 1000.0
                from doxoade.tools.hermes_systems.hbc6_audit import HBC6Decision
                _get_auditor().record(
                    fullname, HBC6Decision.FALLBACK_NO_HBC6,
                    reason=f"Arquivo {hbc6_path.name} não encontrado em build/",
                    py_path=str(py_path),
                    hbc6_path=str(hbc6_path),
                    actual_hash=file_hash,
                    elapsed_us=elapsed,
                    fallback_to="source_py",
                )
            return None

        expected_hash = hbc6_path.stem.rsplit('_', 1)[-1]
        if not file_hash.startswith(expected_hash):
            if _AUDIT_ENABLED:
                elapsed = (time.perf_counter_ns() - t0) / 1000.0
                from doxoade.tools.hermes_systems.hbc6_audit import HBC6Decision
                _get_auditor().record(
                    fullname, HBC6Decision.FALLBACK_HASH_MISMATCH,
                    reason=f".py modificado. Esperado: {expected_hash}, atual: {file_hash[:12]}",
                    py_path=str(py_path),
                    hbc6_path=str(hbc6_path),
                    expected_hash=expected_hash,
                    actual_hash=file_hash[:12],
                    elapsed_us=elapsed,
                    fallback_to="source_py",
                )
            return None

        elapsed = (time.perf_counter_ns() - t0) / 1000.0
        gd_path = self.build_dir / "global_dict.hgd1"

        spec = importlib.util.spec_from_loader(
            fullname,
            HBC6Loader(fullname, hbc6_path, py_path, gd_path),
            origin=str(hbc6_path),
        )
        return spec


class HBC6Loader(importlib.abc.Loader):
    
    def __init__(self, fullname, hermes_path, py_path, gd_path):  # ✅ CORRIGIDO
        self.fullname = fullname
        self.hermes_path = hermes_path
        self.py_path = py_path
        self.gd_path = gd_path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = str(self.py_path)
        module.__loader__ = self
        if '.' in self.fullname:
            module.__package__ = self.fullname.rsplit('.', 1)[0]
        else:
            module.__package__ = self.fullname

        t0 = time.perf_counter_ns()
        code_obj = self._try_c_bridge()
        elapsed = (time.perf_counter_ns() - t0) / 1000.0

        if code_obj is not None:
            if _AUDIT_ENABLED:
                from doxoade.tools.hermes_systems.hbc6_audit import HBC6Decision
                _get_auditor().record(
                    self.fullname, HBC6Decision.MOTOR_C_HIT,
                    reason="Motor C (hermes_bridge.pyd) carregou com sucesso",
                    py_path=str(self.py_path),
                    hbc6_path=str(self.hermes_path),
                    elapsed_us=elapsed,
                    fallback_to="motor_c",
                )
            exec(code_obj, module.__dict__)
        else:
            if _AUDIT_ENABLED:
                from doxoade.tools.hermes_systems.hbc6_audit import HBC6Decision
                _get_auditor().record(
                    self.fullname, HBC6Decision.FALLBACK_C_BRIDGE_NULL,
                    reason="Motor C retornou None → fallback para _python_fallback()",
                    py_path=str(self.py_path),
                    hbc6_path=str(self.hermes_path),
                    elapsed_us=elapsed,
                    fallback_to="source_py",
                )
            self._python_fallback(module)

    def _try_c_bridge(self):
        """Tenta carregar via Motor C com blindagem total."""
        
        # 🛡️ BLINDAGEM 1: Verifica se o Global Dictionary existe
        gd_path = self.gd_path
        if gd_path and not Path(gd_path).exists():
            if _AUDIT_ENABLED:
                from doxoade.tools.hermes_systems.hbc6_audit import HBC6Decision
                _get_auditor().record(
                    self.fullname, HBC6Decision.FALLBACK_C_BRIDGE_NULL,
                    reason=f"Global Dictionary ausente: {gd_path}",
                    fallback_to="source_py",
                )
            return None
        
        # 🛡️ BLINDAGEM 2: Valida o arquivo HBC6 antes de passar para o C
        try:
            with open(self.hermes_path, 'rb') as f:
                magic = f.read(4)
                if magic != b'HBC6':
                    return None
                f.seek(0, 2)
                if f.tell() < 50:
                    return None
        except Exception:
            return None
        
        # 🛡️ BLINDAGEM 3: Chama o Motor C com os argumentos CORRETOS
        try:
            from doxoade.tools.hermes_systems.native import hermes_bridge
            # ✅ CORRIGIDO: passa gd_path, NÃO py_path
            code_obj = hermes_bridge.load_module(
                str(self.hermes_path), str(gd_path)
            )
            return code_obj
        except Exception as e:
            if _AUDIT_ENABLED:
                from doxoade.tools.hermes_systems.hbc6_audit import HBC6Decision
                _get_auditor().record(
                    self.fullname, HBC6Decision.FALLBACK_C_BRIDGE_EXC,
                    reason=f"Exceção: {type(e).__name__}: {e}",
                    exception_msg=str(e),
                    fallback_to="source_py",
                )
            return None

    def _python_fallback(self, module):
        """Fallback: executa o .py original."""
        module.__hermes_fallback__ = True
        module.__hermes_error__ = "Motor C falhou ou HGD1 ausente"  # ✅ CORRIGIDO
        source = self.py_path.read_text(encoding="utf-8")
        code_obj = compile(source, str(self.py_path), "exec")
        exec(code_obj, module.__dict__)


def install_hbc6_hook(project_root):
    """Instala o HBC6Finder no sys.meta_path."""
    finder = HBC6Finder(project_root)
    sys.meta_path.insert(0, finder)
    return finder