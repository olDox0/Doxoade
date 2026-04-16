# doxoade/doxoade/experiments/optimizer_systems/optimizer_benchmark.py
import time
import importlib.util
from pathlib import Path

class OptimizerBenchmark:

    def __init__(self, original_file: Path, runs: int=10):
        self.original_file = original_file
        self.runs = runs

    def _load_and_run(self, file_path: Path):
        spec = importlib.util.spec_from_file_location('bench_mod', file_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, 'benchmark_entry'):
            raise RuntimeError('Arquivo não define benchmark_entry()')
        start = time.perf_counter()
        mod.benchmark_entry()
        return time.perf_counter() - start

    def run(self, optimized_file: Path):
        orig_times = [self._load_and_run(self.original_file) for _ in range(self.runs)]
        opt_times = [self._load_and_run(optimized_file) for _ in range(self.runs)]
        return {'original_avg': sum(orig_times) / self.runs, 'optimized_avg': sum(opt_times) / self.runs, 'delta_pct': (sum(orig_times) - sum(opt_times)) / sum(orig_times) * 100}