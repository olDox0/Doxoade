# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd.py

import textwrap
import sys
import signal
import os
import subprocess
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

_doxo_activate_vulcan = None
_doxo_install_meta_finder = None
_doxo_probe_embedded = None
_doxo_project_root = None

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
    try:
        _doxo_install_meta_finder(_doxo_project_root)
    except Exception:
        # não falha a execução do bootstrap — metas podem já estar instalados
        pass

# 2. Tenta usar o loader "embedded" (safe wrapper com safe_call + checagem de assinatura)
try:
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

# 3. Fallback: runtime.activate_vulcan (mantém compatibilidade retroativa)
# Chamamos em try/except para não interromper o fluxo caso o runtime injete de forma insegura.
if callable(_doxo_activate_vulcan):
    try:
        _doxo_activate_vulcan(globals(), __file__)
    except Exception:
        # não propaga erro — se falhar, o projeto seguirá com implementações Python originais
        pass

# 4. Diagnóstico opcional (útil para startup lento em servidores externos)
if callable(_doxo_probe_embedded):
    try:
        __doxoade_vulcan_probe__ = _doxo_probe_embedded(_doxo_project_root)
        if _doxo_sys.environ.get("VULCAN_DIAG", "").strip() == "1":
            _doxo_sys.stderr.write(
                "[VULCAN:DIAG] "
                + "finder_count=" + str(__doxoade_vulcan_probe__.get("finder_count", 0)) + " "
                + "bin=" + str(__doxoade_vulcan_probe__.get("bin_count", 0)) + " "
                + "lib_bin=" + str(__doxoade_vulcan_probe__.get("lib_bin_count", 0)) + "\\n"
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
        from ..tools.vulcan.hybrid_forge import hybrid_ignite, hybrid_scan_file

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
@click.option('--analyze', '--analyse', 'analyze', is_flag=True, help="Lista dependências 'quentes' candidatas à compilação.")
@click.option('--target', help="Compila uma biblioteca específica de requirements.txt.")
@click.option('--auto', is_flag=True, help="Compila automaticamente os melhores candidatos da análise.")
@click.option('--integrity', is_flag=True, help="Executa análise de integridade dos binários de libs compiladas.")
@click.option('--benchmark', is_flag=True, help="Executa benchmark de import da biblioteca alvo (Python x Vulcan lib_bin).")
@click.option('--benchmark-runs', default=8, type=int, show_default=True, help="Número de execuções para benchmark de import.")
@click.option('--run-tests/--no-run-tests', default=False, help="Executa smoke tests do Vulcan após a compilação para validar.")
@click.pass_context
def vulcan_lib(ctx, analyze, target, auto, integrity, benchmark, benchmark_runs, run_tests):
    """Compila dependências de terceiros para performance nativa."""
    root = _find_project_root(os.getcwd())
    
    with ExecutionLogger('vulcan_lib', root, ctx.params) as logger:
        
        # --- Fase 1: Análise e Identificação ---
        if analyze:
            click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [VULCAN LIB] Analisando Telemetria de Dependências ---{Style.RESET_ALL}")
            from ..tools.vulcan.advisor import VulcanAdvisor
            advisor = VulcanAdvisor(root)
            
            # Precisamos de um novo método no Advisor para isso
            hot_deps = advisor.get_hot_dependencies()
            
            if not hot_deps:
                click.echo(Fore.YELLOW + "Nenhuma dependência 'quente' encontrada na telemetria recente.")
                return

            click.echo(f"{'BIBLIOTECA':<25} | {'PONTOS DE CALOR (HITS)'}")
            click.echo("-" * 50)
            for dep, hits in hot_deps.items():
                click.echo(f"{Fore.WHITE}{dep:<25}{Style.RESET_ALL} | {Fore.RED}{hits}{Style.RESET_ALL}")
            return

        if target:
            click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [VULCAN LIB] Forjando: {target} ---{Style.RESET_ALL}")
            from ..tools.vulcan.lib_forge import LibForge
            
            forge = LibForge(root)
            success, result_message = forge.compile_library(target)
            
            if success:
                click.echo(f"{Fore.GREEN}{Style.BRIGHT}\n[SUCESSO] {result_message}{Style.RESET_ALL}")
                if run_tests:
                    click.echo(f"{Fore.CYAN}   > Validando estabilidade com smoke tests do Vulcan...{Style.RESET_ALL}")
                    test_cmd = [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        "commands_test/test_vulcan_lib_forge.py",
                        "commands_test/test_vulcan_compiler_errors.py",
                    ]
                    try:
                        proc = subprocess.run(test_cmd, cwd=str(root), check=False)
                        if proc.returncode == 0:
                            click.echo(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Smoke tests do Vulcan passaram após compilação da lib.")
                        else:
                            click.echo(
                                f"{Fore.YELLOW}[AVISO]{Style.RESET_ALL} Smoke tests do Vulcan falharam "
                                f"(exit={proc.returncode}). Recomendado rollback da lib em .doxoade/vulcan/lib_bin/."
                            )
                    except FileNotFoundError:
                        click.echo(
                            f"{Fore.YELLOW}[AVISO]{Style.RESET_ALL} pytest não está disponível no ambiente; "
                            "validação de testes foi ignorada."
                        )
            else:
                click.echo(f"{Fore.RED}{Style.BRIGHT}\n[FALHA] {result_message}{Style.RESET_ALL}")

            if success and integrity:
                report = forge.integrity_report(target)
                status = f"{Fore.GREEN}[OK]{Style.RESET_ALL}" if report.get("ok") else f"{Fore.YELLOW}[AVISO]{Style.RESET_ALL}"
                click.echo(f"{status} Integridade lib '{target}': {len(report.get('entries', []))} binários, "
                           f"missing={report.get('missing_files', 0)}, invalid_host={report.get('invalid_host', 0)}")

            if success and benchmark:
                bench = forge.benchmark_library(target, runs=benchmark_runs)
                if bench.get("ok"):
                    click.echo(
                        f"{Fore.CYAN}[BENCH]{Style.RESET_ALL} {bench['library']} | "
                        f"python={bench['mean_import_seconds_python']:.6f}s "
                        f"vulcan={bench['mean_import_seconds_vulcan']:.6f}s "
                        f"speedup={bench['speedup']:.2f}x redirected={bench.get('redirected_modules', 0)}"
                    )
                else:
                    details = bench.get("details") or {}
                    detail_msg = details.get("vulcan_error") or details.get("python_baseline_error")
                    if detail_msg:
                        click.echo(
                            f"{Fore.YELLOW}[AVISO]{Style.RESET_ALL} Benchmark não executado: "
                            f"{bench.get('error', 'erro desconhecido')} | detalhe: {detail_msg}"
                        )
                    else:
                        click.echo(f"{Fore.YELLOW}[AVISO]{Style.RESET_ALL} Benchmark não executado: {bench.get('error', 'erro desconhecido')}")

            return

        if integrity:
            from ..tools.vulcan.lib_forge import LibForge

            forge = LibForge(root)
            report = forge.integrity_report(None)
            if not report.get("entries"):
                click.echo(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Nenhum binário de lib compilada encontrado em .doxoade/vulcan/lib_bin")
                return
            status = f"{Fore.GREEN}[OK]{Style.RESET_ALL}" if report.get("ok") else f"{Fore.YELLOW}[AVISO]{Style.RESET_ALL}"
            click.echo(f"{status} Integridade geral: libs={report.get('libraries_checked', 0)} "
                       f"binários={len(report.get('entries', []))} missing={report.get('missing_files', 0)} "
                       f"invalid_host={report.get('invalid_host', 0)}")
            return

        if benchmark:
            from ..tools.vulcan.lib_forge import LibForge

            forge = LibForge(root)
            manifest = forge._load_manifest()
            libs = sorted((manifest.get("libraries") or {}).keys())
            if not libs:
                click.echo(
                    f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Nenhuma lib registrada em manifest para benchmark. "
                    "Compile com --target <lib> antes."
                )
                return

            click.echo(f"{Fore.CYAN}[BENCH]{Style.RESET_ALL} Rodando benchmark para {len(libs)} lib(s) do manifest...")
            for lib in libs:
                bench = forge.benchmark_library(lib, runs=benchmark_runs)
                if bench.get("ok"):
                    click.echo(
                        f"  - {bench['library']}: python={bench['mean_import_seconds_python']:.6f}s "
                        f"vulcan={bench['mean_import_seconds_vulcan']:.6f}s speedup={bench['speedup']:.2f}x "
                        f"redirected={bench.get('redirected_modules', 0)}"
                    )
                else:
                    details = bench.get("details") or {}
                    detail_msg = details.get("vulcan_error") or details.get("python_baseline_error") or bench.get("error")
                    click.echo(f"  - {lib}: {Fore.YELLOW}[AVISO]{Style.RESET_ALL} benchmark falhou ({detail_msg})")
            return

        elif auto:
            click.echo(f"{Fore.YELLOW}Funcionalidade '--auto' em desenvolvimento.{Style.RESET_ALL}")
            
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


@vulcan_group.command('status')
def vulcan_status():
    """Lista módulos otimizados e ganhos de performance."""
    root = _find_project_root(os.getcwd())
    bin_dir     = os.path.join(root, ".doxoade", "vulcan", "bin")
    lib_bin_dir = os.path.join(root, ".doxoade", "vulcan", "lib_bin")  # ← adicionar

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ESTADO DA FOUNDRY VULCAN:{Style.RESET_ALL}")

    for label, directory in [("Projeto", bin_dir), ("Libs", lib_bin_dir)]:
        if not os.path.exists(directory):
            continue
        binaries = [f for f in os.listdir(directory) if f.endswith(('.pyd', '.so'))]
        if binaries:
            click.echo(f"\n  {Fore.YELLOW}[{label}]{Style.RESET_ALL}")
            for b in binaries:
                size = os.path.getsize(os.path.join(directory, b)) / 1024
                click.echo(f"   {Fore.GREEN}{b:<40} {Fore.WHITE}| {size:>6.1f} KB {Fore.YELLOW}[ATIVO]")

    # fallback se nenhum binário encontrado em nenhuma pasta
    all_bins = []
    for d in [bin_dir, lib_bin_dir]:
        if os.path.exists(d):
            all_bins += [f for f in os.listdir(d) if f.endswith(('.pyd', '.so'))]
    if not all_bins:
        click.echo("   Nenhum binário ativo encontrado.")


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
    """
    Escreve no projeto alvo:
      - .doxoade/__init__.py
      - .doxoade/vulcan/__init__.py
      - .doxoade/vulcan/runtime.py   (SafeExtensionLoader + VulcanBinaryFinder + install_meta_finder + probe_embedded)
      - .doxoade/vulcan/vulcan_embedded.py (safe loader)
    Retorna o path do runtime (runtime_dst).
    """
    project_root = Path(project_root).resolve()
    vulcan_dir = project_root / ".doxoade" / "vulcan"
    vulcan_dir.mkdir(parents=True, exist_ok=True)

    # Ensure package markers for importability
    (project_root / ".doxoade" / "__init__.py").write_text("# marker package for doxoade\n", encoding="utf-8")
    (vulcan_dir / "__init__.py").write_text("# marker package for doxoade.vulcan\n", encoding="utf-8")

    runtime_src = Path(__file__).resolve().parents[1] / "tools" / "vulcan" / "runtime.py"
    runtime_content = runtime_src.read_text(encoding="utf-8")

    runtime_dst = vulcan_dir / "runtime.py"
    runtime_dst.write_text(runtime_content, encoding="utf-8")

    (vulcan_dir / "vulcan_embedded.py").write_text(_VULCAN_EMBEDDED_CONTENT.lstrip(), encoding="utf-8")


    return runtime_dst


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


def _print_vulcan_forensic(scope: str, e: Exception):
    """Interface Forense para falhas de metalurgia (MPoT-5.3)."""
    import sys as exc_sys, os as exc_os
    _, exc_obj, exc_tb = exc_sys.exc_info()
    f_name = exc_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else "vulcan_cmd.py"
    line_n = exc_tb.tb_lineno if exc_tb else 0

    click.echo(f"\n\033[1;34m\n[ ■ FORENSIC:VULCAN:{scope} ]\033[0m \033[1m\n ■ File: {f_name} | L: {line_n}\033[0m")
    exc_value = '\n  >>>   '.join(str(exc_obj).split("'"))
    click.echo(f"\033[31m\n ■ Tipo: {type(e).__name__} \n ■ Exception value: {exc_value} \n ■ Valor: {e}\n\033[0m")
