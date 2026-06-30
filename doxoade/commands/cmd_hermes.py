# -*- coding: utf-8 -*-
# doxoade/commands/cmd_hermes.py
import click
import os
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.hermes_systems.hermes_scanner import run_hermes_reconnaissance
from doxoade.tools.hermes_systems.hermes_dict.hermes_builder import HermesDictionaryBuilder
from doxoade.tools.hermes_systems.hermes_compress import HermesCompressor

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
    
    for struct_hash, count in results:
        source_code = mapping[struct_hash]
        # Mostra o ID que será substituído e o código real
        click.echo(f"  {Fore.YELLOW}[{struct_hash}]{Style.RESET_ALL} {count:4} repetições | {Fore.WHITE}{source_code}{Style.RESET_ALL}")
#        click.echo(f"  {Fore.YELLOW}[{struct_hash}]{Style.RESET_ALL} {count:4} ocorrências | {Fore.WHITE}{source_code}{Style.RESET_ALL}")
        
    click.echo(f"{Style.DIM}{'-'*80}{Style.RESET_ALL}")
    click.echo(f"Ação sugerida: Os itens com alta ocorrência receberão IDs de 1 byte (0x01 a 0xFF).")
    
@hermes_group.command('build')
@click.argument('file', required=False, type=click.Path(exists=True))
@click.option('--target', '-t', default='.', help="Diretório alvo para scan.")
@click.option('--optimize', '-o', is_flag=True, help="Aplica otimizações pré-compressão.")
@click.option('--dynamic', '-d', is_flag=True, help="Usa dynamic scanner local.")
@click.option('--max-tokens', default=5000, help="Número máximo de tokens no dicionário global.")
def build(file, target, optimize, dynamic, max_tokens):
    """[Fase 2] Gera o Dicionário e Comprime arquivos para .hermes."""
    click.echo(f"\n{Fore.MAGENTA}{Style.BRIGHT}☤ [HERMES] Construindo Matriz de Compressão...{Style.RESET_ALL}")
    
    if file:
        # MODO ARQUIVO ESPECÍFICO
        file_path = Path(file).resolve()
        project_root = Path.cwd().resolve()
        
        click.echo(f"  {Fore.CYAN}▶ Modo: Arquivo específico{Style.RESET_ALL}")
        click.echo(f"  {Fore.CYAN}▶ Alvo: {file_path.name}{Style.RESET_ALL}")
        
        optimized_content = None
        if optimize:
            from doxoade.tools.hermes_systems.hermes_preprocessor import preprocess_for_hermes
            click.echo(f"  {Fore.YELLOW}▶ Aplicando otimizações pré-compressão...{Style.RESET_ALL}")
            optimized_content, metrics = preprocess_for_hermes(file_path, str(project_root))
            
            click.echo(f"     {Fore.GREEN}✔ Docstrings removidos: {metrics['docstrings_removed']}{Style.RESET_ALL}")
            click.echo(f"     {Fore.GREEN}✔ Imports removidos: {metrics['imports_removed']}{Style.RESET_ALL}")
            click.echo(f"     {Fore.GREEN}✔ Comentários removidos: {metrics['comments_removed']}{Style.RESET_ALL}")
            click.echo(f"     {Fore.GREEN}✔ Linhas vazias removidas: {metrics['blank_lines_removed']}{Style.RESET_ALL}")
        
        dict_path = project_root / '.doxoade' / 'hermes' / 'master.dict'
        if not dict_path.exists():
            click.echo(f"{Fore.RED}✘ Dicionário não encontrado. Execute 'doxoade hermes build' primeiro.{Style.RESET_ALL}")
            return
        
        compressor = HermesCompressor(str(project_root))
        try:
            result = compressor.compress_file(
                file_path,
                optimized_content,
                use_dynamic_scan=dynamic
            )
            # Suporta retorno com 4 elementos (com dynamic_count)
            if len(result) == 4:
                orig_sz, new_sz, hermes_file, dynamic_count = result
            else:
                orig_sz, new_sz, hermes_file = result
                dynamic_count = 0

            savings = 100 - ((new_sz / orig_sz) * 100) if orig_sz > 0 else 0
            click.echo(f"  {Fore.GREEN}✔ Comprimido: {file_path.name} -> {hermes_file.name}{Style.RESET_ALL}")
            click.echo(f"     Tamanho: {orig_sz} bytes -> {new_sz} bytes ({Fore.GREEN}-{savings:.1f}%{Style.RESET_ALL})")
            if dynamic_count > 0:
                click.echo(f"     {Fore.BLUE}🔬 Dynamic Scanner: +{dynamic_count} tokens locais{Style.RESET_ALL}")
        except Exception as e:
            click.echo(f"{Fore.RED}✘ Falha na compressão: {e}{Style.RESET_ALL}")
    
    else:
        # MODO SCAN COMPLETO
        click.echo(f"  {Fore.CYAN}▶ Modo: Scan completo + Prova de Conceito{Style.RESET_ALL}")
        click.echo(f"  {Fore.CYAN}▶ Limite de tokens: {max_tokens}{Style.RESET_ALL}")
        
        results, mapping = run_hermes_reconnaissance(target, max_tokens=max_tokens)
        
        builder = HermesDictionaryBuilder(target)
        token_count, dict_path = builder.build_from_scan(results, mapping, max_tokens=max_tokens)
        click.echo(f"  {Fore.GREEN}✔ Dicionário Master criado em: {dict_path.name} ({token_count} tokens){Style.RESET_ALL}")
        
        compressor = HermesCompressor(target)
        main_file = Path(target) / "doxoade" / "__main__.py"
        
        if main_file.exists():
            result = compressor.compress_file(main_file)
            # Suporta retorno com 3 ou 4 elementos
            if len(result) == 4:
                orig_sz, new_sz, hermes_file, _ = result
            else:
                orig_sz, new_sz, hermes_file = result
            
            savings = 100 - ((new_sz / orig_sz) * 100) if orig_sz > 0 else 0
            click.echo(f"  {Fore.CYAN}✔ Prova de Conceito: {main_file.name} -> {hermes_file.name}{Style.RESET_ALL}")
            click.echo(f"     Tamanho: {orig_sz} bytes -> {new_sz} bytes ({Fore.GREEN}-{savings:.1f}%{Style.RESET_ALL})")
        
@hermes_group.command('run')
@click.argument('module_or_file')
@click.option('--save', '-s', is_flag=True, help="Salva o .py reconstruído no disco.")
def run(module_or_file, save):
    """[Fase 3] Descomprime e executa um arquivo .hermes.
    
    Aceita tanto caminho de arquivo quanto nome de módulo:
      doxoade hermes run doxoade/commands/intelligence_engine.py
      doxoade hermes run doxoade.commands.intelligence_engine
    """
    from doxoade.tools.hermes_systems.hermes_loader import HermesLoader, verify_lossless
    
    project_root = Path.cwd().resolve()
    
    click.echo(f"\n{Fore.BLUE}{Style.BRIGHT}☤ [HERMES] Carregando Loader...{Style.RESET_ALL}")
    
    try:
        loader = HermesLoader(str(project_root))
    except FileNotFoundError as e:
        click.echo(f"{Fore.RED}✘ {e}{Style.RESET_ALL}")
        return
    
    # Determina o caminho do .hermes
    if '/' in module_or_file or '\\' in module_or_file or module_or_file.endswith('.hermes'):
        # É um caminho de arquivo
        hermes_path = Path(module_or_file).resolve()
        if not hermes_path.suffix == '.hermes':
            hermes_path = hermes_path.with_suffix('.hermes')
        
        # Se o caminho não existe, tenta no diretório .doxoade/hermes/
        if not hermes_path.exists():
            relative = hermes_path.relative_to(project_root) if hermes_path.is_relative_to(project_root) else hermes_path.name
            hermes_path = loader.hermes_base_dir / relative
    else:
        # É um nome de módulo
        hermes_path = loader.find_hermes_for_module(module_or_file)
        if not hermes_path:
            click.echo(f"{Fore.RED}✘ Arquivo .hermes não encontrado para o módulo: {module_or_file}{Style.RESET_ALL}")
            return
    
    if not hermes_path.exists():
        click.echo(f"{Fore.RED}✘ Arquivo .hermes não encontrado: {hermes_path}{Style.RESET_ALL}")
        return
    
    # 1. Descompressão
    click.echo(f"  {Fore.CYAN}▶ Descomprimindo: {hermes_path.name}{Style.RESET_ALL}")
    try:
        python_code = loader.decompress_file(hermes_path)
    except Exception as e:
        click.echo(f"{Fore.RED}✘ Falha na descompressão: {e}{Style.RESET_ALL}")
        return
    
    click.echo(f"  {Fore.GREEN}✔ Código reconstruído: {len(python_code)} caracteres{Style.RESET_ALL}")
    
    # 2. Verificação Lossless (se existir o .py original)
    # Tenta encontrar o .py original no projeto
    relative_to_hermes = hermes_path.relative_to(loader.hermes_base_dir)
    original_py = project_root / relative_to_hermes.with_suffix('.py')
    
    if original_py.exists():
        is_lossless = verify_lossless(original_py, hermes_path, loader)
        if is_lossless:
            click.echo(f"  {Fore.GREEN}✔ PROVA LOSSLESS: O .py reconstruído é IDÊNTICO ao original!{Style.RESET_ALL}")
        else:
            click.echo(f"  {Fore.YELLOW}⚠ DIVERGÊNCIA detectada entre original e reconstruído.{Style.RESET_ALL}")
    
    # 3. Salvar ou Executar
    if save:
        output = hermes_path.with_suffix('.restored.py')
        output.write_text(python_code, encoding='utf-8')
        click.echo(f"  {Fore.GREEN}✔ Salvo em: {output}{Style.RESET_ALL}")
    else:
        click.echo(f"\n{Fore.MAGENTA}--- Código Reconstruído (Preview) ---{Style.RESET_ALL}")
        preview = python_code
        click.echo(preview)
        click.echo(f"{Fore.MAGENTA}-----------------------------------{Style.RESET_ALL}")
        click.echo(f"{Fore.CYAN}Use --save para gravar o .py reconstruído.{Style.RESET_ALL}")
        
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
