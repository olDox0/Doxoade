# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_benchmark.py
"""
Hermes Benchmark - Sistema Avançado de Medição de Performance.
Telemetria rica: CPU time, cache stats, memory breakdown, percentis.
"""
import time
import sys
import os
import json
import gc
import subprocess
import statistics

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field

from doxoade.tools.doxcolors import Fore, Style

@dataclass
class MemoryStats:
    """Estatísticas detalhadas de memória."""
    rss_mb: float = 0.0          # Resident Set Size
    vms_mb: float = 0.0          # Virtual Memory Size
    shared_mb: float = 0.0       # Memória compartilhada
    text_mb: float = 0.0         # Código executável
    data_mb: float = 0.0         # Dados + BSS
    
    @property
    def total_mb(self) -> float:
        return self.rss_mb

@dataclass
class CPUStats:
    """Estatísticas de CPU."""
    user_time_ms: float = 0.0    # Tempo em user space
    system_time_ms: float = 0.0  # Tempo em kernel space
    cpu_percent: float = 0.0     # % de CPU usado
    
    @property
    def total_time_ms(self) -> float:
        return self.user_time_ms + self.system_time_ms

@dataclass
class CacheStats:
    """Estatísticas de cache do Hermes."""
    cache_hits: int = 0
    cache_misses: int = 0
    decompression_time_ms: float = 0.0
    execution_time_ms: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0

@dataclass
class PipelineStats:
    """Estatísticas detalhadas do pipeline Hermes."""
    find_spec_ms: float = 0.0
    decompress_ms: float = 0.0
    reverse_tokens_ms: float = 0.0
    marshal_loads_ms: float = 0.0
    exec_module_ms: float = 0.0
    total_ms: float = 0.0

@dataclass
class BenchmarkResult:
    """Resultado de um benchmark individual."""
    test_name: str
    scenario: str  # 'hermes', 'python', 'pyc'
    duration_ms: float
    memory: MemoryStats = field(default_factory=MemoryStats)
    cpu: CPUStats = field(default_factory=CPUStats)
    cache: CacheStats = field(default_factory=CacheStats)
    pipeline: PipelineStats = field(default_factory=PipelineStats)
    details: str = ''
    
    # Percentis
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0

@dataclass
class BenchmarkReport:
    """Relatório completo de benchmark."""
    timestamp: str
    project_root: str
    python_version: str
    results: List[BenchmarkResult]
    
    @property
    def hermes_results(self) -> List[BenchmarkResult]:
        return [r for r in self.results if r.scenario == 'hermes']
    
    @property
    def python_results(self) -> List[BenchmarkResult]:
        return [r for r in self.results if r.scenario == 'python']
    
    @property
    def pyc_results(self) -> List[BenchmarkResult]:
        return [r for r in self.results if r.scenario == 'pyc']
    
    def get_speedup(self, test_name: str, baseline: str = 'python') -> Optional[float]:
        """Calcula speedup de Hermes vs baseline."""
        hermes = next((r for r in self.hermes_results if r.test_name == test_name), None)
        base = next((r for r in self.results if r.test_name == test_name and r.scenario == baseline), None)
        
        if hermes and base and hermes.duration_ms > 0 and base.duration_ms > 0:
            return base.duration_ms / hermes.duration_ms
        return None
    
    def get_memory_savings(self, test_name: str) -> Optional[float]:
        """Calcula economia de memória (MB)."""
        hermes = next((r for r in self.hermes_results if r.test_name == test_name), None)
        python = next((r for r in self.python_results if r.test_name == test_name), None)
        
        if hermes and python:
            return python.memory.rss_mb - hermes.memory.rss_mb
        return None

class HermesBenchmark:
    """Motor de benchmark avançado do Hermes."""
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.results: List[BenchmarkResult] = []
    
    def _get_detailed_memory(self) -> MemoryStats:
        """Retorna estatísticas detalhadas de memória."""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            
            return MemoryStats(
                rss_mb=mem_info.rss / 1024 / 1024,
                vms_mb=mem_info.vms / 1024 / 1024,
                shared_mb=getattr(mem_info, 'shared', 0) / 1024 / 1024,
                text_mb=getattr(mem_info, 'text', 0) / 1024 / 1024,
                data_mb=getattr(mem_info, 'data', 0) / 1024 / 1024
            )
        except ImportError:
            return MemoryStats()
    
    def _get_detailed_cpu(self) -> CPUStats:
        """Retorna estatísticas detalhadas de CPU."""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            cpu_times = process.cpu_times()
            
            return CPUStats(
                user_time_ms=cpu_times.user * 1000,
                system_time_ms=cpu_times.system * 1000,
                cpu_percent=process.cpu_percent(interval=0.1)
            )
        except ImportError:
            return CPUStats()
    
    def _measure_subprocess_advanced(self, test_name: str, scenario: str, 
                                     script: str, iterations: int = 10) -> BenchmarkResult:
        """Mede performance com subprocess isolado e telemetria rica."""
        durations = []
        memory_samples = []
        cpu_samples = []
        pipeline_samples = []
        
        # ═══════════════════════════════════════════════════════════════════
        # FIX CRÍTICO: Indenta o script corretamente dentro do try:
        # ═══════════════════════════════════════════════════════════════════
        indented_script = '\n'.join('    ' + line if line.strip() else '' 
                                    for line in script.strip().splitlines())
        
        for iteration in range(iterations):
            gc.collect()
            
            # Script com indentação CORRETA
            wrapped_script = f"""import time
import sys
import json

pipeline_stats = {{
    'find_spec_ms': 0.0,
    'decompress_ms': 0.0,
    'reverse_tokens_ms': 0.0,
    'marshal_loads_ms': 0.0,
    'exec_module_ms': 0.0,
}}

try:
    from doxoade.tools.hermes_systems.hermes_hook import HermesFinder
    _original_find_spec = HermesFinder.find_spec
    def instrumented_find_spec(self, fullname, path, target=None):
        t0 = time.perf_counter()
        result = _original_find_spec(self, fullname, path, target)
        t1 = time.perf_counter()
        pipeline_stats['find_spec_ms'] += (t1 - t0) * 1000
        return result
    HermesFinder.find_spec = instrumented_find_spec
except Exception as e:
    print(f"Warning: Failed to patch HermesFinder: {{e}}", file=sys.stderr)

try:
    from doxoade.tools.hermes_systems.hermes_loader import HermesLoader
    _original_decompress = HermesLoader.decompress_to_code
    def instrumented_decompress(self, hermes_path):
        t_total_start = time.perf_counter()
        import marshal
        _original_marshal_loads = marshal.loads
        marshal_time = [0.0]
        def instrumented_marshal_loads(data):
            t0 = time.perf_counter()
            result = _original_marshal_loads(data)
            marshal_time[0] = (time.perf_counter() - t0) * 1000
            return result
        marshal.loads = instrumented_marshal_loads
        try:
            result = _original_decompress(self, hermes_path)
        finally:
            marshal.loads = _original_marshal_loads
        t_total = (time.perf_counter() - t_total_start) * 1000
        pipeline_stats['decompress_ms'] += t_total
        pipeline_stats['marshal_loads_ms'] += marshal_time[0]
        pipeline_stats['reverse_tokens_ms'] += (t_total - marshal_time[0])
        return result
    HermesLoader.decompress_to_code = instrumented_decompress
except Exception as e:
    print(f"Warning: Failed to patch HermesLoader: {{e}}", file=sys.stderr)

try:
    from doxoade.tools.hermes_systems.hermes_hook import HermesModuleLoader
    _original_exec = HermesModuleLoader.exec_module
    def instrumented_exec(self, module):
        t0 = time.perf_counter()
        result = _original_exec(self, module)
        t1 = time.perf_counter()
        pipeline_stats['exec_module_ms'] += (t1 - t0) * 1000
        return result
    HermesModuleLoader.exec_module = instrumented_exec
except Exception as e:
    print(f"Warning: Failed to patch HermesModuleLoader: {{e}}", file=sys.stderr)

start = time.perf_counter()
try:
{indented_script}
except Exception as e:
    print(f"ERROR in test script: {{e}}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
end = time.perf_counter()

pipeline_stats['total_ms'] = (
    pipeline_stats['find_spec_ms'] +
    pipeline_stats['decompress_ms'] +
    pipeline_stats['exec_module_ms']
)

output = {{
    'duration_ms': (end - start) * 1000,
    'pipeline': pipeline_stats
}}
print(json.dumps(output))
"""
            
            result = subprocess.run(
                [sys.executable, '-c', wrapped_script],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                if iteration == 0:
                    print(f"\n  {Fore.RED}⚠ Subprocess error (iteration 0):{Style.RESET_ALL}")
                    if result.stderr:
                        print(f"    {result.stderr}\n{result}")
                continue
            
            if result.stdout.strip():
                try:
                    metrics = json.loads(result.stdout.strip())
                    duration = metrics['duration_ms']
                    
                    if duration < 0.1:
                        if iteration == 0:
                            print(f"\n  {Fore.YELLOW}⚠ Suspicious low duration: {duration}ms{Style.RESET_ALL}")
                        continue
                    
                    durations.append(duration)
                    pipeline = metrics.get('pipeline', {})
                    pipeline_samples.append(pipeline)
                    
                    mem = self._get_detailed_memory()
                    cpu = self._get_detailed_cpu()
                    memory_samples.append(mem)
                    cpu_samples.append(cpu)
                    
                except (json.JSONDecodeError, KeyError) as e:
                    if iteration == 0:
                        print(f"\n  {Fore.RED}⚠ Failed to parse metrics: {e}{Style.RESET_ALL}")
                        print(f"    stdout: {result.stdout[:200]}")
        
        if not durations:
            return BenchmarkResult(
                test_name=test_name,
                scenario=scenario,
                duration_ms=0.0,
                details='Falha na medição - nenhum dado válido'
            )
        
        avg_duration = statistics.mean(durations)
        p50 = statistics.median(durations)
        p95 = statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations)
        p99 = statistics.quantiles(durations, n=100)[98] if len(durations) >= 100 else max(durations)
        
        avg_pipeline = PipelineStats()
        if pipeline_samples:
            for sample in pipeline_samples:
                avg_pipeline.find_spec_ms += sample.get('find_spec_ms', 0.0)
                avg_pipeline.decompress_ms += sample.get('decompress_ms', 0.0)
                avg_pipeline.reverse_tokens_ms += sample.get('reverse_tokens_ms', 0.0)
                avg_pipeline.marshal_loads_ms += sample.get('marshal_loads_ms', 0.0)
                avg_pipeline.exec_module_ms += sample.get('exec_module_ms', 0.0)
                avg_pipeline.total_ms += sample.get('total_ms', 0.0)
            
            n = len(pipeline_samples)
            avg_pipeline.find_spec_ms /= n
            avg_pipeline.decompress_ms /= n
            avg_pipeline.reverse_tokens_ms /= n
            avg_pipeline.marshal_loads_ms /= n
            avg_pipeline.exec_module_ms /= n
            avg_pipeline.total_ms /= n
        
        avg_memory = MemoryStats()
        avg_cpu = CPUStats()
        
        if memory_samples:
            avg_memory.rss_mb = statistics.mean([m.rss_mb for m in memory_samples])
            avg_memory.vms_mb = statistics.mean([m.vms_mb for m in memory_samples])
            avg_memory.shared_mb = statistics.mean([m.shared_mb for m in memory_samples])
        
        if cpu_samples:
            avg_cpu.user_time_ms = statistics.mean([c.user_time_ms for c in cpu_samples])
            avg_cpu.system_time_ms = statistics.mean([c.system_time_ms for c in cpu_samples])
            avg_cpu.cpu_percent = statistics.mean([c.cpu_percent for c in cpu_samples])
        
        return BenchmarkResult(
            test_name=test_name,
            scenario=scenario,
            duration_ms=avg_duration,
            memory=avg_memory,
            cpu=avg_cpu,
            pipeline=avg_pipeline,
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99
        )

    def benchmark_module_import_advanced(self, module_name: str, iterations: int = 10) -> None:
        """Benchmark de import de módulo específico com telemetria completa."""
        print(f"  [2/4] Benchmarking {module_name}...")
        
        # ═══════════════════════════════════════════════════════════════════
        # FIX CRÍTICO: Scripts com indentação CORRETA
        # ═══════════════════════════════════════════════════════════════════
        script_python = f"""import sys
if '{module_name}' in sys.modules:
    del sys.modules['{module_name}']
import {module_name}
"""
        result_python = self._measure_subprocess_advanced(
            module_name, 'python', script_python, iterations
        )
        self.results.append(result_python)
        
        script_hermes = f"""import sys
if '{module_name}' in sys.modules:
    del sys.modules['{module_name}']
import {module_name}
"""
        result_hermes = self._measure_subprocess_advanced(
            module_name, 'hermes', script_hermes, iterations
        )
        self.results.append(result_hermes)
        
        script_pyc = f"""import sys
if '{module_name}' in sys.modules:
    del sys.modules['{module_name}']
import {module_name}
"""
        result_pyc = self._measure_subprocess_advanced(
            module_name, 'pyc', script_pyc, iterations
        )
        self.results.append(result_pyc)

    def benchmark_startup_advanced(self, iterations: int = 10) -> None:
        """Benchmark de startup com telemetria completa."""
        print("\n  [1/4] Benchmarking startup...")
        
        # Python puro
        result_python = self._measure_subprocess_advanced(
            'startup', 'python', 'pass', iterations
        )
        self.results.append(result_python)
        
        # Hermes
        result_hermes = self._measure_subprocess_advanced(
            'startup', 'hermes',
            'import doxoade.cli',
            iterations
        )
        self.results.append(result_hermes)
        
        # .pyc (baseline compilado)
        result_pyc = self._measure_subprocess_advanced(
            'startup', 'pyc',
            'import doxoade.cli',
            iterations
        )
        self.results.append(result_pyc)
    
    def benchmark_module_import_advanced(self, module_name: str, iterations: int = 10) -> None:
        """Benchmark de import de módulo específico com telemetria completa."""
        print(f"  [2/4] Benchmarking {module_name}...")
        
        # Python puro
        script_python = f'''
import sys
# Remove do sys.modules para forçar reimport
if '{module_name}' in sys.modules:
    del sys.modules['{module_name}']
import {module_name}
'''
        result_python = self._measure_subprocess_advanced(
            module_name, 'python', script_python, iterations
        )
        self.results.append(result_python)
        
        # Hermes
        script_hermes = f'''
import sys
# Remove do sys.modules para forçar reimport
if '{module_name}' in sys.modules:
    del sys.modules['{module_name}']
import {module_name}
'''
        result_hermes = self._measure_subprocess_advanced(
            module_name, 'hermes', script_hermes, iterations
        )
        self.results.append(result_hermes)
        
        # .pyc
        script_pyc = f'''
import sys
if '{module_name}' in sys.modules:
    del sys.modules['{module_name}']
import {module_name}
'''
        result_pyc = self._measure_subprocess_advanced(
            module_name, 'pyc', script_pyc, iterations
        )
        self.results.append(result_pyc)
    
    def benchmark_cache_performance(self, iterations: int = 5) -> None:
        """Benchmark de performance do cache."""
        print("  [3/4] Benchmarking cache performance...")
        
        script = '''
import time
from pathlib import Path
from doxoade.tools.hermes_systems.hermes_loader import HermesLoader

loader = HermesLoader('.')
hermes_files = list(Path('.doxoade/hermes/build').glob('*.hermes'))[:5]

# Teste de cache hit/miss
start = time.perf_counter()
for _ in range(10):
    for hf in hermes_files:
        loader.decompress_to_code(hf)
end = time.perf_counter()

print(f"{{(end - start) * 1000:.2f}}")
'''
        
        durations = []
        for _ in range(iterations):
            result = subprocess.run(
                [sys.executable, '-c', script],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                try:
                    duration = float(result.stdout.strip())
                    durations.append(duration)
                except ValueError:
                    pass
        
        if durations:
            avg_duration = statistics.mean(durations)
            self.results.append(BenchmarkResult(
                test_name='cache_test',
                scenario='hermes',
                duration_ms=avg_duration,
                details=f'Cache performance ({iterations} iterações)'
            ))
    
    def benchmark_critical_modules_advanced(self, iterations: int = 10) -> None:
        """Benchmark dos módulos críticos do projeto."""
        print("  [4/4] Benchmarking módulos críticos...")
        
        critical_modules = [
            'doxoade.cli',
            'doxoade.tools.hermes_systems.hermes_loader',
            'doxoade.tools.vulcan.autopilot',
            'doxoade.tools.vulcan.compiler',
            'doxoade.tools.vulcan.forge',
        ]
        
        for module in critical_modules:
            self.benchmark_module_import_advanced(module, iterations)
    
    def generate_report(self) -> BenchmarkReport:
        """Gera relatório final."""
        return BenchmarkReport(
            timestamp=datetime.now().isoformat(),
            project_root=str(self.root),
            python_version=sys.version,
            results=self.results
        )
    
    def print_summary_advanced(self, report: BenchmarkReport) -> None:
        """Imprime resumo detalhado com análise de pipeline."""
        print("\n" + "═" * 80)
        print("  ☤ HERMES ADVANCED BENCHMARK REPORT")
        print("═" * 80)
        
        print(f"\n■ Timestamp: {report.timestamp}")
        print(f"■ Python: {report.python_version.split()[0]}")
        print(f"■ Projeto: {report.project_root}")
        
        # Startup
        print("\n■ STARTUP TIME")
        for scenario in ['python', 'hermes', 'pyc']:
            result = next((r for r in report.results 
                          if r.test_name == 'startup' and r.scenario == scenario), None)
            if result:
                print(f"  {scenario:<6}: {result.duration_ms:>8.2f} ms  (p95: {result.p95_ms:.2f}ms)")
        
        speedup = report.get_speedup('startup')
        if speedup:
            print(f"  Speedup: {speedup:.2f}×")
        
        # Imports críticos com análise de pipeline
        print("\n■ IMPORTS CRÍTICOS (com análise de pipeline)")
        critical_modules = [
            'doxoade.cli',
            'doxoade.tools.hermes_systems.hermes_loader',
            'doxoade.tools.vulcan.autopilot',
            'doxoade.tools.vulcan.compiler',
            'doxoade.tools.vulcan.forge',
        ]
        
        for module in critical_modules:
            python_result = next((r for r in report.python_results if r.test_name == module), None)
            hermes_result = next((r for r in report.hermes_results if r.test_name == module), None)
            pyc_result = next((r for r in report.pyc_results if r.test_name == module), None)
            
            if python_result and hermes_result:
                print(f"\n  {module}")
                print(f"    python  : {python_result.duration_ms:>7.2f}ms | Mem: {python_result.memory.rss_mb:.1f}MB | CPU: {python_result.cpu.total_time_ms:.1f}ms")
                print(f"    hermes  : {hermes_result.duration_ms:>7.2f}ms | Mem: {hermes_result.memory.rss_mb:.1f}MB | CPU: {hermes_result.cpu.total_time_ms:.1f}ms")
                
                if pyc_result:
                    print(f"    pyc     : {pyc_result.duration_ms:>7.2f}ms | Mem: {pyc_result.memory.rss_mb:.1f}MB | CPU: {pyc_result.cpu.total_time_ms:.1f}ms")
                
                # Análise de pipeline Hermes
                if hermes_result.pipeline.total_ms > 0:
                    print(f"    └─ Pipeline Hermes:")
                    print(f"       find_spec     : {hermes_result.pipeline.find_spec_ms:>7.2f}ms")
                    print(f"       decompress    : {hermes_result.pipeline.decompress_ms:>7.2f}ms")
                    print(f"         └─ marshal  : {hermes_result.pipeline.marshal_loads_ms:>7.2f}ms")
                    print(f"         └─ reverse  : {hermes_result.pipeline.reverse_tokens_ms:>7.2f}ms")
                    print(f"       exec_module   : {hermes_result.pipeline.exec_module_ms:>7.2f}ms")
                    print(f"       total pipeline: {hermes_result.pipeline.total_ms:>7.2f}ms")
                
                speedup = report.get_speedup(module)
                if speedup:
                    print(f"    Speedup: {speedup:.2f}×")
        
        # Cache performance
        print("\n■ CACHE PERFORMANCE")
        cache_results = [r for r in report.results if r.test_name == 'cache_test']
        for result in cache_results:
            print(f"  cache_test               : {result.duration_ms:>8.2f}ms")
        
        # Memory breakdown
        print("\n■ MEMORY BREAKDOWN (Startup)")
        for scenario in ['python', 'hermes', 'pyc']:
            results = [r for r in report.results 
                      if r.test_name == 'startup' and r.scenario == scenario]
            for result in results:
                print(f"  {scenario:<6}: RSS={result.memory.rss_mb:.1f}MB | "
                      f"VMS={result.memory.vms_mb:.1f}MB | "
                      f"Shared={result.memory.shared_mb:.1f}MB")
    
    def save_report(self, report: BenchmarkReport) -> None:
        """Salva relatório em JSON."""
        report_dir = self.root / '.doxoade' / 'hermes'
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = report_dir / 'benchmark_report.json'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': report.timestamp,
                'project_root': report.project_root,
                'python_version': report.python_version,
                'results': [asdict(r) for r in report.results]
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n✔ Relatório salvo em: {report_file}")

    def _measure_subprocess_advanced(self, test_name: str, scenario: str, 
                                     script: str, iterations: int = 10) -> BenchmarkResult:
        """Mede performance com subprocess isolado e telemetria rica."""
        durations = []
        memory_samples = []
        cpu_samples = []
        pipeline_samples = []
        
        for iteration in range(iterations):
            gc.collect()
            
            # ═══════════════════════════════════════════════════════════════════
            # FIX CRÍTICO: Indenta o script corretamente dentro do try:
            # ═══════════════════════════════════════════════════════════════════
            indented_script = '\n'.join('    ' + line if line.strip() else '' 
                                        for line in script.strip().splitlines())
            
            wrapped_script = f"""import time
import sys
import json

pipeline_stats = {{
    'find_spec_ms': 0.0,
    'decompress_ms': 0.0,
    'reverse_tokens_ms': 0.0,
    'marshal_loads_ms': 0.0,
    'exec_module_ms': 0.0,
}}

try:
    from doxoade.tools.hermes_systems.hermes_hook import HermesFinder
    _original_find_spec = HermesFinder.find_spec
    def instrumented_find_spec(self, fullname, path, target=None):
        t0 = time.perf_counter()
        result = _original_find_spec(self, fullname, path, target)
        t1 = time.perf_counter()
        pipeline_stats['find_spec_ms'] += (t1 - t0) * 1000
        return result
    HermesFinder.find_spec = instrumented_find_spec
except Exception as e:
    print(f"Warning: Failed to patch HermesFinder: {{e}}", file=sys.stderr)

try:
    from doxoade.tools.hermes_systems.hermes_loader import HermesLoader
    _original_decompress = HermesLoader.decompress_to_code
    def instrumented_decompress(self, hermes_path):
        t_total_start = time.perf_counter()
        import marshal
        _original_marshal_loads = marshal.loads
        marshal_time = [0.0]
        def instrumented_marshal_loads(data):
            t0 = time.perf_counter()
            result = _original_marshal_loads(data)
            marshal_time[0] = (time.perf_counter() - t0) * 1000
            return result
        marshal.loads = instrumented_marshal_loads
        try:
            result = _original_decompress(self, hermes_path)
        finally:
            marshal.loads = _original_marshal_loads
        t_total = (time.perf_counter() - t_total_start) * 1000
        pipeline_stats['decompress_ms'] += t_total
        pipeline_stats['marshal_loads_ms'] += marshal_time[0]
        pipeline_stats['reverse_tokens_ms'] += (t_total - marshal_time[0])
        return result
    HermesLoader.decompress_to_code = instrumented_decompress
except Exception as e:
    print(f"Warning: Failed to patch HermesLoader: {{e}}", file=sys.stderr)

try:
    from doxoade.tools.hermes_systems.hermes_hook import HermesModuleLoader
    _original_exec = HermesModuleLoader.exec_module
    def instrumented_exec(self, module):
        t0 = time.perf_counter()
        result = _original_exec(self, module)
        t1 = time.perf_counter()
        pipeline_stats['exec_module_ms'] += (t1 - t0) * 1000
        return result
    HermesModuleLoader.exec_module = instrumented_exec
except Exception as e:
    print(f"Warning: Failed to patch HermesModuleLoader: {{e}}", file=sys.stderr)

start = time.perf_counter()
try:
{indented_script}
except Exception as e:
    print(f"ERROR in test script: {{e}}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
end = time.perf_counter()

pipeline_stats['total_ms'] = (
    pipeline_stats['find_spec_ms'] +
    pipeline_stats['decompress_ms'] +
    pipeline_stats['exec_module_ms']
)

output = {{
    'duration_ms': (end - start) * 1000,
    'pipeline': pipeline_stats
}}
print(json.dumps(output))
"""
            
            result = subprocess.run(
                [sys.executable, '-c', wrapped_script],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # ═══════════════════════════════════════════════════════════════════
            # DEBUG: Se houver erro, mostra o código COMPLETO da sonda e PARA
            # ═══════════════════════════════════════════════════════════════════
            if result.returncode != 0:
                print(f"\n{Fore.RED}{'═' * 80}{Style.RESET_ALL}")
                print(f"{Fore.RED}{Style.BRIGHT}🔥 ERRO NO SUBPROCESS — ITERAÇÃO {iteration}{Style.RESET_ALL}")
                print(f"{Fore.RED}{'═' * 80}{Style.RESET_ALL}")
                print(f"\n{Fore.YELLOW}📋 CÓDIGO COMPLETO DA SONDA:{Style.RESET_ALL}")
                print(f"{Fore.CYAN}{'─' * 80}{Style.RESET_ALL}")
                
                # Mostra o código com numeração de linhas
                for i, line in enumerate(wrapped_script.splitlines(), 1):
                    print(f"{Fore.DIM}{i:4d}{Style.RESET_ALL} │ {line}")
                
                print(f"{Fore.CYAN}{'─' * 80}{Style.RESET_ALL}")
                print(f"\n{Fore.RED}📝 STDERR DO SUBPROCESS:{Style.RESET_ALL}")
                print(result.stderr)
                print(f"{Fore.RED}{'═' * 80}{Style.RESET_ALL}")
                
                # PARA a execução — não continua com outras iterações
                return BenchmarkResult(
                    test_name=test_name,
                    scenario=scenario,
                    duration_ms=0.0,
                    details=f'ERRO: subprocess falhou na iteração {iteration}. Veja código acima.'
                )
            
            if result.stdout.strip():
                try:
                    metrics = json.loads(result.stdout.strip())
                    duration = metrics['duration_ms']
                    
                    if duration < 0.1:
                        if iteration == 0:
                            print(f"\n  {Fore.YELLOW}⚠ Suspicious low duration: {duration}ms{Style.RESET_ALL}")
                        continue
                    
                    durations.append(duration)
                    pipeline = metrics.get('pipeline', {})
                    pipeline_samples.append(pipeline)
                    
                    mem = self._get_detailed_memory()
                    cpu = self._get_detailed_cpu()
                    memory_samples.append(mem)
                    cpu_samples.append(cpu)
                    
                except (json.JSONDecodeError, KeyError) as e:
                    if iteration == 0:
                        print(f"\n  {Fore.RED}⚠ Failed to parse metrics: {e}{Style.RESET_ALL}")
                        print(f"    stdout: {result.stdout[:200]}")
        
        if not durations:
            return BenchmarkResult(
                test_name=test_name,
                scenario=scenario,
                duration_ms=0.0,
                details='Falha na medição - nenhum dado válido'
            )
        
        avg_duration = statistics.mean(durations)
        p50 = statistics.median(durations)
        p95 = statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations)
        p99 = statistics.quantiles(durations, n=100)[98] if len(durations) >= 100 else max(durations)
        
        avg_pipeline = PipelineStats()
        if pipeline_samples:
            for sample in pipeline_samples:
                avg_pipeline.find_spec_ms += sample.get('find_spec_ms', 0.0)
                avg_pipeline.decompress_ms += sample.get('decompress_ms', 0.0)
                avg_pipeline.reverse_tokens_ms += sample.get('reverse_tokens_ms', 0.0)
                avg_pipeline.marshal_loads_ms += sample.get('marshal_loads_ms', 0.0)
                avg_pipeline.exec_module_ms += sample.get('exec_module_ms', 0.0)
                avg_pipeline.total_ms += sample.get('total_ms', 0.0)
            
            n = len(pipeline_samples)
            avg_pipeline.find_spec_ms /= n
            avg_pipeline.decompress_ms /= n
            avg_pipeline.reverse_tokens_ms /= n
            avg_pipeline.marshal_loads_ms /= n
            avg_pipeline.exec_module_ms /= n
            avg_pipeline.total_ms /= n
        
        avg_memory = MemoryStats()
        avg_cpu = CPUStats()
        
        if memory_samples:
            avg_memory.rss_mb = statistics.mean([m.rss_mb for m in memory_samples])
            avg_memory.vms_mb = statistics.mean([m.vms_mb for m in memory_samples])
            avg_memory.shared_mb = statistics.mean([m.shared_mb for m in memory_samples])
        
        if cpu_samples:
            avg_cpu.user_time_ms = statistics.mean([c.user_time_ms for c in cpu_samples])
            avg_cpu.system_time_ms = statistics.mean([c.system_time_ms for c in cpu_samples])
            avg_cpu.cpu_percent = statistics.mean([c.cpu_percent for c in cpu_samples])
        
        return BenchmarkResult(
            test_name=test_name,
            scenario=scenario,
            duration_ms=avg_duration,
            memory=avg_memory,
            cpu=avg_cpu,
            pipeline=avg_pipeline,
            p50_ms=p50,
            p95_ms=p95,
            p99_ms=p99
        )

def run_benchmark(project_root: str, iterations: int = 10):
    """Executa benchmark completo."""
    benchmark = HermesBenchmark(project_root)
    
    print("\n☤ Executando benchmark avançado Hermes...")
    print(f"  Iterações por teste: {iterations}")
    
    benchmark.benchmark_startup_advanced(iterations)
    benchmark.benchmark_critical_modules_advanced(iterations)
    benchmark.benchmark_cache_performance(iterations // 2)
    
    report = benchmark.generate_report()
    benchmark.print_summary_advanced(report)
    benchmark.save_report(report)
    
    # ═══════════════════════════════════════════════════════════════════
    # FIX CRÍTICO: Verificar se speedup é None antes de formatar
    # ═══════════════════════════════════════════════════════════════════
    speedup = report.get_speedup('startup')
    if speedup is None:
        print(f"\n{Fore.YELLOW}⚠ Não foi possível calcular speedup (dados insuficientes){Style.RESET_ALL}")
    elif speedup > 1.0:
        print(f"\n{Fore.GREEN}✔ GANHO SIGNIFICATIVO: {speedup:.2f}× mais rápido que Python puro!{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.RED}✘ Sem ganho significativo (speedup: {speedup:.2f}×){Style.RESET_ALL}")
    
    return report