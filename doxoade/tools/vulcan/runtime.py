# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/runtime.py
"""Runtime bridge para consumir binários Vulcan em projetos externos.

Uso rápido no ``__main__.py`` de outro projeto::

    from doxoade.tools.vulcan.runtime import activate_vulcan, install_meta_finder

    install_meta_finder(project_root)    # redirecionamento global de imports
    activate_vulcan(globals(), __file__) # injeta funções do __main__ específico

Arquitetura do redirecionamento (v3 — VulcanLoader):
  O PYD gerado pelo PitStop é compilado como ``v_{stem}_{hash}`` e exporta
  ``PyInit_v_{stem}_{hash}``. Se o VulcanBinaryFinder retornar o PYD
  diretamente como spec de ``engine.cli``, o Python procura ``PyInit_cli``
  e falha com "does not define module export function".

  Solução: VulcanLoader usa um padrão wrapper/decorator de loader:
    1. Deixa o loader original do .py executar o módulo normalmente.
    2. Carrega o PYD sob seu nome nativo (v_cli_abc123) em paralelo.
    3. Injeta as funções ``*_vulcan_optimized`` sobre as originais do módulo.

  O módulo Python resultante tem o nome correto (engine.cli), todas as
  suas APIs intactas e as funções hot-path substituídas pelo metal nativo.
"""

from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import os
import struct
import sys
from pathlib import Path
from types import ModuleType
from typing import MutableMapping, Optional

_OPTIMIZED_SUFFIX = "_vulcan_optimized"
_BINARY_EXT = ".pyd" if os.name == "nt" else ".so"

# Ativa logging de redirecionamento: set VULCAN_VERBOSE=1 antes de executar.
_VERBOSE = os.environ.get("VULCAN_VERBOSE", "").strip() == "1"


def _vlog(msg: str) -> None:
    """Log de redirecionamento — ativo apenas com VULCAN_VERBOSE=1."""
    if _VERBOSE:
        sys.stderr.write(f"[VULCAN:REDIRECT] {msg}\n")


# ---------------------------------------------------------------------------
# Helpers de binário
# ---------------------------------------------------------------------------
def _binary_ext() -> str:
    return _BINARY_EXT


def _is_binary_valid_for_host(bin_path: Path) -> bool:
    """Validação mínima de integridade/arquitetura do binário nativo."""
    try:
        if not bin_path.exists() or bin_path.stat().st_size < 4096:
            return False
        with bin_path.open("rb") as f:
            head = f.read(64)
        if os.name == "nt":
            if not head.startswith(b"MZ"):
                return False
            with bin_path.open("rb") as f:
                f.seek(0x3C)
                e_lfanew = struct.unpack("<I", f.read(4))[0]
                f.seek(e_lfanew + 4)
                machine = struct.unpack("<H", f.read(2))[0]
            host_bits = struct.calcsize("P") * 8
            if host_bits == 64 and machine != 0x8664:
                return False
            if host_bits == 32 and machine != 0x014C:
                return False
        else:
            if not head.startswith(b"ELF"):
                return False
        return True
    except Exception:
        return False


def _is_binary_stale(bin_path: Path, source_path: Path | None) -> bool:
    """True se o .py foi modificado depois do .pyd (binário desatualizado)."""
    if not source_path or not source_path.exists():
        return False
    try:
        return source_path.stat().st_mtime > bin_path.stat().st_mtime
    except OSError:
        return False


def _find_pyd_for_source(bin_dir: Path, source_path: Path) -> Path | None:
    """
    Localiza o PYD correspondente a um .py usando o mesmo esquema de
    nomenclatura do PitStop: ``v_{stem}_{sha256(abs_path)[:6]}.pyd``.

    Ordem de busca:
      1. Hash do path absoluto  (padrão PitStop atual)
      2. Glob ``v_{stem}_*.pyd`` — qualquer hash para este stem (mais recente)
      3. ``v_{stem}.pyd``        — legado sem hash
    """
    stem = source_path.stem
    ext = _binary_ext()

    # 1. Hash exato derivado do path absoluto
    abs_hash = hashlib.sha256(str(source_path.resolve()).encode()).hexdigest()[:6]
    candidate = bin_dir / f"v_{stem}_{abs_hash}{ext}"
    if candidate.exists():
        return candidate

    # 2. Glob — pega o mais recente para este stem
    matches = sorted(
        bin_dir.glob(f"v_{stem}_*{ext}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if matches:
        return matches[0]

    # 3. Legado
    legacy = bin_dir / f"v_{stem}{ext}"
    if legacy.exists():
        return legacy

    return None



# ====== VulcanLoader  —  wrapper que injeta metal depois do .py ======

def _safe_call(py_fn, native_fn):
    def wrapper(*args, **kwargs):
        try:
            return native_fn(*args, **kwargs)
        except TypeError:
            return py_fn(*args, **kwargs)
        except Exception:
            return py_fn(*args, **kwargs)
    wrapper.__name__ = py_fn.__name__
    wrapper.__doc__ = py_fn.__doc__
    return wrapper
    
class VulcanLoader(importlib.abc.Loader):
    """
    Loader em dois tempos:
      1. Executa o módulo Python original (via original_loader).
      2. Carrega o PYD sob seu nome nativo e injeta *_vulcan_optimized.

    O módulo final tem o fullname correto (ex: engine.cli) e todas as
    APIs Python preservadas — apenas as funções hot-path são substituídas.
    Qualquer falha na fase 2 é silenciada: o Python original permanece intacto.
    """

    def __init__(
        self,
        original_loader: importlib.abc.Loader,
        bin_path: Path,
        native_module_name: str,
    ):
        self._original_loader = original_loader
        self._bin_path = bin_path
        self._native_name = native_module_name

    def create_module(self, spec) -> ModuleType | None:
        if hasattr(self._original_loader, "create_module"):
            return self._original_loader.create_module(spec)
        return None

    def exec_module(self, module: ModuleType) -> None:
        # ── Garante __file__, __spec__.origin e __loader__ antes de executar ─
        # O ModuleSpec customizado pode não propagar __file__ automaticamente
        # dependendo da versão do Python / bootstrap. Forçamos aqui para que
        # qualquer uso de Path(__file__) dentro do módulo funcione corretamente.
        if not getattr(module, "__file__", None):
            # Tenta obter o path real a partir do loader original
            origin = (
                getattr(self._original_loader, "path", None)      # SourceFileLoader
                or getattr(self._original_loader, "get_filename", lambda: None)()
                or (getattr(module, "__spec__", None) and getattr(module.__spec__, "origin", None))
            )
            if origin:
                module.__file__ = str(origin)
        # Garante __loader__ para compatibilidade com pkgutil e inspect
        if not getattr(module, "__loader__", None):
            module.__loader__ = self._original_loader

        # ── Fase 1: executa o Python original ────────────────────────────────
        self._original_loader.exec_module(module)

        # ── Fase 2: carrega o PYD sob seu nome nativo ────────────────────────
        try:
            native_spec = importlib.util.spec_from_file_location(
                self._native_name, str(self._bin_path)
            )
            if not (native_spec and native_spec.loader):
                _vlog(f"SKIP {module.__name__} — spec inválido para {self._bin_path.name}")
                return

            native_mod = importlib.util.module_from_spec(native_spec)
            sys.modules[self._native_name] = native_mod
            
            # Após exec_module do native_mod, antes do loop de injeção:
            native_spec.loader.exec_module(native_mod)

            # Após exec_module do native_mod, ANTES do loop de injeção de globals:
            native_mod.__package__ = module.__package__   # ex: "click"
            native_mod.__spec__    = module.__spec__
            native_mod.__name__    = module.__name__       # ex: "click.formatting"

            # Agora injeta os globals do módulo original
            for key, val in vars(module).items():
                if not hasattr(native_mod, key):
                    try:
                        setattr(native_mod, key, val)
                    except (AttributeError, TypeError):
                        pass

            # ── Fase 3: injeta funções otimizadas ────────────────────────────
            injected = []
            for attr in dir(native_mod):
                if not attr.endswith(_OPTIMIZED_SUFFIX):
                    continue
                orig_name = attr[: -len(_OPTIMIZED_SUFFIX)]
                if hasattr(module, orig_name):
                    py_fn = getattr(module, orig_name)
                    native_fn = getattr(native_mod, attr)

                    # Valida assinatura antes de injetar
                    import inspect
                    try:
                        py_sig = inspect.signature(py_fn)
                        native_sig = inspect.signature(native_fn)
                        # Se assinaturas batem, injeta direto
                        setattr(module, orig_name, native_fn)
                    except (ValueError, TypeError):
                        # Não foi possível validar, usa wrapper como segurança
                        setattr(module, orig_name, _safe_call(py_fn, native_fn))
                    injected.append(orig_name)

            if injected:
                _vlog(f"OK   {module.__name__} ← {self._bin_path.name} ({', '.join(injected)})")
                module.__file__ = str(self._bin_path)  # ← sinaliza que binário está ativo
            else:
                _vlog(f"LOAD {module.__name__} ← {self._bin_path.name} (sem funções otimizadas)")

        except Exception as exc:
            # Safe-fail: Python original permanece intacto
            _vlog(f"FAIL {module.__name__} ← {self._bin_path.name} — {exc}")


# ---------------------------------------------------------------------------
# VulcanBinaryFinder  —  MetaPathFinder que injeta VulcanLoader quando cabível
# ---------------------------------------------------------------------------
class VulcanBinaryFinder(importlib.abc.MetaPathFinder):
    """
    MetaPathFinder para projetos externos com bootstrap Vulcan.

    NÃO substitui o módulo pelo PYD diretamente (causaria PyInit mismatch).
    Envolve o loader original com VulcanLoader, que executa o .py e depois
    injeta o metal sob o nome nativo correto do PYD.

    Só atua quando:
      - Existe um PYD correspondente em .doxoade/vulcan/bin/
      - O PYD não está desatualizado (stale) em relação ao .py
      - O PYD passa na validação de host (arquitetura correta)
    """

    _BYPASS_PREFIXES = (
        "doxoade.", "encodings.", "codecs.", "_", "builtins",
        "importlib", "sys", "os", "pathlib", "abc",
    )

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.bin_dir = self.project_root / ".doxoade" / "vulcan" / "bin"
        # Cache: fullname → (bin_path_str, native_name) | None
        self._cache: dict[str, tuple[str, str] | None] = {}

    def _resolve_original_spec(self, fullname: str, path):
        """Obtém o spec do .py original sem acionar este finder recursivamente."""
        for finder in sys.meta_path:
            if finder is self:
                continue
            if not hasattr(finder, "find_spec"):
                continue
            try:
                spec = finder.find_spec(fullname, path, None)
                if spec and spec.origin and spec.origin not in ("built-in", "frozen"):
                    if Path(spec.origin).suffix == ".py":
                        return spec
            except Exception:
                continue
        return None

    def find_spec(self, fullname: str, path, target=None):
        if any(fullname.startswith(p) for p in self._BYPASS_PREFIXES):
            return None
        if not self.bin_dir.exists():
            return None

        # Cache de miss — evita resolver o mesmo módulo repetidamente
        if fullname in self._cache:
            cached = self._cache[fullname]
            if cached is None:
                return None
            bin_path = Path(cached[0])
            original_spec = self._resolve_original_spec(fullname, path)
            source = Path(original_spec.origin) if original_spec else None
            if (
                bin_path.exists()
                and not _is_binary_stale(bin_path, source)
                and original_spec
                and original_spec.loader
            ):
                new_spec = importlib.machinery.ModuleSpec(
                    fullname,
                    VulcanLoader(original_spec.loader, bin_path, cached[1]),
                    origin=original_spec.origin,
                )
                new_spec.has_location = True  # garante que __file__ é propagado pelo bootstrap
                return new_spec
            del self._cache[fullname]

        # Resolve o spec original do .py
        original_spec = self._resolve_original_spec(fullname, path)
        if not original_spec or not original_spec.loader:
            return None

        source_path = Path(original_spec.origin)

        # Procura PYD correspondente
        bin_path = _find_pyd_for_source(self.bin_dir, source_path)
        if not bin_path:
            self._cache[fullname] = None
            return None

        if not _is_binary_valid_for_host(bin_path):
            self._cache[fullname] = None
            return None
        if _is_binary_stale(bin_path, source_path):
            self._cache[fullname] = None
            return None

        # O nome nativo é apenas a parte base do stem, sem a tag de plataforma.
        # ex: v_cli_a7a05c.cp312-win_amd64.pyd → stem = v_cli_a7a05c.cp312-win_amd64
        #     → native_name = v_cli_a7a05c  (só até o primeiro ponto)
        # Isso garante que PyInit_v_cli_a7a05c seja procurado corretamente.
        native_name = bin_path.stem.split(".")[0]

        self._cache[fullname] = (str(bin_path), native_name)
        _vlog(f"INTERCEPT {fullname} → {bin_path.name}")

        new_spec = importlib.machinery.ModuleSpec(
            fullname,
            VulcanLoader(original_spec.loader, bin_path, native_name),
            origin=original_spec.origin,
        )
        new_spec.has_location = True  # garante que __file__ é propagado pelo bootstrap
        return new_spec


# ---------------------------------------------------------------------------
# MetaFinder registry  —  evita instalar múltiplas vezes
# ---------------------------------------------------------------------------
_installed_finders: dict[str, VulcanBinaryFinder] = {}


def install_meta_finder(project_root: str | Path) -> VulcanBinaryFinder:
    """
    Instala VulcanBinaryFinder no sys.meta_path do projeto.

    Idempotente — seguro para múltiplas chamadas com o mesmo project_root.
    Retorna o finder ativo (novo ou existente).
    """
    root_str = str(Path(project_root).resolve())

    for existing in sys.meta_path:
        if isinstance(existing, VulcanBinaryFinder):
            if str(existing.project_root) == root_str:
                return existing

    finder = VulcanBinaryFinder(root_str)
    sys.meta_path.insert(0, finder)
    _installed_finders[root_str] = finder
    return finder


def uninstall_meta_finder(project_root: str | Path | None = None) -> None:
    """Remove VulcanBinaryFinder(s) do sys.meta_path."""
    root_str = str(Path(project_root).resolve()) if project_root else None
    sys.meta_path[:] = [
        f for f in sys.meta_path
        if not (
            isinstance(f, VulcanBinaryFinder)
            and (root_str is None or str(f.project_root) == root_str)
        )
    ]
    if root_str:
        _installed_finders.pop(root_str, None)
    else:
        _installed_finders.clear()


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def find_vulcan_project_root(start: str | Path) -> Optional[Path]:
    """Localiza a raiz de projeto com ``.doxoade/vulcan/bin``."""
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent
    for node in [current, *current.parents]:
        if (node / ".doxoade" / "vulcan" / "bin").exists():
            return node
    return None


def load_vulcan_binary(module_name: str, project_root: str | Path) -> Optional[ModuleType]:
    """
    Carrega um binário Vulcan pelo nome nativo (ex: ``v_engine_abc123``).
    Uso direto — para injeção manual de símbolos via activate_vulcan.
    O nome deve ser apenas a parte base sem tag de plataforma (ex: v_cli_a7a05c).
    """
    root = Path(project_root).resolve()
    bin_dir = root / ".doxoade" / "vulcan" / "bin"
    ext = _binary_ext()

    # Tenta o path exato primeiro, depois glob com tag de plataforma
    # ex: v_cli_a7a05c.pyd ou v_cli_a7a05c.cp312-win_amd64.pyd
    bin_path = bin_dir / f"{module_name}{ext}"
    if not bin_path.exists():
        matches = sorted(
            bin_dir.glob(f"{module_name}*{ext}"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not matches:
            return None
        bin_path = matches[0]

    if not _is_binary_valid_for_host(bin_path):
        return None

    old_path = sys.path.copy()
    try:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

        venv = root / "venv"
        if venv.exists():
            if os.name == "nt":
                sp = venv / "Lib" / "site-packages"
            else:
                pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"
                sp = venv / "lib" / pyver / "site-packages"
            if sp.exists():
                sp_str = str(sp)
                if sp_str not in sys.path:
                    sys.path.insert(1, sp_str)

        spec = importlib.util.spec_from_file_location(module_name, str(bin_path))
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None
    finally:
        sys.path = old_path


def activate_vulcan(
    globs: MutableMapping[str, object],
    source_file: str,
    *,
    project_root: str | Path | None = None,
    optimized_suffix: str = _OPTIMIZED_SUFFIX,
) -> bool:
    """
    Ativa funções otimizadas do Vulcan no escopo informado.

    1. Instala MetaFinder global (redirecionamento automático de imports).
    2. Tenta carregar o PYD específico do source_file e injeta símbolos
       no dicionário ``globs`` (normalmente globals() do __main__).

    Retorna True quando ao menos um símbolo foi injetado.
    """
    root = Path(project_root).resolve() if project_root else find_vulcan_project_root(source_file)
    if not root:
        return False

    # Garante MetaFinder instalado para redirecionamento global de imports
    install_meta_finder(root)

    source_path = Path(source_file)

    bin_dir = root / ".doxoade" / "vulcan" / "bin"
    bin_path = _find_pyd_for_source(bin_dir, source_path)
    if not bin_path:
        return False
    if not _is_binary_valid_for_host(bin_path):
        return False
    if _is_binary_stale(bin_path, source_path):
        return False

    native_name = bin_path.stem.split(".")[0]  # remove tag de plataforma (.cp312-win_amd64)
    module = load_vulcan_binary(native_name, root)
    if not module:
        return False

    injected = 0
    for attr in dir(module):
        if not attr.endswith(optimized_suffix):
            continue
        orig_name = attr[: -len(optimized_suffix)]
        globs[orig_name] = getattr(module, attr)
        injected += 1

    return injected > 0