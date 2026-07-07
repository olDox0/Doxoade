# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_auto_preload.py
"""
Hermes Auto-Preload System v2.1
================================
Carregamento inteligente de módulos críticos com:
- Cache de performance (só preloads se ganho > 1.5×)
- Smart Preload (lê métricas antes de pré-carregar)
- Fallback automático
- Telemetria de boot time
- Invalidação baseada em hash
"""
import sys
import os
import time
import json
import hashlib
from pathlib import Path
from typing import List, Set, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configurações
CACHE_DIR = Path(".doxoade/hermes/cache")
CRITICAL_MODULES_CACHE = CACHE_DIR / "critical_modules.json"
PERFORMANCE_CACHE = CACHE_DIR / "performance_metrics.json"
PRELOAD_THRESHOLD = 1.5  # Ajustado: só preloads se ganho > 50%
MAX_WORKERS = 4  # Threads paralelas

class HermesAutoPreloader:
    """Sistema de preload inteligente com cache de performance."""
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.cache_dir = self.root / ".doxoade" / "hermes" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_cache = self.cache_dir / "performance_metrics.json"
        self.critical_cache = self.cache_dir / "critical_modules.json"
        
    def _get_module_hash(self, module_name: str) -> str:
        """Gera hash do módulo para invalidação de cache."""
        try:
            # Converte nome do módulo para path do arquivo
            module_path = module_name.replace('.', '/') + '.py'
            full_path = self.root / module_path
            
            if not full_path.exists():
                return "unknown"
            
            content = full_path.read_bytes()
            return hashlib.sha256(content).hexdigest()[:16]
        except Exception:
            return "unknown"
    
    def _load_performance_cache(self) -> dict:
        """Carrega métricas de performance salvas."""
        if self.metrics_cache.exists():
            try:
                return json.loads(self.metrics_cache.read_text())
            except Exception:
                return {}
        return {}
    
    def _save_performance_cache(self, metrics: dict):
        """Salva métricas de performance."""
        try:
            self.metrics_cache.write_text(json.dumps(metrics, indent=2))
        except Exception as e:
            print(f"[HERMES] Warning: Failed to save performance cache: {e}")
    
    def _benchmark_module(self, module_name: str) -> dict:
        """Mede tempo de import de um módulo."""
        # Remove do cache se existir
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        start = time.perf_counter_ns()
        try:
            __import__(module_name)
            elapsed = (time.perf_counter_ns() - start) / 1_000_000
            return {
                "module": module_name,
                "time_ms": elapsed,
                "success": True
            }
        except Exception as e:
            return {
                "module": module_name,
                "time_ms": 0,
                "success": False,
                "error": str(e)
            }
    
    def _should_preload(self, module_name: str, metrics: dict) -> bool:
        """
        Smart Preload: Decide se um módulo deve ser pré-carregado.
        
        Critérios:
        1. Se não tem métricas, tenta preloads (primeira execução)
        2. Se o módulo mudou (hash diferente), reavalia
        3. Se o ganho é significativo (>= PRELOAD_THRESHOLD), preloads
        4. Se o módulo está na blacklist, não preloads
        """
        # Blacklist de módulos que nunca devem ser pré-carregados
        blacklist = {
            'doxoade.tools.hermes_systems',
            'doxoade.tools.vulcan',
            'doxoade.tools.aegis',
            'doxoade.core_database',
            'doxoade.boot',
        }
        
        if any(module_name.startswith(b) for b in blacklist):
            return False
        
        # Se não tem métricas, tenta preloads (primeira execução)
        if module_name not in metrics:
            return True
        
        cached = metrics[module_name]
        current_hash = self._get_module_hash(module_name)
        
        # Se o módulo mudou, reavalia
        if cached.get("hash") != current_hash:
            return True
        
        # Se o ganho é significativo, preloads
        speedup = cached.get("speedup", 1.0)
        return speedup >= PRELOAD_THRESHOLD
    
    def preload_critical_modules(self, modules: List[str], verbose: bool = False) -> dict:
        """
        Pré-carrega módulos críticos com cache inteligente.
        
        Returns:
            dict com estatísticas:
            - 'loaded': número de módulos carregados com sucesso
            - 'failed': número de módulos que falharam
            - 'fallback': número de módulos que usaram fallback .py
            - 'skipped': número de módulos pulados (cache hit ou ganho insuficiente)
            - 'total_time_ms': tempo total
        """
        stats = {
            'loaded': [],
            'failed': [],
            'fallback': [],
            'skipped': [],
            'total_time_ms': 0,
            'cache_hits': 0
        }
        
        start = time.perf_counter_ns()
        
        # Carrega métricas de performance
        metrics = self._load_performance_cache()
        
        # Filtra módulos que devem ser pré-carregados
        to_preload = []
        for mod in modules:
            if self._should_preload(mod, metrics):
                to_preload.append(mod)
            else:
                stats['skipped'].append(mod)
                stats['cache_hits'] += 1
        
        if verbose:
            print(f"[HERMES] Preloading {len(to_preload)} modules ({len(stats['skipped'])} skipped)")
        
        # Preloads em paralelo
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(self._benchmark_module, mod): mod for mod in to_preload}
            
            for future in as_completed(futures):
                result = future.result()
                mod_name = result["module"]
                
                if result["success"]:
                    stats['loaded'].append(mod_name)
                    
                    # Atualiza métricas
                    metrics[mod_name] = {
                        "hash": self._get_module_hash(mod_name),
                        "time_ms": result["time_ms"],
                        "speedup": 1.5,  # Placeholder (será atualizado pelo benchmark)
                        "last_preload": time.time()
                    }
                else:
                    stats['failed'].append({
                        'module': mod_name,
                        'error': result.get("error", "unknown")
                    })
        
        # Salva métricas atualizadas
        self._save_performance_cache(metrics)
        
        stats["total_time_ms"] = (time.perf_counter_ns() - start) / 1_000_000
        
        if verbose:
            print(f"[HERMES] Preload complete: {len(stats['loaded'])} loaded, "
                  f"{len(stats['skipped'])} skipped, {len(stats['failed'])} failed "
                  f"({stats['total_time_ms']:.1f}ms)")
        
        return stats
    
    def update_performance_metrics(self, module_name: str, python_time: float, mercury_time: float):
        """Atualiza métricas de performance com dados reais."""
        metrics = self._load_performance_cache()
        
        if module_name in metrics:
            speedup = python_time / mercury_time if mercury_time > 0 else 1.0
            
            metrics[module_name].update({
                "python_time_ms": python_time,
                "mercury_time_ms": mercury_time,
                "speedup": speedup,
                "last_benchmark": time.time()
            })
            
            self._save_performance_cache(metrics)
    
    def get_critical_modules(self) -> List[str]:
        """Retorna lista de módulos críticos baseada em métricas."""
        metrics = self._load_performance_cache()
        
        # Ordena por speedup (maior primeiro)
        sorted_modules = sorted(
            metrics.items(),
            key=lambda x: x[1].get("speedup", 1.0),
            reverse=True
        )
        
        # Retorna top 20 módulos com speedup > PRELOAD_THRESHOLD
        return [
            mod for mod, data in sorted_modules[:20]
            if data.get("speedup", 1.0) >= PRELOAD_THRESHOLD
        ]


# API Pública
def auto_preload(project_root: str, modules: Optional[List[str]] = None, verbose: bool = False) -> dict:
    """
    Pré-carrega módulos críticos automaticamente.
    
    Args:
        project_root: Raiz do projeto
        modules: Lista de módulos (None = usa cache)
        verbose: Mostra logs detalhados
    
    Returns:
        dict com estatísticas de preload
    """
    preloader = HermesAutoPreloader(project_root)
    
    # Se não especificou módulos, usa cache
    if modules is None:
        modules = preloader.get_critical_modules()
        
        # Se cache vazio, usa lista padrão
        if not modules:
            modules = [
                "doxoade.tools.doxcolors",
                "doxoade.tools.error_info",
                "doxoade.tools.filesystem",
                "doxoade.tools.git",
                "doxoade.rescue",
                "doxoade.tools.aegis.nexus_db",
                "doxoade.tools.alexandria.engine",
                "doxoade.tools.telemetry_tools.logger",
                "doxoade.tools.aegis.aegis_utils",
                "doxoade.core_database",
                "doxoade.tools.display",
                "doxoade.tools.aegis.aegis_core",
                "doxoade.cli",
                "doxoade.tools.analysis",
                "doxoade.tools.streamer",
                "doxoade.tools.vulcan.opt_cache",
                "doxoade.tools.vulcan.lib_optimizer",
                "doxoade.tools.vulcan.meta_finder",
                "doxoade.tools.vulcan.bridge",
                "doxoade.dnm"
            ]
    
    return preloader.preload_critical_modules(modules, verbose=verbose)


def update_metrics(project_root: str, module_name: str, python_time: float, mercury_time: float):
    """Atualiza métricas de performance de um módulo."""
    preloader = HermesAutoPreloader(project_root)
    preloader.update_performance_metrics(module_name, python_time, mercury_time)


if __name__ == "__main__":
    # Teste rápido
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    
    stats = auto_preload(".", verbose=True)
    print(f"\nResultados:")
    print(f"  Carregados: {len(stats['loaded'])}")
    print(f"  Cache hits: {stats['cache_hits']}")
    print(f"  Falhas: {len(stats['failed'])}")
    print(f"  Tempo total: {stats['total_time_ms']:.1f}ms")