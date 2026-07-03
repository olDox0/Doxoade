# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd_data.py
import os
import sys
import time
import json
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.vulcan.hermes_data import compress_to_hbd1

@click.group('data')
def vulcan_data():
    """[MERCURY] Processamento de Dados Orientado a Memória (HBD1)."""
    pass

@vulcan_data.command('pack')
@click.argument('source', type=click.Path(exists=True))
@click.option('--out', '-o', help="Arquivo de saída (.hbd1)")
def pack_data(source, out):
    """Comprime JSON/TXT/LOGS para o formato Hermes Binary Data 1."""
    src_path = Path(source)
    out_path = Path(out) if out else src_path.with_suffix('.hbd1')
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}☤ [MERCURY] Comprimindo {src_path.name}...{Style.RESET_ALL}")
    
    t0 = time.perf_counter()
    stats = compress_to_hbd1(source, str(out_path))
    t1 = time.perf_counter()
    
    click.echo(f"  {Fore.GREEN}✔ HBD1 gerado em {(t1-t0)*1000:.1f}ms{Style.RESET_ALL}")
    click.echo(f"  Tokens dinâmicos : {stats['tokens']}")
    click.echo(f"  Tamanho Original : {stats['original_bytes']/1024:.1f} KB")
    click.echo(f"  Tamanho Comprimido: {stats['compressed_bytes']/1024:.1f} KB")
    click.echo(f"  Economia         : {Fore.GREEN}{stats['ratio']*100:.1f}%{Style.RESET_ALL}\n")

@vulcan_data.command('benchmark')
@click.option('--size', default=50000, help="Número de registros falsos no JSON.")
def benchmark_data(size):
    """Mede a Velocidade de Expansão na RAM: CPython vs Accelerator C."""
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}☤ [MERCURY] Preparando Payload de Teste ({size} registros)...{Style.RESET_ALL}")
    
    test_json = Path('.doxoade/vulcan/bench_data.json')
    test_hbd1 = Path('.doxoade/vulcan/bench_data.hbd1')
    test_json.parent.mkdir(parents=True, exist_ok=True)
    
    # Gera um JSON de telemetria altamente repetitivo
    data = []
    for i in range(size):
        data.append({
            "timestamp": f"2026-07-03T12:00:{i%60:02d}.000Z",
            "module": "doxoade.tools.vulcan.compiler",
            "level": "INFO",
            "message": "Iniciando compilação do módulo alvo com otimização Hórus.",
            "status": "SUCCESS"
        })
        
    json_str = json.dumps(data)
    test_json.write_text(json_str, encoding='utf-8')
    orig_kb = len(json_str) / 1024
    
    compress_to_hbd1(str(test_json), str(test_hbd1))
    comp_kb = test_hbd1.stat().st_size / 1024
    
    click.echo(f"\n{Fore.WHITE}■ ARQUIVOS EM DISCO:{Style.RESET_ALL}")
    click.echo(f"  JSON Puro : {orig_kb:.1f} KB")
    click.echo(f"  HBD1 Cmp. : {comp_kb:.1f} KB ({Fore.GREEN}-{(1 - comp_kb/orig_kb)*100:.1f}%{Style.RESET_ALL})")
    
    click.echo(f"\n{Fore.WHITE}■ CORRIDA DE EXPANSÃO NA RAM (Leitura de Disco -> String em Memória):{Style.RESET_ALL}")
    
    # 1. TESTE PYTHON PURO
    t0 = time.perf_counter()
    raw_text = test_json.read_text(encoding='utf-8')
    t_py = (time.perf_counter() - t0) * 1000
    click.echo(f"  {Fore.YELLOW}Python (Read JSON)   :{Style.RESET_ALL} {t_py:>6.1f} ms")

    # 2. TESTE ACELERADOR C (MERCURY)
    # Adicionamos a pasta native ao sys.path temporariamente para carregar a DLL
    import sys
    native_dir = Path(__file__).resolve().parents[1] / 'tools' / 'vulcan' / 'native'
    sys.path.insert(0, str(native_dir))
    
    try:
        import mercury_core as acc
    except ImportError as e:
        click.echo(f"  {Fore.RED}✘ mercury_core não encontrado! Recompile o C. ({e}){Style.RESET_ALL}")
        return

    t0 = time.perf_counter()
    raw_hbd1_text = acc.load_hermes_data(str(test_hbd1))
    t_c = (time.perf_counter() - t0) * 1000
    
    if raw_hbd1_text != raw_text:
        click.echo(f"  {Fore.RED}✘ FALHA DE INTEGRIDADE: O C-Decoder gerou uma string diferente!{Style.RESET_ALL}")
        return
        
    speedup = t_py / t_c if t_c > 0 else 0
    color = Fore.GREEN if speedup > 1.0 else Fore.RED
    click.echo(f"  {Fore.CYAN}Mercury C (Read HBD1):{Style.RESET_ALL} {t_c:>6.1f} ms  {color}[Speedup: {speedup:.2f}x]{Style.RESET_ALL}")
    
    click.echo(f"\n{Fore.MAGENTA}  ⬡ CONCLUSÃO:{Style.RESET_ALL}")
    click.echo(f"  O C-Accelerator leu o arquivo {comp_kb:.1f}KB do disco e expandiu o Dicionário")
    click.echo(f"  diretamente no Cache da CPU, entregando uma String de {orig_kb:.1f}KB pronta para o Python.")
    
    test_json.unlink(missing_ok=True)
    test_hbd1.unlink(missing_ok=True)