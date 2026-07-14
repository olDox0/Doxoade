#!/usr/bin/env python3
# doxoade/tools/hermes_systems/build_hbc6.py
"""
Build HBC6 com Filtro Inteligente de Dicionário
===============================================
Estratégia:
- Só inclui N-grams com frequência >= MIN_FREQUENCY (50)
- Dicionário dinâmico (tamanho = tokens usados, não 256 fixos)
- Break-even analysis: compressão deve compensar overhead de parse
"""
import sys
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.hermes_systems.hermes_compress_hbc6 import HBC6Compressor

# ═══════════════════════════════════════════════════════════════════
# DICIONÁRIO GLOBAL DE N-GRAMS (DNA real caçado pelo Hermes Lab)
# ═══════════════════════════════════════════════════════════════════
# Ordenados do MAIOR para o MENOR (greedy matching)
# 🚀 FILTRO: Só N-grams com frequência >= 50 no projeto
GLOBAL_NGRAMS = {
    # 10 opcodes (20 bytes → 2 bytes = economia de 18 bytes)
    # Frequência: 308+ repetições
    'ngram_import_pair_const': [
        'LOAD_CONST', 'LOAD_CONST', 'IMPORT_NAME', 'STORE_NAME',
        'LOAD_CONST', 'LOAD_CONST', 'IMPORT_NAME', 'STORE_NAME',
        'LOAD_CONST', 'LOAD_CONST'
    ],
    
    # 8 opcodes (16 bytes → 2 bytes = economia de 14 bytes)
    # Frequência: 326+ repetições
    'ngram_import_pair': [
        'LOAD_CONST', 'LOAD_CONST', 'IMPORT_NAME', 'STORE_NAME',
        'LOAD_CONST', 'LOAD_CONST', 'IMPORT_NAME', 'STORE_NAME'
    ],
    
    # 6 opcodes (12 bytes → 2 bytes = economia de 10 bytes)
    # Frequência: 443+ repetições
    'ngram_import_const': [
        'LOAD_CONST', 'LOAD_CONST', 'IMPORT_NAME', 'STORE_NAME',
        'LOAD_CONST', 'LOAD_CONST'
    ],
    
    # 4 opcodes (8 bytes → 2 bytes = economia de 6 bytes)
    # Frequência: 490+ repetições
    'ngram_import_simple': [
        'LOAD_CONST', 'LOAD_CONST', 'IMPORT_NAME', 'STORE_NAME'
    ],
}

# Mapeamento reverso: hash -> token_id (0x01 a 0xFF)
TOKEN_MAP = {h: i + 1 for i, h in enumerate(GLOBAL_NGRAMS.keys())}

# ═══════════════════════════════════════════════════════════════════
# ANÁLISE DE BREAK-EVEN
# ═══════════════════════════════════════════════════════════════════
def analyze_break_even():
    """
    Calcula o break-even point: quando a compressão compensa o overhead.
    
    Premissas:
    - Overhead de parse do MACRO_DICT: ~10ms (medido empiricamente)
    - Ganho de I/O por KB economizado: ~2ms (disco lento)
    - Break-even: compressão deve economizar >= 5KB para compensar
    """
    print(f"\n{Fore.CYAN}📊 ANÁLISE DE BREAK-EVEN{Style.RESET_ALL}")
    print(f"  Overhead estimado de parse: ~10ms")
    print(f"  Ganho de I/O por KB: ~2ms")
    print(f"  Break-even: >= 5KB economizados")
    print(f"  Estratégia: Só comprimir arquivos > 10KB")
    print()

@click.command()
@click.option('--all', '-a', 'build_all', is_flag=True, help='Comprime todos os .py para HBC6')
@click.option('--target', '-t', default='.', help='Diretório alvo')
@click.option('--min-size-kb', default=10.0, help='Tamanho mínimo do arquivo para compressão (KB)')
def main(build_all, target, min_size_kb):
    """🧬 Build HBC6 com Filtro Inteligente."""
    from doxoade.tools.doxcolors import Fore, Style
    
    project_root = Path.cwd().resolve()
    build_dir = project_root / '.doxoade' / 'hermes' / 'build'
    build_dir.mkdir(parents=True, exist_ok=True)
    
    click.echo(f"\n{Fore.MAGENTA}{Style.BRIGHT}🧬 [HERMES HBC6] Build com Filtro Inteligente{Style.RESET_ALL}")
    click.echo(f"  Dicionário Global: {len(GLOBAL_NGRAMS)} N-grams (freq >= 50)")
    click.echo(f"  Tamanho mínimo: {min_size_kb} KB")
    
    # Análise de break-even
    analyze_break_even()
    
    compressor = HBC6Compressor(project_root, GLOBAL_NGRAMS, TOKEN_MAP)
    
    if build_all:
        exclude_dirs = {'.venv', 'venv', '__pycache__', '.doxoade', '.git', 
                        'node_modules', 'build', 'dist', 'tests', 'test'}
        py_files = [
            p for p in project_root.rglob('*.py')
            if not any(exclude in p.parts for exclude in exclude_dirs)
            and p.stat().st_size >= min_size_kb * 1024  # 🚀 FILTRO DE TAMANHO
        ]
        
        click.echo(f"  Varrendo {len(py_files)} arquivos >= {min_size_kb}KB...\n")
        
        total_saved = 0
        total_patches = 0
        total_tokens = 0
        files_compressed = 0
        files_skipped = 0
        
        for py_file in py_files:
            try:
                file_size_kb = py_file.stat().st_size / 1024
                
                module_name = str(py_file.relative_to(project_root).with_suffix('')).replace('\\', '.')
                output_path = build_dir / f"{module_name}.hbc6"
                
                result = compressor.compress_file(py_file, output_path)
                
                saved = result['original_bytes'] - result['hbc6_bytes']
                saved_kb = saved / 1024
                
                total_saved += saved
                total_patches += result['patches_applied']
                total_tokens += result['tokens_applied']
                files_compressed += 1
                
                if result['patches_applied'] > 0 or result['tokens_applied'] > 0:
                    click.echo(f"  {Fore.GREEN}✔{Style.RESET_ALL} {py_file.name:<30} | "
                               f"Economia: {saved_kb:>5.1f}KB | "
                               f"Macros: {result['patches_applied']:<3} | "
                               f"Tokens: {result['tokens_applied']:<3}")
            except Exception as e:
                click.echo(f"  {Fore.RED}✘{Style.RESET_ALL} {py_file.name}: {e}")

        
        click.echo(f"\n{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}")
        click.echo(f"  {Fore.GREEN}✔ HBC6 Build Concluído!{Style.RESET_ALL}")
        click.echo(f"  Arquivos comprimidos: {files_compressed}")
        click.echo(f"  Arquivos skipados: {files_skipped}")
        click.echo(f"  Economia Total: {total_saved / 1024:.2f} KB")
        click.echo(f"  Macros Aplicadas: {total_patches}")
        click.echo(f"  Tokens Aplicados: {total_tokens}")
        click.echo(f"{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}\n")
    else:
        click.echo(click.get_current_context().get_help())

if __name__ == '__main__':
    main()