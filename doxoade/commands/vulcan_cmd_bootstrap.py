# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd_bootstrap.py
"""
Subcomandos de instalação e verificação do bootstrap Vulcan.

  module → instala módulo de acionamento Vulcan em projetos externos
  probe  → verifica status dos binários (.pyd/.so) ativos
  verify → testa redirecionamento PYD em subprocess isolado
"""

import os
import sys
import re
import subprocess
import json
import hashlib
import click
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import _find_project_root
from .vulcan_cmd import _print_vulcan_forensic, _is_doxoade_project


# ── Constantes de bootstrap ───────────────────────────────────────────────────

_BOOTSTRAP_START = "# --- DOXOADE_VULCAN_BOOTSTRAP:START ---"
_BOOTSTRAP_END   = "# --- DOXOADE_VULCAN_BOOTSTRAP:END ---"
_BOOTSTRAP_BLOCK = f'''{_BOOTSTRAP_START}
from pathlib import Path as _doxo_path
import importlib.util as _doxo_importlib_util
import sys as _doxo_sys
import time as _doxo_time

_doxo_activate_vulcan = None
_doxo_install_meta_finder = None
_doxo_probe_embedded = None
_doxo_project_root = None
_doxo_boot_t0 = _doxo_time.monotonic()
_doxo_install_ms = 0
_doxo_embedded_ms = 0
_doxo_fallback_ms = 0

for _doxo_base in [_doxo_path(__file__).resolve(), *_doxo_path(__file__).resolve().parents]:
    _doxo_runtime_file = _doxo_base / ".doxoade" / "vulcan" / "runtime.py"
    if not _doxo_runtime_file.exists():
        continue
    _doxo_spec = _doxo_importlib_util.spec_from_file_location("_doxoade_vulcan_runtime", str(_doxo_runtime_file))
    if not (_doxo_spec and _doxo_spec.loader):
        continue
    _doxo_mod = _doxo_importlib_util.module_from_spec(_doxo_spec)
    _doxo_sys.modules["_doxoade_vulcan_runtime"] = _doxo_mod
    _doxo_spec.loader.exec_module(_doxo_mod)
    _doxo_activate_vulcan = getattr(_doxo_mod, "activate_vulcan", None)
    _doxo_install_meta_finder = getattr(_doxo_mod, "install_meta_finder", None)
    _doxo_probe_embedded = getattr(_doxo_mod, "probe_embedded", None)
    _doxo_project_root = str(_doxo_base)
    break

# 1. Instala MetaFinder primeiro
if callable(_doxo_install_meta_finder) and _doxo_project_root:
    _doxo_t = _doxo_time.monotonic()
    try:
        _doxo_install_meta_finder(_doxo_project_root)
    except Exception:
        pass
    finally:
        _doxo_install_ms = int((_doxo_time.monotonic() - _doxo_t) * 1000)

# 2. Tenta usar o loader "embedded"
try:
    _doxo_t = _doxo_time.monotonic()   # inicializado ANTES do if — evita NameError no finally
    if _doxo_project_root:
        _embedded_path = _doxo_path(_doxo_project_root) / ".doxoade" / "vulcan" / "vulcan_embedded.py"
        if _embedded_path.exists():
            _doxo_spec2 = _doxo_importlib_util.spec_from_file_location("_doxoade_vulcan_embedded", str(_embedded_path))
            if _doxo_spec2 and _doxo_spec2.loader:
                _doxo_mod2 = _doxo_importlib_util.module_from_spec(_doxo_spec2)
                _doxo_sys.modules["_doxoade_vulcan_embedded"] = _doxo_mod2
                _doxo_spec2.loader.exec_module(_doxo_mod2)
                _doxo_activate_embedded = getattr(_doxo_mod2, "activate_embedded", None)
                _doxo_safe_call = getattr(_doxo_mod2, "safe_call", None)
                if callable(_doxo_activate_embedded):
                    try:
                        _doxo_activate_embedded(globals(), __file__, _doxo_project_root)
                    except Exception:
                        pass
                if callable(_doxo_safe_call):
                    try:
                        import sys as _d_sys
                        _bin_dir = _doxo_path(_doxo_project_root) / ".doxoade" / "vulcan" / "bin"
                        # sys.intern no sufixo — a comparação endswith é feita N_módulos×N_attrs vezes
                        _vulcan_suffix = _d_sys.intern("_vulcan_optimized")
                        _suffix_len    = len(_vulcan_suffix)
                        for mname, mod in list(_d_sys.modules.items()):
                            try:
                                mfile = getattr(mod, "__file__", None)
                                if not mfile:
                                    continue  # saída antecipada — evita construir Path para módulos builtin
                                mpath = _doxo_path(mfile)
                                if _bin_dir not in mpath.parents:
                                    continue
                                for attr in dir(mod):
                                    if not attr.endswith(_vulcan_suffix):
                                        continue
                                    native_obj = getattr(mod, attr, None)
                                    if not callable(native_obj):
                                        continue
                                    base = attr[: -_suffix_len]
                                    try:
                                        setattr(mod, base, _doxo_safe_call(native_obj, getattr(mod, base, None)))
                                    except Exception:
                                        continue
                            except Exception:
                                continue
                    except Exception:
                        pass
except Exception:
    pass
finally:
    _doxo_embedded_ms = int((_doxo_time.monotonic() - _doxo_t) * 1000)

# 3. Fallback: runtime.activate_vulcan
if callable(_doxo_activate_vulcan):
    _doxo_t = _doxo_time.monotonic()
    try:
        _doxo_activate_vulcan(globals(), __file__)
    except Exception:
        pass
    finally:
        _doxo_fallback_ms = int((_doxo_time.monotonic() - _doxo_t) * 1000)

# 4. Diagnóstico opcional
if callable(_doxo_probe_embedded):
    try:
        __doxoade_vulcan_probe__ = _doxo_probe_embedded(_doxo_project_root)
        __doxoade_vulcan_probe__["install_meta_ms"] = _doxo_install_ms
        __doxoade_vulcan_probe__["embedded_load_ms"] = _doxo_embedded_ms
        __doxoade_vulcan_probe__["fallback_ms"] = _doxo_fallback_ms
        __doxoade_vulcan_probe__["boot_ms"] = int((_doxo_time.monotonic() - _doxo_boot_t0) * 1000)
        if _doxo_sys.environ.get("VULCAN_DIAG", "").strip() == "1":
            _doxo_sys.stderr.write(
                "[VULCAN:DIAG] "
                + "finder_count=" + str(__doxoade_vulcan_probe__.get("finder_count", 0)) + " "
                + "bin=" + str(__doxoade_vulcan_probe__.get("bin_count", 0)) + " "
                + "lib_bin=" + str(__doxoade_vulcan_probe__.get("lib_bin_count", 0)) + " "
                + "boot_ms=" + str(__doxoade_vulcan_probe__.get("boot_ms", 0)) + " "
                + "install_ms=" + str(__doxoade_vulcan_probe__.get("install_meta_ms", 0)) + " "
                + "embedded_ms=" + str(__doxoade_vulcan_probe__.get("embedded_load_ms", 0)) + " "
                + "fallback_ms=" + str(__doxoade_vulcan_probe__.get("fallback_ms", 0)) + "\n"
            )
    except Exception:
        pass
{_BOOTSTRAP_END}
'''

_VULCAN_EMBEDDED_CONTENT = r'''# -*- coding: utf-8 -*-
"""vulcan_embedded.py — safe loader gerado pelo doxoade (opt-in)."""

from functools import wraps
from pathlib import Path
import sys
import os
import importlib.util
import importlib.machinery

def _vlog(*args, **kwargs):
    return None

class ExecutionContext:
    __slots__ = ("argv", "env", "cwd", "project_root")
    def __init__(self):
        self.argv = sys.argv
        self.env  = dict(os.environ)
        self.cwd  = Path.cwd()
        main = sys.modules.get("__main__")
        self.project_root = getattr(main, "__file__", None)

def safe_call(native_fn, fallback_fn=None):
    @wraps(fallback_fn or native_fn)
    def wrapper(*args, **kwargs):
        try:
            return native_fn(ExecutionContext(), *args, **kwargs)
        except TypeError:
            pass
        except Exception:
            if callable(fallback_fn):
                return fallback_fn(*args, **kwargs)
            raise
        try:
            return native_fn(*args, **kwargs)
        except TypeError:
            pass
        except Exception:
            if callable(fallback_fn):
                return fallback_fn(*args, **kwargs)
            raise
        if callable(fallback_fn):
            return fallback_fn(*args, **kwargs)
        raise RuntimeError(f"[vulcan_embedded] assinatura incompatível: {getattr(native_fn,'__name__',str(native_fn))}")
    return wrapper

_OPTIMIZED_SUFFIX = "_vulcan_optimized"

def inject_optimized(module, native_module, suffix=_OPTIMIZED_SUFFIX):
    import inspect
    injected = []
    skipped  = []
    for attr in dir(native_module):
        if not attr.endswith(suffix):
            continue
        orig_name   = attr[:-len(suffix)]
        if not hasattr(module, orig_name):
            continue
        py_func     = getattr(module, orig_name)
        native_func = getattr(native_module, attr)
        if not callable(py_func) or not callable(native_func):
            skipped.append(orig_name)
            continue
        try:
            if inspect.signature(py_func).parameters != inspect.signature(native_func).parameters:
                skipped.append(orig_name)
                continue
        except (ValueError, TypeError):
            skipped.append(orig_name)
            continue
        try:
            setattr(module, orig_name, safe_call(native_func, py_func))
            injected.append(orig_name)
        except Exception:
            skipped.append(orig_name)

def _binary_ext():
    return ".pyd" if os.name == "nt" else ".so"

def _find_pyd_for_source(bin_dir, source_path):
    stem = source_path.stem
    ext  = _binary_ext()
    try:
        import hashlib
        abs_hash  = hashlib.sha256(str(source_path.resolve()).encode()).hexdigest()[:6]
        candidate = bin_dir / f"v_{stem}_{abs_hash}{ext}"
        if candidate.exists():
            return candidate
    except Exception:
        pass
    matches = sorted(bin_dir.glob(f"v_{stem}_*{ext}"), key=lambda p: p.stat().st_mtime, reverse=True)
    if matches:
        return matches[0]
    matches2 = sorted(bin_dir.glob(f"v_{stem}*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches2[0] if matches2 else None

def _is_binary_valid_for_host(bin_path):
    try:
        return bin_path.exists() and bin_path.stat().st_size > 4096
    except Exception:
        return False

def _load_extension_from_path(module_name, bin_path):
    try:
        spec = importlib.util.spec_from_file_location(module_name, str(bin_path))
        if not spec or not spec.loader:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        sys.modules.pop(module_name, None)
        return None

def activate_embedded(globs, source_file, project_root=None, suffix=_OPTIMIZED_SUFFIX):
    try:
        src  = Path(source_file).resolve()
        root = Path(project_root).resolve() if project_root else None
        if not root:
            cur = src.parent
            while True:
                candidate = cur / ".doxoade" / "vulcan" / "bin"
                if candidate.exists():
                    root = cur
                    break
                if cur == cur.parent:
                    break
                cur = cur.parent
        if not root:
            return False
        bin_dir = Path(root) / ".doxoade" / "vulcan" / "bin"
        if not bin_dir.exists():
            return False
        source_path = src if src.exists() else None
        if not source_path:
            return False
        pyd_path = _find_pyd_for_source(bin_dir, source_path)
        if not pyd_path or not _is_binary_valid_for_host(pyd_path):
            return False
        native_name = pyd_path.stem.split(".")[0]
        native_mod  = _load_extension_from_path(native_name, pyd_path)
        if not native_mod:
            return False
        injected = 0
        for attr in dir(native_mod):
            if not attr.endswith(suffix):
                continue
            base = attr[: -len(suffix)]
            if base in globs:
                try:
                    native_obj = getattr(native_mod, attr)
                    py_obj     = globs.get(base)
                    globs[base] = safe_call(native_obj, py_obj) if callable(native_obj) else native_obj
                    injected += 1
                except Exception:
                    continue
        return injected > 0
    except Exception:
        return False
'''

VULCAN_STUB_VERSION = 3


def generate_vulcan_stub() -> str:
    return f'''# -*- coding: utf-8 -*-
"""
Stub Vulcan embutido no projeto.
Gerenciado automaticamente pelo doxoade.
"""

VULCAN_STUB_VERSION = {VULCAN_STUB_VERSION}

def activate():
    try:
        from doxoade.tools.vulcan.runtime import install_meta_finder, find_vulcan_project_root
        import __main__
        root = find_vulcan_project_root(__file__)
        if root:
            install_meta_finder(root)
        return True
    except Exception:
        return False
'''


def read_stub_version(stub_path: Path) -> int | None:
    if not stub_path.exists():
        return None
    try:
        text = stub_path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"VULCAN_STUB_VERSION\s*=\s*(\d+)", text)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None


def _write_safe_runtime(project_root: Path) -> Path:
    project_root = Path(project_root).resolve()
    vulcan_dir   = project_root / ".doxoade" / "vulcan"
    vulcan_dir.mkdir(parents=True, exist_ok=True)

    (project_root / ".doxoade" / "__init__.py").write_text("# doxoade vulcan marker\n", encoding="utf-8")
    (vulcan_dir / "__init__.py").write_text("# doxoade vulcan marker\n", encoding="utf-8")

    vulcan_src = Path(__file__).resolve().parents[1] / "tools" / "vulcan"
    for fname in ("runtime.py", "opt_cache.py", "lib_optimizer.py"):
        src_file = vulcan_src / fname
        if src_file.exists():
            (vulcan_dir / fname).write_text(src_file.read_text(encoding="utf-8"), encoding="utf-8")

    (vulcan_dir / "vulcan_embedded.py").write_text(_VULCAN_EMBEDDED_CONTENT.lstrip(), encoding="utf-8")
    return vulcan_dir / "runtime.py"


def _iter_project_main_files(project_root: Path):
    skip = {".git", "venv", ".venv", "__pycache__", "build", "dist", ".pytest_cache"}
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip]
        if "__main__.py" in files:
            yield Path(root) / "__main__.py"


def _inject_bootstrap(main_file: Path) -> bool:
    original = main_file.read_text(encoding="utf-8", errors="replace")
    content  = original
    while True:
        start = content.find(_BOOTSTRAP_START)
        if start < 0:
            break
        end = content.find(_BOOTSTRAP_END, start)
        if end < 0:
            break
        end += len(_BOOTSTRAP_END)
        if end < len(content) and content[end] == "\n":
            end += 1
        content = content[:start] + content[end:]
    updated = _BOOTSTRAP_BLOCK + content
    if updated == original:
        return False
    main_file.write_text(updated, encoding="utf-8")
    return True


# ── Comandos ──────────────────────────────────────────────────────────────────

@click.command('module')
@click.option('--path', 'target_path', default='.', type=click.Path(exists=True, file_okay=False, dir_okay=True),
              show_default=True, help='Projeto alvo que receberá o módulo de acionamento Vulcan.')
@click.option('--main', 'main_files', multiple=True, type=click.Path(exists=True, dir_okay=False),
              help='Arquivo __main__.py específico para injetar bootstrap.')
@click.option('--auto-main', is_flag=True, help='Detecta e injeta em todos os __main__.py do projeto.')
@click.option('--force-stub', is_flag=True, help="Recria o stub Vulcan mesmo se já existir.")
def vulcan_module(target_path, main_files, auto_main, force_stub):
    """Instala módulo de acionamento Vulcan em projetos externos."""
    project_root = Path(target_path).resolve()
    stub_path    = project_root / ".doxoade" / "vulcan_embedded.py"

    current_version = read_stub_version(stub_path)
    should_write = force_stub or current_version is None or current_version != VULCAN_STUB_VERSION

    if should_write:
        stub_path.parent.mkdir(parents=True, exist_ok=True)
        stub_path.write_text(generate_vulcan_stub(), encoding="utf-8")
        if force_stub:
            click.echo(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Stub Vulcan recriado (--force-stub).")
        elif current_version is None:
            click.echo(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Stub Vulcan criado.")
        else:
            click.echo(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Stub Vulcan atualizado.")
    else:
        click.echo(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Stub Vulcan já está atualizado.")

    if _is_doxoade_project(project_root):
        click.echo(f"\n{Fore.RED}[ERRO] vulcan module não pode ser aplicado ao próprio projeto doxoade.{Style.RESET_ALL}")
        click.echo(
            f"{Fore.YELLOW}[INFO] O doxoade já possui MetaFinder nativo em "
            f"doxoade/tools/vulcan/meta_finder.py{Style.RESET_ALL}"
        )
        click.echo(f"{Fore.CYAN}[DICA] Para compilar módulos do doxoade, use: doxoade vulcan ignite{Style.RESET_ALL}")
        return

    click.echo(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Stub Vulcan embutido criado em {stub_path}")

    runtime_dst = _write_safe_runtime(project_root)
    click.echo(f"{Fore.GREEN}[OK]{Fore.RESET} Runtime instalado em: {runtime_dst}")

    changed = []
    if main_files:
        for item in main_files:
            p = Path(item).resolve()
            if _inject_bootstrap(p):
                changed.append(p)
    elif auto_main:
        for p in _iter_project_main_files(project_root):
            if _inject_bootstrap(p):
                changed.append(p)

    if changed:
        click.echo(f"{Fore.GREEN}[OK]{Fore.RESET} Bootstrap v2 injetado em:")
        for p in changed:
            click.echo(f"  - {p}")
        click.echo(
            f"\n{Fore.CYAN}[INFO] Bootstrap v2 instala MetaFinder automaticamente.{Style.RESET_ALL}"
        )
    elif main_files or auto_main:
        click.echo(f"{Fore.YELLOW}[INFO]{Fore.RESET} Nenhum __main__.py precisou de alteração.")
    else:
        click.echo(
            f"{Fore.CYAN}[DICA]{Fore.RESET} Use --auto-main para injetar automaticamente, "
            "ou --main <arquivo> para alvo específico."
        )


@click.command('probe')
@click.option('--path', 'target_path', default='.', type=click.Path(exists=True, file_okay=False, dir_okay=True),
              show_default=True, help='Projeto alvo a inspecionar.')
@click.option('--verbose', '-v', is_flag=True, help='Mostra detalhes de hash e paths.')
def vulcan_probe(target_path, verbose):
    """Verifica quais módulos estão ativos e seriam redirecionados para PYD."""
    project_root = Path(target_path).resolve()
    bin_dir      = project_root / ".doxoade" / "vulcan" / "bin"

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  VULCAN PROBE — {project_root.name}{Style.RESET_ALL}")

    if not bin_dir.exists():
        click.echo(f"  {Fore.RED}Nenhuma foundry encontrada em {bin_dir}{Fore.RESET}")
        return

    ext      = ".pyd" if os.name == "nt" else ".so"
    binaries = sorted(bin_dir.glob(f"*{ext}"))

    if not binaries:
        click.echo(f"  {Fore.YELLOW}Nenhum binário ativo.{Fore.RESET}")
        return

    skip     = {".git", "venv", ".venv", "__pycache__", "build", "dist", ".doxoade"}
    py_files : list[Path] = []
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith(".py"):
                py_files.append(Path(root) / f)

    hash_index: dict[str, Path] = {}
    for py in py_files:
        h = hashlib.sha256(str(py.resolve()).encode()).hexdigest()[:6]
        hash_index[h] = py

    active, stale, orphan = [], [], []

    for bin_path in binaries:
        base     = bin_path.stem.split(".")[0]
        parts    = base.split("_")
        pyd_hash = parts[-1] if len(parts) >= 3 else None
        pyd_stem = "_".join(parts[1:-1]) if pyd_hash else "_".join(parts[1:])
        source   = hash_index.get(pyd_hash) if pyd_hash else None

        if not source:
            for py in py_files:
                if py.stem == pyd_stem:
                    source = py
                    break

        if not source:
            orphan.append((bin_path, pyd_stem, pyd_hash))
            continue

        try:
            is_stale = source.stat().st_mtime > bin_path.stat().st_mtime
        except OSError:
            is_stale = True

        rel_src = source.relative_to(project_root)
        (stale if is_stale else active).append((bin_path, rel_src, source))

    click.echo(f"\n  {Fore.GREEN}{Style.BRIGHT}✔ ATIVOS ({len(active)}):{Style.RESET_ALL}")
    if active:
        for bin_path, rel_src, source in active:
            size_kb = bin_path.stat().st_size / 1024
            click.echo(
                f"    {Fore.GREEN}✔{Fore.RESET} {str(rel_src):<45} "
                f"{Fore.WHITE}{size_kb:>6.1f} KB{Fore.RESET}"
            )
            if verbose:
                click.echo(f"       {Fore.CYAN}PYD:{Fore.RESET} {bin_path.name}")
                click.echo(f"       {Fore.CYAN}SRC:{Fore.RESET} {source}")
    else:
        click.echo(f"    {Fore.YELLOW}(nenhum){Fore.RESET}")

    if stale:
        click.echo(f"\n  {Fore.YELLOW}{Style.BRIGHT}⚠ STALE ({len(stale)}):{Style.RESET_ALL}")
        for bin_path, rel_src, source in stale:
            click.echo(
                f"    {Fore.YELLOW}⚠{Fore.RESET} {str(rel_src):<45} "
                f"{Fore.YELLOW}[recompile: doxoade vulcan ignite]{Fore.RESET}"
            )
            if verbose:
                import time as _time
                py_t  = _time.strftime('%Y-%m-%d %H:%M:%S', _time.localtime(source.stat().st_mtime))
                pyd_t = _time.strftime('%Y-%m-%d %H:%M:%S', _time.localtime(bin_path.stat().st_mtime))
                click.echo(f"       .py  modificado: {py_t}")
                click.echo(f"       .pyd compilado : {pyd_t}")

    if orphan:
        click.echo(f"\n  {Fore.RED}{Style.BRIGHT}✘ ÓRFÃOS ({len(orphan)}):{Style.RESET_ALL}")
        for bin_path, pyd_stem, pyd_hash in orphan:
            click.echo(
                f"    {Fore.RED}✘{Fore.RESET} {bin_path.name}"
                + (f"  {Fore.YELLOW}(hash: {pyd_hash}){Fore.RESET}" if pyd_hash else "")
            )

    total = len(binaries)
    click.echo(f"\n  {Fore.CYAN}{'─' * 55}{Fore.RESET}")
    click.echo(
        f"  Total: {total}  │  "
        f"{Fore.GREEN}Ativos: {len(active)}{Fore.RESET}  │  "
        f"{Fore.YELLOW}Stale: {len(stale)}{Fore.RESET}  │  "
        f"{Fore.RED}Órfãos: {len(orphan)}{Fore.RESET}"
    )
    if len(active) == total:
        click.echo(f"\n  {Fore.GREEN}{Style.BRIGHT}✅ 100% dos módulos redirecionados para PYD.{Style.RESET_ALL}")
    elif active:
        pct = (len(active) / total) * 100
        click.echo(f"\n  {Fore.YELLOW}⚡ {pct:.0f}% ativos. Use 'doxoade vulcan ignite' para recompilar stale.{Fore.RESET}")
    else:
        click.echo(f"\n  {Fore.RED}Nenhum módulo ativo. Execute 'doxoade vulcan ignite'.{Fore.RESET}")
    click.echo()


@click.command('verify')
@click.argument('target_path', default='.', type=click.Path(exists=True))
@click.option('--verbose', '-v', is_flag=True)
def vulcan_verify(target_path, verbose):
    """Verifica se o redirecionamento PYD está funcional em projeto externo.

    \b
    Separa dois tipos de binário:
      bin/     → binários do PROJETO (rastreáveis por hash ao .py de origem)
      lib_bin/ → binários de LIBS EXTERNAS (compilados de site-packages,
                 não rastreáveis ao projeto — mostrados como seção separada)
    """
    project_root = Path(target_path).resolve()
    bin_dir      = project_root / ".doxoade" / "vulcan" / "bin"
    lib_bin_dir  = project_root / ".doxoade" / "vulcan" / "lib_bin"
    runtime_py   = project_root / ".doxoade" / "vulcan" / "runtime.py"

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ⬡ VULCAN VERIFY — {project_root.name}{Style.RESET_ALL}")

    # ── Pré-checks ────────────────────────────────────────────────────────────
    ext         = ".pyd" if os.name == "nt" else ".so"
    proj_bins   = list(bin_dir.glob(f"*{ext}"))     if bin_dir.exists()     else []
    lib_bins    = list(lib_bin_dir.glob(f"*{ext}")) if lib_bin_dir.exists() else []
    any_bins    = bool(proj_bins or lib_bins)

    checks = {
        "runtime.py presente":        runtime_py.exists(),
        "bin/ presente":               bin_dir.exists(),
        "vulcan_embedded.py presente": (project_root / ".doxoade" / "vulcan" / "vulcan_embedded.py").exists(),
    }

    main_files      = list(project_root.rglob("__main__.py"))
    bootstrap_found = any(
        _BOOTSTRAP_START in p.read_text(encoding="utf-8", errors="ignore")
        for p in main_files
        if ".doxoade" not in str(p)
    )
    checks["bootstrap em __main__.py"] = bootstrap_found
    checks[f"binários {ext} presentes (bin/ + lib_bin/)"] = any_bins

    all_ok = True
    for label, ok in checks.items():
        icon   = f"{Fore.GREEN}✔" if ok else f"{Fore.RED}✘"
        all_ok = all_ok and ok
        click.echo(f"   {icon}{Style.RESET_ALL} {label}")

    # Mostra contagem de lib_bin mesmo durante pré-checks
    if lib_bins:
        total_kb = sum(p.stat().st_size for p in lib_bins) / 1024
        click.echo(
            f"   {Fore.CYAN}ℹ{Style.RESET_ALL}  lib_bin/: "
            f"{len(lib_bins)} lib binário(s)  ({total_kb:.1f} KB total)"
        )

    if not all_ok:
        click.echo(
            f"\n{Fore.YELLOW}  ⚠ Pré-checks falharam. "
            f"Execute 'doxoade vulcan module --path {target_path} --auto-main' primeiro.{Style.RESET_ALL}"
        )
        return

    # ── Seção 1: lib_bin/ — libs externas (sem teste de redirecionamento) ─────
    if lib_bins:
        click.echo(f"\n{Fore.MAGENTA}{Style.BRIGHT}  ⬡ LIBS EXTERNAS COMPILADAS (lib_bin/) — {len(lib_bins)} binário(s){Style.RESET_ALL}")
        click.echo(
            f"  {Style.DIM}Estes binários são carregados pelo MetaFinder quando a lib "
            f"é importada.\n  O hash no nome refere-se ao caminho temporário de compilação "
            f"— isso é esperado.{Style.RESET_ALL}"
        )
        # Agrupa por prefixo de nome (ex: formatting, parser, ...)
        lib_by_stem: dict[str, list] = {}
        for bp in sorted(lib_bins):
            parts = bp.stem.split(".")[0].split("_")          # v_formatting_1779ae
            stem  = "_".join(parts[1:-1]) if len(parts) >= 3 else bp.stem
            lib_by_stem.setdefault(stem, []).append(bp)

        for stem, paths in sorted(lib_by_stem.items()):
            # Mostra apenas o mais recente se houver múltiplas versões
            newest   = max(paths, key=lambda p: p.stat().st_mtime)
            size_kb  = newest.stat().st_size / 1024
            n_extra  = len(paths) - 1
            extra    = f"  {Style.DIM}(+{n_extra} versão(ões) antiga(s)){Style.RESET_ALL}" if n_extra else ""
            click.echo(
                f"   {Fore.MAGENTA}⬡{Style.RESET_ALL} {stem:<30} "
                f"{Fore.WHITE}{size_kb:>6.1f} KB{Style.RESET_ALL}{extra}"
            )
            if verbose:
                for p in sorted(paths, key=lambda x: x.stat().st_mtime, reverse=True):
                    age = "← atual" if p is newest else "← antiga"
                    click.echo(f"       {Fore.CYAN}{p.name}{Style.RESET_ALL}  {Style.DIM}{age}{Style.RESET_ALL}")

        # Aviso sobre versões antigas acumuladas
        n_old = sum(len(v) - 1 for v in lib_by_stem.values())
        if n_old > 0:
            click.echo(
                f"\n  {Fore.YELLOW}⚠ {n_old} binário(s) antigo(s) em lib_bin/ "
                f"(recompilações anteriores).{Style.RESET_ALL}\n"
                f"  {Fore.CYAN}  Limpe com: doxoade vulcan purge{Style.RESET_ALL}"
            )

    # ── Seção 2: bin/ — binários do projeto (teste de redirecionamento) ────────
    if not proj_bins:
        if lib_bins:
            click.echo(
                f"\n{Fore.CYAN}  ℹ bin/ vazio — nenhum binário de projeto para testar.{Style.RESET_ALL}\n"
                f"  Execute 'doxoade vulcan ignite' para compilar o projeto."
            )
        else:
            click.echo(
                f"\n{Fore.RED}  ✘ Nenhum binário encontrado em bin/ ou lib_bin/.{Style.RESET_ALL}\n"
                f"  Execute 'doxoade vulcan ignite' ou 'doxoade vulcan lib --target <lib>'."
            )
        click.echo()
        return

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ⬡ PROJETO (bin/) — testando redirecionamento...{Style.RESET_ALL}")

    # Índice hash → .py do PROJETO (não de site-packages)
    skip     = {".git", "venv", ".venv", "__pycache__", "build", "dist", ".doxoade"}
    py_index : dict[str, Path] = {}
    for r, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith(".py"):
                p = Path(r) / f
                h = hashlib.sha256(str(p.resolve()).encode()).hexdigest()[:6]
                py_index[h] = p

    results = []
    for bin_path in proj_bins[:10]:
        base  = bin_path.stem.split(".")[0]
        parts = base.split("_")
        phash = parts[-1] if len(parts) >= 3 else None
        src   = py_index.get(phash)

        if not src:
            results.append({"bin": bin_path.name, "status": "ÓRFÃO", "src": None})
            continue

        try:
            modname = str(src.with_suffix("").relative_to(project_root)).replace(os.sep, ".")
        except ValueError:
            modname = src.stem

        probe_script = f"""
import sys, importlib, json
sys.path.insert(0, r'{project_root}')
import importlib.util as _u
_spec = _u.spec_from_file_location('_rt', r'{runtime_py}')
_mod  = _u.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_mod.install_meta_finder(r'{project_root}')
modname = '{modname}'
try:
    mod  = importlib.import_module(modname)
    file = getattr(mod, '__file__', '') or ''
    loader_name = type(getattr(mod, '__loader__', None)).__name__
    redirected = '.doxoade' in file.replace('\\\\', '/') or loader_name == 'VulcanLoader'
    print(json.dumps({{"stem": modname, "file": file, "loader": loader_name, "redirected": redirected}}))
except Exception as e:
    print(json.dumps({{"stem": modname, "file": "", "redirected": False, "error": str(e)}}))
"""

        try:
            proc = subprocess.run(
                [sys.executable, "-c", probe_script],
                capture_output=True, text=True, timeout=10,
                cwd=str(project_root),
            )
            for line in proc.stdout.strip().splitlines():
                try:
                    data = json.loads(line)
                    data["bin"] = bin_path.name
                    data["src"] = str(src.relative_to(project_root))
                    results.append(data)
                except Exception:
                    pass
        except subprocess.TimeoutExpired:
            results.append({"bin": bin_path.name, "status": "TIMEOUT", "src": str(src)})
        except Exception as exc:
            results.append({"bin": bin_path.name, "status": f"ERRO: {exc}", "src": str(src)})

    redirected = [r for r in results if r.get("redirected")]
    not_redir  = [r for r in results if not r.get("redirected") and r.get("src")]
    orphans    = [r for r in results if r.get("status") == "ÓRFÃO"]

    click.echo(f"\n{Fore.CYAN}  {'─' * 55}{Style.RESET_ALL}")

    if redirected:
        click.echo(f"  {Fore.GREEN}{Style.BRIGHT}✔ REDIRECIONADOS ({len(redirected)}):{Style.RESET_ALL}")
        for r in redirected:
            click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} {r['src']}")
            if verbose:
                click.echo(f"     → {Fore.CYAN}{r.get('file','')}{Style.RESET_ALL}")

    if not_redir:
        click.echo(f"\n  {Fore.YELLOW}{Style.BRIGHT}⚠ NÃO REDIRECIONADOS ({len(not_redir)}):{Style.RESET_ALL}")
        for r in not_redir:
            err = r.get("error", "import retornou .py original")
            click.echo(f"   {Fore.YELLOW}⚠{Style.RESET_ALL} {r['src']}  {Style.DIM}({err}){Style.RESET_ALL}")

    if orphans:
        click.echo(
            f"\n  {Fore.RED}{Style.BRIGHT}✘ ÓRFÃOS — hash não encontrado no projeto ({len(orphans)}):{Style.RESET_ALL}"
        )
        for r in orphans:
            click.echo(f"   {Fore.RED}✘{Style.RESET_ALL} {r['bin']}")
        click.echo(
            f"  {Style.DIM}Estes binários podem ser de uma compilação antiga "
            f"(arquivos .py movidos/renomeados).{Style.RESET_ALL}\n"
            f"  {Fore.CYAN}  Limpe com: doxoade vulcan purge{Style.RESET_ALL}"
        )

    total = len(results)
    pct   = (len(redirected) / total * 100) if total else 0
    click.echo(
        f"\n  {Fore.CYAN}Projeto — Total: {total}  │  "
        f"{Fore.GREEN}Redirecionados: {len(redirected)} ({pct:.0f}%){Fore.RESET}  │  "
        f"{Fore.YELLOW}Falhos: {len(not_redir)}{Fore.RESET}  │  "
        f"{Fore.RED}Órfãos: {len(orphans)}{Style.RESET_ALL}"
    )

    if pct == 100 and total > 0:
        click.echo(f"\n  {Fore.GREEN}{Style.BRIGHT}✅ Redirecionamento 100% funcional.{Style.RESET_ALL}")
    elif pct > 0:
        click.echo(
            f"\n  {Fore.YELLOW}⚡ Redirecionamento parcial. "
            f"Verifique se o bootstrap está no __main__.py e rode 'vulcan ignite'.{Style.RESET_ALL}"
        )
    elif total > 0:
        click.echo(
            f"\n  {Fore.RED}✘ Nenhum redirecionamento ativo. "
            f"Execute 'doxoade vulcan module --path {target_path} --auto-main'.{Style.RESET_ALL}"
        )
    click.echo()