# doxoade/doxoade/tools/vulcan/pitstop.py
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
import hashlib, json, os, shutil, subprocess, sys, threading, time, traceback, re
import concurrent.futures
from doxoade.tools.doxcolors import Fore, Style
from concurrent.futures import ThreadPoolExecutor as TPE, as_completed
from pathlib import Path
from queue import Empty, Queue
from typing import Callable
from .artifact_manager import ensure_dirs
from .environment import VulcanEnvironment as VulEnv
from .forge import VulcanForge as VForge, assess_file_for_vulcan as AFVul
_BATCH_SIZE: int = int(os.environ.get('DOXOADE_PITSTOP_BATCH', '8'))
_BATCH_TIMEOUT: int = 300
_QUEUE_SENTINEL = object()

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

    def _load(self) -> dict:
        try:
            if self._path.exists():
                return json.loads(self._path.read_text(encoding='utf-8'))
        except Exception as e:
            print(f'\x1b[31m ■ Erro: {e}')
            traceback.print_tb(e.__traceback__)
        return {}

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                self._path.write_text(json.dumps(self._data, indent=2), encoding='utf-8')
        except Exception as e:
            print(f'\x1b[31m ■ Erro: {e}')
            traceback.print_tb(e.__traceback__)

    def _content_hash(self, path: Path) -> str | None:
        """Hash de conteúdo ultra-rápido."""
        try:
            with open(path, 'rb', buffering=1024 * 1024) as f:
                return hashlib.sha256(f.read()).hexdigest()[:20]
        except OSError:
            return None

    def is_stale(self, py_path: str, bin_dir: Path) -> bool:
        """True  → arquivo mudou ou binário ausente → precisa recompilar."""
        abs_path = Path(py_path).resolve()
        content_hash = self._content_hash(abs_path)
        if content_hash is None:
            return True
        entry = self._data.get(str(abs_path), {})
        if entry.get('hash') != content_hash:
            return True
        path_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
        ext = '.pyd' if os.name == 'nt' else '.so'
        return not (bin_dir / f'v_{abs_path.stem}_{path_hash}{ext}').exists()

    def mark_compiled(self, py_path: str) -> None:
        abs_path = Path(py_path).resolve()
        content_hash = self._content_hash(abs_path)
        if content_hash is None:
            return
        with self._lock:
            self._data[str(abs_path)] = {'hash': content_hash, 'compiled_at': time.time()}

    def invalidate(self, py_path: str) -> None:
        with self._lock:
            self._data.pop(str(Path(py_path).resolve()), None)

    def stats(self) -> dict:
        return {'entries': len(self._data), 'path': str(self._path)}

def _forge_to_pyx(task: dict) -> dict:
    """
    Transforma um arquivo .py em .pyx (Tier 1) e opt_.py (Tier 2).
    Versão Forense: Captura falhas de tradução com rastro completo.
    """
    import traceback
    import hashlib
    import re
    import ast
    import time
    import sys
    from pathlib import Path
    from .forge import VulcanForge as VForge, assess_file_for_vulcan as AFVul
    
    t_start = time.perf_counter()
    file_path = Path(task['file_path'])
    foundry = Path(task['foundry'])
    abs_path = file_path.resolve()
    
    # Gerador de Assinatura Única (Doxoade Standard)
    path_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
    _safe_stem = re.sub('[^a-zA-Z0-9_]', '_', abs_path.stem)
    module_name = f'v_{_safe_stem}_{path_hash}'
    pyx_path = foundry / f'{module_name}.pyx'
    
    # 1. Check de Elegibilidade
    eligible, reason = AFVul(str(abs_path))
    if not eligible:
        return {'ok': False, 'skip': True, 'file': str(file_path), 'err': f'pulado: {reason}'}

    try:
        # 2. Análise de Carga AST
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read())
        node_count = sum(1 for _ in ast.walk(tree))
        
        # LOG LIVE: Informa o início do processamento deste arquivo específico
        sys.stdout.write(f"   [FORGE] {file_path.name:<25} | Densidade: {node_count:>4} nodes...")
        sys.stdout.flush()

        # 3. Forja do Código Nativo (Tier 1)
        forge = VForge(str(abs_path))
        pyx_code = forge.generate_source(str(abs_path))
        
        if not pyx_code:
             return {'ok': False, 'file': str(file_path), 'err': 'pyx_code vazio'}

        pyx_path.write_text(pyx_code, encoding='utf-8')
        
        # 4. Geração do Fallback (Tier 2) - Python Otimizado
        # Tenta localizar o root se não fornecido para o opt_cache
        project_root = task.get('project_root')
        if not project_root:
            cur = abs_path.parent
            while cur != cur.parent:
                if (cur / '.doxoade' / 'vulcan').exists():
                    project_root = cur; break
                cur = cur.parent

        if project_root:
            try:
                from doxoade.tools.vulcan.opt_cache import generate_opt_py
                generate_opt_py(Path(project_root), abs_path)
            except: pass

        duration_ms = (time.perf_counter() - t_start) * 1000
        
        # Completa a linha de log com o tempo
        sys.stdout.write(f" [{duration_ms:.1f}ms]\n")
        sys.stdout.flush()

        return {
            'ok': True, 
            'file': str(file_path), 
            'module_name': module_name, 
            'nodes': node_count,
            'forge_ms': duration_ms
        }

    except Exception as e:
        sys.stdout.write(f" [ERRO]\n")
        return {
            'ok': False, 
            'module_name': module_name,
            'err': str(e), 
            'traceback': traceback.format_exc(),
            'file': str(file_path)
        }

def _batch_setup_content(entries: list[dict], extra_args: list[str], nthreads: int) -> str:
    """
    Gera um setup.py temporário que compila N extensões em paralelo.

    nthreads controla paralelismo interno do Cython (transpilação .pyx → .c).
    GCC compila cada .c de forma independente; setuptools usa -j automaticamente
    nas versões modernas, e MAKEFLAGS pode forçar valor.
    """
    ext_lines = []
    for entry in entries:
        name = entry['module_name']
        ext_lines.append(f'    Extension("{name}", ["{name}.pyx"], extra_compile_args={extra_args!r}, include_dirs=_incdirs),')
    exts_block = '\n'.join(ext_lines)
    return f'# -*- coding: utf-8 -*- — GERADO PELO PITSTOP ENGINE\nfrom setuptools import setup, Extension\nfrom Cython.Build import cythonize\ntry:\n    import numpy as np; _incdirs = [np.get_include()]\nexcept ImportError:\n    _incdirs = []\n_exts = [\n{exts_block}\n]\nsetup(\n    ext_modules=cythonize(\n        _exts,\n        nthreads={nthreads},\n        language_level=3,\n        quiet=True,\n    )\n)\n'

def _tail(text: str, n: int=12) -> str:
    lines = [ln for ln in (text or '').splitlines() if ln.strip()]
    return '\n'.join(lines[-n:]) if lines else '(vazio)'

def _extract_real_error(stderr: str, stdout: str, module_name: str) -> str:
    """
    Extrai erro real de GCC/Cython do stderr, descartando ruído de setuptools.

    Problemas conhecidos descartados:
      - "return fut.result(timeout)" — internal setuptools/concurrent.futures
      - "Traceback (most recent call last)" sem relevância ao módulo
      - Linhas vazias / só espaço
    """
    NOISE_PATTERNS = ('return fut.result(', 'concurrent.futures', 'Future.result', '_base.py', 'raise exception', 'if self._exception')
    lines = (stderr or '').splitlines() + (stdout or '').splitlines()
    module_lines = [ln for ln in lines if module_name in ln and ln.strip() and (not any((p in ln for p in NOISE_PATTERNS)))]
    error_lines = [ln for ln in lines if any((kw in ln for kw in ('error:', 'fatal error:', 'undefined', 'cannot find'))) and (not any((p in ln for p in NOISE_PATTERNS))) and ln.strip()]
    best = module_lines[:6] or error_lines[:6] or []
    if best:
        return '\n'.join(best)
    clean = [ln for ln in lines if ln.strip() and (not any((p in ln for p in NOISE_PATTERNS)))]
    return '\n'.join(clean[-8:]) if clean else '(sem saída de erro)'

def _compile_single(name: str, foundry_str: str, bin_dir_str: str, build_env: dict, python_exe: str, worker_id: int=0) -> tuple[str, bool, str | None]:
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
    ext = '.pyd' if _os.name == 'nt' else '.so'
    extra_args = ['-O2'] if _os.name == 'nt' else ['-O3', '-ffast-math']
    import tempfile as _tf
    build_tmp = _Path(_tf.gettempdir()) / f'vk_{worker_id}'
    (build_tmp / 'Release').mkdir(parents=True, exist_ok=True)
    setup_name = f'_solo_{name}_w{worker_id}_setup.py'
    setup_path = foundry_path / setup_name
    setup_content = f'from setuptools import setup, Extension\nfrom Cython.Build import cythonize\ntry:\n    import numpy as np; _incdirs = [np.get_include()]\nexcept ImportError:\n    _incdirs = []\next = Extension("{name}", ["{name}.pyx"], extra_compile_args={extra_args!r}, include_dirs=_incdirs)\nsetup(ext_modules=cythonize(ext, language_level=3, quiet=True))\n'
    setup_path.write_text(setup_content, encoding='utf-8')
    cmd = [python_exe, setup_name, 'build_ext', '--inplace', '--build-temp', str(build_tmp)]
    if _os.name == 'nt':
        cmd.append('--compiler=mingw32')
    try:
        proc = _subprocess.run(cmd, cwd=str(foundry_path), env=build_env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
        if proc.returncode == 0:
            bin_file = next(foundry_path.glob(f'{name}*{ext}'), None)
            if bin_file:
                dst = bin_dir / bin_file.name
                _shutil.move(str(bin_file), str(dst))
                return (name, True, None)
            return (name, False, f'exit=0 mas binário ausente: {name}')
        else:
            return (name, False, _extract_real_error(proc.stderr, proc.stdout, name))
    except _subprocess.TimeoutExpired:
        return (name, False, 'Timeout (>180s)')
    except Exception as exc:
        return (name, False, f'Exceção: {exc}')
    finally:
        try:
            setup_path.unlink(missing_ok=True)
        except Exception as e:
            print(f'\x1b[31m ■ Erro: {e}')
            traceback.print_tb(e.__traceback__)
        try:
            _shutil.rmtree(str(build_tmp), ignore_errors=True)
        except Exception as e:
            print(f'\x1b[31m ■ Erro: {e}')
            traceback.print_tb(e.__traceback__)

def _parallel_compile(entries: list[dict], foundry_path: Path, bin_dir: Path, build_env: dict, python_exe: str, n_workers: int, label: str='paralelo') -> dict[str, tuple[bool, str | None]]:
    """
    Compila N módulos em paralelo usando ProcessPoolExecutor.

    Cada worker é um processo Python independente → múltiplos GCC simultâneos.
    Usa diretórios de build isolados por worker_id para evitar conflito no Windows.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
    #from concurrent.futures import ProcessPoolExecutor, as_completed as _as_completed
    results: dict[str, tuple[bool, str | None]] = {}
    foundry_str = str(foundry_path)
    bin_dir_str = str(bin_dir)
    print(f'      \x1b[33m⚡ [{label}] {len(entries)} módulo(s) × {n_workers} processo(s) GCC...\x1b[0m')
    tasks = [(e['module_name'], foundry_str, bin_dir_str, build_env, python_exe, i % n_workers) for i, e in enumerate(entries)]
    try:
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
#        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = {pool.submit(_compile_single, *task): task[0] for task in tasks}
            for future in _as_completed(futures):
                try:
                    mod_name, ok, err = future.result(timeout=200)
                except Exception as exc:
                    mod_name = futures[future]
                    ok, err = (False, f'Worker crash: {exc}')
                results[mod_name] = (ok, err)
                mark = '\x1b[32m✔\x1b[0m' if ok else '\x1b[31m✘\x1b[0m'
                print(f'      {mark} {mod_name}')
    except KeyboardInterrupt:
        raise
    return results

def compile_batch(entries: list[dict], foundry_path: Path, bin_dir: Path, build_env: dict, python_exe: str, max_gcc_jobs: int=0) -> dict[str, tuple[bool, str | None]]:
    """
    Estratégia adaptativa de compilação:

    • Windows / mingw32 : pula batch (sempre falha com múltiplas extensões)
      → vai direto ao ProcessPoolExecutor paralelo.
    • Linux / macOS     : tenta batch primeiro; se exit != 0, resgata binários
      já gerados, usa ProcessPoolExecutor para os restantes.

    Retorna: { module_name → (ok, error_msg) }
    """
    if not entries:
        return {}
    n_workers = max(1, max_gcc_jobs) if max_gcc_jobs > 0 else max(1, os.cpu_count() or 2)
    ext = '.pyd' if os.name == 'nt' else '.so'
    if os.name == 'nt':
        return _parallel_compile(entries, foundry_path, bin_dir, build_env, python_exe, n_workers, label='PITSTOP:PARALLEL')
    extra_args = ['-O3', '-ffast-math']
    nthreads = max(1, min(len(entries), os.cpu_count() or 2))
    setup_path = foundry_path / '_pitstop_batch_setup.py'
    setup_path.write_text(_batch_setup_content(entries, extra_args, nthreads), encoding='utf-8')
    cmd = [python_exe, setup_path.name, 'build_ext', '--inplace']
    env = build_env.copy()
    if n_workers > 0:
        env['MAKEFLAGS'] = f'-j{n_workers}'
    results: dict[str, tuple[bool, str | None]] = {}
    batch_exit = 1
    try:
        proc = subprocess.run(cmd, cwd=str(foundry_path), env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=_BATCH_TIMEOUT)
        batch_exit = proc.returncode
    except subprocess.TimeoutExpired:
        for entry in entries:
            results[entry['module_name']] = (False, 'Timeout no lote de compilação')
        return results
    except Exception as exc:
        for entry in entries:
            results[entry['module_name']] = (False, f'Exceção no batch: {exc}')
        return results
    finally:
        try:
            setup_path.unlink(missing_ok=True)
        except Exception as e:
            print(f'\x1b[31m ■ Erro: {e}')
            traceback.print_tb(e.__traceback__)
    rescued: set[str] = set()
    for entry in entries:
        name = entry['module_name']
        bin_file = next(foundry_path.glob(f'{name}*{ext}'), None)
        if bin_file:
            try:
                shutil.move(str(bin_file), str(bin_dir / bin_file.name))
                results[name] = (True, None)
                rescued.add(name)
            except Exception as e:
                results[name] = (False, f'Move: {e}')
    if batch_exit == 0:
        for entry in entries:
            if entry['module_name'] not in results:
                results[entry['module_name']] = (False, 'Binário não encontrado')
        return results
    needs_retry = [e for e in entries if e['module_name'] not in rescued]
    if needs_retry:
        parallel_res = _parallel_compile(needs_retry, foundry_path, bin_dir, build_env, python_exe, n_workers, label=f'fallback batch exit={batch_exit}')
        results.update(parallel_res)
    return results

def _parse_batch_errors(stderr: str, stdout: str, entries: list[dict]) -> dict[str, tuple[bool, str | None]]:
    """Mantido por compatibilidade (usado apenas em código externo legado)."""
    results: dict[str, tuple[bool, str | None]] = {}
    stderr_lines = stderr.splitlines()
    for entry in entries:
        name = entry['module_name']
        relevant = [ln for ln in stderr_lines if name in ln]
        if relevant:
            results[name] = (False, '\n'.join(relevant[-6:]))
    return results

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

    def __init__(self, env: VulEnv, pid_registry: dict | None=None) -> None:
        self.env = env
        self.root = env.root
        self._pid_registry: dict = pid_registry or {}
        cache_path = self.root / '.doxoade' / 'vulcan' / 'pitstop_cache.json'
        self.cache = WarmupCache(cache_path)
        self._build_env: dict = self._prepare_build_env()
        self._python_exe: str = self._resolve_python()

    def _load_cache(self):
        if self.cache_path.exists():
            try: return json.loads(self.cache_path.read_text(encoding='utf-8'))
            except: return {}
        return {}

    def save_cache(self):
        self.cache_file.write_text(json.dumps(self.cache, indent=2))

    def get_content_hash(self, path):
        """Hash ultra-rápido para detecção de mudança de código."""
        try:
            with open(path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except: return None

    def run_ignition(self, targets, compiler):
        import shutil
        import doxoade.tools.vulcan as vulcan_core
        
        # Localiza o nexus_math.c no coração do Doxoade
        core_dir = Path(vulcan_core.__file__).parent
        kernel_src = core_dir / 'nexus_math.c'
        kernel_dst = self.env.foundry / 'nexus_math.c'
        
        # [FORCE COPY]
        if kernel_src.exists():
            shutil.copy2(kernel_src, kernel_dst)
            print(f"   [LOGISTICS] Kernel {kernel_src.name} entregue à foundry.")
        else:
            # Fallback se o arquivo sumiu do HD
            kernel_dst.write_text("#include <stdint.h>\nint nexus_encode_varint_branchless(uint64_t n, uint8_t* out){...}")
        
        click_echo(f"{Fore.CYAN}[DIAG] Core Path: {core_dir}{Style.RESET_ALL}")
        print(f"\x1b[94m[*] [LOGISTICS] Provisionando kernel: {kernel_src.name}\x1b[0m")
        
        if kernel_src.exists():
            shutil.copy2(kernel_src, kernel_dst)
            click_echo(f"{Fore.GREEN}   ✔ Kernel provisionado em: {kernel_dst}{Style.RESET_ALL}")
        else:
            raise FileNotFoundError(f"Erro Crítico: Kernel não encontrado no Core: {kernel_src}")
            # Se falhar aqui, sabemos que o arquivo não está na pasta do Doxoade
#            click_echo(f"{Fore.RED}   ✘ FALHA CRÍTICA: Kernel não encontrado em {kernel_src}{Style.RESET_ALL}")
#            return False
        
        click_echo(f"{Fore.CYAN}🚀 [NEXUS WARP] Iniciando Forja Paralela (N2808 Optimized)...{Style.RESET_ALL}")
        
        stale_modules = []
        start_time = time.time()

        # FASE 1: Forge em Paralelo (Usa as 2 threads do Atom para processar AST)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_to_file = {executor.submit(self._forge_task, t): t for t in targets}
            
            for future in concurrent.futures.as_completed(future_to_file):
                f_path = future_to_file[future]
                res = future.result()
                
                if res['status'] == 'FORGED':
                    stale_modules.append(res['module_name'])
                    click_echo(f"   {Fore.YELLOW}• {Path(f_path).name} -> Pyx gerado.{Style.RESET_ALL}")
                elif res['status'] == 'ERROR':
                    click_echo(f"   {Fore.RED}✘ Falha no Forge: {Path(f_path).name} ({res['msg']}){Style.RESET_ALL}")

        # FASE 2: Compilação em Lote (Batch Ignition)
        if stale_modules:
            click_echo(f"\n{Fore.CYAN}🔨 [HAMMER] Compilando {len(stale_modules)} módulos em lote único...{Style.RESET_ALL}")
            if compiler.compile_batch(stale_modules):
                self.cache_path.write_text(json.dumps(self.cache, indent=2))
                duration = time.time() - start_time
                click_echo(f"{Fore.SUCCESS}✅ Warp concluído em {duration:.2f}s.{Style.RESET_ALL}")
                return True
        else:
            click_echo(f"{Fore.GREEN}✨ Todos os binários estão sincronizados (Cache Hit).{Style.RESET_ALL}")
            return True
        return False
        
    def _forge_task(self, file_path):
        from .forge import VulcanForge
        abs_path = os.path.abspath(file_path)
        c_hash = self.get_content_hash(abs_path)
        
        # Só forja se o hash mudou ou binário sumiu
        if self.cache.get(abs_path) == c_hash:
            # Verifica se o arquivo .pyd/.so correspondente ainda existe
            return {'status': 'CACHED'}

        try:
            forge = VulcanForge(abs_path)
            pyx_code = forge.generate_source(abs_path)
            
            # Salva o .pyx para o lote
            module_name = f"v_{Path(file_path).stem}_{c_hash[:6]}"
            from .environment import VulcanEnvironment
            env = VulcanEnvironment('.')
            (env.foundry / f"{module_name}.pyx").write_text(pyx_code, encoding='utf-8')
            
            self.cache[abs_path] = c_hash
            return {'status': 'FORGED', 'module_name': module_name}
        except Exception as e:
            return {'status': 'ERROR', 'msg': str(e)}

    def process_parallel(self, targets, compiler):
        """Fase 1: Forge Paralelo (Multi-threading)."""
        from .forge import VulcanForge
        
        click_echo = __import__('click').echo
        click_echo(f"{Fore.CYAN}🚀 [NEXUS WARP] Sincronizando Forja...{Style.RESET_ALL}")
        
        to_compile = []
        
        # Uso de ThreadPool para processar AST sem travar o I/O
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_to_file = {executor.submit(self._forge_task, t): t for t in targets}
            
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    res = future.result()
                    if res['status'] == 'STALE':
                        to_compile.append(res['module_name'])
                        click_echo(f"   {Fore.YELLOW}• {Path(file_path).name} -> Metal fundido.{Style.RESET_ALL}")
                    else:
                        click_echo(f"   {Fore.STABLE}• {Path(file_path).name} -> Mantido em Cache.{Style.RESET_ALL}")
                except Exception as e:
                    click_echo(f"   {Fore.RED}✘ Erro no Forge: {file_path} ({e}){Style.RESET_ALL}")
        
        # Fase 2: Batch Hammer (Compilação em Lote)
        if to_compile:
            click_echo(f"\n{Fore.CYAN}🔨 [BATCH HAMMER] Fundindo {len(to_compile)} módulos em lote único...{Style.RESET_ALL}")
            success = compiler.compile_batch(to_compile)
            if success:
                self.save_cache()
                return True
        return False

    def _forge_task(self, file_path):
        """Tarefa individual de thread."""
        from .forge import VulcanForge
        abs_path = os.path.abspath(file_path)
        current_hash = self.get_content_hash(abs_path)
        
        # Verifica se o binário já existe e o código é o mesmo
        if self.cache.get(abs_path) == current_hash:
            return {'status': 'CACHED', 'module_name': None}
        
        # Roda a forja
        forge = VulcanForge(abs_path)
        pyx_code = forge.generate_source(abs_path)
        
        # Salva o .pyx na foundry para o GCC
        module_name = f"v_{Path(file_path).stem}"
        from .environment import VulcanEnvironment
        env = VulcanEnvironment('.')
        (env.foundry / f"{module_name}.pyx").write_text(pyx_code, encoding='utf-8')
        
        self.cache[abs_path] = current_hash
        return {'status': 'STALE', 'module_name': module_name}

    def run_warp_drive(self, targets):
        click_echo = __import__('click').echo
        click_echo(f"{Fore.CYAN}🚀 [NEXUS WARP] Iniciando Forja Paralela...{Style.RESET_ALL}")
        
        # 1. Forge em Paralelo (Usa as 2 threads do N2808 para processar AST)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._forge_task, t) for t in targets]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                # Feedback incremental
        
        # 2. Compilação em Bloco
        # Reduz o tempo de boot do GCC de N vezes para 1 vez.

    def _prepare_build_env(self):
        """Warm-up do ambiente de compilação."""
        from .compiler import VulcanCompiler
        compiler = VulcanCompiler(self.env)
        compiler._ensure_pch()
        return compiler._prepare_pitstop_env()

    def _resolve_python(self) -> str:
        core_root = Path(__file__).resolve().parents[3]
        candidate = core_root / 'venv' / 'Scripts' / 'python.exe' if os.name == 'nt' else sys.executable
        return str(candidate) if Path(candidate).exists() else sys.executable

    def run(self, candidates: list[dict], max_workers: int | None=None, force_recompile: bool=False, on_result: Callable[[str, bool, str | None], None] | None=None) -> dict:
        """
        Executa pipeline PitStop completo com telemetria multidimensional.
        """
        ensure_dirs(str(self.root))
        self.env.foundry.mkdir(parents=True, exist_ok=True)
        self.env.bin_dir.mkdir(parents=True, exist_ok=True)
        n_workers = self._resolve_workers(max_workers)
        
        # [MUDANÇA CRÍTICA 1] Instanciamos o compilador aqui para ele ser o dono da telemetria
        from .compiler import VulcanCompiler
        compiler = VulcanCompiler(self.env, pid_registry=self._pid_registry)
        
        stats: dict = {'total': len(candidates), 'cached': 0, 'stale': 0, 'success': 0, 'failed': 0, 'skipped': 0, 'forge_time': 0.0, 'compile_time': 0.0, 'total_time': 0.0}
        t_start = time.perf_counter()
        
        if not force_recompile:
            stale, cached_count = self._filter_stale(candidates)
            stats['cached'] = cached_count
        else:
            stale = candidates
            
        stats['stale'] = len(stale)
        if not stale:
            stats['total_time'] = time.perf_counter() - t_start
            return stats

        # --- FASE 1: FORGE (AST) ---
        t_forge = time.perf_counter()
        forge_out = self._phase_forge(stale, n_workers)
        stats['forge_time'] = round(time.perf_counter() - t_forge, 3)
        
        ready: list[dict] = []
        for r in forge_out:
            if r.get('skip'):
                stats['skipped'] += 1
                if on_result:
                    on_result(r['file'], False, r.get('err'))
            elif not r['ok']:
                stats['failed'] += 1
                fname = r.get('name', 'desconhecido')
                erro = r.get('err', 'Erro não especificado')
                print(f"   {Fore.RED}✘ Falha no Forge [{fname}]: {erro}{Fore.RESET}")
                if 'traceback' in r:
                    print(f"{Style.DIM}{r['traceback']}{Style.RESET_ALL}")
            else:
                ready.append(r)

        if not ready:
            self.cache.save()
            stats['total_time'] = round(time.perf_counter() - t_start, 3)
            return stats

        # --- FASE 2: BATCH COMPILE (Linkagem) ---
        t_compile = time.perf_counter()
        # [MUDANÇA CRÍTICA 2] Passamos o objeto 'compiler' para a função
        compile_results = self._phase_batch_compile(ready, n_workers, compiler)
        stats['compile_time'] = round(time.perf_counter() - t_compile, 3)

        # --- MAPA DA DOR VULCAN V4 (Industrial) ---
        print(f"\n{Fore.CYAN}{Style.BRIGHT}🌡️  MAPA DE CALOR: CUSTO DE FUNDIÇÃO (N2808){Style.RESET_ALL}")
        header = f"{'MÓDULO':<25} │ {'NODES':>6} │ {'TRANS':>8} │ {'LINK':>8} │ {'VELOCIDADE'}"
        print(header)
        print("─" * 70)

        # Ordenamos pela "dor" total (TRANS + LINK)
        sorted_ready = sorted(ready, key=lambda x: (
            compiler.detailed_telemetry.get(x['module_name'], {}).get('transpile_ms', 0) +
            compiler.detailed_telemetry.get(x['module_name'], {}).get('link_ms', 0)
        ), reverse=True)

        for entry in sorted_ready:
            name = entry['module_name']
            file_ptr = entry.get('file', 'desconhecido') 
            m = compiler.detailed_telemetry.get(name, {})
            
            nodes = entry.get('nodes', 0)
            f_ms = entry.get('forge_ms', 0)
            t_ms = m.get('transpile_ms', 0)
            l_ms = m.get('link_ms', 0) # Se falhou, será 0 ou o tempo até a falha
            
            total_s = (f_ms + t_ms + l_ms) / 1000
            v_fundicao = (nodes / total_s) if total_s > 0 else 0

            # Exibição do Mapa de Calor
            color = Fore.WHITE
            if total_s > 30: color = Fore.RED + Style.BRIGHT
            elif total_s > 10: color = Fore.YELLOW
            v_color = Fore.GREEN if v_fundicao > 100 else Fore.RED

            print(f"{color}{name[:25]:<25}{Style.RESET_ALL} │ "
                  f"{nodes:6d} │ {t_ms:7.0f}ms │ {l_ms:7.0f}ms │ "
                  f"{v_color}{v_fundicao:5.1f} n/s{Fore.RESET}")
            
            # --- PROCESSAMENTO HONESTO DE RESULTADOS ---
            res_pair = compile_results.get(name)
            ok = res_pair[0] if res_pair else False
            err = res_pair[1] if res_pair else "Falha na fundição"

            if ok:
                stats['success'] += 1
                self.cache.mark_compiled(file_ptr) # Sincronizado
            else:
                stats['failed'] += 1
                self.cache.invalidate(file_ptr) # Invalida se o GCC falhou

        stats['total_time'] = round(time.perf_counter() - t_start, 3)
        self.cache.save()
        return stats

    def run_streaming(self, candidates: list[dict], max_workers: int | None=None, force_recompile: bool=False, on_result: Callable[[str, bool, str | None], None] | None=None) -> dict:
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
            stale, cached_count = (candidates, 0)
        stats: dict = {'total': len(candidates), 'cached': cached_count, 'stale': len(stale), 'success': 0, 'failed': 0, 'skipped': 0, 'forge_time': 0.0, 'compile_time': 0.0, 'total_time': 0.0}
        if not stale:
            return stats
        t_start = time.perf_counter()
        forge_queue: Queue[dict | object] = Queue()
        compile_results_store: dict = {}
        compile_lock = threading.Lock()

        def _compile_consumer() -> None:
            batch: list[dict] = []
            t_compile_acc = 0.0
            while True:
                try:
                    item = forge_queue.get(timeout=0.3)
                except Empty:
                    if batch:
                        t0 = time.perf_counter()
                        res = compile_batch(batch, self.env.foundry, self.env.bin_dir, self._build_env, self._python_exe, n_workers)
                        t_compile_acc += time.perf_counter() - t0
                        with compile_lock:
                            compile_results_store.update(res)
                        batch = []
                    continue
                if item is _QUEUE_SENTINEL:
                    if batch:
                        t0 = time.perf_counter()
                        res = compile_batch(batch, self.env.foundry, self.env.bin_dir, self._build_env, self._python_exe, n_workers)
                        t_compile_acc += time.perf_counter() - t0
                        with compile_lock:
                            compile_results_store.update(res)
                    with compile_lock:
                        compile_results_store['__compile_time__'] = t_compile_acc
                    break
                batch.append(item)
                if len(batch) >= _BATCH_SIZE:
                    t0 = time.perf_counter()
                    res = compile_batch(batch, self.env.foundry, self.env.bin_dir, self._build_env, self._python_exe, n_workers)
                    t_compile_acc += time.perf_counter() - t0
                    with compile_lock:
                        compile_results_store.update(res)
                    batch = []
        compiler_thread = threading.Thread(target=_compile_consumer, daemon=True)
        compiler_thread.start()
        t_forge = time.perf_counter()
        forge_tasks = [{'file_path': c['file'], 'foundry': str(self.env.foundry)} for c in stale]
        with TPE(max_workers=n_workers) as executor:
            futures = {executor.submit(_forge_to_pyx, task): task for task in forge_tasks}
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as exc:
                    task = futures[future]
                    result = {'ok': False, 'file': task['file_path'], 'module_name': '', 'err': str(exc)}
                if result.get('skip') or not result['ok']:
                    key = 'skipped' if result.get('skip') else 'failed'
                    stats[key] += 1
                    if on_result:
                        on_result(result['file'], False, result.get('err'))
                else:
                    forge_queue.put(result)
        stats['forge_time'] = round(time.perf_counter() - t_forge, 3)
        forge_queue.put(_QUEUE_SENTINEL)
        compiler_thread.join(timeout=_BATCH_TIMEOUT + 30)
        stats['compile_time'] = round(compile_results_store.pop('__compile_time__', 0.0), 3)
        for c in stale:
            file_path = c['file']
            abs_path = str(Path(file_path).resolve())
            path_hash = hashlib.sha256(abs_path.encode()).hexdigest()[:6]
            stem = Path(file_path).stem
            module_name = f'v_{stem}_{path_hash}'
            ok, err = compile_results_store.get(module_name, (False, None))
            if ok:
                stats['success'] += 1
                self.cache.mark_compiled(file_path)
                if on_result:
                    on_result(file_path, True, None)
            elif module_name not in compile_results_store:
                pass
            else:
                stats['failed'] += 1
                self.cache.invalidate(file_path)
                if on_result:
                    on_result(file_path, False, err)
        stats['total_time'] = round(time.perf_counter() - t_start, 3)
        self.cache.save()
        return stats

    def _filter_stale(self, candidates: list[dict]) -> tuple[list[dict], int]:
        stale, cached = ([], 0)
        for c in candidates:
            if self.cache.is_stale(c['file'], self.env.bin_dir):
                stale.append(c)
            else:
                cached += 1
        if cached:
            print(f'   \x1b[36m↷ PitStop cache quente: {cached} módulo(s) sem mudança → ignorado(s)\x1b[0m')
        return (stale, cached)

    def _phase_forge(self, candidates: list[dict], n_workers: int) -> list[dict]:
        import click
        results: list[dict] = []
        tasks = [{'file_path': c['file'], 'foundry': str(self.env.foundry)} for c in candidates]
        
        with TPE(max_workers=n_workers) as executor:
            # Mapeamos os nomes para a barra
            futures = {executor.submit(_forge_to_pyx, t): Path(t['file_path']).name for t in tasks}
            
            with click.progressbar(as_completed(futures), 
                                 length=len(tasks),
                                 label='  [VULCAN:FORGE]',
                                 show_pos=True, # Mostra (1/29)
                                 item_show_func=lambda f: futures.get(f, '') if f else '') as bar:
                for future in bar:
                    results.append(future.result())
        return results

    def _phase_batch_compile(self, ready, n_workers, compiler):
        """Fase 2: Fundição Paralela usando o compilador injetado."""
        import click
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # REMOVA ou COMENTE a linha abaixo se ela existir, 
        # pois agora usamos o compilador que veio de fora:
        # compiler = VulcanCompiler(self.env, pid_registry=self._pid_registry)

        module_names = [r['module_name'] for r in ready]

        # --- PASSO 1: TRANSPILE ---
        print(f"   {Fore.YELLOW}⚙ Gerando fontes C (Cython Core)...{Fore.RESET}")
        compiler.transpile_batch(module_names) 

        # --- PASSO 2: LINKAGEM PARALELA (GCC) ---
        results = {}
        max_linkers = 2 # Ideal para o seu N2808
        
        print(f"   {Fore.CYAN}🚀 [WARP DRIVE] Fundindo {len(ready)} binários em {max_linkers} núcleos...{Fore.RESET}")
        
        with ThreadPoolExecutor(max_workers=max_linkers) as executor:
            future_to_mod = {executor.submit(compiler._run_gcc_direct, r['module_name']): r['module_name'] for r in ready}
            
            with click.progressbar(length=len(ready), label='  [VULCAN:LINK ]') as bar:
                # [MUDANÇA] Em vez de as_completed puro, usamos um loop com timeout
                while future_to_mod:
                    for future in list(future_to_mod.keys()):
                        if future.done():
                            mod_name = future_to_mod.pop(future)
                            try:
                                ok = future.result()
                                results[mod_name] = (ok, None if ok else "Falha no GCC")
                            except Exception as e:
                                results[mod_name] = (False, str(e))
                            bar.update(1)
                    # [VITAL] Sleep de 50ms evita que o CPU fique em 100% apenas esperando
                    time.sleep(0.05)
                    
        return results

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
        env_val = os.environ.get('DOXOADE_PITSTOP_NTHREADS', '').strip()
        if env_val.isdigit() and int(env_val) > 0:
            return int(env_val)
        cpu = os.cpu_count() or 2
        return max(2, min(8, cpu))

    def warmup_info(self) -> dict:
        """Diagnóstico do estado do motor."""
        n = self._resolve_workers(None)
        return {'python_exe': self._python_exe, 'foundry': str(self.env.foundry), 'bin_dir': str(self.env.bin_dir), 'batch_size': _BATCH_SIZE, 'workers': n, 'parallel_strategy': 'ProcessPoolExecutor (Windows)' if os.name == 'nt' else 'batch+fallback (Linux/macOS)', 'cache': self.cache.stats(), 'build_env_keys': sorted((k for k in self._build_env if k not in os.environ))}