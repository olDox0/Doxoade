# doxoade/doxoade/commands/debug_systems/debug_engine.py
"""
Debug Engine v2.5 - Chief Gold Orchestrator.

Novidades:
  - Shield SIGINT: Doxoade CLI aguarda o processo filho realizar o gracefully shutdown no Ctrl+C.
  - Duplo Ctrl+C para Force Kill.
"""
import re
import sys
import subprocess
import json
import click
from doxoade.tools.doxcolors import Fore, Style
from .debug_utils import get_debug_env, build_probe_command, build_flow_command
from .debug_io import print_debug_header, render_variable_table, report_crash, render_profile_report
from doxoade.tools.filesystem import _get_venv_python_executable
_MARKER_DEBUG = '---DOXOADE-DEBUG-DATA---'
_MARKER_PROFILE = '---DOXOADE-PROFILE-DATA---'
_RE_ANSI = re.compile('\\033\\[[0-9;]*m')
_RE_FLOW_MS = re.compile('[│|]\\s*([\\d]+\\.[\\d]+)ms\\s*[│|]')
_MS_COLORS = [(500.0, float('inf'), '\x1b[1;31m'), (100.0, 500.0, '\x1b[31m'), (20.0, 100.0, '\x1b[33m'), (5.0, 20.0, '\x1b[93m'), (0.0, 5.0, '\x1b[2m')]
_RESET = '\x1b[0m'

def _strip_ansi(s: str) -> str:
    return _RE_ANSI.sub('', s)

def _line_ms(line: str) -> float | None:
    m = _RE_FLOW_MS.search(_strip_ansi(line))
    return float(m.group(1)) if m else None

def _ms_color(ms: float) -> str:
    for lo, hi, color in _MS_COLORS:
        if lo <= ms < hi:
            return color
    return ''

def _colorize_ms_in_line(line: str, ms: float) -> str:
    color = _ms_color(ms)
    target = f'{ms:.1f}ms'
    idx = line.find(target)
    if idx == -1:
        return line
    return line[:idx] + color + target + _RESET + line[idx + len(target):]

def _stream_and_capture(process: subprocess.Popen, marker: str) -> str:
    data_str = ''
    capturing = False
    import signal
    original_sigint = signal.getsignal(signal.SIGINT)

    def sigint_handler(signum, frame):
        click.secho('\n[!] Interrupção detectada (Ctrl+C). Aguardando finalização e dados da sonda...', fg='yellow')
        signal.signal(signal.SIGINT, original_sigint)
    signal.signal(signal.SIGINT, sigint_handler)
    try:
        for line in iter(process.stdout.readline, ''):
            if marker in line:
                capturing = True
                parts = line.split(marker)
                if parts[0]:
                    sys.stdout.write(parts[0])
                    sys.stdout.flush()
                data_str += parts[1] if len(parts) > 1 else ''
                continue
            if capturing:
                data_str += line
            else:
                sys.stdout.write(line)
                sys.stdout.flush()
        process.wait()
    except KeyboardInterrupt:
        click.secho('\n[!] Cancelamento forçado (Duplo Ctrl+C). Sonda abortada.', fg='red')
        process.terminate()
        process.wait()
    finally:
        signal.signal(signal.SIGINT, original_sigint)
    return data_str.strip()

def _stream_live(process: subprocess.Popen, threshold_ms: float, colorize: bool=True) -> None:
    total_ms = 0.0
    max_ms = 0.0
    max_line = ''
    count = 0
    try:
        for line in iter(process.stdout.readline, ''):
            ms = _line_ms(line)
            if ms is None:
                sys.stdout.write(line)
                sys.stdout.flush()
                continue
            if threshold_ms > 0 and ms < threshold_ms:
                continue
            out = _colorize_ms_in_line(line, ms) if colorize else line
            sys.stdout.write(out)
            sys.stdout.flush()
            total_ms += ms
            count += 1
            if ms > max_ms:
                max_ms = ms
                max_line = _strip_ansi(line).strip()
        process.wait()
    except KeyboardInterrupt:
        click.secho('\n[!] Interrupção manual (Ctrl+C). Encerrando monitoramento...', fg='yellow')
        process.terminate()
        process.wait()
    _print_summary(total_ms, max_ms, max_line, count, threshold_ms)

def _print_summary(total_ms: float, max_ms: float, max_line: str, count: int, threshold_ms: float):
    if count == 0:
        click.echo(f'\n   {Style.DIM}(nenhuma linha acima de {threshold_ms} ms registrada){_RESET}')
        return
    total_color = _ms_color(total_ms)
    max_color = _ms_color(max_ms)
    sep = f'{Style.DIM}{'─' * 80}{_RESET}'
    click.echo(f'\n{sep}')
    click.echo(f'   {Style.BRIGHT}Sumário do Fluxo{_RESET}  {Style.DIM}({count} linhas exibidas' + (f', filtro ≥ {threshold_ms} ms' if threshold_ms > 0 else '') + f'){_RESET}')
    click.echo(f'   {Style.BRIGHT}Total acumulado:{_RESET}  {total_color}{total_ms:.1f} ms{_RESET}')
    click.echo(f'   {Style.BRIGHT}Linha mais lenta:{_RESET} {max_color}{max_ms:.1f} ms{_RESET}' + (f'  {Style.DIM}» {max_line[:60]}{_RESET}' if max_line else ''))
    click.echo(sep)

def _run_autopsy(python_exe, script, args, env):
    from ...probes import debug_probe
    print_debug_header(script, 'DEBUG')
    cmd = build_probe_command(python_exe, debug_probe.__file__, script, mode='debug', args=args)
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1, env=env)
        click.echo(Fore.YELLOW + '   > Iniciando sonda e rastreando saída em tempo real...\n' + Fore.RESET)
        data_str = _stream_and_capture(process, _MARKER_DEBUG)
        if data_str:
            try:
                data = json.loads(data_str)
                if data.get('status') == 'error':
                    report_crash(data, script)
                else:
                    click.secho('\n✅[ SUCESSO ] Autópsia de variáveis concluída.', fg='green')
                    render_variable_table(data.get('variables'))
            except json.JSONDecodeError:
                click.secho('\n🚨 [ FALHA ] Não foi possível decodificar os dados da sonda.', fg='red', bold=True)
                click.echo(data_str)
        else:
            rc = process.returncode
            if rc is not None and rc != 0:
                click.secho(f'\n🚨[ FALHA OU ABORTO ] Processo encerrou com código {rc}', fg='red', bold=True)
            else:
                click.secho('\n📡 [ FINALIZADO ] Processo encerrou sem emitir dados.', fg='cyan')
    except Exception as e:
        click.secho(f'\n❌ Erro no Orquestrador: {e}', fg='red')

def _run_profile(python_exe, script, args, env):
    from ...probes import debug_probe
    print_debug_header(script, 'PERFIL')
    cmd = build_probe_command(python_exe, debug_probe.__file__, script, mode='profile', args=args)
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1, env=env)
        click.echo(Fore.YELLOW + '   > Instrumentando com line-timer + cProfile + tracemalloc...\n' + Fore.RESET)
        data_str = _stream_and_capture(process, _MARKER_PROFILE)
        if data_str:
            try:
                data = json.loads(data_str)
                render_profile_report(data, script)
            except json.JSONDecodeError:
                click.secho('\n🚨 [ FALHA ] Não foi possível decodificar o perfil.', fg='red', bold=True)
                click.echo(data_str)
        else:
            rc = process.returncode
            if rc is not None and rc != 0:
                click.secho(f'\n🚨[ FALHA DE BOOTSTRAP ] Processo encerrou com código {rc}', fg='red', bold=True)
            else:
                click.secho('\n📡 [ FINALIZADO ] Processo encerrou sem emitir dados de perfil.', fg='cyan')
    except Exception as e:
        click.secho(f'\n❌ Erro no Orquestrador (perfil): {e}', fg='red')

def _run_live(python_exe, script, watch, bottleneck, threshold, no_compress, args, env):
    from ...probes import flow_runner
    mode_label = 'VIGILÂNCIA' if watch else 'GARGALOS'
    print_debug_header(script, mode_label)
    if threshold > 0:
        click.echo(f'   {Fore.YELLOW}> Filtro ativo: exibindo apenas linhas ≥ {threshold} ms{Fore.RESET}')
    if no_compress:
        click.echo(f'   {Fore.CYAN}> Iron Gate desativado: todos os loops serão exibidos{Fore.RESET}')
    click.echo('')
    cmd = build_flow_command(python_exe, flow_runner.__file__, script, watch=watch, bottleneck=bottleneck, no_compress=no_compress, args=args)
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1, env=env)
        _stream_live(process, threshold_ms=threshold, colorize=True)
    except Exception as e:
        click.secho(f'\n❌ Erro no modo live: {e}', fg='red')

def _run_memory(python_exe, script, args, env):
    from ...probes import debug_probe
    from .debug_io import render_memory_forensics
    print_debug_header(script, 'MEMÓRIA')
    cmd = build_probe_command(python_exe, debug_probe.__file__, script, mode='memory', args=args)
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1, env=env)
        click.echo(Fore.BLUE + '   > Raio-X ativo: Coletando Garbage Collector e Árvores de Alocação...\n' + Fore.RESET)
        data_str = _stream_and_capture(process, '---DOXOADE-MEMORY-DATA---')
        if data_str:
            try:
                data = json.loads(data_str)
                render_memory_forensics(data, script)
            except json.JSONDecodeError:
                click.secho('\n🚨[ FALHA ] Não foi possível decodificar os dados de memória.', fg='red', bold=True)
                click.echo(data_str)
        else:
            click.secho('\n📡[ FINALIZADO ] Processo encerrou sem emitir dados.', fg='cyan')
    except Exception as e:
        click.secho(f'\n❌ Erro no Orquestrador (memória): {e}', fg='red')

def execute_debug(script: str, watch: str, bottleneck: bool, threshold: float, no_compress: bool, args: str, profile: bool=False, memory: bool=False):
    if (profile or memory) and (watch or bottleneck):
        click.secho('\n❌ Modos profundos (-p, -m) incompatíveis com tempo real (-b, --watch).', fg='red')
        return
    if profile and memory:
        click.secho('\n❌ Use -p (CPU) ou -m (Memória) separadamente para evitar interferência.', fg='red')
        return
    python_exe = _get_venv_python_executable() or sys.executable
    env = get_debug_env(script)
    if watch or bottleneck:
        _run_live(python_exe, script, watch, bottleneck, threshold, no_compress, args, env)
    elif profile:
        _run_profile(python_exe, script, args, env)
    elif memory:
        _run_memory(python_exe, script, args, env)
    else:
        _run_autopsy(python_exe, script, args, env)
