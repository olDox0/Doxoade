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
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime

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
class BenchmarkResult:
    """Resultado de um benchmark individual."""
    test_name: str
    scenario: str  # 'hermes', 'python', 'pyc'
    duration_ms: float
    memory: MemoryStats = field(default_factory=MemoryStats)
    cpu: CPUStats = field(default_factory=CPUStats)
    cache: CacheStats = field(default_factory=CacheStats)
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
    
# Substituir o método _measure_subprocess_advanced (linhas ~100-150)
    def _measure_subprocess_advanced(self, test_name: str, scenario: str, script: str) -> BenchmarkResult:
        """Executa script em subprocesso com telemetria de memória REAL dentro do subprocesso."""
        gc.collect()
        
        # ═══════════════════════════════════════════════════════════════════
        # Script wrapper que mede memória DENTRO do subprocesso via psutil
        # ═══════════════════════════════════════════════════════════════════
        wrapped_script = f'''
import sys, os, time
try:
    import psutil
    _proc = psutil.Process(os.getpid())
    _mem_before = _proc.memory_info()
    _cpu_before = _proc.cpu_times()
    _has_psutil = True
except ImportError:
    _has_psutil = False

_start = time.perf_counter()
try:
{chr(10).join("    " + line for line in script.split(chr(10)))}
    _duration = (time.perf_counter() - _start) * 1000
    _exit_code = 0
except Exception as _e:
    _duration = (time.perf_counter() - _start) * 1000
    import traceback
    print(f"ERROR: {{traceback.format_exc()}}", file=sys.stderr)
    _exit_code = 1

if _has_psutil:
    _mem_after = _proc.memory_info()
    _cpu_after = _proc.cpu_times()
    print(f"__METRICS__|{{_duration:.3f}}|{{_mem_after.rss - _mem_before.rss}}|{{_mem_after.vms - _mem_before.vms}}|{{getattr(_mem_after, 'shared', 0) - getattr(_mem_before, 'shared', 0)}}|{{(_cpu_after.user - _cpu_before.user) * 1000:.3f}}|{{(_cpu_after.system - _cpu_before.system) * 1000:.3f}}")
else:
    print(f"__METRICS__|{{_duration:.3f}}|0|0|0|0|0")
sys.exit(_exit_code)
'''
        
        start = time.perf_counter()
        try:
            result = subprocess.run(
                [sys.executable, '-c', wrapped_script],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.root),
                encoding='utf-8',
                errors='replace'
            )
            duration = (time.perf_counter() - start) * 1000
        except subprocess.TimeoutExpired:
            duration = 30000.0
            result = None
        except Exception:
            duration = 0.0
            result = None
        
        # ═══════════════════════════════════════════════════════════════════
        # Parse das métricas do subprocesso (linha __METRICS__)
        # ═══════════════════════════════════════════════════════════════════
        mem_delta = MemoryStats()
        cpu_delta = CPUStats()
        details = ''
        script_duration = duration
        
        if result and result.stdout:
            for line in result.stdout.split('\n'):
                if line.startswith('__METRICS__|'):
                    try:
                        parts = line.split('|')
                        script_duration = float(parts[1])
                        mem_delta = MemoryStats(
                            rss_mb=int(parts[2]) / 1024 / 1024,
                            vms_mb=int(parts[3]) / 1024 / 1024,
                            shared_mb=int(parts[4]) / 1024 / 1024,
                        )
                        cpu_delta = CPUStats(
                            user_time_ms=float(parts[5]),
                            system_time_ms=float(parts[6]),
                        )
                    except (IndexError, ValueError):
                        pass
                else:
                    details += line + '\n'
        
        bm_result = BenchmarkResult(
            test_name=test_name,
            scenario=scenario,
            duration_ms=script_duration if script_duration > 0 else duration,
            memory=mem_delta,
            cpu=cpu_delta,
            details=details.strip()
        )
        self.results.append(bm_result)
        return bm_result
    
    def benchmark_startup_advanced(self, iterations: int = 10) -> Dict[str, BenchmarkResult]:
        """Benchmark avançado de startup com percentis."""
        results = {}
        
        # Scripts de teste
        scripts = {
            'python': """
import sys
import time
start = time.perf_counter()
from doxoade import cli
duration = (time.perf_counter() - start) * 1000
print(f"{duration:.3f}")
""",
            'hermes': """
import sys
import time
start = time.perf_counter()
from doxoade.tools.hermes_systems.hermes_hook import install
install('.')
from doxoade import cli
duration = (time.perf_counter() - start) * 1000
print(f"{duration:.3f}")
""",
            'pyc': """
import sys
import time
import py_compile
# Força compilação para .pyc
py_compile.compile('doxoade/cli.py', doraise=True)
start = time.perf_counter()
from doxoade import cli
duration = (time.perf_counter() - start) * 1000
print(f"{duration:.3f}")
"""
        }
        
        for scenario, script in scripts.items():
            durations = []
            for i in range(iterations):
                result = self._measure_subprocess_advanced('startup', scenario, script)
                try:
                    duration = float(result.details.strip())
                    durations.append(duration)
                except:
                    durations.append(result.duration_ms)
            
            # Calcula percentis
            durations.sort()
            p50 = statistics.median(durations)
            p95 = durations[int(len(durations) * 0.95)] if len(durations) >= 20 else durations[-1]
            p99 = durations[int(len(durations) * 0.99)] if len(durations) >= 100 else durations[-1]
            
            # Usa mediana como valor principal
            results[scenario] = BenchmarkResult(
                test_name='startup',
                scenario=scenario,
                duration_ms=p50,
                p50_ms=p50,
                p95_ms=p95,
                p99_ms=p99,
                memory=results.get(scenario, BenchmarkResult('', '', 0)).memory,
                cpu=results.get(scenario, BenchmarkResult('', '', 0)).cpu,
                details=f'{iterations} iterações | p50={p50:.2f}ms | p95={p95:.2f}ms | p99={p99:.2f}ms'
            )
        
        return results
    
    def benchmark_module_import_advanced(self, module_name: str, iterations: int = 10) -> Dict[str, BenchmarkResult]:
        """Benchmark avançado de import com telemetria completa."""
        results = {}
        
        scripts = {
            'python': f"""
import sys
import time
start = time.perf_counter()
import {module_name}
duration = (time.perf_counter() - start) * 1000
print(f"{{duration:.3f}}")
""",
            'hermes': f"""
import sys
import time
from doxoade.tools.hermes_systems.hermes_hook import install
install('.')
start = time.perf_counter()
import {module_name}
duration = (time.perf_counter() - start) * 1000
print(f"{{duration:.3f}}")
""",
            'pyc': f"""
import sys
import time
import py_compile
# Força compilação para .pyc
try:
    py_compile.compile('{module_name.replace('.', '/')}.py', doraise=True)
except:
    pass
start = time.perf_counter()
import {module_name}
duration = (time.perf_counter() - start) * 1000
print(f"{{duration:.3f}}")
"""
        }
        
        for scenario, script in scripts.items():
            durations = []
            for i in range(iterations):
                result = self._measure_subprocess_advanced(f'import_{module_name}', scenario, script)
                try:
                    duration = float(result.details.strip())
                    durations.append(duration)
                except:
                    durations.append(result.duration_ms)
            
            # Calcula percentis
            durations.sort()
            p50 = statistics.median(durations)
            p95 = durations[int(len(durations) * 0.95)] if len(durations) >= 20 else durations[-1]
            p99 = durations[int(len(durations) * 0.99)] if len(durations) >= 100 else durations[-1]
            
            results[scenario] = BenchmarkResult(
                test_name=f'import_{module_name}',
                scenario=scenario,
                duration_ms=p50,
                p50_ms=p50,
                p95_ms=p95,
                p99_ms=p99,
                memory=result.memory,
                cpu=result.cpu,
                details=f'{iterations} iterações | p50={p50:.2f}ms | p95={p95:.2f}ms'
            )
        
        return results
    
    def benchmark_cache_performance(self, iterations: int = 5) -> Dict[str, BenchmarkResult]:
        """Benchmark específico de performance do cache Hermes."""
        results = {}
        
        script = """
import sys
import time
from doxoade.tools.hermes_systems.hermes_hook import install
install('.')

# Primeiro import (cache miss)
start = time.perf_counter()
import doxoade.cli
first_import = (time.perf_counter() - start) * 1000

# Limpa módulos para forçar segundo import
for mod in list(sys.modules.keys()):
    if mod.startswith('doxoade'):
        del sys.modules[mod]

# Segundo import (cache hit - se cache persistente)
start = time.perf_counter()
import doxoade.cli
second_import = (time.perf_counter() - start) * 1000

print(f"{first_import:.3f},{second_import:.3f}")
"""
        
        durations_first = []
        durations_second = []
        
        for i in range(iterations):
            result = self._measure_subprocess_advanced('cache_test', 'hermes', script)
            try:
                parts = result.details.strip().split(',')
                first = float(parts[0])
                second = float(parts[1])
                durations_first.append(first)
                durations_second.append(second)
            except:
                pass
        
        if durations_first and durations_second:
            results['first_import'] = BenchmarkResult(
                test_name='cache_first_import',
                scenario='hermes',
                duration_ms=statistics.median(durations_first),
                details=f'Cache miss | {iterations} iterações'
            )
            results['second_import'] = BenchmarkResult(
                test_name='cache_second_import',
                scenario='hermes',
                duration_ms=statistics.median(durations_second),
                details=f'Cache hit | {iterations} iterações'
            )
        
        return results
    
    def benchmark_critical_modules_advanced(self, iterations: int = 10) -> Dict[str, Dict[str, BenchmarkResult]]:
        """Benchmark avançado dos módulos críticos."""
        critical_modules = [
            'doxoade.cli',
            'doxoade.tools.hermes_systems.hermes_loader',
            'doxoade.tools.vulcan.forge',
            'doxoade.tools.vulcan.compiler',
            'doxoade.tools.vulcan.autopilot',
        ]
        
        all_results = {}
        for module in critical_modules:
            all_results[module] = self.benchmark_module_import_advanced(module, iterations)
        
        return all_results
    
    def generate_report(self) -> BenchmarkReport:
        """Gera relatório final."""
        report = BenchmarkReport(
            timestamp=datetime.now().isoformat(),
            project_root=str(self.root),
            python_version=sys.version,
            results=self.results
        )
        
        return report
    
    def print_summary_advanced(self, report: BenchmarkReport):
        """Imprime resumo avançado do benchmark."""
        from doxoade.tools.doxcolors import Fore, Style
        
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═'*80}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{Style.BRIGHT}  ☤ HERMES ADVANCED BENCHMARK REPORT{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{Style.BRIGHT}{'═'*80}{Style.RESET_ALL}\n")
        
        print(f"{Fore.WHITE}■ Timestamp: {Style.RESET_ALL}{report.timestamp}")
        print(f"{Fore.WHITE}■ Python: {Style.RESET_ALL}{report.python_version.split()[0]}")
        print(f"{Fore.WHITE}■ Projeto: {Style.RESET_ALL}{report.project_root}\n")
        
        # Startup
        print(f"{Fore.YELLOW}{Style.BRIGHT}■ STARTUP TIME{Style.RESET_ALL}")
        for scenario in ['python', 'hermes', 'pyc']:
            result = next((r for r in report.results if r.test_name == 'startup' and r.scenario == scenario), None)
            if result:
                color = Fore.GREEN if scenario == 'python' else (Fore.CYAN if scenario == 'hermes' else Fore.MAGENTA)
                print(f"  {color}{scenario:8}{Style.RESET_ALL}: {result.duration_ms:8.2f} ms  (p95: {result.p95_ms:.2f}ms)")
        
        startup_speedup = report.get_speedup('startup')
        if startup_speedup:
            color = Fore.GREEN if startup_speedup > 1.0 else Fore.RED
            print(f"  Speedup: {color}{startup_speedup:.2f}×{Style.RESET_ALL}\n")
        
        # Imports críticos
        print(f"{Fore.YELLOW}{Style.BRIGHT}■ IMPORTS CRÍTICOS{Style.RESET_ALL}")
        test_names = set(r.test_name for r in report.results if r.test_name.startswith('import_'))
        
        for test_name in sorted(test_names):
            module = test_name.replace('import_', '')
            print(f"\n  {Fore.WHITE}{module}{Style.RESET_ALL}")
            
            for scenario in ['python', 'hermes', 'pyc']:
                result = next((r for r in report.results if r.test_name == test_name and r.scenario == scenario), None)
                if result:
                    color = Fore.GREEN if scenario == 'python' else (Fore.CYAN if scenario == 'hermes' else Fore.MAGENTA)
                    print(f"    {color}{scenario:8}{Style.RESET_ALL}: {result.duration_ms:6.2f}ms | Mem: {result.memory.rss_mb:.1f}MB | CPU: {result.cpu.user_time_ms:.1f}ms")
            
            speedup = report.get_speedup(test_name)
            if speedup:
                color = Fore.GREEN if speedup > 1.0 else Fore.RED
                print(f"    Speedup: {color}{speedup:.2f}×{Style.RESET_ALL}")
        
        # Cache performance
        cache_results = [r for r in report.results if 'cache' in r.test_name]
        if cache_results:
            print(f"\n{Fore.YELLOW}{Style.BRIGHT}■ CACHE PERFORMANCE{Style.RESET_ALL}")
            for result in cache_results:
                print(f"  {result.test_name:25}: {result.duration_ms:.2f}ms")
        
        # Memory breakdown
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}■ MEMORY BREAKDOWN (Startup){Style.RESET_ALL}")
        startup_results = [r for r in report.results if r.test_name == 'startup']
        for result in startup_results:
            color = Fore.GREEN if result.scenario == 'python' else (Fore.CYAN if result.scenario == 'hermes' else Fore.MAGENTA)
            print(f"  {color}{result.scenario:8}{Style.RESET_ALL}: RSS={result.memory.rss_mb:.1f}MB | VMS={result.memory.vms_mb:.1f}MB | Shared={result.memory.shared_mb:.1f}MB")
        
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═'*80}{Style.RESET_ALL}\n")
    
    def save_report(self, report: BenchmarkReport, output_path: Optional[Path] = None):
        """Salva relatório em JSON."""
        if output_path is None:
            output_path = self.root / '.doxoade' / 'hermes' / 'benchmark_report.json'
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'timestamp': report.timestamp,
            'project_root': report.project_root,
            'python_version': report.python_version,
            'results': [asdict(r) for r in report.results]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return output_path


def run_benchmark(project_root: str, iterations: int = 10, output: bool = True, advanced: bool = True):
    """Executa benchmark completo."""
    from doxoade.tools.doxcolors import Fore, Style
    
    benchmark = HermesBenchmark(project_root)
    
    print(f"\n{Fore.CYAN}☤ Executando benchmark avançado Hermes...{Style.RESET_ALL}")
    print(f"  Iterações por teste: {iterations}\n")
    
    # Benchmark de startup
    print(f"  [1/4] Benchmarking startup...")
    benchmark.benchmark_startup_advanced(iterations=iterations)
    
    # Benchmark de imports críticos
    print(f"  [2/4] Benchmarking imports críticos...")
    benchmark.benchmark_critical_modules_advanced(iterations=iterations)
    
    # Benchmark de cache
    print(f"  [3/4] Benchmarking cache performance...")
    benchmark.benchmark_cache_performance(iterations=5)
    
    # Gera relatório
    print(f"  [4/4] Gerando relatório...")
    report = benchmark.generate_report()
    
    if output:
        benchmark.print_summary_advanced(report)
        output_path = benchmark.save_report(report)
        print(f"{Fore.GREEN}✔ Relatório salvo em: {output_path}{Style.RESET_ALL}\n")
    
    return report