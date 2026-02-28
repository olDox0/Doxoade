# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/pitstop.py
"""
Vulcan PitStop Engine — v1.0 Warm-Up Streaming Compiler
=========================================================

Pipeline de compilação em 3 fases sobrepostas:
  Phase 1  [Forge Stream]   : .py → .pyx em ThreadPool (puro AST, zero subprocess)
  Phase 2  [Batch Compile]  : N .pyx → N binários em UMA única chamada setup.py
  Phase 3  [Promote Stream] : move binários para bin/ com resultado incremental

Ganhos em relação ao sistema anterior (1 subprocess por módulo):
  • N inícios de Python → 1          (maior ganho: ~2-5 s por módulo no Windows)
  • Cython transpila N arquivos com nthreads em paralelo
  • GCC recebe todos os .c de uma vez (reutiliza cache de objeto, -j automático)
  • WarmupCache (SHA-256 de conteúdo) elimina reforjas de arquivos inalterados
  • Forge e compilação se sobrepõem via fila produtor-consumidor

Variáveis de ambiente:
  DOXOADE_PITSTOP_BATCH     tamanho do lote (padrão: 8)
  DOXOADE_PITSTOP_NTHREADS  threads de forge (padrão: auto)
"""

from __future__ import annotations

import hashlib, json, os, shutil, subprocess, sys, threading, time

from concurrent.futures import ThreadPoolExecutor as TPE, as_completed
from pathlib import Path
from queue import Empty, Queue
from typing import Callable

from .artifact_manager import ensure_dirs
from .environment import VulcanEnvironment as VulEnv
from .forge import VulcanForge as VForge, assess_file_for_vulcan as AFVul

# ------------ Constantes ------------

_BATCH_SIZE: int = int(os.environ.get("DOXOADE_PITSTOP_BATCH", "8"))
_BATCH_TIMEOUT: int = 360           # segundos por lote
_QUEUE_SENTINEL = object()          # token de encerramento de fila


# ------------ WarmupCache ------------

class WarmupCache:
    """
    Cache persistente baseado em SHA-256 do conteúdo do arquivo.

    Diferença em relação ao mtime check do VulcanAdvisor:
      • Mtime muda ao tocar arquivo mesmo sem alteração real → recompila
      • Hash de conteúdo é imutável enquanto código não muda → pula
    """

    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        self._data: dict[str, dict] = self._load()
        self._lock = threading.Lock()

    # --------- Persistência ---------
    def _load(self) -> dict:
        try:
            if self._path.exists():
                return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception e: print(f"\033[31m ■ Erro: {e}"); traceback.print_tb(e.__traceback__)
        return {}

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                self._path.write_text(
                    json.dumps(self._data, indent=2), encoding="utf-8"
                )
        except Exception e: print(f"\033[31m ■ Erro: {e}"); traceback.print_tb(e.__traceback__)

    # --------- Verificação ---------
    def _content_hash(self, path: Path) -> str | None:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()[:20]
        except OSError: return None

    def is_stale(self, py_path: str, bin_dir: Path) -> bool:
        """True  → arquivo mudou ou binário ausente → precisa recompilar."""
        abs_path = Path(py_path).resolve()
        content_hash = self._content_hash(abs_path)
        if content_hash is None: return True

        entry = self._data.get(str(abs_path), {})
        if entry.get("hash") != content_hash: return True

        # Binário ainda deve existir em disco
        path_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
        ext = ".pyd" if os.name == "nt" else ".so"
        return not (bin_dir / f"v_{abs_path.stem}_{path_hash}{ext}").exists()

    def mark_compiled(self, py_path: str) -> None:
        abs_path = Path(py_path).resolve()
        content_hash = self._content_hash(abs_path)
        if content_hash is None: return
        with self._lock:
            self._data[str(abs_path)] = {
                "hash": content_hash,
                "compiled_at": time.time(),
            }

    def invalidate(self, py_path: str) -> None:
        with self._lock:
            self._data.pop(str(Path(py_path).resolve()), None)

    def stats(self) -> dict:
        return {"entries": len(self._data), "path": str(self._path)}


# --------- Phase 1 — Forge worker  (puro Python/AST, sem subprocess) ---------

def _forge_to_pyx(task: dict) -> dict:
    """
    Transforma um arquivo .py em .pyx usando VForge.

    Roda dentro de uma thread do TPE — sem custo de startup
    de subprocesso. É a operação mais leve do pipeline.
    """
    file_path = Path(task["file_path"])
    foundry = Path(task["foundry"])
    abs_path = file_path.resolve()

    path_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
    module_name = f"v_{abs_path.stem}_{path_hash}"
    pyx_path = foundry / f"{module_name}.pyx"

    try:
        # Verifica elegibilidade antes de gastar CPU no AST
        eligible, reason = AFVul(str(abs_path))
        if not eligible:
            return {
                "ok": False, "skip": True,
                "file": str(file_path), "module_name": module_name,
                "err": f"pulado: {reason}",
            }

        forge = VForge(str(abs_path))
        pyx_code = forge.generate_source(str(abs_path))
        if not pyx_code:
            return {
                "ok": True, "file": str(file_path),
                "module_name": module_name, "err": "pyx_code vazio",
            }

        pyx_path.write_text(pyx_code, encoding="utf-8")
        return {
            "ok": True,
            "file": str(file_path),
            "module_name": module_name,
            "pyx_path": str(pyx_path),
        }
    except Exception as exc:
        return {
            "ok": False, "file": str(file_path),
            "module_name": module_name, "err": str(exc)[:160],
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 2 — Batch compiler  (N módulos → 1 subprocess)
# ─────────────────────────────────────────────────────────────────────────────
def _batch_setup_content(entries: list[dict], extra_args: list[str], nthreads: int) -> str:
    """
    Gera um setup.py temporário que compila N extensões em paralelo.

    nthreads controla paralelismo interno do Cython (transpilação .pyx → .c).
    GCC compila cada .c de forma independente; setuptools usa -j automaticamente
    nas versões modernas, e MAKEFLAGS pode forçar valor.
    """
    ext_lines = []
    for entry in entries:
        name = entry["module_name"]
        ext_lines.append(
            f'    Extension("{name}", ["{name}.pyx"], '
            f"extra_compile_args={extra_args!r}, include_dirs=_incdirs),"
        )
    exts_block = "\n".join(ext_lines)

    return (
        "# -*- coding: utf-8 -*- — GERADO PELO PITSTOP ENGINE\n"
        "from setuptools import setup, Extension\n"
        "from Cython.Build import cythonize\n"
        "try:\n"
        "    import numpy as np; _incdirs = [np.get_include()]\n"
        "except ImportError:\n"
        "    _incdirs = []\n"
        f"_exts = [\n{exts_block}\n]\n"
        "setup(\n"
        "    ext_modules=cythonize(\n"
        "        _exts,\n"
        f"        nthreads={nthreads},\n"
        "        language_level=3,\n"
        "        quiet=True,\n"
        "    )\n"
        ")\n"
    )


def _tail(text: str, n: int = 12) -> str:
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    return "\n".join(lines[-n:]) if lines else "(vazio)"


def _extract_real_error(stderr: str, stdout: str, module_name: str) -> str:
    """
    Extrai erro real de GCC/Cython do stderr, descartando ruído de setuptools.

    Problemas conhecidos descartados:
      - "return fut.result(timeout)" — internal setuptools/concurrent.futures
      - "Traceback (most recent call last)" sem relevância ao módulo
      - Linhas vazias / só espaço
    """
    NOISE_PATTERNS = (
        "return fut.result(",
        "concurrent.futures",
        "Future.result",
        "_base.py",
        "raise exception",
        "if self._exception",
    )

    lines = (stderr or "").splitlines() + (stdout or "").splitlines()

    # 1. Linhas que mencionam módulo diretamente
    module_lines = [
        ln for ln in lines
        if module_name in ln and ln.strip() and not any(p in ln for p in NOISE_PATTERNS)
    ]

    # 2. Linhas de erro GCC/Cython genuínas (error:, warning:, fatal error:)
    error_lines = [
        ln for ln in lines
        if any(kw in ln for kw in ("error:", "fatal error:", "undefined", "cannot find"))
        and not any(p in ln for p in NOISE_PATTERNS)
        and ln.strip()
    ]

    # Prioriza erros específicos do módulo, depois erros genéricos, depois tail do stderr
    best = module_lines[:6] or error_lines[:6] or []
    if best:
        return "\n".join(best)

    # Último recurso: tail do stderr sem as linhas de ruído
    clean = [ln for ln in lines if ln.strip() and not any(p in ln for p in NOISE_PATTERNS)]
    return "\n".join(clean[-8:]) if clean else "(sem saída de erro)"


def _compile_single(
    name: str,
    foundry_str: str,
    bin_dir_str: str,
    build_env: dict,
    python_exe: str,
    worker_id: int = 0,
) -> tuple[str, bool, str | None]:
    """
    Compila UM único módulo em subprocesso isolado.

    Cada worker recebe um ``worker_id`` único → diretório ``build_w{id}/``
    separado dentro da foundry, evitando colisão de artefatos intermediários
    quando vários ProcessPoolExecutor workers rodam em paralelo no Windows.

    Retorna: (module_name, ok, error_msg)
    Assinatura plana (sem Path/objetos custom) para ser picklável no Windows.
    """
    import os as _os
    import shutil as _shutil
    import subprocess as _subprocess
    from pathlib import Path as _Path

    foundry_path = _Path(foundry_str)
    bin_dir = _Path(bin_dir_str)
    ext = ".pyd" if _os.name == "nt" else ".so"
    extra_args = ["-O2"] if _os.name == "nt" else ["-O3", "-ffast-math"]

    # Diretório de build isolado por worker — evita colisão em paralelo
    build_tmp = foundry_path / f"_build_w{worker_id}"
    build_tmp.mkdir(parents=True, exist_ok=True)

    setup_name = f"_solo_{name}_w{worker_id}_setup.py"
    setup_path = foundry_path / setup_name
    setup_content = (
        "from setuptools import setup, Extension\n"
        "from Cython.Build import cythonize\n"
        "try:\n"
        "    import numpy as np; _incdirs = [np.get_include()]\n"
        "except ImportError:\n"
        "    _incdirs = []\n"
        f'ext = Extension("{name}", ["{name}.pyx"], '
        f"extra_compile_args={extra_args!r}, include_dirs=_incdirs)\n"
        "setup(ext_modules=cythonize(ext, language_level=3, quiet=True))\n"
    )
    setup_path.write_text(setup_content, encoding="utf-8")

    cmd = [
        python_exe, setup_name, "build_ext", "--inplace",
        "--build-temp", str(build_tmp),
    ]
    if _os.name == "nt":
        cmd.append("--compiler=mingw32")

    try:
        proc = _subprocess.run(
            cmd, cwd=str(foundry_path), env=build_env,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180,
        )
        if proc.returncode == 0:
            bin_file = next(foundry_path.glob(f"{name}*{ext}"), None)
            if bin_file:
                dst = bin_dir / bin_file.name
                _shutil.move(str(bin_file), str(dst))
                return name, True, None
            return name, False, f"exit=0 mas binário ausente: {name}"
        else:
            return name, False, _extract_real_error(proc.stderr, proc.stdout, name)
    except _subprocess.TimeoutExpired: return name, False, "Timeout (>180s)"
    except Exception as exc: return name, False, f"Exceção: {exc}"
    finally:
        try:
            setup_path.unlink(missing_ok=True)
        except Exception as e: print(f"\033[31m ■ Erro: {e}"); traceback.print_tb(e.__traceback__)
        try:
            _shutil.rmtree(str(build_tmp), ignore_errors=True)
        except Exception e: print(f"\033[31m ■ Erro: {e}"); traceback.print_tb(e.__traceback__)


def _parallel_compile(
    entries: list[dict],
    foundry_path: Path,
    bin_dir: Path,
    build_env: dict,
    python_exe: str,
    n_workers: int,
    label: str = "paralelo",
) -> dict[str, tuple[bool, str | None]]:
    """
    Compila N módulos em paralelo usando ProcessPoolExecutor.

    Cada worker é um processo Python independente → múltiplos GCC simultâneos.
    Usa diretórios de build isolados por worker_id para evitar conflito no Windows.
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed as _as_completed

    results: dict[str, tuple[bool, str | None]] = {}
    foundry_str = str(foundry_path)
    bin_dir_str = str(bin_dir)

    print(
        f"      \033[33m⚡ [{label}] {len(entries)} módulo(s) × {n_workers} processo(s) GCC...\033[0m"
    )

    # Atribui worker_id único a cada entry (round-robin sobre n_workers)
    tasks = [
        (e["module_name"], foundry_str, bin_dir_str, build_env, python_exe, i % n_workers)
        for i, e in enumerate(entries)
    ]

    try:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = {
                pool.submit(_compile_single, *task): task[0]
                for task in tasks
            }
            for future in _as_completed(futures):
                try:
                    mod_name, ok, err = future.result(timeout=200)
                except Exception as exc:
                    mod_name = futures[future]
                    ok, err = False, f"Worker crash: {exc}"
                results[mod_name] = (ok, err)
                mark = "\033[32m✔\033[0m" if ok else "\033[31m✘\033[0m"
                print(f"      {mark} {mod_name}")
    except KeyboardInterrupt:
        raise
    return results

def compile_batch(entries: list[dict],    foundry_path: Path,
                  bin_dir: Path,          build_env: dict,
                  python_exe: str,        max_gcc_jobs: int = 0,
                  ) -> dict[str, tuple[bool, str | None]]:
    """
    Estratégia adaptativa de compilação:

    • Windows / mingw32 : pula batch (sempre falha com múltiplas extensões)
      → vai direto ao ProcessPoolExecutor paralelo.
    • Linux / macOS     : tenta batch primeiro; se exit != 0, resgata binários
      já gerados, usa ProcessPoolExecutor para os restantes.

    Retorna: { module_name → (ok, error_msg) }
    """
    if not entries: return {}

    n_workers = max(1, max_gcc_jobs) if max_gcc_jobs > 0 else max(1, os.cpu_count() or 2)
    ext = ".pyd" if os.name == "nt" else ".so"

    # ── Windows: pula batch, vai direto ao paralelo ───────────────────────────
    # mingw32 falha consistentemente com múltiplas extensões no mesmo setup.py
    # (colisão de artefatos intermediários + bug de lock no linker).
    if os.name == "nt":
        return _parallel_compile(
            entries, foundry_path, bin_dir, build_env, python_exe, n_workers,
            label="PITSTOP:PARALLEL"
        )

    # ── Linux/macOS: tenta batch único primeiro ───────────────────────────────
    extra_args = ["-O3", "-ffast-math"]
    nthreads = max(1, min(len(entries), os.cpu_count() or 2))

    setup_path = foundry_path / "_pitstop_batch_setup.py"
    setup_path.write_text(
        _batch_setup_content(entries, extra_args, nthreads), encoding="utf-8"
    )
    cmd = [python_exe, setup_path.name, "build_ext", "--inplace"]
    env = build_env.copy()
    if n_workers > 0:
        env["MAKEFLAGS"] = f"-j{n_workers}"

    results: dict[str, tuple[bool, str | None]] = {}
    batch_exit = 1

    try:
        proc = subprocess.run(
            cmd, cwd=str(foundry_path), env=env,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=_BATCH_TIMEOUT,
        )
        batch_exit = proc.returncode
    except subprocess.TimeoutExpired:
        for entry in entries:
            results[entry["module_name"]] = (False, "Timeout no lote de compilação")
        return results
    except Exception as exc:
        for entry in entries:
            results[entry["module_name"]] = (False, f"Exceção no batch: {exc}")
        return results
    finally:
        try:
            setup_path.unlink(missing_ok=True)
        except Exception e: print(f"\033[31m ■ Erro: {e}"); traceback.print_tb(e.__traceback__)

    # Resgata binários já gerados mesmo com exit != 0
    rescued: set[str] = set()
    for entry in entries:
        name = entry["module_name"]
        bin_file = next(foundry_path.glob(f"{name}*{ext}"), None)
        if bin_file:
            try:
                shutil.move(str(bin_file), str(bin_dir / bin_file.name))
                results[name] = (True, None)
                rescued.add(name)
            except Exception as e:
                results[name] = (False, f"Move: {e}")

    if batch_exit == 0:
        for entry in entries:
            if entry["module_name"] not in results:
                results[entry["module_name"]] = (False, "Binário não encontrado")
        return results

    # Fallback paralelo para os não resgatados
    needs_retry = [e for e in entries if e["module_name"] not in rescued]
    if needs_retry:
        parallel_res = _parallel_compile(
            needs_retry, foundry_path, bin_dir, build_env, python_exe, n_workers,
            label=f"fallback batch exit={batch_exit}"
        )
        results.update(parallel_res)

    return results


def _parse_batch_errors(
    stderr: str, stdout: str, entries: list[dict]
) -> dict[str, tuple[bool, str | None]]:
    """Mantido por compatibilidade (usado apenas em código externo legado)."""
    results: dict[str, tuple[bool, str | None]] = {}
    stderr_lines = stderr.splitlines()
    for entry in entries:
        name = entry["module_name"]
        relevant = [ln for ln in stderr_lines if name in ln]
        if relevant:
            results[name] = (False, "\n".join(relevant[-6:]))
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  PitStop Engine  —  orquestra pipeline completo
# ─────────────────────────────────────────────────────────────────────────────
class PitstopEngine:
    """
    Motor de compilação pré-aquecida com streaming em 3 fases.

    Uso:

        engine = PitstopEngine(vulcan_env)
        stats  = engine.run(candidates, on_result=lambda f, ok, err: print(f, ok))
        print(stats)

    callback ``on_result`` é chamado assim que cada módulo é processado,
    permitindo exibição incremental de progresso (streaming).
    """

    def __init__(
        self,
        env: VulEnv,
        pid_registry: dict | None = None,
    ) -> None:
        self.env = env
        self.root = env.root
        self._pid_registry: dict = pid_registry or {}

        # Cache de conteúdo persistente
        cache_path = self.root / ".doxoade" / "vulcan" / "pitstop_cache.json"
        self.cache = WarmupCache(cache_path)

        # Ambiente GCC pré-aquecido (equivalente ao VulcanCompiler._prepare_pitstop_env)
        self._build_env: dict = self._prepare_build_env()
        self._python_exe: str = self._resolve_python()

    # ── Configuração ──────────────────────────────────────────────────────────
    def _prepare_build_env(self) -> dict:
        core_root = Path(__file__).resolve().parents[3]
        gcc_exe = core_root / "opt" / "w64devkit" / "bin" / "gcc.exe"
        env = os.environ.copy()
        if gcc_exe.exists():
            bin_dir = str(gcc_exe.parent)
            env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
            env["CC"] = "gcc"
            env["CXX"] = "g++"
            env["DISTUTILS_USE_SDK"] = "1"
            env["PY_VULCAN_PITSTOP"] = "1"
        return env

    def _resolve_python(self) -> str:
        core_root = Path(__file__).resolve().parents[3]
        candidate = (
            core_root / "venv" / "Scripts" / "python.exe"
            if os.name == "nt"
            else sys.executable
        )
        return str(candidate) if Path(candidate).exists() else sys.executable

    # ── Pipeline principal ────────────────────────────────────────────────────
    def run(
        self,
        candidates: list[dict],
        max_workers: int | None = None,
        force_recompile: bool = False,
        on_result: Callable[[str, bool, str | None], None] | None = None,
    ) -> dict:
        """
        Executa pipeline PitStop completo.

        Parâmetros:
            candidates      lista de dicts com chave 'file'
            max_workers     threads de forge (None = auto)
            force_recompile ignora WarmupCache
            on_result       callback(file_path, success, error_msg) por módulo
        """
        ensure_dirs(str(self.root))
        self.env.foundry.mkdir(parents=True, exist_ok=True)
        self.env.bin_dir.mkdir(parents=True, exist_ok=True)

        n_workers = self._resolve_workers(max_workers)
        stats: dict = {
            "total": len(candidates),
            "cached": 0,
            "stale": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "forge_time": 0.0,
            "compile_time": 0.0,
            "total_time": 0.0,
        }
        t_start = time.perf_counter()

        # ── 0. Filtragem por WarmupCache ──────────────────────────────────────
        if not force_recompile:
            stale, cached_count = self._filter_stale(candidates)
            stats["cached"] = cached_count
        else:
            stale = candidates
        stats["stale"] = len(stale)

        if not stale:
            stats["total_time"] = time.perf_counter() - t_start
            return stats

        # ── Phase 1: Forge Stream ─────────────────────────────────────────────
        # .py → .pyx em threads paralelas (sem subprocesso)
        t_forge = time.perf_counter()
        forge_out = self._phase_forge(stale, n_workers)
        stats["forge_time"] = round(time.perf_counter() - t_forge, 3)

        ready: list[dict] = []
        for r in forge_out:
            if r.get("skip"):
                stats["skipped"] += 1
                if on_result:
                    on_result(r["file"], False, r.get("err"))
            elif not r["ok"]:
                stats["failed"] += 1
                if on_result:
                    on_result(r["file"], False, r.get("err"))
            else:
                ready.append(r)

        if not ready:
            self.cache.save()
            stats["total_time"] = round(time.perf_counter() - t_start, 3)
            return stats

        # ── Phase 2: Batch Compile ────────────────────────────────────────────
        # N .pyx → N binários em UMA única chamada setup.py
        t_compile = time.perf_counter()
        compile_results = self._phase_batch_compile(ready, n_workers)
        stats["compile_time"] = round(time.perf_counter() - t_compile, 3)

        # ── Phase 3: Promote + Report ─────────────────────────────────────────
        for entry in ready:
            name = entry["module_name"]
            file_path = entry["file"]
            ok, err = compile_results.get(name, (False, "Resultado ausente"))
            if ok:
                stats["success"] += 1
                self.cache.mark_compiled(file_path)
                if on_result:
                    on_result(file_path, True, None)
            else:
                stats["failed"] += 1
                self.cache.invalidate(file_path)
                if on_result:
                    on_result(file_path, False, err)

        stats["total_time"] = round(time.perf_counter() - t_start, 3)
        self.cache.save()
        return stats

    # ── Streaming produtor-consumidor ─────────────────────────────────────────
    def run_streaming(
        self,
        candidates: list[dict],
        max_workers: int | None = None,
        force_recompile: bool = False,
        on_result: Callable[[str, bool, str | None], None] | None = None,
    ) -> dict:
        """
        Variante streaming: forge, compilação se sobrepõem via fila.

        Enquanto ThreadPool gera .pyx, compilador consome lotes assim
        que BATCH_SIZE itens estiverem prontos — sem esperar forge completo.
        Útil para lotes grandes (> 20 módulos) onde sobreposição compensa.
        """
        ensure_dirs(str(self.root))
        self.env.foundry.mkdir(parents=True, exist_ok=True)
        self.env.bin_dir.mkdir(parents=True, exist_ok=True)

        n_workers = self._resolve_workers(max_workers)

        if not force_recompile:
            stale, cached_count = self._filter_stale(candidates)
        else:
            stale, cached_count = candidates, 0

        stats: dict = {
            "total": len(candidates),
            "cached": cached_count,
            "stale": len(stale),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "forge_time": 0.0,
            "compile_time": 0.0,
            "total_time": 0.0,
        }

        if not stale:
            return stats

        t_start = time.perf_counter()
        forge_queue: Queue[dict | object] = Queue()
        compile_results_store: dict = {}
        compile_lock = threading.Lock()

        # Compilador consumidor: drena fila em lotes e compila
        def _compile_consumer() -> None:
            batch: list[dict] = []
            t_compile_acc = 0.0

            while True:
                try:
                    item = forge_queue.get(timeout=0.3)
                except Empty:
                    # Flush parcial se há itens esperando
                    if batch:
                        t0 = time.perf_counter()
                        res = compile_batch(
                            batch, self.env.foundry, self.env.bin_dir,
                            self._build_env, self._python_exe, n_workers,
                        )
                        t_compile_acc += time.perf_counter() - t0
                        with compile_lock:
                            compile_results_store.update(res)
                        batch = []
                    continue

                if item is _QUEUE_SENTINEL:
                    # Flush final
                    if batch:
                        t0 = time.perf_counter()
                        res = compile_batch(
                            batch, self.env.foundry, self.env.bin_dir,
                            self._build_env, self._python_exe, n_workers,
                        )
                        t_compile_acc += time.perf_counter() - t0
                        with compile_lock:
                            compile_results_store.update(res)
                    with compile_lock:
                        compile_results_store["__compile_time__"] = t_compile_acc
                    break

                batch.append(item)
                if len(batch) >= _BATCH_SIZE:
                    t0 = time.perf_counter()
                    res = compile_batch(
                        batch, self.env.foundry, self.env.bin_dir,
                        self._build_env, self._python_exe, n_workers,
                    )
                    t_compile_acc += time.perf_counter() - t0
                    with compile_lock:
                        compile_results_store.update(res)
                    batch = []

        compiler_thread = threading.Thread(target=_compile_consumer, daemon=True)
        compiler_thread.start()

        # Forge producer: gera .pyx em paralelo, enfileira para compilação
        t_forge = time.perf_counter()
        forge_tasks = [{"file_path": c["file"], "foundry": str(self.env.foundry)} for c in stale]

        with TPE(max_workers=n_workers) as executor:
            futures = {executor.submit(_forge_to_pyx, task): task for task in forge_tasks}
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as exc:
                    task = futures[future]
                    result = {
                        "ok": False, "file": task["file_path"],
                        "module_name": "", "err": str(exc),
                    }

                if result.get("skip") or not result["ok"]:
                    key = "skipped" if result.get("skip") else "failed"
                    stats[key] += 1
                    if on_result:
                        on_result(result["file"], False, result.get("err"))
                else:
                    forge_queue.put(result)

        stats["forge_time"] = round(time.perf_counter() - t_forge, 3)

        # Sinaliza fim ao compilador e aguarda
        forge_queue.put(_QUEUE_SENTINEL)
        compiler_thread.join(timeout=_BATCH_TIMEOUT + 30)

        # Coleta resultados e reporta
        stats["compile_time"] = round(
            compile_results_store.pop("__compile_time__", 0.0), 3
        )

        for c in stale:
            file_path = c["file"]
            abs_path = str(Path(file_path).resolve())
            path_hash = hashlib.sha256(abs_path.encode()).hexdigest()[:6]
            stem = Path(file_path).stem
            module_name = f"v_{stem}_{path_hash}"

            ok, err = compile_results_store.get(module_name, (False, None))
            if ok:
                stats["success"] += 1
                self.cache.mark_compiled(file_path)
                if on_result:
                    on_result(file_path, True, None)
            elif module_name not in compile_results_store:
                pass  # Provavelmente caiu no skip/failed da forge phase
            else:
                stats["failed"] += 1
                self.cache.invalidate(file_path)
                if on_result:
                    on_result(file_path, False, err)

        stats["total_time"] = round(time.perf_counter() - t_start, 3)
        self.cache.save()
        return stats

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _filter_stale(self, candidates: list[dict]) -> tuple[list[dict], int]:
        stale, cached = [], 0
        for c in candidates:
            if self.cache.is_stale(c["file"], self.env.bin_dir):
                stale.append(c)
            else:
                cached += 1
        if cached:
            print(
                f"   \033[36m↷ PitStop cache quente: "
                f"{cached} módulo(s) sem mudança → ignorado(s)\033[0m"
            )
        return stale, cached

    def _phase_forge(self, candidates: list[dict], n_workers: int) -> list[dict]:
        """Phase 1: gera todos os .pyx em paralelo (puro AST, sem subprocess)."""
        results: list[dict] = []
        tasks = [{"file_path": c["file"], "foundry": str(self.env.foundry)} for c in candidates]

        with TPE(max_workers=n_workers) as executor:
            futures = {executor.submit(_forge_to_pyx, t): t for t in tasks}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as exc:
                    t = futures[future]
                    results.append({
                        "ok": False, "file": t["file_path"],
                        "module_name": "", "err": str(exc),
                    })
        return results

    def _phase_batch_compile(
        self, ready: list[dict], n_workers: int
    ) -> dict[str, tuple[bool, str | None]]:
        """
        Phase 2: compila em lotes.

        No Windows vai direto ao ProcessPoolExecutor paralelo (via compile_batch).
        No Linux/macOS tenta batch único primeiro, paralelo como fallback.
        feedback por módulo é impresso inline por _parallel_compile — não
        repetimos aqui para evitar saída duplicada.
        """
        all_results: dict[str, tuple[bool, str | None]] = {}
        total_batches = (len(ready) + _BATCH_SIZE - 1) // _BATCH_SIZE

        for i in range(0, len(ready), _BATCH_SIZE):
            batch = ready[i : i + _BATCH_SIZE]
            batch_num = i // _BATCH_SIZE + 1
            print(
                f"   \033[33m🔥 [PITSTOP] Lote {batch_num}/{total_batches} "
                f"({len(batch)} módulos × {n_workers} workers)...\033[0m"
            )
            res = compile_batch(
                entries=batch,
                foundry_path=self.env.foundry,
                bin_dir=self.env.bin_dir,
                build_env=self._build_env,
                python_exe=self._python_exe,
                max_gcc_jobs=n_workers,
            )
            all_results.update(res)

            # No Linux com batch success, _parallel_compile não roda →
            # imprimimos feedback aqui (sem duplicar no Windows).
            if os.name != "nt":
                for name, (ok, err) in res.items():
                    mark = "\033[32m✔\033[0m" if ok else "\033[31m✘\033[0m"
                    print(f"      {mark} {name}")

        return all_results

    @staticmethod
    def _resolve_workers(max_workers: int | None) -> int:
        """
        Resolve número de workers de compilação.

        Para compilação (spawn de GCC), mais workers = mais GCC simultâneos.
        Não há GIL contention — ProcessPoolExecutor escala bem até N cores.
        Default: todos os cores disponíveis (cap em 8 para não sobrecarregar I/O).
        """
        if isinstance(max_workers, int) and max_workers > 0:
            return max_workers
        env_val = os.environ.get("DOXOADE_PITSTOP_NTHREADS", "").strip()
        if env_val.isdigit() and int(env_val) > 0:
            return int(env_val)
        cpu = os.cpu_count() or 2
        # Usa todos os cores disponíveis (cap em 8 para evitar thrashing de I/O)
        return max(2, min(8, cpu))

    def warmup_info(self) -> dict:
        """Diagnóstico do estado do motor."""
        n = self._resolve_workers(None)
        return {
            "python_exe": self._python_exe,     "foundry": str(self.env.foundry),
            "bin_dir": str(self.env.bin_dir),   "batch_size": _BATCH_SIZE,
            "workers": n,
            "parallel_strategy": "ProcessPoolExecutor (Windows)" if os.name == "nt" else "batch+fallback (Linux/macOS)",
            "cache": self.cache.stats(),
            "build_env_keys": sorted(
                k for k in self._build_env if k not in os.environ
            ),
        }