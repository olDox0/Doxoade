# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_metrics.py
"""
Hermes Metrics - Sistema de Medição e Cobertura.
Responsável por coletar métricas em cada etapa do pipeline de compressão
e gerar relatórios de cobertura do dicionário.
"""
import json
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from collections import Counter


@dataclass
class CompressionMetrics:
    """Métricas de um único arquivo comprimido."""
    file_path: str
    original_size: int = 0
    optimized_size: int = 0
    compressed_size: int = 0
    
    original_lines: int = 0
    optimized_lines: int = 0
    tokenized_lines: int = 0
    kept_lines: int = 0
    
    tokens_applied: Dict[str, int] = field(default_factory=dict)
    uncovered_patterns: List[str] = field(default_factory=list)
    
    compression_time_ms: float = 0.0
    decompression_time_ms: float = 0.0
    
    @property
    def dictionary_coverage(self) -> float:
        """% de linhas que foram tokenizadas."""
        if self.original_lines == 0:
            return 0.0
        return (self.tokenized_lines / self.original_lines) * 100
    
    @property
    def size_reduction(self) -> float:
        """% de redução de tamanho (original → comprimido)."""
        if self.original_size == 0:
            return 0.0
        return (1 - (self.compressed_size / self.original_size)) * 100
    
    @property
    def optimization_gain(self) -> float:
        """% de redução pela otimização pré-compressão."""
        if self.original_size == 0:
            return 0.0
        return (1 - (self.optimized_size / self.original_size)) * 100


@dataclass
class ProjectMetrics:
    """Métricas agregadas do projeto."""
    project_root: str
    total_files: int = 0
    compressed_files: int = 0
    
    total_original_size: int = 0
    total_compressed_size: int = 0
    
    total_original_lines: int = 0
    total_tokenized_lines: int = 0
    
    files: List[CompressionMetrics] = field(default_factory=list)
    
    @property
    def overall_coverage(self) -> float:
        """Cobertura média do dicionário no projeto."""
        if self.total_original_lines == 0:
            return 0.0
        return (self.total_tokenized_lines / self.total_original_lines) * 100
    
    @property
    def overall_reduction(self) -> float:
        """Redução total de tamanho no projeto."""
        if self.total_original_size == 0:
            return 0.0
        return (1 - (self.total_compressed_size / self.total_original_size)) * 100
    
    def add_file(self, metrics: CompressionMetrics):
        self.files.append(metrics)
        self.compressed_files += 1
        self.total_original_size += metrics.original_size
        self.total_compressed_size += metrics.compressed_size
        self.total_original_lines += metrics.original_lines
        self.total_tokenized_lines += metrics.tokenized_lines


class HermesMetricsCollector:
    """Coletor de métricas durante a compressão."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.metrics_file = self.project_root / '.doxoade' / 'hermes' / 'metrics.json'
        self.project_metrics = ProjectMetrics(project_root=str(self.project_root))
    
    def analyze_file(self, py_file: Path, encoder: dict) -> CompressionMetrics:
        """Analisa um arquivo Python e calcula métricas de cobertura."""
        metrics = CompressionMetrics(file_path=str(py_file))
        
        try:
            content = py_file.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            metrics.uncovered_patterns.append(f"Erro de leitura: {e}")
            return metrics
        
        metrics.original_size = len(content.encode('utf-8'))
        lines = content.splitlines()
        metrics.original_lines = len(lines)
        
        # Análise linha por linha
        token_counter = Counter()
        uncovered = []
        compressed_size = 0  # ← NOVO: Calcula tamanho comprimido real
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                compressed_size += 1  # Linha vazia = 1 byte (\n)
                continue
            
            if stripped in encoder:
                token = encoder[stripped]
                token_counter[str(token)] += 1
                metrics.tokenized_lines += 1
                # chr(token) terá exatos 3 bytes em U+E000 no file system
                compressed_size += len(chr(token).encode('utf-8')) + 1
            else:
                metrics.kept_lines += 1
                compressed_size += len(line.encode('utf-8')) + 1  # Linha original + \n
                
                if self._is_interesting_line(stripped):
                    uncovered.append(stripped)
        
        metrics.compressed_size = compressed_size  # ← NOVO: Atribui o tamanho
        metrics.tokens_applied = dict(token_counter)
        
        # Top 10 padrões não cobertos
        uncovered_counter = Counter(uncovered)
        metrics.uncovered_patterns = [
            pattern for pattern, _ in uncovered_counter.most_common(10)
        ]
        
        return metrics
    
    def _is_interesting_line(self, line: str) -> bool:
        """Filtra linhas triviais (comentários, strings vazias)."""
        if not line or line.startswith('#'):
            return False
        if len(line) < 5:
            return False
        if line.startswith(('return', 'pass', 'break', 'continue')):
            return False
        return True
    
    def analyze_project(self, encoder: dict, target: str = '.') -> ProjectMetrics:
        """Analisa todos os .py do projeto."""
        target_path = Path(target).resolve()
        self.project_metrics.total_files = 0
        
        for py_file in target_path.rglob('*.py'):
            # Ignora venv, .doxoade, __pycache__, etc
            if any(part in py_file.parts for part in [
                'venv', '.venv', '.doxoade', '__pycache__', 
                'build', 'dist', 'node_modules', 'tests'
            ]):
                continue
            
            self.project_metrics.total_files += 1
            metrics = self.analyze_file(py_file, encoder)
            self.project_metrics.add_file(metrics)
        
        return self.project_metrics
    
    def save_report(self) -> Path:
        """Salva o relatório em JSON."""
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            'project_root': self.project_metrics.project_root,
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'total_files': self.project_metrics.total_files,
                'compressed_files': self.project_metrics.compressed_files,
                'total_original_size': self.project_metrics.total_original_size,
                'total_compressed_size': self.project_metrics.total_compressed_size,
                'overall_coverage': round(self.project_metrics.overall_coverage, 2),
                'overall_reduction': round(self.project_metrics.overall_reduction, 2),
            },
            'files': [asdict(f) for f in self.project_metrics.files]
        }
        
        with open(self.metrics_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return self.metrics_file
    
    def print_report(self):
        """Imprime relatório formatado no terminal."""
        from doxoade.tools.doxcolors import Fore, Style
        
        pm = self.project_metrics
        
        print(f"\n{Fore.CYAN}{Style.BRIGHT}╔══════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{Style.BRIGHT}║         ☤ HERMES METRICS REPORT                         ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{Style.BRIGHT}╚══════════════════════════════════════════════════════════╝{Style.RESET_ALL}\n")
        
        # Resumo geral
        print(f"{Fore.WHITE}{Style.BRIGHT}■ RESUMO DO PROJETO{Style.RESET_ALL}")
        print(f"  {Fore.CYAN}Total de arquivos:{Style.RESET_ALL}  {pm.total_files}")
        print(f"  {Fore.CYAN}Tamanho original:{Style.RESET_ALL}   {pm.total_original_size:,} bytes")
        print(f"  {Fore.CYAN}Tamanho comprimido:{Style.RESET_ALL} {pm.total_compressed_size:,} bytes")
        
        reduction_color = Fore.GREEN if pm.overall_reduction > 10 else Fore.YELLOW
        print(f"  {Fore.CYAN}Redução total:{Style.RESET_ALL}      {reduction_color}{pm.overall_reduction:.2f}%{Style.RESET_ALL}")
        
        coverage_color = Fore.GREEN if pm.overall_coverage > 30 else Fore.YELLOW
        print(f"  {Fore.CYAN}Cobertura do dict:{Style.RESET_ALL}  {coverage_color}{pm.overall_coverage:.2f}%{Style.RESET_ALL}")
        print(f"  {Fore.CYAN}Linhas tokenizadas:{Style.RESET_ALL} {pm.total_tokenized_lines:,} / {pm.total_original_lines:,}")
        
        # Top 10 arquivos por cobertura
        print(f"\n{Fore.WHITE}{Style.BRIGHT}■ TOP 10 ARQUIVOS POR COBERTURA{Style.RESET_ALL}")
        sorted_files = sorted(pm.files, key=lambda f: f.dictionary_coverage, reverse=True)[:10]
        
        for f in sorted_files:
            file_name = Path(f.file_path).name
            cov_color = Fore.GREEN if f.dictionary_coverage > 30 else Fore.YELLOW
            red_color = Fore.GREEN if f.size_reduction > 10 else Fore.YELLOW
            print(f"  {cov_color}{f.dictionary_coverage:5.1f}%{Style.RESET_ALL} cov | "
                  f"{red_color}{f.size_reduction:5.1f}%{Style.RESET_ALL} red | "
                  f"{Fore.WHITE}{file_name:<30}{Style.RESET_ALL} "
                  f"({f.tokenized_lines}/{f.original_lines} linhas)")
        
        # Top 10 padrões não cobertos (globais)
        print(f"\n{Fore.WHITE}{Style.BRIGHT}■ TOP 10 PADRÕES NÃO COBERTOS (oportunidades){Style.RESET_ALL}")
        all_uncovered = Counter()
        for f in pm.files:
            all_uncovered.update(f.uncovered_patterns)
        
        for pattern, count in all_uncovered.most_common(10):
            preview = pattern[:60] + ('...' if len(pattern) > 60 else '')
            print(f"  {Fore.MAGENTA}{count:4}x{Style.RESET_ALL} | {Fore.WHITE}{preview}{Style.RESET_ALL}")
        
        print(f"\n{Fore.CYAN}Relatório completo salvo em:{Style.RESET_ALL} {self.metrics_file}")