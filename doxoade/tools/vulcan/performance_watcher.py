# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/performance_watcher.py
"""
PerformanceWatcher
==================
Avalia automaticamente se funções compiladas com Cython ganharam ou
regrediram em performance, e alimenta o RegressionRegistry.

Fluxo:
  compilação → PerformanceWatcher.evaluate(py_file, module_name)
             → mede Python vs Cython para cada função exportada
             → atualiza RegressionRegistry
             → retorna WatchResult com diagnóstico claro

A medição é feita dentro do próprio processo: importa o módulo .so
gerado e cronometra N execuções com timeit, comparando com a versão
Python original.

Compatível com Python 3.8+. Sem dependências externas.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import sys
import timeit
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .regression_registry import (
    RegressionRegistry,
    STATUS_AGGRESSIVE,
    STATUS_EXCLUDED,
    MIN_SPEEDUP_DEFAULT,
)

# ── Configuração ─────────────────────────────────────────────────────────────

DEFAULT_RUNS       = 500     # execuções por função
DEFAULT_WARMUP     = 10      # warmups antes de medir
MIN_RUNTIME_US     = 0.5     # μs mínimo para considerar a função "mensurável"

# ── Resultados ────────────────────────────────────────────────────────────────

@dataclass
class FuncMeasurement:
    """Resultado de uma função individual."""
    name:         str
    speedup:      Optional[float]   # None = não mensurável / erro
    py_time_us:   Optional[float]
    cy_time_us:   Optional[float]
    status:       str               # "OK" | "REGRESSION" | "ERROR" | "UNMEASURABLE"
    note:         str = ""

    @property
    def gained(self) -> bool:
        return self.speedup is not None and self.speedup >= MIN_SPEEDUP_DEFAULT

    @property
    def regressed(self) -> bool:
        return self.speedup is not None and self.speedup < MIN_SPEEDUP_DEFAULT


@dataclass
class WatchResult:
    """Resultado de avaliação de um arquivo/módulo compilado."""
    file_path:    str
    module_name:  str
    functions:    List[FuncMeasurement] = field(default_factory=list)
    registry_summary: Dict[str, int]   = field(default_factory=dict)

    @property
    def ok(self) -> List[FuncMeasurement]:
        return [f for f in self.functions if f.gained]

    @property
    def regressions(self) -> List[FuncMeasurement]:
        return [f for f in self.functions if f.regressed]

    @property
    def errors(self) -> List[FuncMeasurement]:
        return [f for f in self.functions if f.status == "ERROR"]

    def render_cli(self) -> None:
        """Imprime diagnóstico colorido no terminal."""
        G   = "\033[32m"
        R   = "\033[31m"
        Y   = "\033[33m"
        C   = "\033[36m"
        DIM = "\033[2m"
        B   = "\033[1m"
        RST = "\033[0m"

        src = Path(self.file_path).name
        print(f"\n  {B}{C}⬡ VULCAN WATCHER — {src}{RST}")
        print(f"  Módulo  : {self.module_name}")
        print(f"  Funções : {len(self.functions)}  "
              f"{G}OK: {len(self.ok)}{RST}  "
              f"{R}Regressões: {len(self.regressions)}{RST}  "
              f"{Y}Erros: {len(self.errors)}{RST}")

        if not self.functions:
            print(f"  {DIM}Nenhuma função avaliada.{RST}\n")
            return

        print(f"\n  {'FUNÇÃO':<38} {'PY (μs)':>10} {'CY (μs)':>10} {'SPEEDUP':>9}  STATUS")
        print(f"  {'─'*38} {'─'*10} {'─'*10} {'─'*9}  {'─'*20}")

        for m in sorted(self.functions, key=lambda x: (x.speedup or 0)):
            if m.speedup is None:
                color  = DIM
                spd_s  = "   n/a"
                py_s   = "   n/a"
                cy_s   = "   n/a"
            else:
                color  = G if m.gained else R
                spd_s  = f"{m.speedup:>6.2f}x"
                py_s   = f"{m.py_time_us:>9.2f}" if m.py_time_us else "   n/a"
                cy_s   = f"{m.cy_time_us:>9.2f}" if m.cy_time_us else "   n/a"

            print(
                f"  {m.name:<38} "
                f"{DIM}{py_s}{RST} "
                f"{DIM}{cy_s}{RST} "
                f"{color}{spd_s}{RST}  "
                f"{color}{m.status:<20}{RST}"
                + (f"  {DIM}{m.note}{RST}" if m.note else "")
            )

        # Summary do registry
        if self.registry_summary:
            rs = self.registry_summary
            print(f"\n  {B}Registry atualizado:{RST}  "
                  f"{R}Excluídas: {rs.get('excluded', 0)}{RST}  "
                  f"{Y}Retry-Agressivo: {rs.get('retry_aggressive', 0)}{RST}  "
                  f"{G}Promovidas: {rs.get('promoted', 0)}{RST}")
        print()


# ── Watcher principal ─────────────────────────────────────────────────────────

class PerformanceWatcher:
    """
    Mede Python vs Cython para cada função exportada de um módulo compilado,
    detecta regressões e atualiza o RegressionRegistry automaticamente.

    Parâmetros:
        project_root  — raiz do projeto (onde está .doxoade/)
        runs          — execuções por função (padrão: 500)
        min_speedup   — speedup mínimo para não ser regressão (padrão: 1.10)
        foundry       — diretório onde o .so compilado foi gerado
    """

    def __init__(
        self,
        project_root: "str | Path",
        *,
        runs:        int   = DEFAULT_RUNS,
        min_speedup: float = MIN_SPEEDUP_DEFAULT,
        foundry:     "str | Path | None" = None,
        bin_dir:     "str | Path | None" = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.runs         = runs
        self.min_speedup  = min_speedup
        # foundry → onde os .pyx são gerados (intermediário)
        # bin_dir → onde os .so/.pyd compilados ficam (destino real)
        self.foundry  = Path(foundry) if foundry else (self.project_root / ".doxoade" / "vulcan" / "foundry")
        self.bin_dir  = Path(bin_dir) if bin_dir  else (self.project_root / ".doxoade" / "vulcan" / "bin")
        self.registry = RegressionRegistry(project_root)

    # ── API pública ───────────────────────────────────────────────────────────

    def evaluate(
        self,
        py_file:     "str | Path",
        module_name: str,
        *,
        update_registry: bool = True,
    ) -> WatchResult:
        """
        Avalia as funções compiladas de `module_name` (gerado de `py_file`).

        Parâmetros:
            py_file         — arquivo Python fonte
            module_name     — nome do módulo .so gerado (sem extensão)
            update_registry — se True, atualiza o registry automaticamente

        Retorna WatchResult com medições e ações do registry.
        """
        py_file = Path(py_file).resolve()
        result  = WatchResult(file_path=str(py_file), module_name=module_name)

        # carrega módulo Python original
        py_funcs = self._load_py_functions(py_file)
        if not py_funcs:
            return result

        # carrega módulo Cython compilado
        cy_mod = self._import_compiled(module_name)
        if cy_mod is None:
            for name in py_funcs:
                result.functions.append(FuncMeasurement(
                    name=name, speedup=None,
                    py_time_us=None, cy_time_us=None,
                    status="ERROR", note="módulo compilado não encontrado",
                ))
            return result

        # mede cada função
        for func_name, py_func in py_funcs.items():
            cy_name = f"{func_name}_vulcan_optimized"
            cy_func = getattr(cy_mod, cy_name, None)

            if cy_func is None:
                result.functions.append(FuncMeasurement(
                    name=func_name, speedup=None,
                    py_time_us=None, cy_time_us=None,
                    status="UNMEASURABLE", note=f"{cy_name} não encontrado no .so",
                ))
                continue

            measurement = self._measure(func_name, py_func, cy_func)
            result.functions.append(measurement)

        # atualiza registry
        if update_registry:
            summary = self._update_registry(py_file, result)
            result.registry_summary = summary

        return result

    def evaluate_all_compiled(self, *, update_registry: bool = True) -> List[WatchResult]:
        """
        Avalia todos os módulos compilados disponíveis no foundry.
        Útil para rodar uma varredura global após um ignite.
        """
        results = []
        if not self.foundry.exists():
            return results

        for so_file in self.foundry.glob("*.so"):
            module_name = so_file.stem
            # tenta descobrir arquivo fonte pelo nome do módulo
            py_file = self._find_source_for(module_name)
            if py_file is None:
                continue
            results.append(self.evaluate(py_file, module_name,
                                         update_registry=update_registry))
        return results

    # ── medição ───────────────────────────────────────────────────────────────

    def _measure(
        self,
        func_name: str,
        py_func:   Callable,
        cy_func:   Callable,
    ) -> FuncMeasurement:
        """
        Mede tempo médio de py_func e cy_func.
        Usa args sintéticos gerados por _make_args.
        """
        args, kwargs = self._make_args(py_func)

        py_us = self._time_func(py_func, args, kwargs)
        cy_us = self._time_func(cy_func, args, kwargs)

        if py_us is None or cy_us is None:
            return FuncMeasurement(
                name=func_name, speedup=None,
                py_time_us=py_us, cy_time_us=cy_us,
                status="ERROR", note="exceção durante medição",
            )

        if py_us < MIN_RUNTIME_US:
            return FuncMeasurement(
                name=func_name, speedup=None,
                py_time_us=py_us, cy_time_us=cy_us,
                status="UNMEASURABLE",
                note=f"função muito rápida para medir ({py_us:.3f}μs)",
            )

        speedup = py_us / cy_us if cy_us > 0 else float("inf")
        status  = "OK" if speedup >= self.min_speedup else "REGRESSION"

        return FuncMeasurement(
            name=func_name,
            speedup=speedup,
            py_time_us=py_us,
            cy_time_us=cy_us,
            status=status,
        )

    def _time_func(
        self,
        func:   Callable,
        args:   tuple,
        kwargs: dict,
    ) -> Optional[float]:
        """
        Cronometra a função. Retorna tempo médio em microsegundos, ou None em erro.
        """
        try:
            # warmup
            for _ in range(DEFAULT_WARMUP):
                func(*args, **kwargs)

            t = timeit.timeit(lambda: func(*args, **kwargs), number=self.runs)
            return (t / self.runs) * 1_000_000   # → microsegundos
        except Exception:
            return None

    # ── geração de args sintéticos ───────────────────────────────────────────

    @staticmethod
    def _make_args(func: Callable) -> Tuple[tuple, dict]:
        """
        Gera argumentos sintéticos simples baseados na assinatura da função.
        Usa int=1, float=1.0, str="a", list=[], dict={}, bool=True.
        Parâmetros sem anotação → int.
        """
        try:
            sig = inspect.signature(func)
        except (ValueError, TypeError):
            return (), {}

        args   = []
        kwargs = {}

        _defaults: Dict[type, Any] = {
            int: 1, float: 1.0, str: "a",
            list: [], dict: {}, bool: True,
            bytes: b"a", tuple: (),
        }

        for name, param in sig.parameters.items():
            if name in ("self", "cls"):
                continue
            ann = param.annotation
            val = _defaults.get(ann, 1)

            if param.default is inspect.Parameter.empty:
                if param.kind in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.POSITIONAL_ONLY,
                ):
                    args.append(val)
                elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                    kwargs[name] = val
                # VAR_POSITIONAL / VAR_KEYWORD → ignora
            # com default → deixa usar o default

        return tuple(args), kwargs

    # ── carregamento de módulos ───────────────────────────────────────────────

    @staticmethod
    def _load_py_functions(py_file: Path) -> Dict[str, Callable]:
        """
        Importa o arquivo Python e retorna apenas funções DEFINIDAS nele.
        Exclui funções importadas de outros módulos (ex: echo, dataclass, field).
        A filtragem usa __code__.co_filename para garantir origem correta.
        """
        spec = importlib.util.spec_from_file_location("_vulcan_py_orig", py_file)
        if spec is None or spec.loader is None:
            return {}
        try:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]

            # Caminho resolvido do arquivo fonte — usado para filtrar imports
            resolved = str(py_file.resolve())

            return {
                name: obj
                for name, obj in vars(mod).items()
                if (
                    inspect.isfunction(obj)
                    and not name.startswith("_")
                    # Só funções cujo código foi definido NESTE arquivo
                    and hasattr(obj, "__code__")
                    and Path(obj.__code__.co_filename).resolve() == Path(resolved)
                )
            }
        except Exception:
            return {}

    def _import_compiled(self, module_name: str) -> Optional[Any]:
        """
        Tenta importar o módulo compilado.
        Busca em bin_dir (destino dos .so/.pyd) e também em foundry (fallback).
        O .so vai para bin_dir após compilação; foundry só tem os .pyx intermediários.
        """
        # Busca primeiro em bin_dir, depois em foundry como fallback
        search_dirs = []
        for d in (self.bin_dir, self.foundry):
            s = str(d)
            if s not in search_dirs:
                search_dirs.append(s)

        inserted = []
        for d in search_dirs:
            if d not in sys.path:
                sys.path.insert(0, d)
                inserted.append(d)

        try:
            if module_name in sys.modules:
                del sys.modules[module_name]
            return importlib.import_module(module_name)
        except Exception:
            return None
        finally:
            for d in inserted:
                try:
                    sys.path.remove(d)
                except ValueError:
                    pass

    def _find_source_for(self, module_name: str) -> Optional[Path]:
        """
        Tenta achar o .py fonte de um módulo compilado.
        Procura o stem do hash embutido no nome (v_{stem}_{hash6}).
        """
        # formato: v_{safe_stem}_{hash6}
        parts = module_name.split("_")
        if len(parts) < 3 or parts[0] != "v":
            return None
        stem_parts = parts[1:-1]   # remove 'v' e hash final
        stem = "_".join(stem_parts)

        for py_file in self.project_root.rglob(f"{stem}.py"):
            return py_file
        return None

    # ── atualiza registry ─────────────────────────────────────────────────────

    def _update_registry(self, py_file: Path, result: WatchResult) -> dict:
        """Chama o registry para cada função medida e salva."""
        summary = {"excluded": 0, "retry_aggressive": 0, "promoted": 0, "ok": 0}

        for m in result.functions:
            if m.status == "OK" and m.speedup is not None and m.speedup >= self.min_speedup:
                promoted = self.registry.record_success(str(py_file), m.name)
                summary["promoted" if promoted else "ok"] += 1

            elif m.status == "REGRESSION" and m.speedup is not None:
                new_status = self.registry.record_regression(
                    str(py_file), m.name, m.speedup
                )
                summary["retry_aggressive" if new_status == STATUS_AGGRESSIVE else "excluded"] += 1

        self.registry.save()
        return summary