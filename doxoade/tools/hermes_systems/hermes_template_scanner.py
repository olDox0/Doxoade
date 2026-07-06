# doxoade/tools/hermes_systems/hermes_template_scanner.py
"""
Hermes Template Scanner v1.0 - Identificação de Padrões Estruturais.
Escaneia código Python otimizado e identifica templates repetitivos.

Templates identificados:
- IMPORT_AS: from module import name as alias
- IMPORT_FROM: from module import names
- CLASS_DEF: class Name(Base):
- FUNCTION_DEF: def name(args) -> return:
- DECORATOR: @decorator
- TRY_EXCEPT: try: ... except Exception:
- WITH_STATEMENT: with context as var:

Esses templates são substituídos por tokens únicos no bytecode,
reduzindo drasticamente o tamanho do dicionário Hermes.
"""
import re
import ast
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass


@dataclass
class TemplateMatch:
    """Representa um match de template no código."""
    template_name: str
    original_text: str
    groups: List[str]
    line_number: int
    column: int


class HermesTemplateScanner:
    """Identifica padrões estruturais repetitivos no código."""
    
    # Templates pré-definidos (ordem de prioridade)
    TEMPLATES = {
        'IMPORT_AS': r'from\s+([\w.]+)\s+import\s+(\w+)\s+as\s+(Ia\d+)',
        'IMPORT_FROM': r'from\s+([\w.]+)\s+import\s+([\w,\s]+)',
        'IMPORT_DIRECT': r'import\s+([\w.]+)(?:\s+as\s+(Ia\d+))?',
        'CLASS_DEF': r'class\s+(\w+)\s*\(([^)]*)\):',
        'FUNCTION_DEF': r'def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([\w\[\],\s|]+))?:',
        'DECORATOR': r'@([\w.]+)(?:\(([^)]*)\))?',
        'TRY_EXCEPT': r'try:\s*\n\s*(.+?)\s*\n\s*except\s+(\w+)(?:\s+as\s+(\w+))?:',
        'WITH_STATEMENT': r'with\s+([\w.()]+)\s+as\s+(\w+):',
    }
    
    def __init__(self):
        self.template_counts = Counter()
        self.template_matches: Dict[str, List[TemplateMatch]] = {}
        
    def scan_file(self, file_path: Path) -> Dict[str, List[TemplateMatch]]:
        """
        Escaneia arquivo e retorna templates encontrados.
        
        Returns:
            {template_name: [TemplateMatch, ...]}
        """
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception:
            return {}
        
        results = {}
        
        for template_name, pattern in self.TEMPLATES.items():
            matches = []
            for match in re.finditer(pattern, content, re.MULTILINE):
                template_match = TemplateMatch(
                    template_name=template_name,
                    original_text=match.group(0),
                    groups=list(match.groups()),
                    line_number=content[:match.start()].count('\n') + 1,
                    column=match.start() - content.rfind('\n', 0, match.start())
                )
                matches.append(template_match)
                self.template_counts[template_name] += 1
            
            if matches:
                results[template_name] = matches
                if template_name not in self.template_matches:
                    self.template_matches[template_name] = []
                self.template_matches[template_name].extend(matches)
        
        return results
    
    def scan_directory(self, dir_path: Path) -> Dict[str, int]:
        """Escaneia diretório e retorna contagem de templates."""
        for py_file in dir_path.rglob('*.py'):
            if any(part in py_file.parts for part in ['.venv', 'venv', '__pycache__', '.doxoade']):
                continue
            self.scan_file(py_file)
        
        return dict(self.template_counts)
    
    def get_template_stats(self) -> Dict[str, Dict]:
        """Retorna estatísticas dos templates encontrados."""
        stats = {}
        
        for template_name, count in self.template_counts.items():
            matches = self.template_matches.get(template_name, [])
            
            # Calcula economia estimada
            if matches:
                avg_match_len = sum(len(m.original_text) for m in matches) / len(matches)
                template_overhead = 20  # bytes do template + dados
                total_original = sum(len(m.original_text) for m in matches)
                total_compressed = template_overhead + (len(matches) * 10)  # ~10 bytes por dado
                savings = total_original - total_compressed
                savings_pct = (savings / total_original * 100) if total_original > 0 else 0
                
                stats[template_name] = {
                    'count': count,
                    'avg_length': avg_match_len,
                    'total_original': total_original,
                    'total_compressed': total_compressed,
                    'savings_bytes': savings,
                    'savings_pct': savings_pct,
                }
        
        return stats


def scan_templates(project_root: str) -> Dict[str, int]:
    """Função auxiliar para escanear templates no projeto."""
    scanner = HermesTemplateScanner()
    return scanner.scan_directory(Path(project_root))


if __name__ == '__main__':
    import sys
    from doxoade.tools.doxcolors import Fore, Style
    
    project_root = Path.cwd()
    scanner = HermesTemplateScanner()
    
    print(f"\n{Fore.CYAN}🔍 Hermes Template Scanner{Style.RESET_ALL}\n")
    
    counts = scanner.scan_directory(project_root)
    stats = scanner.get_template_stats()
    
    print(f"{Fore.WHITE}{'Template':<20} {'Count':<10} {'Savings':<15} {'%':<10}{Style.RESET_ALL}")
    print("-" * 60)
    
    for template_name, data in sorted(stats.items(), key=lambda x: x[1]['savings_bytes'], reverse=True):
        color = Fore.GREEN if data['savings_pct'] > 50 else Fore.YELLOW
        print(f"{template_name:<20} {data['count']:<10} {data['savings_bytes']:>10,} B {color}{data['savings_pct']:>6.1f}%{Style.RESET_ALL}")
    
    total_savings = sum(d['savings_bytes'] for d in stats.values())
    print(f"\n{Fore.GREEN}💰 Economia total estimada: {total_savings:,} bytes{Style.RESET_ALL}\n")
