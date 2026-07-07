# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_diagnose.py
"""
Hermes Diagnostic System v1.0
==============================
Diagnostica problemas no sistema Hermes:
- Valida arquivos .pyd/.so
- Verifica cache de performance
- Analisa métricas de preload
- Detecta módulos corrompidos
"""
import sys
import json
import hashlib
from pathlib import Path
from typing import List, Dict

class HermesDiagnostics:
    """Sistema de diagnóstico do Hermes."""
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.cache_dir = self.root / ".doxoade" / "hermes" / "cache"
        self.native_dir = self.root / "doxoade" / "tools" / "hermes_systems" / "native"
    
    def validate_binary(self, binary_path: Path) -> Dict:
        """Valida um binário .pyd/.so."""
        result = {
            'path': str(binary_path),
            'exists': binary_path.exists(),
            'valid': False,
            'size_kb': 0,
            'error': None
        }
        
        if not binary_path.exists():
            result['error'] = 'File not found'
            return result
        
        try:
            result['size_kb'] = binary_path.stat().st_size / 1024
            
            # Tenta ler como texto para verificar se é binário válido
            try:
                content = binary_path.read_text(encoding='utf-8', errors='strict')
                # Se conseguir ler como texto, não é um binário válido
                result['error'] = 'File appears to be text, not binary (corrupted)'
                return result
            except UnicodeDecodeError:
                # Binário válido (não é texto)
                result['valid'] = True
                return result
            except Exception as e:
                result['error'] = f'Validation error: {e}'
                return result
                
        except Exception as e:
            result['error'] = f'Stat error: {e}'
            return result
    
    def check_performance_cache(self) -> Dict:
        """Verifica o cache de performance."""
        cache_file = self.cache_dir / "performance_metrics.json"
        
        result = {
            'exists': cache_file.exists(),
            'valid': False,
            'modules': 0,
            'avg_speedup': 0.0,
            'error': None
        }
        
        if not cache_file.exists():
            result['error'] = 'Cache file not found'
            return result
        
        try:
            metrics = json.loads(cache_file.read_text())
            result['valid'] = True
            result['modules'] = len(metrics)
            
            if metrics:
                speedups = [m.get('speedup', 1.0) for m in metrics.values()]
                result['avg_speedup'] = sum(speedups) / len(speedups)
            
            return result
        except Exception as e:
            result['error'] = f'Parse error: {e}'
            return result
    
    def check_source_files(self) -> List[Dict]:
        """Verifica arquivos fonte C."""
        results = []
        
        c_files = list(self.native_dir.glob("*.c"))
        
        for c_file in c_files:
            result = {
                'path': str(c_file),
                'name': c_file.name,
                'valid': False,
                'size_kb': 0,
                'error': None
            }
            
            try:
                result['size_kb'] = c_file.stat().st_size / 1024
                content = c_file.read_text(encoding='utf-8', errors='strict')
                
                # Verifica se contém código C válido
                if '#include' not in content and 'int main' not in content:
                    result['error'] = 'File does not appear to be C code'
                    results.append(result)
                    continue
                
                # Verifica se não contém bytes nulos
                if '\x00' in content:
                    result['error'] = 'File contains null bytes (corrupted)'
                    results.append(result)
                    continue
                
                result['valid'] = True
                results.append(result)
                
            except UnicodeDecodeError:
                result['error'] = 'File is not valid UTF-8 text'
                results.append(result)
            except Exception as e:
                result['error'] = f'Error: {e}'
                results.append(result)
        
        return results
    
    def run_full_diagnostic(self) -> Dict:
        """Executa diagnóstico completo."""
        print("\n" + "=" * 70)
        print("  🔍 HERMES DIAGNOSTIC SYSTEM")
        print("=" * 70)
        
        report = {
            'binaries': [],
            'sources': [],
            'cache': {},
            'summary': {
                'total_binaries': 0,
                'valid_binaries': 0,
                'total_sources': 0,
                'valid_sources': 0,
                'cache_valid': False
            }
        }
        
        # 1. Verifica binários
        print("\n[1/3] Verificando binários nativos...")
        binaries = [
            self.native_dir / "hermes_decoder.pyd",
            self.native_dir / "hermes_decoder.so",
            self.native_dir / "hermes_bridge.pyd",
            self.native_dir / "hermes_bridge.so",
        ]
        
        for binary in binaries:
            if binary.exists():
                result = self.validate_binary(binary)
                report['binaries'].append(result)
                report['summary']['total_binaries'] += 1
                if result['valid']:
                    report['summary']['valid_binaries'] += 1
                    print(f"  ✔ {binary.name} ({result['size_kb']:.1f} KB)")
                else:
                    print(f"  ✘ {binary.name}: {result['error']}")
        
        # 2. Verifica fontes C
        print("\n[2/3] Verificando arquivos fonte C...")
        sources = self.check_source_files()
        report['sources'] = sources
        report['summary']['total_sources'] = len(sources)
        report['summary']['valid_sources'] = sum(1 for s in sources if s['valid'])
        
        for source in sources:
            if source['valid']:
                print(f"  ✔ {source['name']} ({source['size_kb']:.1f} KB)")
            else:
                print(f"  ✘ {source['name']}: {source['error']}")
        
        # 3. Verifica cache de performance
        print("\n[3/3] Verificando cache de performance...")
        cache = self.check_performance_cache()
        report['cache'] = cache
        
        if cache['valid']:
            report['summary']['cache_valid'] = True
            print(f"  ✔ Cache válido: {cache['modules']} módulos, speedup médio: {cache['avg_speedup']:.2f}×")
        else:
            print(f"  ✘ Cache: {cache['error']}")
        
        # Resumo
        print("\n" + "=" * 70)
        print("  📊 RESUMO")
        print("=" * 70)
        print(f"  Binários: {report['summary']['valid_binaries']}/{report['summary']['total_binaries']} válidos")
        print(f"  Fontes C: {report['summary']['valid_sources']}/{report['summary']['total_sources']} válidos")
        print(f"  Cache: {'✔ Válido' if report['summary']['cache_valid'] else '✘ Inválido'}")
        
        # Recomendações
        print("\n" + "=" * 70)
        print("  💡 RECOMENDAÇÕES")
        print("=" * 70)
        
        if report['summary']['valid_binaries'] < report['summary']['total_binaries']:
            print("  ⚠ Binários corrompidos detectados!")
            print("    → Execute: python doxoade/tools/hermes_systems/native/build_auto.py")
        
        if not report['summary']['cache_valid']:
            print("  ⚠ Cache de performance inválido!")
            print("    → Execute: doxoade hermes auto-benchmark")
        
        if report['summary']['valid_sources'] < report['summary']['total_sources']:
            print("  ⚠ Arquivos fonte corrompidos!")
            print("    → Restaure os arquivos .c do backup")
        
        print("=" * 70 + "\n")
        
        return report


def diagnose(project_root: str) -> Dict:
    """API pública para diagnóstico."""
    diag = HermesDiagnostics(project_root)
    return diag.run_full_diagnostic()


if __name__ == "__main__":
    import sys
    project_root = Path(__file__).resolve().parents[3]
    report = diagnose(str(project_root))
    
    # Exit code baseado no diagnóstico
    if (report['summary']['valid_binaries'] == report['summary']['total_binaries'] and
        report['summary']['valid_sources'] == report['summary']['total_sources'] and
        report['summary']['cache_valid']):
        sys.exit(0)
    else:
        sys.exit(1)