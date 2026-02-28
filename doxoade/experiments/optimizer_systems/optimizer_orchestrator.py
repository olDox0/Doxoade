# doxoade/experiments/optimizer_systems/optimizer_orchestrator.py
from pathlib import Path

from .optimizer_engine import OptimizerEngine
from .optimizer_benchmark import OptimizerBenchmark
from .probes.ast_probe import ast_probe
from .probes.semantic_probe import semantic_probe


class OptimizerOrchestrator:
    def __init__(self, target_file: Path):
        self.target_file = Path(target_file)
        self.engine = OptimizerEngine()
        self.benchmark = OptimizerBenchmark(self.target_file)

    def run(self):
        # 1. Probes básicos
        ast_info = ast_probe(self.target_file)
        if not semantic_probe(ast_info):
            raise RuntimeError("Arquivo reprovado por segurança semântica")

        # 2. Otimização (PMV = identidade)
        optimized_path = self.engine.optimize(self.target_file, ast_info)

        # 3. Benchmark A/B
        return self.benchmark.run(optimized_path)