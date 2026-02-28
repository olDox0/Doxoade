# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/hybrid_benchmark.py
"""
Vulcan HybridBenchmark — Medição de ganho real Python vs Cython.
=================================================================

Mede o speedup real de cada função compilada pelo HybridForge,
comparando execução Python pura vs binário Cython.

Uso via CLI:
    doxoade vulcan benchmark doxoade/tools/
    doxoade vulcan benchmark doxoade/tools/analysis.py --runs 500
    doxoade vulcan benchmark doxoade/tools/ --json > bench_results.json

Saída:
    Tabela com: arquivo | função | Python ms | Cython ms | speedup | status

Compliance:
    OSL-4  : única responsabilidade — só mede, não compila
    OSL-5  : falhas de import/execução são capturadas e reportadas como N/A
    PASC-6 : função sem binário é relatada como "não compilada"
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
# [DOX-UNUSED] import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Estruturas de resultado
# ---------------------------------------------------------------------------

@dataclass
class FunctionBenchResult:
    """Resultado do benchmark de uma função individual."""
    file_name:     str
    func_name:     str
    py_ms:         Optional[float]  = None   # tempo Python (médio, ms)
    cy_ms:         Optional[float]  = None   # tempo Cython (médio, ms)
    speedup:       Optional[float]  = None   # py_ms / cy_ms
    error:         Optional[str]    = None
    status:        str              = "OK"   # OK | NO_BINARY | ERROR | WARMUP_FAIL

    @property
    def speedup_label(self) -> str:
        if self.speedup is None:
            return "N/A"
        return f"{self.speedup:.2f}×"

    @property
    def status_color(self) -> str:
        if self.status != "OK":
            return "\033[33m"   # amarelo
        if self.speedup and self.speedup >= 5.0:
            return "\033[32m"   # verde
        if self.speedup and self.speedup >= 1.5:
            return "\033[36m"   # cyan
        return "\033[37m"       # branco


@dataclass
class FileBenchResult:
    """Resultado do benchmark de um arquivo."""
    file_path:  str
    functions:  list[FunctionBenchResult] = field(default_factory=list)

    @property
    def best_speedup(self) -> Optional[float]:
        valids = [f.speedup for f in self.functions if f.speedup is not None]
        return max(valids) if valids else None

    @property
    def avg_speedup(self) -> Optional[float]:
        valids = [f.speedup for f in self.functions if f.speedup is not None]
        return sum(valids) / len(valids) if valids else None


# ---------------------------------------------------------------------------
# HybridBenchmark
# ---------------------------------------------------------------------------

class HybridBenchmark:
    """
    Mede speedup real de funções compiladas pelo HybridForge.

    Estratégia:
      1. Localiza o binário Cython (.pyd/.so) para o arquivo
      2. Carrega o módulo Python original e o binário
      3. Gera fixtures de entrada adequadas via FunctionProber
      4. Executa N vezes cada versão e mede tempo médio
      5. Calcula speedup e reporta
    """

    def __init__(self, project_root: str | Path, runs: int = 200):
        self.root     = Path(project_root).resolve()
        self.bin_dir  = self.root / ".doxoade" / "vulcan" / "bin"
        self.runs     = runs
        self._ext     = ".pyd" if os.name == "nt" else ".so"
        self._prober  = FunctionProber()

    # ── Entry-point ───────────────────────────────────────────────────────────

    def run(
        self,
        target: str | Path,
        output_json: bool = False,
    ) -> list[FileBenchResult]:
        """
        Benchmarka todas as funções compiladas no target (arquivo ou dir).
        Retorna lista de FileBenchResult.
        """
        target_path = Path(target).resolve()
        py_files    = self._collect_py_files(target_path)
        all_results: list[FileBenchResult] = []

        for py_file in py_files:
            binary = self._find_binary(py_file)
            if not binary:
                continue   # sem binário → não foi compilado, pula silencioso

            file_result = self._benchmark_file(py_file, binary)
            if file_result.functions:
                all_results.append(file_result)

        if output_json:
            self._print_json(all_results)
        else:
            self._print_table(all_results)

        return all_results

    # ── Benchmark de um arquivo ───────────────────────────────────────────────

    def _benchmark_file(self, py_file: Path, binary: Path) -> FileBenchResult:
        result = FileBenchResult(file_path=str(py_file))

        # Carrega o módulo Python original
        py_module = self._load_py_module(py_file)
        if py_module is None:
            result.functions.append(FunctionBenchResult(
                file_name=py_file.name,
                func_name="<module>",
                status="ERROR",
                error="falha ao carregar módulo Python",
            ))
            return result

        # Carrega o módulo binário Cython
        cy_module = self._load_binary(binary)
        if cy_module is None:
            result.functions.append(FunctionBenchResult(
                file_name=py_file.name,
                func_name="<binary>",
                status="ERROR",
                error=f"falha ao carregar binário: {binary.name}",
            ))
            return result

        # Descobre funções disponíveis no binário
        cy_funcs = {
            name.replace('_vulcan_optimized', ''): getattr(cy_module, name)
            for name in dir(cy_module)
            if name.endswith('_vulcan_optimized') and callable(getattr(cy_module, name))
        }

        for orig_name, cy_func in cy_funcs.items():
            py_func = getattr(py_module, orig_name, None)
            if py_func is None or not callable(py_func):
                result.functions.append(FunctionBenchResult(
                    file_name=py_file.name,
                    func_name=orig_name,
                    status="NO_BINARY",
                    error="função Python não encontrada no módulo original",
                ))
                continue

            bench = self._bench_pair(py_file.name, orig_name, py_func, cy_func)
            result.functions.append(bench)

        return result

    # ── Medição de par Python/Cython ─────────────────────────────────────────

    def _bench_pair(
        self,
        file_name: str,
        func_name: str,
        py_func:   Callable,
        cy_func:   Callable,
    ) -> FunctionBenchResult:
        """Mede py_func vs cy_func com fixtures geradas automaticamente."""
        result = FunctionBenchResult(file_name=file_name, func_name=func_name)

        # Gera fixture de entrada
        try:
            fixture = self._prober.generate_fixture(py_func)
        except Exception as e:
            result.status = "WARMUP_FAIL"
            result.error  = f"fixture: {e}"
            return result

        # Warmup (Cython precisa de JIT-warmup para ser justo)
        try:
            for _ in range(3):
                py_func(*fixture)
                cy_func(*fixture)
        except Exception as e:
            result.status = "WARMUP_FAIL"
            result.error  = f"warmup: {e}"
            return result

        # Medição Python
        try:
            t0 = time.perf_counter()
            for _ in range(self.runs):
                py_func(*fixture)
            result.py_ms = (time.perf_counter() - t0) * 1000 / self.runs
        except Exception as e:
            result.status = "ERROR"
            result.error  = f"python exec: {e}"
            return result

        # Medição Cython
        try:
            t0 = time.perf_counter()
            for _ in range(self.runs):
                cy_func(*fixture)
            result.cy_ms = (time.perf_counter() - t0) * 1000 / self.runs
        except Exception as e:
            result.status = "ERROR"
            result.error  = f"cython exec: {e}"
            return result

        # Speedup
        if result.cy_ms and result.cy_ms > 0:
            result.speedup = result.py_ms / result.cy_ms
        else:
            result.speedup = None
            result.status  = "ERROR"
            result.error   = "cy_ms = 0"

        return result

    # ── Utilitários ───────────────────────────────────────────────────────────

    def _find_binary(self, py_file: Path) -> Optional[Path]:
        """Localiza o binário .pyd/.so para um arquivo .py pelo hash do path."""
        abs_path  = py_file.resolve()
        path_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
        stem      = abs_path.stem
        pattern   = f"v_{stem}_{path_hash}{self._ext}"
        candidate = self.bin_dir / pattern
        return candidate if candidate.exists() else None

    @staticmethod
    def _load_py_module(py_file: Path):
        """Carrega módulo Python via importlib sem alterar sys.modules."""
        try:
            spec   = importlib.util.spec_from_file_location(
                f"_bench_py_{py_file.stem}", str(py_file)
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception:
            return None

    @staticmethod
    def _load_binary(binary: Path):
        """Carrega binário Cython via importlib."""
        try:
            spec   = importlib.util.spec_from_file_location(
                f"_bench_cy_{binary.stem}", str(binary)
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception:
            return None

    @staticmethod
    def _collect_py_files(target: Path) -> list[Path]:
        _IGNORE_DIRS = frozenset({
            'venv', '.git', '__pycache__', 'build', 'dist', '.doxoade',
        })
        _IGNORE_STEMS = frozenset({
            '__init__', '__main__', 'setup',
            'hybrid_forge', 'hybrid_optimizer', 'hybrid_benchmark',
            'forge', 'compiler', 'autopilot', 'bridge', 'advisor',
        })
        if target.is_file():
            return [target] if target.stem not in _IGNORE_STEMS else []
        files = []
        for root, dirs, filenames in os.walk(str(target)):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
            for f in filenames:
                p = Path(root) / f
                if p.suffix == '.py' and p.stem not in _IGNORE_STEMS:
                    files.append(p)
        return files

    # ── Output ────────────────────────────────────────────────────────────────

    @staticmethod
    def _print_table(results: list[FileBenchResult]):
        if not results:
            print("\n\033[33m  Nenhuma função benchmarkada. "
                  "Execute --hybrid primeiro.\033[0m")
            return

        RESET = "\033[0m"
        BOLD  = "\033[1m"
        CYAN  = "\033[36m"
        DIM   = "\033[2m"

        print(f"\n{CYAN}{'─'*70}{RESET}")
        print(f"{BOLD}  VULCAN HYBRID BENCHMARK{RESET}")
        print(f"{CYAN}{'─'*70}{RESET}")
        print(
            f"  {'Arquivo':<20} {'Função':<35} "
            f"{'Py ms':>7} {'Cy ms':>7} {'Speedup':>8}  Status"
        )
        print(f"{DIM}  {'─'*20} {'─'*35} {'─'*7} {'─'*7} {'─'*8}  {'─'*12}{RESET}")

        total_speedup = 0.0
        total_ok      = 0

        for file_res in results:
            fname = Path(file_res.file_path).name[:20]
            for f in file_res.functions:
                col   = f.status_color
                spd   = f.speedup_label
                py_s  = f"{f.py_ms:.3f}" if f.py_ms is not None else "N/A"
                cy_s  = f"{f.cy_ms:.3f}" if f.cy_ms is not None else "N/A"
                err   = f" ({f.error[:30]})" if f.error else ""
                print(
                    f"  {fname:<20} {f.func_name:<35} "
                    f"{py_s:>7} {cy_s:>7} "
                    f"{col}{spd:>8}{RESET}  {f.status}{DIM}{err}{RESET}"
                )
                if f.speedup:
                    total_speedup += f.speedup
                    total_ok      += 1

        print(f"{CYAN}{'─'*70}{RESET}")
        if total_ok > 0:
            avg = total_speedup / total_ok
            bar = _speedup_bar(avg)
            print(f"  {BOLD}Speedup médio : {avg:.2f}×  {bar}{RESET}")
            print(f"  Funções OK    : {total_ok}")
        print(f"{CYAN}{'─'*70}{RESET}\n")

    @staticmethod
    def _print_json(results: list[FileBenchResult]):
        data = []
        for file_res in results:
            for f in file_res.functions:
                data.append({
                    "file":    file_res.file_path,
                    "func":    f.func_name,
                    "py_ms":   f.py_ms,
                    "cy_ms":   f.cy_ms,
                    "speedup": f.speedup,
                    "status":  f.status,
                    "error":   f.error,
                })
        print(json.dumps(data, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# FunctionProber — gera fixtures de entrada automaticamente
# ---------------------------------------------------------------------------

class FunctionProber:
    """
    Gera argumentos de entrada para funções a partir da sua assinatura.

    Estratégia por nome de parâmetro:
      - file_path / path / src → string de caminho válido
      - findings / items / results → lista de dicts de exemplo
      - content / source / text → string Python de amostra
      - tree / node → ast.Module de amostra
      - func_node → ast.FunctionDef de amostra
      - lines → lista de strings
      - defaults numéricos e bool para o restante
    """

    # Código Python de amostra usado como fixture de análise AST
    _SAMPLE_CODE = (
        "import os\nimport sys\n"
        "def hello(name: str) -> str:\n"
        "    return f'hello {name}'\n"
        "class Foo:\n"
        "    def __init__(self):\n"
        "        self.x = 0\n"
        "    def bar(self, n):\n"
        "        total = 0\n"
        "        for i in range(n):\n"
        "            total += i\n"
        "        return total\n"
    )

    _SAMPLE_FINDINGS = [
        {'severity': 'WARNING', 'category': 'UNUSED', 'message': 'unused var x',
         'file': 'test.py', 'line': 10, 'finding_hash': 'abc123'},
        {'severity': 'ERROR', 'category': 'SYNTAX', 'message': 'invalid syntax',
         'file': 'test.py', 'line': 20, 'finding_hash': 'def456'},
    ]

    def generate_fixture(self, func: Callable) -> tuple:
        """
        Gera uma tupla de argumentos posicionais para a função.
        Levanta TypeError se não conseguir inferir.
        """
        try:
            import inspect
            sig    = inspect.signature(func)
            params = list(sig.parameters.values())
        except (ValueError, TypeError):
            return ()   # sem args — tenta chamar sem nada

        args = []
        for p in params:
            if p.name in ('self', 'cls'):
                continue
            args.append(self._infer_arg(p.name, p.annotation, p.default))
        return tuple(args)

    def _infer_arg(self, name: str, annotation, default) -> Any:
        """Infere valor adequado pelo nome do parâmetro."""
        import inspect

        # Se tem default, usa ele (mais seguro)
        if default is not inspect.Parameter.empty:
            return default

        n = name.lower()

        # AST types
        if n in ('tree', 'node', 'module'):
            return ast.parse(self._SAMPLE_CODE)
        if 'func_node' in n or n == 'func':
            tree = ast.parse(self._SAMPLE_CODE)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return node
            return ast.parse("def f(): pass").body[0]

        # Strings de código/conteúdo
        if n in ('content', 'source', 'code', 'text', 'pyx_code', 'pyx_source'):
            return self._SAMPLE_CODE
        if n in ('file_path', 'path', 'src', 'filename', 'file'):
            return __file__   # path deste arquivo — existe em disco

        # Coleções
        if n in ('findings', 'items', 'results', 'all_findings'):
            return list(self._SAMPLE_FINDINGS)
        if n in ('lines', 'content_lines', 'file_lines'):
            return self._SAMPLE_CODE.splitlines()
        if n in ('templates',):
            return []

        # Numéricos e flags
        if n in ('line_number', 'lineno', 'line', 'line_num'):
            return 5
        if n in ('context_lines', 'context'):
            return 2
        if n in ('complexity', 'hits', 'count', 'n', 'size'):
            return 10
        if n in ('is_test_mode', 'allow_imports', 'force', 'show_code'):
            return False
        if n in ('project_root', 'project_path', 'root_path'):
            return str(Path(__file__).resolve().parents[3])

        # Dicts
        if n in ('taint_map', 'tainted', 'imports'):
            return {'x': 'input', 'y': 'sys.argv'}

        # Fallback: string vazia ou 0
        if annotation == str:
            return ""
        if annotation == int:
            return 0
        if annotation == bool:
            return False
        if annotation == list:
            return []
        if annotation == dict:
            return {}

        return None   # último recurso


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _speedup_bar(speedup: float) -> str:
    """Barra visual de speedup."""
    filled = min(int(speedup * 2), 20)
    bar    = "█" * filled + "░" * (20 - filled)
    if speedup >= 10:
        color = "\033[32m"   # verde
    elif speedup >= 3:
        color = "\033[36m"   # cyan
    else:
        color = "\033[37m"   # branco
    return f"{color}[{bar}]\033[0m"


# ---------------------------------------------------------------------------
# API pública (chamada pelo vulcan_cmd.py)
# ---------------------------------------------------------------------------

def run_benchmark(
    project_root: str | Path,
    target:       str | Path,
    runs:         int  = 200,
    output_json:  bool = False,
) -> list[FileBenchResult]:
    """Entry-point chamado pelo vulcan_cmd benchmark."""
    bench = HybridBenchmark(project_root=project_root, runs=runs)
    return bench.run(target=target, output_json=output_json)