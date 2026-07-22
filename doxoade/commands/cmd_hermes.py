# -*- coding: utf-8 -*-
# doxoade/commands/cmd_hermes.py
import os
import dis
import glob
import click
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.hermes_systems.hermes_scanner import run_hermes_reconnaissance
from doxoade.tools.hermes_systems.hermes_dict.hermes_builder import HermesDictionaryBuilder
from doxoade.tools.hermes_systems.hermes_compress import HermesCompressor

from doxoade.tools.error_info import formated_traceback

@click.group('hermes', invoke_without_command=True)
@click.pass_context
def hermes_group(ctx):
    """☤ Sistema Hermes: Compressed Data Processing."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@hermes_group.command('scan')
@click.option('--target', '-t', default='.', help="Diretório alvo para o scan.")
def scan(target):
    """[Fase 1] Mapeia a topologia e frequência de código (Imports)."""
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}☤ [HERMES] Iniciando Scanner de Mapeamento em: {target}{Style.RESET_ALL}")
    
    results, mapping = run_hermes_reconnaissance(target)
    
    if not results:
        click.echo(f"{Fore.RED}✘ Nenhum padrão encontrado ou diretório vazio.{Style.RESET_ALL}")
        return

    click.echo(f"\n{Fore.GREEN}Top Padrões (Candidatos ao Dicionário Binário):{Style.RESET_ALL}")
    click.echo(f"{Style.DIM}{'-'*80}{Style.RESET_ALL}")
    
    # 🚀 CORREÇÃO: O scanner retorna 3 elementos (pattern, freq, type)
    for pattern, count, _pattern_type in results:
        source_code = mapping[pattern]
        # Trunca a exibição para manter a UI limpa no terminal
        display_hash = pattern if len(pattern) <= 40 else pattern[:37] + "..."
        display_code = source_code if len(source_code) <= 35 else source_code[:32] + "..."
        
        click.echo(f"  {Fore.YELLOW}[{display_hash}]{Style.RESET_ALL} {count:4} reps | {Fore.WHITE}{display_code}{Style.RESET_ALL}")
        
    click.echo(f"{Style.DIM}{'-'*80}{Style.RESET_ALL}")
    click.echo(f"Ação sugerida: Os itens com alta ocorrência receberão IDs de 1 byte (0x01 a 0xFF).")
    
@hermes_group.command('build')
@click.argument('file', required=False, type=click.Path(exists=True))
@click.option('--target', '-t', default='.', help="Diretório alvo para scan.")
@click.option('--optimize', '-o', is_flag=True, help="Aplica otimizações pré-compressão.")
@click.option('--dynamic', '-d', is_flag=True, help="Usa dynamic scanner local (HBC3).")
@click.option('--hbc4', is_flag=True, help="Usa formato HBC4 (sem LZMA, mais rápido).")
@click.option('--hbc5', is_flag=True, help="Usa formato HBC5 (sem LZMA + flags, mais rápido ainda).")
@click.option('--all', '-a', 'build_all', is_flag=True, help="Comprime TODOS os .py do projeto.")
@click.option('--workers', '-w', default=4, help="Threads paralelas para --all.")
@click.option('--max-tokens', default=5000, help="Número máximo de tokens no dicionário global.")
def build(file, target, optimize, dynamic, hbc4, hbc5, build_all, workers, max_tokens):
    """[Fase 2] Gera o Dicionário e Comprime arquivos para .hermes."""
    from doxoade.tools.hermes_systems.hermes_loader import HermesLoader, verify_lossless
    from doxoade.tools.hermes_systems.hermes_compress import HermesCompressor
    
    click.echo(f"\n{Fore.MAGENTA}{Style.BRIGHT}☤ [HERMES] Construindo Matriz de Compressão...{Style.RESET_ALL}")
    project_root = Path.cwd().resolve()
    
    # ─────────────────────────────────────────────────────────────
    # MODO BATCH (--all)
    # ─────────────────────────────────────────────────────────────
    if build_all:
        _run_batch_build(project_root, optimize, dynamic, workers, hbc4, hbc5)
        return
    
    # ─────────────────────────────────────────────────────────────
    # MODO ARQUIVO ESPECÍFICO
    # ─────────────────────────────────────────────────────────────
    if file:
        _run_single_build(file, project_root, optimize, dynamic, hbc4, hbc5)
        return
    
    # ─────────────────────────────────────────────────────────────
    # MODO SCAN COMPLETO (gera dicionário + PoC)
    # ─────────────────────────────────────────────────────────────
    click.echo(f"  {Fore.CYAN}▶ Modo: Scan completo + Prova de Conceito{Style.RESET_ALL}")
    click.echo(f"  {Fore.CYAN}▶ Limite de tokens: {max_tokens}{Style.RESET_ALL}")
    
    results, mapping = run_hermes_reconnaissance(target, max_tokens=max_tokens)
    builder = HermesDictionaryBuilder(target)
    token_count, dict_path = builder.build_from_scan(results, mapping, max_tokens=max_tokens)
    
    click.echo(f"  {Fore.GREEN}✔ Dicionário Master criado em: {dict_path.name} ({token_count} tokens){Style.RESET_ALL}")
    
    compressor = HermesCompressor(target)
    main_file = Path(target) / "doxoade" / "__main__.py"
    
    if main_file.exists():
        result = compressor.compress_file(main_file, use_hbc4=hbc4, use_hbc5=hbc5)
        
        if len(result) == 4:
            orig_sz, new_sz, hermes_file, _ = result
        else:
            orig_sz, new_sz, hermes_file = result
        
        savings = 100 - ((new_sz / orig_sz) * 100) if orig_sz > 0 else 0
        fmt = "HBC5" if hbc5 else ("HBC4" if hbc4 else "HBC3")
        
        click.echo(f"  {Fore.CYAN}✔ Prova de Conceito: {main_file.name} -> {hermes_file.name}{Style.RESET_ALL}")
        click.echo(f"     Formato: {fmt}")
        click.echo(f"     Tamanho: {orig_sz} bytes -> {new_sz} bytes ({Fore.GREEN}-{savings:.1f}%{Style.RESET_ALL})")

def _run_batch_build(project_root: Path, optimize: bool, dynamic: bool, workers: int, hbc4: bool = False, hbc5: bool = False):
    """Comprime todos os .py do projeto em paralelo."""
    import concurrent.futures
    from doxoade.tools.hermes_systems.hermes_preprocessor import preprocess_for_hermes
    
    # Coleta arquivos (ignora diretórios irrelevantes)
    exclude_dirs = {'.venv', 'venv', '__pycache__', '.doxoade', '.git', 
                    'node_modules', 'build', 'dist', 'tests', 'test'}
    py_files = [
        p for p in project_root.rglob('*.py')
        if not any(exclude in p.parts for exclude in exclude_dirs)
    ]
    
    click.echo(f"  {Fore.CYAN}▶ Modo: Batch ({len(py_files)} arquivos){Style.RESET_ALL}")
    click.echo(f"  {Fore.CYAN}▶ Workers: {workers} | Otimização: {optimize} | Dinâmico: {dynamic} | HBC5: {hbc5}{Style.RESET_ALL}\n")
    
    stats = {
        'success': 0,
        'failed': 0,
        'total_saved_bytes': 0,
        'total_dyn_tokens': 0,
        'hbc1': 0,
        'hbc3': 0,
        'hbc4': 0,
        'hbc5': 0,
    }
    
    def process_file(py_file: Path):
        try:
            optimized_content = None
            if optimize:
                optimized_content, _ = preprocess_for_hermes(py_file, str(project_root))
            
            compressor = HermesCompressor(str(project_root))
            result = compressor.compress_file(
                py_file, optimized_content, use_dynamic_scan=dynamic, use_hbc4=hbc4, use_hbc5=hbc5
            )
            
            if len(result) == 4:
                orig_sz, new_sz, hermes_file, dyn_tokens = result
            else:
                orig_sz, new_sz, hermes_file = result
                dyn_tokens = 0
            
            saved = orig_sz - new_sz
            fmt = 'HBC5' if hbc5 else ('HBC4' if hbc4 else ('HBC3' if dyn_tokens > 0 else 'HBC1'))
            
            return {
                'ok': True,
                'name': py_file.name,
                'saved': saved,
                'dyn_tokens': dyn_tokens,
                'format': fmt,
            }
        except Exception as e:
            return {'ok': False, 'name': py_file.name, 'error': str(e)[:80]}
    
    # Execução paralela
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_file, f): f for f in py_files}
        
        for future in concurrent.futures.as_completed(futures):
            r = future.result()
            
            if r['ok']:
                stats['success'] += 1
                stats['total_saved_bytes'] += r['saved']
                stats['total_dyn_tokens'] += r['dyn_tokens']
                
                if r['format'] == 'HBC5':
                    stats['hbc5'] += 1
                elif r['format'] == 'HBC4':
                    stats['hbc4'] += 1
                elif r['format'] == 'HBC3':
                    stats['hbc3'] += 1
                else:
                    stats['hbc1'] += 1
            else:
                stats['failed'] += 1
                click.echo(f"  {Fore.RED}✘ {r['name']}: {r['error']}{Style.RESET_ALL}")
    
    # Resumo final
    saved_mb = stats['total_saved_bytes'] / 1024 / 1024
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}{'═'*60}{Style.RESET_ALL}")
    click.echo(f"{Fore.GREEN}✔ Batch concluído{Style.RESET_ALL}")
    click.echo(f"  Sucesso: {stats['success']}/{len(py_files)} arquivos")
    click.echo(f"  Falhas:  {stats['failed']}")
    click.echo(f"  HBC1: {stats['hbc1']} | HBC3: {stats['hbc3']} | HBC4: {stats['hbc4']} | HBC5: {stats['hbc5']}")
    click.echo(f"  Tokens dinâmicos totais: {stats['total_dyn_tokens']}")
    click.echo(f"  {Fore.GREEN}Economia total: {saved_mb:.2f} MB{Style.RESET_ALL}")
    click.echo(f"{Fore.CYAN}{Style.BRIGHT}{'═'*60}{Style.RESET_ALL}\n")

def _run_single_build(file: str, project_root: Path, optimize: bool, dynamic: bool, hbc4: bool = False, hbc5: bool = False):
    """Comprime um arquivo específico."""
    from doxoade.tools.hermes_systems.hermes_preprocessor import preprocess_for_hermes
    from doxoade.tools.hermes_systems.hermes_compress import HermesCompressor
    from doxoade.tools.hermes_systems.hermes_loader import HermesLoader, verify_lossless
    
    file_path = Path(file).resolve()
    
    click.echo(f"  {Fore.CYAN}▶ Modo: Arquivo específico{Style.RESET_ALL}")
    click.echo(f"  {Fore.CYAN}▶ Alvo: {file_path.name}{Style.RESET_ALL}")
    
    optimized_content = None
    if optimize:
        click.echo(f"  {Fore.YELLOW}▶ Aplicando otimizações pré-compressão...{Style.RESET_ALL}")
        optimized_content, metrics = preprocess_for_hermes(file_path, str(project_root))
        click.echo(f"     {Fore.GREEN}✔ Docstrings removidos: {metrics['docstrings_removed']}{Style.RESET_ALL}")
        click.echo(f"     {Fore.GREEN}✔ Imports removidos: {metrics['imports_removed']}{Style.RESET_ALL}")
        click.echo(f"     {Fore.GREEN}✔ Comentários removidos: {metrics['comments_removed']}{Style.RESET_ALL}")
        click.echo(f"     {Fore.GREEN}✔ Linhas vazias removidas: {metrics['blank_lines_removed']}{Style.RESET_ALL}")
    
    dict_path = project_root / '.doxoade' / 'hermes' / 'master.dict'
    if not dict_path.exists():
        click.echo(f"{Fore.YELLOW}⚠ Dicionário não encontrado. Gerando automaticamente...{Style.RESET_ALL}")
        results, mapping = run_hermes_reconnaissance(str(project_root))
        builder = HermesDictionaryBuilder(str(project_root))
        builder.build_from_scan(results, mapping)
    
    compressor = HermesCompressor(str(project_root))
    
    try:
        result = compressor.compress_file(
            file_path, optimized_content, use_dynamic_scan=dynamic, use_hbc4=hbc4, use_hbc5=hbc5
        )
        
        if len(result) == 4:
            orig_sz, new_sz, hermes_file, dynamic_count = result
        else:
            orig_sz, new_sz, hermes_file = result
            dynamic_count = 0
        
        savings = 100 - ((new_sz / orig_sz) * 100) if orig_sz > 0 else 0
        fmt = "HBC5" if hbc5 else ("HBC4" if hbc4 else "HBC3")
        
        click.echo(f"  {Fore.GREEN}✔ Comprimido: {file_path.name} -> {hermes_file.name}{Style.RESET_ALL}")
        click.echo(f"     Formato: {fmt}")
        click.echo(f"     Tamanho: {orig_sz} bytes -> {new_sz} bytes ({Fore.GREEN}-{savings:.1f}%{Style.RESET_ALL})")
        
        # Teste de integridade
        source_to_verify = optimized_content if optimize else file_path.read_text(encoding='utf-8')
        loader = HermesLoader(str(project_root))
        is_lossless, hash_orig, hash_recon = verify_lossless(
            source_to_verify, file_path, hermes_file, loader
        )
        
        if is_lossless:
            click.echo(f"     {Fore.CYAN}🛡️ Integridade: 100% Lossless (SHA256: {hash_orig}){Style.RESET_ALL}")
        else:
            click.echo(f"     {Fore.YELLOW}⚠ Integridade: {hash_orig} (verificação estrutural){Style.RESET_ALL}")
        
        if dynamic_count > 0:
            click.echo(f"     {Fore.BLUE}🔬 Dynamic Scanner: +{dynamic_count} tokens locais{Style.RESET_ALL}")
    
    except Exception as e:
        from doxoade.tools.error_info import formated_traceback
        formated_traceback(e, "_run_single_build - Falha na compressão")

@hermes_group.command('run')
@click.argument('module_name')
def run(module_name):
    """[Fase 3] Testa a descompressão e faz Disassembly do Bytecode."""
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}☤ [HERMES] Carregando Loader na Virtual Machine...{Style.RESET_ALL}")
    
    project_root = Path.cwd().resolve()
    from doxoade.tools.hermes_systems.hermes_loader import HermesLoader
    
    loader = HermesLoader(str(project_root))
    hermes_path = loader.find_hermes_for_module(module_name)
    
    if not hermes_path:
        click.echo(f"{Fore.RED}✘ Módulo .hermes não encontrado para: {module_name}{Style.RESET_ALL}")
        return
        
    try:
        # Puxa o objeto executável (bytecode) da memória
        code_obj = loader.decompress_to_code(hermes_path)
        click.echo(f"  {Fore.GREEN}✔ Bytecode reconstruído com sucesso na RAM!{Style.RESET_ALL}")
        
        click.echo(f"\n{Style.DIM}--- Inspeção de Bytecode (Primeiras 20 instruções) ---{Style.RESET_ALL}")
        
        # Faz o disassembly do código de máquina gerado
        import io
        import sys
        
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            dis.dis(code_obj)
            assembly_output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
            
        # Mostra apenas o começo para não poluir o terminal
        lines = assembly_output.split('\n')
        for line in lines[:50]:
            click.echo(f"{Fore.YELLOW}{line}{Style.RESET_ALL}")
            
        if len(lines) > 50:
            click.echo(f"{Style.DIM}... (mais {len(lines) - 50} instruções omitidas){Style.RESET_ALL}")
            
    except Exception as e:
        click.echo(f"{Fore.RED}✘ Falha ao executar bytecode: {e}{Style.RESET_ALL}")
        format_traceback(e, "cmd_hermes - run")
        
@hermes_group.command('report')
@click.option('--target', '-t', default='.', help="Diretório alvo para análise.")
@click.option('--save', '-s', is_flag=True, help="Salva relatório JSON completo.")
def report(target, save):
    """[Fase 6] Relatório de cobertura do dicionário no projeto."""
    from doxoade.tools.hermes_systems.hermes_metrics import HermesMetricsCollector
    from doxoade.tools.hermes_systems.hermes_dict.hermes_builder import HermesDictionaryBuilder
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}☤ [HERMES] Analisando cobertura do dicionário...{Style.RESET_ALL}")
    
    # Carrega o dicionário atual
    builder = HermesDictionaryBuilder(target)
    dictionary = builder.load_dictionary()
    
    if not dictionary:
        click.echo(f"{Fore.RED}✘ Dicionário não encontrado. Execute 'doxoade hermes build' primeiro.{Style.RESET_ALL}")
        return
    
    encoder = dictionary['encoder']
    click.echo(f"  {Fore.CYAN}▶ Dicionário carregado: {len(encoder)} tokens{Style.RESET_ALL}")
    
    # Analisa o projeto
    collector = HermesMetricsCollector(target)
    collector.analyze_project(encoder, target)
    
    # Imprime relatório
    collector.print_report()
    
    if save:
        report_path = collector.save_report()
        click.echo(f"\n{Fore.GREEN}✔ Relatório JSON salvo em: {report_path}{Style.RESET_ALL}")

@hermes_group.command('benchmark')
@click.option('--module', '-m', help='Módulo específico para benchmark (ex: doxoade.tools.filesystem)')
@click.option('--runs', default=3, help='Número de execuções por cenário')
@click.option('--json', 'output_json', is_flag=True, help='Output em JSON')
def hermes_benchmark(module, runs, output_json):
    """🔬 Benchmark Comparativo: Python Puro vs Mercury Systems (Cold/Warm Start)."""
    from doxoade.tools.hermes_systems.hermes_benchmark_compare import run_benchmark_compare
    from pathlib import Path
    
    project_root = Path.cwd().resolve()
    
    if module:
        modules = [module]
    else:
        modules = [
            'doxoade.cli',
            'doxoade.tools.vulcan.forge',
            'doxoade.tools.hermes_systems.hermes_loader',
            'doxoade.core_database',
            'doxoade.tools.filesystem',
        ]
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🔬 MERCURY SYSTEMS BENCHMARK ENGINE{Style.RESET_ALL}")
    click.echo(f"  Projeto: {project_root.name}")
    click.echo(f"  Módulos: {len(modules)}")
    click.echo(f"  Runs:    {runs} por cenário\n")
    
    results = run_benchmark_compare(str(project_root), modules, runs=runs)
    
    if output_json:
        import json
        click.echo(json.dumps(results, indent=2))
        return
    
    # Imprimir tabela formatada
    click.echo(f"\n{Fore.WHITE}{'MÓDULO':<45} {'PYTHON':>10} {'COLD':>10} {'WARM':>10} {'SPD COLD':>10} {'SPD WARM':>10}{Style.RESET_ALL}")
    click.echo(f"{'─' * 105}")
    
    total_py = 0
    total_cold = 0
    total_warm = 0
    valid_speedups_cold = []
    valid_speedups_warm = []
    
    for r in results:
        mod_short = r['module'] if len(r['module']) <= 45 else '...' + r['module'][-42:]
        
        spd_cold = r['python_ms'] / r['cold_ms'] if r['cold_ms'] > 0 else 0
        spd_warm = r['python_ms'] / r['warm_ms'] if r['warm_ms'] > 0 else 0
        
        color_cold = Fore.GREEN if spd_cold >= 2.0 else Fore.CYAN if spd_cold >= 1.0 else Fore.YELLOW
        color_warm = Fore.GREEN if spd_warm >= 2.0 else Fore.CYAN if spd_warm >= 1.0 else Fore.YELLOW
        
        click.echo(f"{mod_short:<45} {r['python_ms']:>8.2f}ms {r['cold_ms']:>8.2f}ms {r['warm_ms']:>8.2f}ms {color_cold}{spd_cold:>8.2f}×{Style.RESET_ALL} {color_warm}{spd_warm:>8.2f}×{Style.RESET_ALL}")
        
        total_py += r['python_ms']
        total_cold += r['cold_ms']
        total_warm += r['warm_ms']
        if spd_cold > 0: valid_speedups_cold.append(spd_cold)
        if spd_warm > 0: valid_speedups_warm.append(spd_warm)
    
    click.echo(f"{'─' * 105}")
    
    avg_speedup_cold = sum(valid_speedups_cold) / len(valid_speedups_cold) if valid_speedups_cold else 0
    avg_speedup_warm = sum(valid_speedups_warm) / len(valid_speedups_warm) if valid_speedups_warm else 0
    
    click.echo(f"{'TOTAL/MÉDIA':<45} {total_py:>8.2f}ms {total_cold:>8.2f}ms {total_warm:>8.2f}ms {Fore.CYAN}{avg_speedup_cold:>8.2f}×{Style.RESET_ALL} {Fore.CYAN}{avg_speedup_warm:>8.2f}×{Style.RESET_ALL}")
    
    if avg_speedup_warm >= 2.0:
        click.echo(f"\n{Fore.GREEN}🏆 VITÓRIA DECISIVA: Mercury Warm Start é {avg_speedup_warm:.2f}× mais rápido que Python Puro!{Style.RESET_ALL}")
        click.echo(f"{Fore.GREEN}   O Marshal Cache + mmap Zero-Copy eliminou o gargalo do import machinery.{Style.RESET_ALL}")
    elif avg_speedup_warm >= 1.0:
        click.echo(f"\n{Fore.CYAN}✔ VITÓRIA: Mercury Warm Start é {avg_speedup_warm:.2f}× mais rápido que Python Puro.{Style.RESET_ALL}")
    else:
        click.echo(f"\n{Fore.YELLOW}⚠ Python Puro ainda vence no cenário atual. O gargalo pode ser I/O do cache_save.{Style.RESET_ALL}")
    
    click.echo(f"\n{Fore.CYAN}{'═' * 105}{Style.RESET_ALL}\n")
            
@hermes_group.command('purge')
@click.option('--lib', help='Nome da biblioteca para purgar (ex: click)')
@click.option('--all', 'purge_all', is_flag=True, help='Remove todos os .hermes do projeto')
@click.option('--force', is_flag=True, help='Confirma sem perguntar')
@click.pass_context
def purge(ctx, lib, purge_all, force):
    """Remove arquivos .hermes problemáticos."""
    from pathlib import Path
    from doxoade.tools.doxcolors import Fore, Style
    
    project_root = Path.cwd().resolve()
    hermes_dir = project_root / '.doxoade' / 'hermes'
    
    if not hermes_dir.exists():
        click.echo(f"{Fore.YELLOW}⚠ Diretório .doxoade/hermes não existe.{Style.RESET_ALL}")
        return
    
    if lib:
        # Purga lib específica
        lib_dir = hermes_dir / 'lib' / lib
        if not lib_dir.exists():
            click.echo(f"{Fore.YELLOW}⚠ Lib '{lib}' não encontrada em {lib_dir}{Style.RESET_ALL}")
            return
        
        hermes_files = list(lib_dir.glob('*.hermes'))
        if not hermes_files:
            click.echo(f"{Fore.YELLOW}⚠ Nenhum .hermes encontrado para '{lib}'{Style.RESET_ALL}")
            return
        
        if not force:
            if not click.confirm(f"Remover {len(hermes_files)} arquivos .hermes de '{lib}'?"):
                return
        
        for f in hermes_files:
            f.unlink()
            click.echo(f"  {Fore.RED}✘{Style.RESET_ALL} {f.name}")
        
        # Remove diretório se vazio
        if not any(lib_dir.iterdir()):
            lib_dir.rmdir()
            click.echo(f"  {Fore.CYAN}📁 Diretório removido: {lib_dir.name}{Style.RESET_ALL}")
        
        click.echo(f"\n{Fore.GREEN}✔ {len(hermes_files)} arquivo(s) removido(s) de '{lib}'{Style.RESET_ALL}")
        click.echo(f"{Fore.YELLOW}💡 Dica: Rebuild com 'doxoade vulcan lib --target {lib} --optimize --hermes'{Style.RESET_ALL}")
    
    elif purge_all:
        # Purga tudo
        build_dir = hermes_dir / 'build'
        lib_base = hermes_dir / 'lib'
        total = 0
        
        if build_dir.exists():
            files = list(build_dir.glob('*.hermes'))
            total += len(files)
            
            if not force:
                if not click.confirm(f"Remover TODOS os {total} arquivos .hermes?"):
                    return
            
            for f in files:
                f.unlink()
        
        if lib_base.exists():
            for lib_dir in lib_base.iterdir():
                if lib_dir.is_dir():
                    files = list(lib_dir.glob('*.hermes'))
                    total += len(files)
                    for f in files:
                        f.unlink()
                    if not any(lib_dir.iterdir()):
                        lib_dir.rmdir()
        
        click.echo(f"\n{Fore.GREEN}✔ {total} arquivo(s) .hermes removido(s){Style.RESET_ALL}")
    
    else:
        click.echo(ctx.get_help())

@hermes_group.command('native')
@click.option('--force', '-f', is_flag=True, help='Força recompilação mesmo se cache válido')
@click.option('--metalcraft', '-m', is_flag=True, default=True, help='Usa Metalcraft (padrão) ou GCC direto')
def build_native(force, metalcraft):
    """Compila o decoder C nativo do Hermes."""
    from doxoade.tools.hermes_systems.native.build_auto import HermesNativeBuilder
    from doxoade.tools.doxcolors import Fore, Style
    
    project_root = Path.cwd().resolve()
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}☤ [HERMES] Build Native Decoder...{Style.RESET_ALL}\n")
    
    builder = HermesNativeBuilder(str(project_root))
    
    if force:
        click.echo(f"  {Fore.YELLOW}⚠ Forçando recompilação (ignorando cache){Style.RESET_ALL}")
        # Remove cache para forçar rebuild
        if builder.cache_file.exists():
            builder.cache_file.unlink()
    
    success = builder.build(use_metalcraft=metalcraft)
    
    if success:
        click.echo(f"\n{Fore.GREEN}✔ Decoder C nativo compilado com sucesso!{Style.RESET_ALL}")
        click.echo(f"  {Fore.CYAN}O Hermes agora usará o decoder acelerado por C.{Style.RESET_ALL}")
    else:
        click.echo(f"\n{Fore.RED}✘ Falha na compilação do decoder C{Style.RESET_ALL}")
        click.echo(f"  {Fore.YELLOW}O Hermes usará o decoder Python puro (mais lento).{Style.RESET_ALL}")

@hermes_group.command('graph')
@click.option('--verbose', '-v', is_flag=True, help='Output detalhado')
@click.option('--save', '-s', is_flag=True, help='Salva grafo em JSON')
@click.option('--preload', '-p', is_flag=True, help='Gera script de preload')
def hermes_graph(verbose, save, preload):
    """🔍 Analisa dependências e gera grafo de import cascade."""
    from doxoade.tools.hermes_systems.hermes_dependency_graph import HermesDependencyGraph
    
    project_root = Path.cwd().resolve()
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🔍 HERMES DEPENDENCY GRAPH ANALYZER{Style.RESET_ALL}")
    click.echo(f"  Projeto: {project_root.name}\n")
    
    graph = HermesDependencyGraph(str(project_root))
    graph.build(verbose=verbose)
    
    if verbose or (not save and not preload):
        graph.print_report()
    
    if save:
        graph.save_json()
    
    if preload:
        graph.generate_preload_script()
        click.echo(f"\n{Fore.GREEN}✔ Para executar o preload:{Style.RESET_ALL}")
        click.echo(f"  python doxoade/tools/hermes_systems/hermes_preload_critical.py\n")
        
@hermes_group.command('auto-benchmark')
@click.option('--runs', '-r', default=3, help='Número de execuções por cenário')
@click.option('--modules', '-m', multiple=True, help='Módulos específicos (padrão: críticos)')
def hermes_auto_benchmark(runs, modules):
    """🔬 Executa benchmark e atualiza métricas de performance automaticamente."""
    from doxoade.tools.hermes_systems.hermes_benchmark_auto import benchmark_and_update, benchmark_critical_modules
    
    if modules:
        benchmark_and_update(list(modules), runs=runs)
    else:
        benchmark_critical_modules(runs=runs)


@hermes_group.command('preload')
@click.option('--verbose', '-v', is_flag=True, help='Mostra logs detalhados')
@click.option('--modules', '-m', multiple=True, help='Módulos específicos (padrão: cache)')
def hermes_preload(verbose, modules):
    """⚡ Pré-carrega módulos críticos com cache inteligente."""
    from doxoade.tools.hermes_systems.hermes_auto_preload import auto_preload
    
    project_root = Path.cwd().resolve()
    
    if modules:
        stats = auto_preload(str(project_root), list(modules), verbose=verbose)
    else:
        stats = auto_preload(str(project_root), verbose=verbose)
    
    click.echo(f"\n{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}")
    click.echo(f"{Fore.CYAN}  ⚡ HERMES AUTO-PRELOAD{Style.RESET_ALL}")
    click.echo(f"{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}")
    click.echo(f"  ✔ Carregados: {len(stats['loaded'])}")
    click.echo(f"  ✔ Cache hits: {stats['cache_hits']}")
    click.echo(f"  ✘ Falhas: {len(stats['failed'])}")
    click.echo(f"  ⏱ Tempo total: {stats['total_time_ms']:.1f}ms")
    click.echo(f"{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}\n")
    
    if stats['failed']:
        click.echo(f"{Fore.YELLOW}  Módulos que falharam:{Style.RESET_ALL}")
        for fail in stats['failed']:
            click.echo(f"    - {fail['module']}: {fail['error']}")
        click.echo()

@hermes_group.command('lab')
@click.option('--mode', '-m', default='ngram-local',
              help="Modo: 'ngram-local' (intra-arquivo) ou 'ngram-global' (cross-file)")
@click.option('--target', '-t', default='.',
              help="Arquivo .py único OU diretório.")
@click.option('--top', default=30, help="Quantos padrões mostrar.")
@click.option('--min-freq', default=3, help="(local) Freq mínima no mesmo arquivo.")
@click.option('--min-files', default=2, help="(global) Mín de arquivos distintos.")
def hermes_lab(mode, target, top, min_freq, min_files):
    """🧬 [R&D] Hermes Lab: Incubador de Pesquisa de Bytecode."""
    from doxoade.tools.hermes_systems.hermes_lab import BytecodeNgramScanner

    click.echo(f"\n{Fore.MAGENTA}{Style.BRIGHT}☤ [HERMES LAB] Modo: {mode}{Style.RESET_ALL}")

    scanner = BytecodeNgramScanner(target, n_sizes=(4, 6, 8, 10))
    scanner.scan()

    if not scanner.file_results:
        click.echo(f"\n{Fore.RED}✘ Nenhum arquivo processado. Verifique o caminho.{Style.RESET_ALL}")
        return

    if mode == 'ngram-local':
        scanner.print_local_report(top_n=top, min_freq=min_freq)
    elif mode == 'ngram-global':
        scanner.print_global_report(top_n=top, min_dispersion=min_files)
    else:
        click.echo(f"{Fore.RED}Modo desconhecido. Use 'ngram-local' ou 'ngram-global'.{Style.RESET_ALL}")

@hermes_group.command('test')
@click.argument('target', required=False, type=click.Path(exists=True))
def hermes_test(target):
    """[CI] Testa a integridade Lossless e performance do Motor C.
    
    Exemplos:
      doxoade hermes test doxoade/cli.py
      doxoade hermes test doxoade/tools/vulcan/forge.py
    """
    from doxoade.tools.hermes_systems.hermes_test import run_hermes_test
    project_root = Path.cwd().resolve()
    
    # Se não passar alvo, usa o cli.py como padrão
    target_file = target or str(project_root / "doxoade" / "cli.py")
    
    success = run_hermes_test(str(project_root), target_file)
    if not success:
        click.echo(f"\n{Fore.RED}✘ TESTE FALHOU. O Motor C está corrompendo o bytecode.{Style.RESET_ALL}")
        sys.exit(1)
    else:
        click.echo(f"\n{Fore.GREEN}✔ TESTE APROVADO. O Motor C está gerando bytecode íntegro.{Style.RESET_ALL}")
        
# Adicione em cmd_hermes.py:
@hermes_group.command('build-logger')
def build_logger_cmd():
    """Compila o Async Logger assíncrono."""
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}☤ [HERMES] Compilando Async Logger...{Style.RESET_ALL}")
    
    import subprocess
    build_script = Path(__file__).parent.parent / 'tools' / 'hermes_systems' / 'native' / 'build_logger.py'
    
    result = subprocess.run([sys.executable, str(build_script)], capture_output=True, text=True)
    
    if result.returncode == 0:
        click.echo(f"{Fore.GREEN}✔ Logger compilado com sucesso{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.RED}✘ Falha na compilação{Style.RESET_ALL}")
        click.echo(result.stderr)