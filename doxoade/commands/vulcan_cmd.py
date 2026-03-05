# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd.py
"""
Patch para adicionar 'doxoade vulcan opt-bench' ao vulcan_cmd.py.

Cole este bloco APÓS a definição do comando 'opt' existente:

    @vulcan_group.command("opt-bench")
    ...

E adicione ao topo do arquivo, junto com os outros imports:
    from .tools.vulcan.opt_benchmark import run_opt_bench, render_results

──────────────────────────────────────────────────────────────────────
INTEGRAÇÃO (vulcan_cmd.py):

1. Imports (no topo, junto com os outros):

    from .tools.vulcan.opt_benchmark import run_opt_bench, render_results

2. Comando (após o comando 'opt'):

    [cole o bloco abaixo]
──────────────────────────────────────────────────────────────────────
"""

# [DOX-UNUSED] import textwrap
import sys
import signal
import os
# [DOX-UNUSED] import subprocess
import click
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import ExecutionLogger, _find_project_root

__version__ = "85.0 Omega (Self-Guard + Redirect Fix + Probe)"


# ================== Vulcan Embedded probes ==================

_BOOTSTRAP_START = "# --- DOXOADE_VULCAN_BOOTSTRAP:START ---"
_BOOTSTRAP_END = "# --- DOXOADE_VULCAN_BOOTSTRAP:END ---"
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

# 1. Instala MetaFinder primeiro — redireciona imports Python → PYD automaticamente
if callable(_doxo_install_meta_finder) and _doxo_project_root:
    _doxo_t = _doxo_time.monotonic()
    try:
        _doxo_install_meta_finder(_doxo_project_root)
    except Exception:
        # não falha a execução do bootstrap — metas podem já estar instalados
        pass
    finally:
        _doxo_install_ms = int((_doxo_time.monotonic() - _doxo_t) * 1000)

# 2. Tenta usar o loader "embedded" (safe wrapper com safe_call + checagem de assinatura)
try:
    _doxo_t = _doxo_time.monotonic()
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
                        # activate_embedded aplica safe_call e valida assinaturas — preferível
                        _doxo_activate_embedded(globals(), __file__, _doxo_project_root)
                    except Exception:
                        pass

                # Se safe_call está exposto, aplicamos um pass de segurança a MÓDULOS JÁ CARREGADOS
                # Isso resolve o caso em que o .pyd já foi importado antes do bootstrap
                if callable(_doxo_safe_call):
                    try:
                        import sys as _d_sys
                        _bin_dir = _doxo_path(_doxo_project_root) / ".doxoade" / "vulcan" / "bin"
                        for mname, mod in list(_d_sys.modules.items()):
                            try:
                                mfile = getattr(mod, "__file__", "")
                                if not mfile:
                                    continue
                                mpath = _doxo_path(mfile)
                                # só módulos que residem na foundry bin
                                if _bin_dir in mpath.parents:
                                    # iterar sobre atributos nativos e aplicar safe_call
                                    for attr in dir(mod):
                                        if not attr.endswith("_vulcan_optimized"):
                                            continue
                                        native_obj = getattr(mod, attr, None)
                                        if not callable(native_obj):
                                            continue
                                        base = attr[: -len("_vulcan_optimized")]
                                        try:
                                            setattr(mod, base, _doxo_safe_call(native_obj, getattr(mod, base, None)))
                                        except Exception:
                                            # não falha a importação; continuamos
                                            continue
                            except Exception:
                                continue
                    except Exception:
                        pass
except Exception:
    pass
finally:
    _doxo_embedded_ms = int((_doxo_time.monotonic() - _doxo_t) * 1000)

# 3. Fallback: runtime.activate_vulcan (mantém compatibilidade retroativa)
# Chamamos em try/except para não interromper o fluxo caso o runtime injete de forma insegura.
if callable(_doxo_activate_vulcan):
    _doxo_t = _doxo_time.monotonic()
    try:
        _doxo_activate_vulcan(globals(), __file__)
    except Exception:
        # não propaga erro — se falhar, o projeto seguirá com implementações Python originais
        pass
    finally:
        _doxo_fallback_ms = int((_doxo_time.monotonic() - _doxo_t) * 1000)

# 4. Diagnóstico opcional (útil para startup lento em servidores externos)
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
                + "fallback_ms=" + str(__doxoade_vulcan_probe__.get("fallback_ms", 0)) + "\\n"
            )
    except Exception:
        pass
{_BOOTSTRAP_END}
'''

_VULCAN_EMBEDDED_CONTENT = r'''# -*- coding: utf-8 -*-
"""vulcan_embedded.py — safe loader gerado pelo doxoade (opt-in).

Este arquivo é INERTE até que o projeto o importe explicitamente:

    try:
        from .doxoade.vulcan.vulcan_embedded import activate_embedded
        activate_embedded(globals(), __file__)
    except Exception:
        pass

Design:
- safe_call: wrapper universal que tenta (ctx, no-ctx, fallback)
- inject_optimized: injeta funções *_vulcan_optimized via wrapper
- activate_embedded: tenta localizar .pyd relativo ao source_file e injeta no scope
"""

from functools import wraps
from pathlib import Path
import sys
import os
import importlib.util
import importlib.machinery

# ---------- pequeno logger interno (silencioso por padrão) ----------
def _vlog(*args, **kwargs):
    # Implementar logging se necessário. Mantido leve para evitar poluição do __main__.
    return None

# ---------- ExecutionContext ----------
class ExecutionContext:
    __slots__ = ("argv", "env", "cwd", "project_root")

    def __init__(self):
        self.argv = sys.argv
        self.env = dict(os.environ)
        self.cwd = Path.cwd()
        main = sys.modules.get("__main__")
        self.project_root = getattr(main, "__file__", None)

# ---------- safe_call ----------
def safe_call(native_fn, fallback_fn=None):
    """Tenta: native(ctx, *a, **k) -> native(*a, **k) -> fallback(*a, **k)."""
    @wraps(fallback_fn or native_fn)
    def wrapper(*args, **kwargs):
        # 1) com contexto
        try:
            return native_fn(ExecutionContext(), *args, **kwargs)
        except TypeError:
            pass
        except Exception:
            # se nativo falhar com outro erro, tente fallback (mais seguro)
            if callable(fallback_fn):
                return fallback_fn(*args, **kwargs)
            raise

        # 2) sem contexto
        try:
            return native_fn(*args, **kwargs)
        except TypeError:
            pass
        except Exception:
            if callable(fallback_fn):
                return fallback_fn(*args, **kwargs)
            raise

        # 3) fallback python
        if callable(fallback_fn):
            return fallback_fn(*args, **kwargs)

        raise RuntimeError(f"[vulcan_embedded] assinatura incompatível: {getattr(native_fn,'__name__',str(native_fn))}")

    return wrapper

# ---------- injection helper ----------
_OPTIMIZED_SUFFIX = "_vulcan_optimized"

def inject_optimized(module, native_module, suffix=_OPTIMIZED_SUFFIX):
    """
    Injeta funções otimizadas do native_module para module usando safe_call.
    Retorna lista de símbolos injetados.
    """
    import inspect

    injected = []
    skipped = []

    for attr in dir(native_module):
        if not attr.endswith(suffix):
            continue

        orig_name = attr[:-len(suffix)]

        if not hasattr(module, orig_name):
            continue

        py_func = getattr(module, orig_name)
        native_func = getattr(native_module, attr)

        # 🔒 Guard 1 — callable
        if not callable(py_func) or not callable(native_func):
            skipped.append(orig_name)
            continue

        # 🔒 Guard 2 — assinatura compatível (checagem conservadora)
        try:
            py_sig = inspect.signature(py_func)
            native_sig = inspect.signature(native_func)
            if py_sig.parameters != native_sig.parameters:
                skipped.append(orig_name)
                continue
        except (ValueError, TypeError):
            # Se não der pra inspecionar, NÃO injeta
            skipped.append(orig_name)
            continue

        try:
            setattr(module, orig_name, safe_call(native_func, py_func))
            injected.append(orig_name)
        except Exception:
            skipped.append(orig_name)
            continue

    if injected:
        _vlog(f"OK   {getattr(module, '__name__', str(module))} ← ({', '.join(injected)})")

    if skipped:
        _vlog(f"SKIP {getattr(module, '__name__', str(module))} ← incompatível ({', '.join(skipped)})")

# ---------- minimal pyd locator & loader ----------
def _binary_ext():
    return ".pyd" if os.name == "nt" else ".so"

def _find_pyd_for_source(bin_dir: Path, source_path: Path):
    """
    Procurar por v_{stem}_{hash}* ou v_{stem}* — devolve Path ou None.
    """
    stem = source_path.stem
    ext = _binary_ext()
    # hash-exato
    try:
        import hashlib
        abs_hash = hashlib.sha256(str(source_path.resolve()).encode()).hexdigest()[:6]
        candidate = bin_dir / f"v_{stem}_{abs_hash}{ext}"
        if candidate.exists():
            return candidate
    except Exception:
        pass

    # glob mais recente
    matches = sorted(bin_dir.glob(f"v_{stem}_*{ext}"), key=lambda p: p.stat().st_mtime, reverse=True)
    if matches:
        return matches[0]

    # fallback v_stem*
    matches2 = sorted(bin_dir.glob(f"v_{stem}*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if matches2:
        return matches2[0]
    return None

def _is_binary_valid_for_host(bin_path: Path) -> bool:
    """
    Validação leve: existe e tamanho mínimo.
    Não tenta parse ELF/PE aqui (mantemos simples).
    """
    try:
        return bin_path.exists() and bin_path.stat().st_size > 4096
    except Exception:
        return False

def _load_extension_from_path(module_name: str, bin_path: Path):
    """
    Carrega um extension module a partir do arquivo binário sem alterar sys.path permanentemente.
    Retorna o módulo ou None.
    """
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

# ---------- API pública (opt-in) ----------
def activate_embedded(globs: dict, source_file: str, project_root: str | None = None, suffix=_OPTIMIZED_SUFFIX):
    """
    Ativa (opcional) otimizações do .doxoade/vulcan/bin para o módulo definido por source_file.
    - globs: normalmente globals() do __main__.py
    - source_file: __file__ do __main__ (string)
    - project_root: se None, procura o diretório ancestor que contenha .doxoade/vulcan/bin
    """
    try:
        src = Path(source_file).resolve()
        root = Path(project_root).resolve() if project_root else None
        if not root:
            # sobe procurando .doxoade/vulcan/bin
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

        # nome nativo simplificado (stem sem tag)
        native_name = pyd_path.stem.split(".")[0]

        native_mod = _load_extension_from_path(native_name, pyd_path)
        if not native_mod:
            return False

        # injetar em globs — globs geralmente representam __main__ namespace
        injected = 0
        for attr in dir(native_mod):
            if not attr.endswith(suffix):
                continue
            base = attr[: -len(suffix)]
            if base in globs:
                try:
                    native_obj = getattr(native_mod, attr)
                    py_obj = globs.get(base)
                    if callable(native_obj):
                        globs[base] = safe_call(native_obj, py_obj)
                    else:
                        globs[base] = native_obj
                    injected += 1
                except Exception:
                    continue

        return injected > 0
    except Exception:
        return False
'''


def generate_vulcan_stub() -> str:
    return '''# -*- coding: utf-8 -*-
"""
Stub Vulcan embutido no projeto.

Este arquivo é gerenciado automaticamente pelo doxoade.
Pode ser versionado com o projeto.
"""

VULCAN_STUB_VERSION = 2

def activate():
    """
    Ativa Vulcan de forma explícita.
    Uso recomendado no __main__.py do projeto.
    """
    try:
        from doxoade.tools.vulcan.runtime import (
            install_meta_finder,
            find_vulcan_project_root,
        )
        import __main__
        root = find_vulcan_project_root(__file__)
        if root:
            install_meta_finder(root)
        return True
    except Exception:
        return False
'''

VULCAN_STUB_VERSION = 3

from pathlib import Path
import re

def read_stub_version(stub_path: Path) -> int | None:
    if not stub_path.exists():
        return None

    try:
        text = stub_path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"VULCAN_STUB_VERSION\s*=\s*(\d+)", text)
        if m:
            return int(m.group(1))
    except Exception:
        return None

    return None

# ================== Detecção de auto-aplicação ==================

def _is_doxoade_project(path: Path) -> bool:
    """
    Retorna True se o caminho alvo é o próprio projeto doxoade.
    O doxoade já possui MetaFinder nativo — injetar bootstrap seria redundante
    e causaria conflito de finders no sys.meta_path.
    """
    # Marcadores exclusivos da infraestrutura interna do doxoade
    markers = [
        path / "doxoade" / "tools" / "vulcan" / "meta_finder.py",
        path / "doxoade" / "tools" / "vulcan" / "runtime.py",
    ]
    return any(m.exists() for m in markers)
    
def _sigint_handler(signum, frame):
    click.echo(f"\n{Fore.RED}Comando interrompido. Saindo...{Style.RESET_ALL}")
    sys.exit(130)


@click.group('vulcan')
def vulcan_group():
    """🔥 Projeto Vulcano: Alta Performance Nativa (C/Cython)."""
    pass


@vulcan_group.command('doctor')
@click.option('--module', help='Nome do m?dulo Python a tentar reparar (ex: doxoade.tools.streamer)')
@click.option('--srcdir', help='Caminho para o c?digo-fonte do m?dulo (opcional)')
@click.option('--retries', default=1, type=int)
def doctor(module, srcdir, retries):
    """Executa diagn?stico Vulcan + tenta reparo autom?tico de um m?dulo."""
    project_root = '.'
    from doxoade.tools.vulcan.diagnostic import VulcanDiagnostic
    diag = VulcanDiagnostic(project_root)
    ok, results = diag.check_environment()
    click.echo(f"Diagnostic: compiler_ok={results.get('compiler')} cython={results.get('cython')}")
    from doxoade.tools.vulcan.abi_gate import run_abi_gate

    run_abi_gate(project_root)
    if module:
        from doxoade.tools.vulcan.auto_repair import auto_repair_module
        res = auto_repair_module(project_root, module, module_src_dir=srcdir, retries=retries)
        click.echo(res)
    else:
        click.echo("Use --module to attempt to repair a specific module.")


# PATCH vulcan_cmd.py — adicionar ao comando ignite existente
# Substitua o decorador + função ignite atual por este bloco completo.

@vulcan_group.command('ignite')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--force',        is_flag=True,  help="Força a re-compilação de todos os alvos.")
@click.option('--jobs',         type=int, default=None, help="Número de workers (sobrescreve auto).")
@click.option('--no-pitstop',   is_flag=True,  help="Usa compilação legada (1 processo por módulo).")
@click.option('--streaming',    is_flag=True,  help="Forge e compilação em paralelo (melhor para > 15 módulos).")
@click.option('--hybrid',       is_flag=True,  help="Compilação seletiva por função (HybridForge).")
@click.option('--scan-only',    is_flag=True,  help="Com --hybrid: mostra candidatos sem compilar.")
@click.pass_context
def ignite(ctx, path, force, jobs, no_pitstop, streaming, hybrid, scan_only):
    """Transforma código Python em binários de alta velocidade.

    Modos:
      padrão   → PitStop Engine (batch compile + warm-up cache)
      --hybrid → HybridForge (seletivo por função, arquivos impuros aceitos)

    Use --scan-only com --hybrid para ver candidatos antes de compilar.
    """
    signal.signal(signal.SIGINT, _sigint_handler)
    root = _find_project_root(os.getcwd())
    target = path or root

    # ── Modo Híbrido ──────────────────────────────────────────────────────────
    if hybrid:
        from ..tools.vulcan.hybrid_forge import hybrid_ignite

        click.echo(f"{Fore.YELLOW}{Style.BRIGHT}⬡ [VULCAN-HYBRID] v{__version__}...{Style.RESET_ALL}")

        if scan_only:
            # Modo diagnóstico: só mostra o que seria compilado
            click.echo(f"{Fore.CYAN}   > Modo: SCAN ONLY (sem compilação){Style.RESET_ALL}")
            _run_hybrid_with_optimizer(target, root)
            return

        click.echo(f"{Fore.CYAN}   > Alvo : {target}{Style.RESET_ALL}")
        click.echo(f"{Fore.CYAN}   > Modo : HÍBRIDO (seletivo por função){Style.RESET_ALL}")

        with ExecutionLogger('vulcan_hybrid', root, ctx.params) as _:
            try:
                hybrid_ignite(
                    project_root = root,
                    target       = target,
                    force        = force,
                    on_progress  = click.echo,
                )
            except KeyboardInterrupt:
                _sigint_handler(None, None)
            except Exception as e:
                _print_vulcan_forensic("HYBRID", e)
                sys.exit(1)
        return

    # ── Modo Padrão (PitStop / Legado) — não alterado ─────────────────────────
    with ExecutionLogger('vulcan_ignite', root, ctx.params) as _:
        click.echo(f"{Fore.YELLOW}{Style.BRIGHT}🔥 [VULCAN-IGNITION] v{__version__}...{Style.RESET_ALL}")

        from ..tools.vulcan.diagnostic import VulcanDiagnostic
        diag = VulcanDiagnostic(root)
        ok, _ = diag.check_environment()

        if not ok:
            diag.render_report()
            sys.exit(1)

        from ..tools.vulcan.autopilot import VulcanAutopilot
        autopilot = VulcanAutopilot(root)

        candidates, mode = [], "AUTOMÁTICO (baseado em telemetria)"

        if path:
            abs_path = os.path.abspath(path)
            if os.path.isfile(abs_path):
                mode = f"MANUAL (arquivo: {os.path.basename(abs_path)})"
                candidates.append({'file': abs_path})
            elif os.path.isdir(abs_path):
                mode = f"MANUAL (diretório: {os.path.basename(abs_path)})"
                from ..dnm import DNM
                dnm = DNM(abs_path)
                py_files = dnm.scan(extensions=['py'])
                candidates = [{'file': f} for f in py_files]

        engine_label = (
            f"{Fore.YELLOW}LEGADO{Style.RESET_ALL}"
            if no_pitstop
            else f"{Fore.GREEN}PITSTOP{Style.RESET_ALL}"
            + (f" {Fore.CYAN}+streaming{Style.RESET_ALL}" if streaming else "")
        )
        click.echo(f"{Fore.CYAN}   > Modo de Operação : {mode}{Style.RESET_ALL}")
        click.echo(f"{Fore.CYAN}   > Engine          : {engine_label}{Style.RESET_ALL}")

        try:
            autopilot.scan_and_optimize(
                candidates    = candidates,
                force_recompile = force,
                max_workers   = jobs,
                use_pitstop   = not no_pitstop,
                streaming     = streaming,
            )
            click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✅ [VULCAN] Forja concluída.{Style.RESET_ALL}")
        except KeyboardInterrupt:
            _sigint_handler(None, None)
        except Exception as e:
            _print_vulcan_forensic("IGNITE", e)
            sys.exit(1)
            
            
def _run_hybrid_with_optimizer(target, root, force):
    """
    Versão atualizada do ignite --hybrid com optimizer integrado.
    Substitui o bloco interno do comando ignite quando --hybrid é passado.
    """
    from ..tools.vulcan.hybrid_forge     import HybridIgnite
    from ..tools.vulcan.hybrid_optimizer import optimize_pyx_file
    from pathlib import Path

    ignite = HybridIgnite(root)
    files  = HybridIgnite._collect_files(Path(target).resolve())

    opt_summary = []   # acumula relatórios do optimizer

    for py_file in files:
        scan = ignite._scanner.scan(str(py_file))
        if not scan.candidates:
            continue

        fname = py_file.name
        click.echo(
            f"   {Fore.YELLOW}[HYBRID]{Style.RESET_ALL} {fname} — "
            f"{len(scan.candidates)} candidato(s):"
        )
        for f in scan.candidates:
            click.echo(
                f"     • {f.name:<35} score={f.score:>2}  "
                f"({', '.join(f.reasons[:3])})"
            )

        # Gera .pyx raw
        pyx_path = ignite._forge.generate(scan)
        if not pyx_path:
            click.echo(f"   {Fore.RED}✘{Style.RESET_ALL} {fname}: forge falhou")
            continue

        # Enriquece com optimizer
        pyx_path, opt_report = optimize_pyx_file(pyx_path)

        if opt_report.transformations and not opt_report.transformations[0].startswith('revertido'):
            opt_summary.append(opt_report)
            n_cdefs = len(opt_report.transformations)
            click.echo(
                f"   {Fore.MAGENTA}  ⬡ optimizer{Style.RESET_ALL}: "
                f"{n_cdefs} cdef(s) injetados → "
                f"{Fore.GREEN}{opt_report.estimated_gain}{Style.RESET_ALL}"
            )

        # Compila
        module_name = pyx_path.stem
        ok, err = ignite._compile(module_name)

        if ok:
            click.echo(
                f"   {Fore.GREEN}✔{Style.RESET_ALL} {fname} → {module_name} "
                f"({len(scan.candidates)} funcs, score={scan.total_score})"
            )
        else:
            click.echo(f"   {Fore.RED}✘{Style.RESET_ALL} {fname}: {str(err)[:80]}")

    # Resumo do optimizer
    if opt_summary:
        total_cdefs = sum(len(r.transformations) for r in opt_summary)
        click.echo(
            f"\n{Fore.MAGENTA}"
            f"  ⬡ OPTIMIZER: {total_cdefs} cdef(s) em {len(opt_summary)} módulo(s)"
            f"{Style.RESET_ALL}"
        )
        for r in opt_summary:
            click.echo(
                f"    {r.module_name:<30} → {Fore.GREEN}{r.estimated_gain}{Style.RESET_ALL}"
            )
            for t in r.transformations[:5]:
                click.echo(f"      {Style.DIM}• {t}{Style.RESET_ALL}")
            if len(r.transformations) > 5:
                click.echo(f"      {Style.DIM}  (+{len(r.transformations)-5} mais){Style.RESET_ALL}")


@vulcan_group.command('pitstop')
@click.option('--clear-cache', is_flag=True, help="Apaga o WarmupCache (força recompilação total na próxima vez).")
def vulcan_pitstop(clear_cache):
    """Informações e controle do PitStop Engine (cache + warm-up)."""
    root = _find_project_root(os.getcwd())

    from ..tools.vulcan.environment import VulcanEnvironment
    from ..tools.vulcan.pitstop import PitstopEngine

    env = VulcanEnvironment(root)
    engine = PitstopEngine(env)
    info = engine.warmup_info()

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  PITSTOP ENGINE INFO:{Style.RESET_ALL}")
    click.echo(f"   Python    : {info['python_exe']}")
    click.echo(f"   Foundry   : {info['foundry']}")
    click.echo(f"   Bin       : {info['bin_dir']}")
    click.echo(f"   Workers   : {info['workers']} processos GCC paralelos")
    click.echo(f"   Estratégia: {info['parallel_strategy']}")
    click.echo(f"   Batch size: {info['batch_size']}")
    click.echo(f"   Cache     : {info['cache']['entries']} entrada(s) em {info['cache']['path']}")

    if info['build_env_keys']:
        click.echo(f"   Env extras: {', '.join(info['build_env_keys'])}")

    if clear_cache:
        cache_path = Path(info['cache']['path'])
        if cache_path.exists():
            cache_path.unlink()
            click.echo(f"\n{Fore.GREEN}[OK]{Fore.RESET} WarmupCache apagado. Próximo ignite recompila tudo.")
        else:
            click.echo(f"\n{Fore.YELLOW}[INFO]{Fore.RESET} Cache já estava vazio.")
            
            
@vulcan_group.command('lib')
@click.option('--analyze', is_flag=True, help="Lista dependências 'quentes' candidatas à compilação.")
@click.option('--target', help="Nome da biblioteca instalada no venv a compilar (ex: requests, pydantic).")
@click.option('--auto', is_flag=True, help="Compila automaticamente os melhores candidatos da análise.")
@click.option('--list-installed', is_flag=True, help="Lista libs instaladas no site-packages com contagem de .py.")
@click.option('--optimize', is_flag=True, help="Apenas otimiza os fontes da biblioteca em cópia isolada. NÃO compila, NÃO gera binários.(exige --target)")
@click.option('--keep-temp', is_flag=True, help="Mantém a cópia temporária da lib para inspeção/debug.")
@click.pass_context
def vulcan_lib(ctx, analyze, target, auto, list_installed, optimize, keep_temp):
    """Compila funções elegíveis de dependências já instaladas no venv.

    Trabalha sempre com uma CÓPIA isolada dos fontes — o venv original
    nunca é modificado. Só compila funções que passem no HybridScanner
    (score >= limiar, sem I/O, sem async, sem unbound locals).

    Exemplos:

      doxoade vulcan lib --target requests

      doxoade vulcan lib --target pydantic

      doxoade vulcan lib --analyze

      doxoade vulcan lib --list-installed
    """
    root = _find_project_root(os.getcwd())

    with ExecutionLogger('vulcan_lib', root, ctx.params) as logger:

        # ── Listar libs instaladas ─────────────────────────────────────────────
        if list_installed:
            click.echo(
                f"{Fore.CYAN}{Style.BRIGHT}"
                f"--- [VULCAN LIB] Libs instaladas no site-packages ---"
                f"{Style.RESET_ALL}"
            )
            import site
            site_dirs = []
            try:
                site_dirs.extend(site.getsitepackages())
            except AttributeError:
                pass
            for p in sys.path:
                if ("site-packages" in p or "dist-packages" in p) and p not in site_dirs:
                    site_dirs.append(p)
            from pathlib import Path
            rows = []
            for sp in site_dirs:
                sp_path = Path(sp)
                if not sp_path.is_dir():
                    continue
                for item in sorted(sp_path.iterdir()):
                    if not item.is_dir():
                        continue
                    if not (item / "__init__.py").exists():
                        continue
                    py_files = list(item.rglob("*.py"))
                    if py_files:
                        rows.append((item.name, len(py_files), str(item)))

            if not rows:
                click.echo(f"{Fore.YELLOW}Nenhum pacote encontrado.{Style.RESET_ALL}")
                return

            rows.sort(key=lambda r: r[1], reverse=True)
            click.echo(f"  {'BIBLIOTECA':<30} {'ARQUIVOS .PY':>14}")
            click.echo(f"  {'-'*30} {'-'*14}")
            for name, count, path in rows[:40]:
                click.echo(
                    f"  {Fore.WHITE}{name:<30}{Style.RESET_ALL} "
                    f"{Fore.CYAN}{count:>14}{Style.RESET_ALL}"
                )
            if len(rows) > 40:
                click.echo(
                    f"  {Style.DIM}... e mais {len(rows) - 40} pacote(s){Style.RESET_ALL}"
                )
            return

        # ── Análise de telemetria ──────────────────────────────────────────────
        if analyze:
            click.echo(
                f"{Fore.CYAN}{Style.BRIGHT}"
                f"--- [VULCAN LIB] Analisando telemetria de dependências ---"
                f"{Style.RESET_ALL}"
            )
            from ..tools.vulcan.advisor import VulcanAdvisor
            advisor = VulcanAdvisor(root)
            hot_deps = advisor.get_hot_dependencies()

            if not hot_deps:
                click.echo(
                    f"{Fore.YELLOW}Nenhuma dependência 'quente' encontrada na telemetria recente.{Style.RESET_ALL}"
                )
                return

            click.echo(f"  {'BIBLIOTECA':<28} {'HITS':>8}  COMANDO")
            click.echo(f"  {'-'*28} {'-'*8}  {'-'*35}")
            for dep, hits in list(hot_deps.items())[:20]:
                click.echo(
                    f"  {Fore.WHITE}{dep:<28}{Style.RESET_ALL} "
                    f"{Fore.RED}{hits:>8}{Style.RESET_ALL}  "
                    f"{Style.DIM}doxoade vulcan lib --target {dep}{Style.RESET_ALL}"
                )
            return

        # ── Apenas otimizar (novo modo) ───────────────────────────────────────
        
        if optimize and not target:
            click.echo(
                f"{Fore.YELLOW}[ERRO] --optimize exige --target.{Style.RESET_ALL}\n"
                f"{Fore.CYAN}Exemplo:{Style.RESET_ALL}\n"
                f"  doxoade vulcan lib --optimize --target click\n\n"
                f"{Fore.CYAN}Dica:{Style.RESET_ALL} use --list-installed para ver libs disponíveis."
            )
            return
        
        if optimize and (target or auto):
            click.echo(f"{Fore.CYAN}   > Modo: OPTIMIZE-ONLY (nenhuma compilação será executada){Style.RESET_ALL}")
            # exige --target para evitar otimizar tudo por engano
            if not target:
                click.echo(
                    f"{Fore.YELLOW}[ERROR] --optimize exige --target. "
                    f"Use --list-installed para ver nomes disponíveis.{Style.RESET_ALL}"
                )
                return

            click.echo(
                f"{Fore.CYAN}{Style.BRIGHT}"
                f"--- [VULCAN LIB] Otimizando (apenas) a biblioteca: {target} ---"
                f"{Style.RESET_ALL}"
            )
            click.echo(f"{Fore.CYAN}  > Criando cópia isolada dos fontes e executando LibOptimizer{Style.RESET_ALL}")

            # implementa sem importar o pacote (usa find_spec)
            import importlib.util
            import shutil
            import tempfile
            from pathlib import Path

            try:
                spec = importlib.util.find_spec(target)
                if spec is None:
                    click.echo(f"{Fore.RED}[FALHA] Não foi possível localizar a biblioteca '{target}' no venv.{Style.RESET_ALL}")
                    click.echo(f"{Fore.YELLOW}[DICA] Verifique o nome ou use --list-installed.{Style.RESET_ALL}")
                    return

                # determina caminho da biblioteca sem executar seu código
                if spec.submodule_search_locations:
                    pkg_path = Path(next(iter(spec.submodule_search_locations)))
                else:
                    # pacote simples (module.py) → usa pasta do arquivo
                    if not spec.origin:
                        click.echo(f"{Fore.RED}[FALHA] Espec não contém origem para '{target}'.{Style.RESET_ALL}")
                        return
                    pkg_path = Path(spec.origin).parent

                if not pkg_path.exists():
                    click.echo(f"{Fore.RED}[FALHA] Caminho da lib não existe: {pkg_path}{Style.RESET_ALL}")
                    return

                # cria tempdir explicitamente (não usar 'with' para permitir cleanup condicional)
                tmp_ctx = tempfile.TemporaryDirectory(prefix=f"vulcan_opt_{target}_")
                tmp = tmp_ctx.name
                dest = Path(tmp) / pkg_path.name

                try:
                    # copytree requer que dest não exista
                    shutil.copytree(pkg_path, dest, dirs_exist_ok=False)

                    # executa LibOptimizer na cópia
                    from ..tools.vulcan.lib_optimizer import LibOptimizer
                    optimizer = LibOptimizer()
                    stats = optimizer.optimize_directory(dest)

                    # grava artifact JSON via ExecutionLogger (se possível)
                    try:
                        logger.write_artifact(
                            name=f"vulcan_lib_opt_{target}.json",
                            data=stats
                        )
                    except Exception:
                        # não bloquear execução por falha de logger
                        pass

                    # resumo amigável — usa get() para robustez
                    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}--- [VULCAN LIB] Resumo da Otimização ---{Style.RESET_ALL}")
                    click.echo(f"  Arquivos processados : {stats.get('files_processed', 0)}")
                    click.echo(f"  Arquivos otimizados  : {stats.get('files_optimized', 0)}")
                    click.echo(f"  Arquivos ignorados   : {stats.get('files_skipped', 0)}")
                    click.echo(f"  Docstrings removidas : {stats.get('docstrings_removed', 0)}")
                    click.echo(f"  Dead branches        : {stats.get('dead_branches', 0)}")
                    click.echo(f"  Imports removidos    : {stats.get('imports_removed', 0)}")
                    click.echo(f"  Locals minificados   : {stats.get('locals_minified', 0)}")
                    bytes_saved = stats.get('bytes_saved', 0)
                    click.echo(f"  Bytes economizados   : {bytes_saved} ({bytes_saved/1024:.1f} KiB)")
                    click.echo(f"\n{Fore.GREEN}[SUCESSO] Otimização concluída na cópia: {dest}{Style.RESET_ALL}")
                    click.echo(f"{Fore.CYAN}[DICA] Se quiser compilar após otimizar, rode: doxoade vulcan lib --target {target}{Style.RESET_ALL}")

                finally:
                    # cleanup condicional do tempdir
                    if keep_temp:
                        click.echo(
                            f"{Fore.YELLOW}[INFO] --keep-temp ativo. Diretório preservado:{Style.RESET_ALL}\n"
                            f"  {Path(tmp)}"
                        )
                    else:
                        try:
                            tmp_ctx.cleanup()
                        except Exception:
                            pass

                return

                click.echo(
                    f"{Fore.CYAN}[INFO] Este modo NÃO compila código.{Style.RESET_ALL}\n"
                    f"{Fore.CYAN}[INFO] Para compilar a lib otimizada, execute manualmente:{Style.RESET_ALL}\n"
                    f"  doxoade vulcan lib --target {target}"
                )

            except Exception as exc:
                click.echo(f"{Fore.RED}[FALHA] Erro durante otimização: {exc}{Style.RESET_ALL}")
                return

        # ── Compilação de biblioteca específica ───────────────────────────────
        if target:
            click.echo(
                f"{Fore.CYAN}{Style.BRIGHT}"
                f"--- [VULCAN LIB] Forjando: {target} ---"
                f"{Style.RESET_ALL}"
            )
            click.echo(
                f"{Fore.CYAN}"
                f"   > Modo: VENV LOCAL (sem download — cópia isolada dos fontes)"
                f"{Style.RESET_ALL}"
            )

            from ..tools.vulcan.lib_forge import LibForge

            forge = LibForge(root)
            success, result_message = forge.compile_library(target)

            if success:
                click.echo(
                    f"{Fore.GREEN}{Style.BRIGHT}\n[SUCESSO] {result_message}{Style.RESET_ALL}"
                )
                click.echo(
                    f"{Fore.CYAN}[DICA] Use 'doxoade vulcan status' para ver os binários ativos.{Style.RESET_ALL}"
                )
            else:
                click.echo(
                    f"{Fore.RED}{Style.BRIGHT}\n[FALHA] {result_message}{Style.RESET_ALL}"
                )
                click.echo(
                    f"{Fore.YELLOW}[DICA] Use --list-installed para ver libs disponíveis no venv.{Style.RESET_ALL}"
                )
            return

        elif auto:
            click.echo(
                f"{Fore.YELLOW}[INFO] --auto: compila as top-3 libs da telemetria automaticamente.{Style.RESET_ALL}"
            )
            from ..tools.vulcan.advisor import VulcanAdvisor
            from ..tools.vulcan.lib_forge import LibForge

            advisor = VulcanAdvisor(root)
            hot_deps = advisor.get_hot_dependencies()

            if not hot_deps:
                click.echo(
                    f"{Fore.YELLOW}Sem dados de telemetria para --auto.{Style.RESET_ALL}"
                )
                return

            forge = LibForge(root)
            top = list(hot_deps.keys())[:3]
            for lib in top:
                click.echo(f"\n{Fore.CYAN}  → Compilando: {lib}{Style.RESET_ALL}")
                success, msg = forge.compile_library(lib)
                if success:
                    click.echo(f"{Fore.GREEN}  ✔ {msg}{Style.RESET_ALL}")
                else:
                    click.echo(f"{Fore.YELLOW}  ↷ {msg}{Style.RESET_ALL}")
            return

        else:
            click.echo(ctx.get_help())


@vulcan_group.command('benchmark')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--runs',       default=200, type=int, show_default=True,
              help='Número de execuções por função para calcular média.')
@click.option('--json',       'output_json', is_flag=True,
              help='Saída em JSON (para integração com CI).')
@click.option('--min-speedup', default=1.1, type=float, show_default=True,
              help='Speedup mínimo para considerar ganho real (regressões abaixo são marcadas).')
@click.option('--save',       is_flag=True,
              help='Salva resultado em .doxoade/vulcan/bench_results.json (feedback loop).')
def vulcan_benchmark(path, runs, output_json, min_speedup, save):
    """Mede speedup real Python vs Cython das funções compiladas.

    Compara execução das funções originais Python com os binários
    gerados pelo --hybrid, exibindo speedup real por função.
    Funções com speedup < --min-speedup são marcadas como REGRESSÃO.

    Exemplos:
      doxoade vulcan benchmark doxoade/tools/
      doxoade vulcan benchmark doxoade/tools/analysis.py --runs 500
      doxoade vulcan benchmark doxoade/tools/ --json > bench.json
      doxoade vulcan benchmark doxoade/tools/ --save --min-speedup 1.2
    """
    root   = _find_project_root(os.getcwd())
    target = path or root

    if not output_json:
        click.echo(
            f"\n{Fore.CYAN}{Style.BRIGHT}"
            f"  ⚡ VULCAN BENCHMARK — {runs} execuções por função"
            f"{Style.RESET_ALL}"
        )
        click.echo(
            f"{Fore.CYAN}  Alvo: {target}{Style.RESET_ALL}\n"
        )

    try:
        from ..tools.vulcan.hybrid_benchmark import run_benchmark
        results = run_benchmark(
            project_root = root,
            target       = target,
            runs         = runs,
            output_json  = output_json,
            min_speedup  = min_speedup,
        )

        if save and results:
            import json as _json
            bench_path = (
                Path(_find_project_root(os.getcwd()))
                / ".doxoade" / "vulcan" / "bench_results.json"
            )
            bench_path.parent.mkdir(parents=True, exist_ok=True)
            # Serializa results (lista de FileBenchResult dataclasses)
            import dataclasses
            serializable = _json.loads(
                _json.dumps(results, default=lambda o: dataclasses.asdict(o) if dataclasses.is_dataclass(o) else str(o))
            )
            bench_path.write_text(_json.dumps(serializable, indent=2), encoding='utf-8')
            click.echo(
                f"\n{Fore.GREEN}  ✔ Resultados salvos em {bench_path}{Style.RESET_ALL}"
            )
            click.echo(
                f"{Fore.CYAN}  Dica: use estes dados para excluir regressões no próximo --hybrid{Style.RESET_ALL}"
            )

    except Exception as e:
        _print_vulcan_forensic("BENCHMARK", e)
        sys.exit(1)


@vulcan_group.command('opt')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--force', is_flag=True, help='Regenera mesmo arquivos já otimizados.')
@click.option('--stats', is_flag=True, help='Mostra estatísticas de economia por arquivo.')
def vulcan_opt(path, force, stats):
    """Gera camada de Python Otimizado (Tier 2) sem compilar.

    Aplica DocstringRemover, DeadBranchEliminator, UnusedImportRemover
    e LocalNameMinifier em cópia isolada de cada .py elegível.

    Os arquivos otimizados ficam em .doxoade/vulcan/opt_py/ e são usados
    automaticamente como fallback quando o binário (.pyd/.so) não está
    disponível ou falhou ao carregar.

    Exemplos:

      doxoade vulcan opt

      doxoade vulcan opt myapp/

      doxoade vulcan opt myapp/core.py --stats
    """
    root   = _find_project_root(os.getcwd())
    target = Path(path).resolve() if path else Path(root)

    click.echo(
        f"\n{Fore.CYAN}{Style.BRIGHT}"
        f"  ⬡ [VULCAN OPT] Gerando camada de Python Otimizado (Tier 2)..."
        f"{Style.RESET_ALL}"
    )
    click.echo(f"{Fore.CYAN}   > Alvo   : {target}{Style.RESET_ALL}")
    click.echo(f"{Fore.CYAN}   > Raiz   : {root}{Style.RESET_ALL}")

    try:
        from doxoade.tools.vulcan.opt_cache import (
            generate_opt_py,
            find_opt_py,
            opt_dir,
        )

        skip_dirs = frozenset({
            '.git', 'venv', '.venv', '__pycache__', 'build', 'dist',
            '.doxoade', 'tests',
        })
        skip_stems = frozenset({
            '__init__', '__main__', 'setup',
            'forge', 'compiler', 'autopilot', 'bridge', 'advisor',
            'environment', 'core', 'pitstop', 'diagnostic', 'guards',
            'meta_finder', 'runtime', 'auto_repair', 'artifact_manager',
            'compiler_safe', 'opt_cache',
        })

        if target.is_file():
            py_files = [target] if target.suffix == '.py' else []
        else:
            py_files = []
            for r, dirs, files in os.walk(str(target)):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for f in files:
                    p = Path(r) / f
                    if p.suffix == '.py' and p.stem not in skip_stems:
                        py_files.append(p)

        total = ok_count = skip_count = 0
        total_saved = 0

        for py_file in py_files:
            total += 1

            # Pula se já está atualizado (a não ser que --force)
            if not force:
                cached = find_opt_py(Path(root), py_file)
                if cached:
                    skip_count += 1
                    click.echo(
                        f"   {Fore.BLUE}↷{Style.RESET_ALL} "
                        f"{py_file.relative_to(target) if py_file.is_relative_to(target) else py_file.name}"
                        f"  {Style.DIM}(cache){Style.RESET_ALL}"
                    )
                    continue

            result = generate_opt_py(Path(root), py_file)
            if result:
                ok_count += 1
                orig_size = py_file.stat().st_size
                opt_size  = result.stat().st_size
                saved     = max(0, orig_size - opt_size)
                total_saved += saved

                rel = py_file.relative_to(target) if py_file.is_relative_to(target) else py_file.name

                if stats and saved > 0:
                    click.echo(
                        f"   {Fore.GREEN}✔{Style.RESET_ALL} {rel}"
                        f"  {Fore.CYAN}{saved:>6} bytes{Style.RESET_ALL}"
                    )
                else:
                    click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} {rel}")
            else:
                click.echo(
                    f"   {Fore.YELLOW}↷{Style.RESET_ALL} "
                    f"{py_file.relative_to(target) if py_file.is_relative_to(target) else py_file.name}"
                    f"  {Style.DIM}(sem ganho){Style.RESET_ALL}"
                )

        # Resumo
        d = opt_dir(Path(root))
        opt_count = len(list(d.glob("opt_*.py")))

        click.echo(f"\n{Fore.CYAN}{'─' * 55}{Style.RESET_ALL}")
        click.echo(
            f"  {Fore.GREEN}✔ {ok_count} gerado(s){Style.RESET_ALL}  "
            f"{Fore.BLUE}↷ {skip_count} cache(s){Style.RESET_ALL}  "
            f"{Fore.CYAN}Total opt_py: {opt_count}{Style.RESET_ALL}"
        )
        if total_saved > 0:
            click.echo(
                f"  {Fore.GREEN}⚡ {total_saved:,} bytes economizados "
                f"({total_saved / 1024:.1f} KiB){Style.RESET_ALL}"
            )
        click.echo(
            f"\n{Fore.CYAN}[INFO] Tier 2 ativo. Quando binário falhar, "
            f"o Python otimizado será usado automaticamente.{Style.RESET_ALL}"
        )
        click.echo(f"{Fore.CYAN}{'─' * 55}{Style.RESET_ALL}")

    except Exception as e:
        from doxoade.commands.vulcan_cmd import _print_vulcan_forensic
        _print_vulcan_forensic("OPT", e)
        sys.exit(1)

@vulcan_group.command('opt-bench')
@click.argument('target', default='.')
@click.option('--rounds',  '-r', default=3,   show_default=True,
              help='Repetições de benchmark por callable.')
@click.option('--calls',   '-c', default=100, show_default=True,
              help='Chamadas por round (melhor de N rounds).')
@click.option('--verbose', '-v', is_flag=True,
              help='Detalha cada callable individualmente.')
@click.option('--csv',     '-o', default=None, metavar='ARQUIVO',
              help='Exporta resultado em CSV.')
@click.pass_context
def opt_bench(ctx, target, rounds, calls, verbose, csv):
    """
    Benchmark Tier 3 (Python Puro) vs Tier 2 (Python Otimizado).

    Mede ganho real de carregamento e execução de callables após
    aplicar as transformações do LibOptimizer.

    Exemplos::

    \b
      doxoade vulcan opt-bench doxoade/commands/check_systems/
      doxoade vulcan opt-bench mymodule.py --rounds 5 --calls 500
      doxoade vulcan opt-bench . --verbose --csv resultado.csv
    """
    import os
    from ..tools.vulcan.opt_benchmark import run_opt_bench, render_results

    project_root = Path(os.getcwd()).resolve()
    target_path  = (project_root / target).resolve()

    if not target_path.exists():
        click.echo(f"\033[31m ■ Alvo não encontrado: {target_path}\033[0m")
        ctx.exit(1)
        return

    print(f"\n  \033[36m⬡\033[0m Alvo   : {target_path}")
    print(f"  \033[36m⬡\033[0m Raiz   : {project_root}")
    print(f"  \033[36m⬡\033[0m Rounds : {rounds} × {calls} chamadas por callable")
    print()

    try:
        results = run_opt_bench(
            target_path,
            project_root,
            rounds=rounds,
            calls=calls,
        )
    except Exception as exc:
        click.echo(f"\033[31m ■ Erro ao executar benchmark: {exc}\033[0m")
        ctx.exit(1)
        return

    if not results:
        click.echo(
            "\033[33m ⚠ Nenhum arquivo .py encontrado no alvo.\033[0m\n"
            "   Dica: use 'doxoade vulcan opt <alvo>' para gerar Tier 2 primeiro."
        )
        return

    csv_path = Path(csv).resolve() if csv else None

    render_results(
        results,
        verbose=verbose,
        show_funcs=True,
        csv_out=csv_path,
    )


# ============================================================================
#  Patch para vulcan_status — exibe também opt_py
# ============================================================================
# SUBSTITUIR o comando vulcan_status existente por este:

@vulcan_group.command('status')
def vulcan_status():
    """Lista módulos otimizados e camadas ativas (binário + opt_py)."""
    root        = _find_project_root(os.getcwd())
    bin_dir     = os.path.join(root, ".doxoade", "vulcan", "bin")
    lib_bin_dir = os.path.join(root, ".doxoade", "vulcan", "lib_bin")
    opt_py_dir  = os.path.join(root, ".doxoade", "vulcan", "opt_py")

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ESTADO DA FOUNDRY VULCAN:{Style.RESET_ALL}")

    # Tier 1: Binários compilados
    for label, directory in [("Projeto (Tier 1)", bin_dir), ("Libs (Tier 1)", lib_bin_dir)]:
        if not os.path.exists(directory):
            continue
        binaries = [f for f in os.listdir(directory) if f.endswith(('.pyd', '.so'))]
        if binaries:
            click.echo(f"\n  {Fore.YELLOW}[{label}]{Style.RESET_ALL}")
            for b in binaries:
                size = os.path.getsize(os.path.join(directory, b)) / 1024
                click.echo(
                    f"   {Fore.GREEN}{b:<40} "
                    f"{Fore.WHITE}| {size:>6.1f} KB {Fore.YELLOW}[ATIVO]{Style.RESET_ALL}"
                )

    # Tier 2: Python Otimizado
    if os.path.exists(opt_py_dir):
        opt_files = [f for f in os.listdir(opt_py_dir) if f.endswith('.py')]
        if opt_files:
            click.echo(f"\n  {Fore.MAGENTA}[Python Otimizado (Tier 2)]{Style.RESET_ALL}")
            for f in opt_files:
                size = os.path.getsize(os.path.join(opt_py_dir, f)) / 1024
                click.echo(
                    f"   {Fore.MAGENTA}{f:<40} "
                    f"{Fore.WHITE}| {size:>6.1f} KB {Fore.CYAN}[OPT]{Style.RESET_ALL}"
                )

    # Verificação global
    all_bins = []
    for d in [bin_dir, lib_bin_dir]:
        if os.path.exists(d):
            all_bins += [f for f in os.listdir(d) if f.endswith(('.pyd', '.so'))]

    all_opts = []
    if os.path.exists(opt_py_dir):
        all_opts = [f for f in os.listdir(opt_py_dir) if f.endswith('.py')]

    if not all_bins and not all_opts:
        click.echo(
            f"   {Fore.YELLOW}Nenhum módulo ativo. "
            f"Execute 'doxoade vulcan ignite' ou 'doxoade vulcan opt'.{Style.RESET_ALL}"
        )
    else:
        click.echo(f"\n  {Fore.CYAN}Resumo:{Style.RESET_ALL}")
        click.echo(
            f"   {Fore.GREEN}Tier 1 (Binários) : {len(all_bins)} módulo(s){Style.RESET_ALL}"
        )
        click.echo(
            f"   {Fore.MAGENTA}Tier 2 (Opt Python): {len(all_opts)} módulo(s){Style.RESET_ALL}"
        )
        click.echo(
            f"   {Fore.WHITE}Tier 3 (Python Puro): sempre disponível{Style.RESET_ALL}"
        )


@vulcan_group.command('purge')
def vulcan_purge():
    """Remove todos os bin?rios e c?digos tempor?rios da forja."""
    root = _find_project_root(os.getcwd())
    from ..tools.vulcan.environment import VulcanEnvironment
    env = VulcanEnvironment(root)

    if click.confirm(f"{Fore.RED}Deseja realmente limpar a foundry Vulcano?{Fore.RESET}"):
        env.purge_unstable()
        click.echo(f"{Fore.GREEN}Foundry purificada.{Fore.RESET}")


def _copy_runtime_module(*_, **__):
    raise RuntimeError(
        "_copy_runtime_module foi removida. "
        "Use _write_safe_runtime(project_root)."
    )


def _write_safe_runtime(project_root: Path) -> Path:
    project_root = Path(project_root).resolve()
    vulcan_dir   = project_root / ".doxoade" / "vulcan"
    vulcan_dir.mkdir(parents=True, exist_ok=True)

    (project_root / ".doxoade" / "__init__.py").write_text(
        "# doxoade vulcan marker\n", encoding="utf-8"
    )
    (vulcan_dir / "__init__.py").write_text(
        "# doxoade vulcan marker\n", encoding="utf-8"
    )

    vulcan_src = Path(__file__).resolve().parents[1] / "tools" / "vulcan"

    # Implanta os 3 módulos necessários para operação autônoma
    for fname in ("runtime.py", "opt_cache.py", "lib_optimizer.py"):
        src_file = vulcan_src / fname
        if src_file.exists():
            (vulcan_dir / fname).write_text(
                src_file.read_text(encoding="utf-8"), encoding="utf-8"
            )

    (vulcan_dir / "vulcan_embedded.py").write_text(
        _VULCAN_EMBEDDED_CONTENT.lstrip(), encoding="utf-8"
    )

    return vulcan_dir / "runtime.py"


def _iter_project_main_files(project_root: Path):
    skip = {".git", "venv", ".venv", "__pycache__", "build", "dist", ".pytest_cache"}
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip]
        if "__main__.py" in files:
            yield Path(root) / "__main__.py"


def _inject_bootstrap(main_file: Path) -> bool:
    original = main_file.read_text(encoding="utf-8", errors="replace")

    content = original
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


@vulcan_group.command('module')
@click.option('--path', 'target_path', default='.', type=click.Path(exists=True, file_okay=False, dir_okay=True), show_default=True,
              help='Projeto alvo que receberá o módulo de acionamento Vulcan.')
@click.option('--main', 'main_files', multiple=True, type=click.Path(exists=True, dir_okay=False),
              help='Arquivo __main__.py específico para injetar bootstrap (pode repetir).')
@click.option('--auto-main', is_flag=True, help='Detecta e injeta em todos os __main__.py do projeto alvo.')
@click.option('--force-stub', is_flag=True, help="Recria o stub Vulcan mesmo se já existir.")
def vulcan_module(target_path, main_files, auto_main, force_stub):
    """Instala módulo de acionamento Vulcan em projetos externos."""
    project_root = Path(target_path).resolve()

    stub_path = project_root / ".doxoade" / "vulcan_embedded.py"

    current_version = read_stub_version(stub_path)

    should_write = (
        force_stub
        or current_version is None
        or current_version != VULCAN_STUB_VERSION
    )

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

    # ── GUARDA DE AUTO-APLICAÇÃO ──────────────────────────────────────────────
    # O doxoade já possui MetaFinder nativo (meta_finder.py) e VulcanBinaryFinder
    # (runtime.py). Injetar o bootstrap seria redundante e causaria conflito de
    # finders duplicados no sys.meta_path durante a execução.
    if _is_doxoade_project(project_root):
        click.echo(
            f"\n{Fore.RED}[ERRO] vulcan module não pode ser aplicado ao próprio projeto doxoade.{Style.RESET_ALL}"
        )
        click.echo(
            f"{Fore.YELLOW}[INFO] O doxoade já possui MetaFinder nativo em "
            f"doxoade/tools/vulcan/meta_finder.py — o redirecionamento PYD "
            f"é ativado automaticamente pelo runtime interno.{Style.RESET_ALL}"
        )
        click.echo(
            f"{Fore.CYAN}[DICA] Para compilar módulos do doxoade, use: "
            f"doxoade vulcan ignite{Style.RESET_ALL}"
        )
        return
        
    click.echo(
        f"{Fore.GREEN}[OK]{Style.RESET_ALL} "
        f"Stub Vulcan embutido criado em {stub_path}"
    )
    
    # ─────────────────────────────────────────────────────────────────────────

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
            f"\n{Fore.CYAN}[INFO] Bootstrap v2 instala MetaFinder automaticamente — "
            f"todos os imports do projeto serão redirecionados para PYD quando disponível.{Style.RESET_ALL}"
        )
    elif main_files or auto_main:
        click.echo(f"{Fore.YELLOW}[INFO]{Fore.RESET} Nenhum __main__.py precisou de alteração.")
    else:
        click.echo(
            f"{Fore.CYAN}[DICA]{Fore.RESET} Use --auto-main para injetar automaticamente nos __main__.py do projeto, "
            "ou --main <arquivo> para alvo específico."
        )
        
        
@vulcan_group.command('probe')
@click.option('--path', 'target_path', default='.', type=click.Path(exists=True, file_okay=False, dir_okay=True),
              show_default=True, help='Projeto alvo a inspecionar.')
@click.option('--verbose', '-v', is_flag=True, help='Mostra detalhes de hash e paths.')
def vulcan_probe(target_path, verbose):
    """Verifica quais módulos estão ativos e seriam redirecionados para PYD.

    Para cada binário em .doxoade/vulcan/bin/, resolve o .py de origem e
    reporta o status: ATIVO, STALE (PYD desatualizado) ou ÓRFÃO (sem .py).
    """
    import hashlib

    project_root = Path(target_path).resolve()
    bin_dir = project_root / ".doxoade" / "vulcan" / "bin"

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  VULCAN PROBE — {project_root.name}{Style.RESET_ALL}")

    if not bin_dir.exists():
        click.echo(f"  {Fore.RED}Nenhuma foundry encontrada em {bin_dir}{Fore.RESET}")
        return

    ext = ".pyd" if os.name == "nt" else ".so"
    binaries = sorted(bin_dir.glob(f"*{ext}"))

    if not binaries:
        click.echo(f"  {Fore.YELLOW}Nenhum binário ativo.{Fore.RESET}")
        return

    # Índice: stem_hash → [py_path] para busca reversa
    # Varre a árvore do projeto para mapear todos os .py existentes
    skip = {".git", "venv", ".venv", "__pycache__", "build", "dist", ".doxoade"}
    py_files: list[Path] = []
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith(".py"):
                py_files.append(Path(root) / f)

    # Monta índice hash(abs_path)[:6] → py_path
    hash_index: dict[str, Path] = {}
    for py in py_files:
        h = hashlib.sha256(str(py.resolve()).encode()).hexdigest()[:6]
        hash_index[h] = py

    # Tabela de status
    active, stale, orphan = [], [], []

    for bin_path in binaries:
        stem = bin_path.stem  # ex: v_cli_a7a05c.cp312-win_amd64
        # Extrai o hash: último segmento antes do primeiro ponto extra
        # Formato: v_{name}_{hash6}.cpXXX-...
        base = stem.split(".")[0]          # v_cli_a7a05c
        parts = base.split("_")
        pyd_hash = parts[-1] if len(parts) >= 3 else None
        pyd_stem = "_".join(parts[1:-1]) if pyd_hash else "_".join(parts[1:])

        source = hash_index.get(pyd_hash) if pyd_hash else None

        # Fallback: procura por stem exato se hash não bater
        if not source:
            for py in py_files:
                if py.stem == pyd_stem:
                    source = py
                    break

        if not source:
            orphan.append((bin_path, pyd_stem, pyd_hash))
            continue

        try:
            py_mtime = source.stat().st_mtime
            pyd_mtime = bin_path.stat().st_mtime
            is_stale = py_mtime > pyd_mtime
        except OSError:
            is_stale = True

        rel_src = source.relative_to(project_root)
        if is_stale:
            stale.append((bin_path, rel_src, source))
        else:
            active.append((bin_path, rel_src, source))

    # ── Relatório ─────────────────────────────────────────────────────────────
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
        click.echo(f"\n  {Fore.YELLOW}{Style.BRIGHT}⚠ STALE — .py mais recente que o PYD ({len(stale)}):{Style.RESET_ALL}")
        for bin_path, rel_src, source in stale:
            click.echo(
                f"    {Fore.YELLOW}⚠{Fore.RESET} {str(rel_src):<45} "
                f"{Fore.YELLOW}[recompile: doxoade vulcan ignite]{Fore.RESET}"
            )
            if verbose:
                import time as _time
                py_t = _time.strftime('%Y-%m-%d %H:%M:%S', _time.localtime(source.stat().st_mtime))
                pyd_t = _time.strftime('%Y-%m-%d %H:%M:%S', _time.localtime(bin_path.stat().st_mtime))
                click.echo(f"       .py  modificado: {py_t}")
                click.echo(f"       .pyd compilado:  {pyd_t}")

    if orphan:
        click.echo(f"\n  {Fore.RED}{Style.BRIGHT}✘ ÓRFÃOS — .py de origem não encontrado ({len(orphan)}):{Style.RESET_ALL}")
        for bin_path, pyd_stem, pyd_hash in orphan:
            click.echo(
                f"    {Fore.RED}✘{Fore.RESET} {bin_path.name}"
                + (f"  {Fore.YELLOW}(hash buscado: {pyd_hash}){Fore.RESET}" if pyd_hash else "")
            )

    # ── Resumo ────────────────────────────────────────────────────────────────
    total = len(binaries)
    click.echo(f"\n  {Fore.CYAN}{'─' * 55}{Fore.RESET}")
    click.echo(
        f"  Total: {total}  │  "
        f"{Fore.GREEN}Ativos: {len(active)}{Fore.RESET}  │  "
        f"{Fore.YELLOW}Stale: {len(stale)}{Fore.RESET}  │  "
        f"{Fore.RED}Órfãos: {len(orphan)}{Fore.RESET}"
    )

    if len(active) == total:
        click.echo(f"\n  {Fore.GREEN}{Style.BRIGHT}✅ 100% dos módulos estão sendo redirecionados para PYD.{Style.RESET_ALL}")
    elif len(active) > 0:
        pct = (len(active) / total) * 100
        click.echo(f"\n  {Fore.YELLOW}⚡ {pct:.0f}% dos módulos ativos. Use 'doxoade vulcan ignite' para recompilar os stale.{Fore.RESET}")
    else:
        click.echo(f"\n  {Fore.RED}Nenhum módulo ativo. Execute 'doxoade vulcan ignite' no projeto alvo.{Fore.RESET}")

    click.echo()

@vulcan_group.command('verify')
@click.argument('target_path', default='.', type=click.Path(exists=True))
@click.option('--verbose', '-v', is_flag=True)
def vulcan_verify(target_path, verbose):
    """Verifica se o redirecionamento PYD está funcional em projeto externo.

    Testa em subprocess isolado se o MetaFinder intercepta corretamente
    os imports e redireciona para os binários compilados.
    """
    import subprocess
    import json
    import hashlib

    project_root = Path(target_path).resolve()
    bin_dir      = project_root / ".doxoade" / "vulcan" / "bin"
    runtime_py   = project_root / ".doxoade" / "vulcan" / "runtime.py"

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ⬡ VULCAN VERIFY — {project_root.name}{Style.RESET_ALL}")

    # ── Pré-checks estruturais ────────────────────────────────────────────────
    checks = {
        "runtime.py presente":        runtime_py.exists(),
        "bin/ presente":               bin_dir.exists(),
        "vulcan_embedded.py presente": (project_root / ".doxoade" / "vulcan" / "vulcan_embedded.py").exists(),
    }

    # Bootstrap injetado em algum __main__.py?
    main_files = list(project_root.rglob("__main__.py"))
    bootstrap_found = any(
        _BOOTSTRAP_START in p.read_text(encoding="utf-8", errors="ignore")
        for p in main_files
        if ".doxoade" not in str(p)
    )
    checks["bootstrap em __main__.py"] = bootstrap_found

    ext = ".pyd" if os.name == "nt" else ".so"
    binaries = list(bin_dir.glob(f"*{ext}")) if bin_dir.exists() else []
    checks[f"binários {ext} presentes"] = bool(binaries)

    all_ok = True
    for label, ok in checks.items():
        icon  = f"{Fore.GREEN}✔" if ok else f"{Fore.RED}✘"
        all_ok = all_ok and ok
        click.echo(f"   {icon}{Style.RESET_ALL} {label}")

    if not all_ok:
        click.echo(
            f"\n{Fore.YELLOW}  ⚠ Pré-checks falharam. "
            f"Execute 'doxoade vulcan module --path {target_path} --auto-main' primeiro.{Style.RESET_ALL}"
        )
        return

    # ── Teste de redirecionamento em subprocess isolado ───────────────────────
    click.echo(f"\n{Fore.CYAN}  ⬡ Testando redirecionamento em subprocess isolado...{Style.RESET_ALL}")

    # Monta mapa stem → hash esperado para cada binário
    skip = {".git", "venv", ".venv", "__pycache__", "build", "dist", ".doxoade"}
    py_index: dict[str, Path] = {}
    for r, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith(".py"):
                p = Path(r) / f
                h = hashlib.sha256(str(p.resolve()).encode()).hexdigest()[:6]
                py_index[h] = p

    results = []
    for bin_path in binaries[:10]:  # limita a 10 para não demorar
        base  = bin_path.stem.split(".")[0]   # v_cli_a7a05c
        parts = base.split("_")
        phash = parts[-1] if len(parts) >= 3 else None
        src   = py_index.get(phash)

        if not src:
            results.append({"bin": bin_path.name, "status": "ÓRFÃO", "src": None})
            continue

        # Calcula modname no processo pai (evita problema de \ no Windows)
        try:
            modname = str(
                src.with_suffix("").relative_to(project_root)
            ).replace(os.sep, ".")
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
    # Redirecionado se: arquivo está no bin/ OU loader é VulcanLoader
    redirected = (
        '.doxoade' in file.replace('\\\\\\\\', '/')
        or loader_name == 'VulcanLoader'
    )
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
            output = proc.stdout.strip().splitlines()
            for line in output:
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

    # ── Relatório ─────────────────────────────────────────────────────────────
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
        click.echo(f"\n  {Fore.RED}{Style.BRIGHT}✘ ÓRFÃOS ({len(orphans)}):{Style.RESET_ALL}")
        for r in orphans:
            click.echo(f"   {Fore.RED}✘{Style.RESET_ALL} {r['bin']}")

    total = len(results)
    pct   = (len(redirected) / total * 100) if total else 0
    click.echo(f"\n  {Fore.CYAN}Total testado: {total}  │  "
               f"{Fore.GREEN}Redirecionados: {len(redirected)} ({pct:.0f}%){Fore.RESET}  │  "
               f"{Fore.YELLOW}Falhos: {len(not_redir)}{Fore.RESET}  │  "
               f"{Fore.RED}Órfãos: {len(orphans)}{Style.RESET_ALL}")

    if pct == 100:
        click.echo(f"\n  {Fore.GREEN}{Style.BRIGHT}✅ Redirecionamento 100% funcional.{Style.RESET_ALL}")
    elif pct > 0:
        click.echo(f"\n  {Fore.YELLOW}⚡ Redirecionamento parcial. "
                   f"Verifique se o bootstrap está no __main__.py e rode 'vulcan ignite'.{Style.RESET_ALL}")
    else:
        click.echo(f"\n  {Fore.RED}✘ Nenhum redirecionamento ativo. "
                   f"Execute 'doxoade vulcan module --path {target_path} --auto-main'.{Style.RESET_ALL}")
    click.echo()
    

def _print_vulcan_forensic(scope: str, e: Exception):
    """Interface Forense para falhas de metalurgia (MPoT-5.3)."""
    import sys as exc_sys, os as exc_os
    _, exc_obj, exc_tb = exc_sys.exc_info()
    f_name = exc_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else "vulcan_cmd.py"
    line_n = exc_tb.tb_lineno if exc_tb else 0

    click.echo(f"\n\033[1;34m\n[ ■ FORENSIC:VULCAN:{scope} ]\033[0m \033[1m\n ■ File: {f_name} | L: {line_n}\033[0m")
    exc_value = '\n  >>>   '.join(str(exc_obj).split("'"))
    click.echo(f"\033[31m\n ■ Tipo: {type(e).__name__} \n ■ Exception value: {exc_value} \n ■ Valor: {e}\n\033[0m")
