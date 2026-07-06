# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd_data.py
import os
import sys
import time
import json
import ctypes
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

    # ═══════════════════════════════════════════════════════════════════
    # 1. TESTE PYTHON PURO
    # ═══════════════════════════════════════════════════════════════════
    t0 = time.perf_counter()
    raw_text = test_json.read_text(encoding='utf-8')
    t_py = (time.perf_counter() - t0) * 1000
    click.echo(f"  {Fore.YELLOW}Python (Read JSON)   :{Style.RESET_ALL} {t_py:>6.1f} ms")

    # ═══════════════════════════════════════════════════════════════════
    # 2. TESTE ACELERADOR C (MERCURY) — via ctypes (DLL pura)
    # ═══════════════════════════════════════════════════════════════════
    native_dir = Path(__file__).resolve().parents[1] / 'tools' / 'vulcan' / 'native'
    ext = '.dll' if os.name == 'nt' else '.so'
    dll_path = native_dir / f'mercury_core{ext}'
    click.echo(f"\n{Fore.CYAN}🔍 DEBUG: Procurando motor nativo...{Style.RESET_ALL}")
    click.echo(f"  Caminho esperado: {dll_path}")
    click.echo(f"  Arquivo existe: {'✔ SIM' if dll_path.exists() else '✘ NÃO'}")
    if not dll_path.exists():
        pyd_path = native_dir / 'mercury_core.pyd'
        if pyd_path.exists():
            dll_path = pyd_path
            click.echo(f"  {Fore.YELLOW}⚠ .dll não encontrado, usando .pyd: {pyd_path.name}{Style.RESET_ALL}")
        else:
            click.echo(f"  {Fore.RED}✘ mercury_core.dll/pyd não encontrado!{Style.RESET_ALL}")
            click.echo(f"  Recompile com: python doxoade/tools/vulcan/native/build_mercury_v2.py")
            return

    try:
        click.echo(f"  Carregando DLL via ctypes...")
        merc = ctypes.CDLL(str(dll_path))
        click.echo(f"  {Fore.GREEN}✔ DLL carregada com sucesso{Style.RESET_ALL}")

        # Configura protótipos (tipagem estrita para segurança)
        # char* mercury_decode_hbd1(const char* data, size_t size, size_t* out_size)
        merc.mercury_decode_hbd1.argtypes = [
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        merc.mercury_decode_hbd1.restype = ctypes.c_void_p

        # void mercury_free(void* ptr)
        merc.mercury_free.argtypes = [ctypes.c_void_p]
        merc.mercury_free.restype = None

        # const char* mercury_version(void)
        merc.mercury_version.argtypes = []
        merc.mercury_version.restype = ctypes.c_char_p

        click.echo(f"  {Fore.GREEN}✔ Funções configuradas{Style.RESET_ALL}")

    except Exception as e:
        click.echo(f"  {Fore.RED}✘ Falha ao carregar mercury_core: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        return

    # Lê o arquivo HBD1 em bytes
    hbd1_bytes = test_hbd1.read_bytes()
    click.echo(f"  Arquivo HBD1: {len(hbd1_bytes)} bytes")

    # Prepara o buffer de saída (out_size)
    out_size = ctypes.c_size_t(0)

    t0 = time.perf_counter()
    result_ptr = merc.mercury_decode_hbd1(
        hbd1_bytes,
        len(hbd1_bytes),
        ctypes.byref(out_size)
    )
    t_c = (time.perf_counter() - t0) * 1000

    click.echo(f"  Tempo de decode: {t_c:.2f} ms")
    click.echo(f"  Ponteiro retornado: {result_ptr}")
    click.echo(f"  Tamanho da saída: {out_size.value}")

    if not result_ptr:
        click.echo(f"  {Fore.RED}✘ C-Decoder retornou NULL (erro interno){Style.RESET_ALL}")
        return

    try:
        # Converte o buffer C para string Python
        raw_hbd1_text = ctypes.string_at(result_ptr, out_size.value).decode('utf-8')
        click.echo(f"  {Fore.GREEN}✔ Decode bem-sucedido: {len(raw_hbd1_text)} chars{Style.RESET_ALL}")
    finally:
        # Libera o buffer alocado pelo C
        merc.mercury_free(result_ptr)

    # Validação de integridade
    if raw_hbd1_text != raw_text:
        click.echo(f"  {Fore.RED}✘ FALHA DE INTEGRIDADE: O C-Decoder gerou uma string diferente!{Style.RESET_ALL}")
        click.echo(f"    Esperado: {len(raw_text)} chars")
        click.echo(f"    Obtido  : {len(raw_hbd1_text)} chars")
        return

    speedup = t_py / t_c if t_c > 0 else 0
    color = Fore.GREEN if speedup > 1.0 else Fore.RED
    click.echo(f"  {Fore.CYAN}Mercury C (Read HBD1):{Style.RESET_ALL} {t_c:>6.1f} ms  {color}[Speedup: {speedup:.2f}x]{Style.RESET_ALL}")

    click.echo(f"\n{Fore.MAGENTA}  ⬡ CONCLUSÃO:{Style.RESET_ALL}")
    click.echo(f"  O C-Accelerator leu o arquivo {comp_kb:.1f}KB do disco e expandiu o Dicionário")
    click.echo(f"  diretamente no Cache da CPU, entregando uma String de {orig_kb:.1f}KB pronta para o Python.")

    # Limpeza
    test_json.unlink(missing_ok=True)
    test_hbd1.unlink(missing_ok=True)