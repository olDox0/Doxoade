#!/usr/bin/env python3
# doxoade/tools/hermes_systems/build_hbc5.py
"""
Build script para converter arquivos .hermes para formato HBC5.
Uso:
    python build_hbc5.py [arquivo.py] [--all]
"""
import sys
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style

@click.command()
@click.argument('file', required=False, type=click.Path(exists=True))
@click.option('--all', '-a', 'build_all', is_flag=True, help='Converte todos os .hermes para HBC5')
@click.option('--dynamic', '-d', is_flag=True, help='Usa dynamic scanner local')
def main(file, build_all, dynamic):
    """Converte arquivos .hermes para formato HBC5 (zero-compression)."""
    from doxoade.tools.hermes_systems.hermes_compress_hbc5 import HermesCompressorHBC5
    
    project_root = Path.cwd().resolve()
    compressor = HermesCompressorHBC5(str(project_root))
    
    if build_all:
        click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}☤ [HERMES] Convertendo todos os .py para HBC5...{Style.RESET_ALL}")
        
        hermes_dir = project_root / '.doxoade' / 'hermes' / 'build'
        converted = 0
        
        for py_file in project_root.rglob('*.py'):
            if '.doxoade' in str(py_file) or 'venv' in str(py_file):
                continue
            
            try:
                orig_sz, final_sz, hermes_file, dyn_count = compressor.compress_file(
                    py_file, use_dynamic_scan=dynamic
                )
                savings = 100 - ((final_sz / orig_sz) * 100) if orig_sz > 0 else 0
                click.echo(f"  {Fore.GREEN}✔{Style.RESET_ALL} {py_file.name} -> {hermes_file.name} ({savings:.1f}% menor)")
                converted += 1
            except Exception as e:
                click.echo(f"  {Fore.RED}✘{Style.RESET_ALL} {py_file.name}: {e}")
        
        click.echo(f"\n{Fore.GREEN}✔ Convertidos {converted} arquivos para HBC5{Style.RESET_ALL}")
    
    elif file:
        click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}☤ [HERMES] Convertendo {file} para HBC5...{Style.RESET_ALL}")
        
        py_file = Path(file)
        try:
            orig_sz, final_sz, hermes_file, dyn_count = compressor.compress_file(
                py_file, use_dynamic_scan=dynamic
            )
            savings = 100 - ((final_sz / orig_sz) * 100) if orig_sz > 0 else 0
            
            click.echo(f"  {Fore.GREEN}✔ Comprimido: {py_file.name} -> {hermes_file.name}{Style.RESET_ALL}")
            click.echo(f"     Formato: HBC5 (zero-compression)")
            click.echo(f"     Tamanho: {orig_sz} bytes -> {final_sz} bytes ({savings:.1f}% menor)")
            
            if dyn_count > 0:
                click.echo(f"     🔬 Dynamic Scanner: +{dyn_count} tokens locais")
        
        except Exception as e:
            click.echo(f"  {Fore.RED}✘ Erro: {e}{Style.RESET_ALL}")
            sys.exit(1)
    
    else:
        click.echo(click.get_current_context().get_help())

if __name__ == '__main__':
    main()