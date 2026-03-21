# -*- coding: utf-8 -*-
"""
Debug Engine v2.4 - Chief Gold Orchestrator.

Novidades:
  - Threshold aceita float (ex: -t 0.5)
  - Flag --no-compress / -nc desativa Iron Gate no flow_runner
  - Colorização de ms por faixa em cada linha do flow
  - Sumário colorido ao final: total acumulado + linha mais lenta
"""
import re
import sys
import subprocess
import json
import click
from doxoade.tools.doxcolors import Fore, Style
from .debug_utils import get_debug_env, build_probe_command, build_flow_command
from .debug_io import (
    print_debug_header,
    render_variable_table,
    report_crash,
    render_profile_report,
)
from ...shared_tools import _get_venv_python_executable


# ─── CONSTANTES ──────────────────────────────────────────────────────────────

_MARKER_DEBUG   = "---DOXOADE-DEBUG-DATA---"
_MARKER_PROFILE = "---DOXOADE-PROFILE-DATA---"

_RE_ANSI    = re.compile(r'\033\[[0-9;]*m')
_RE_FLOW_MS = re.compile(r'[│|]\s*([\d]+\.[\d]+)ms\s*[│|]')

# Faixas de cor para o valor ms (aplicadas na colorização inline)
# (min_ms, max_ms, cor_ansi)
_MS_COLORS = [
    (500.0, float('inf'), '\033[1;31m'),   # vermelho brilhante   ≥ 500 ms
    (100.0, 500.0,        '\033[31m'),     # vermelho             100–500 ms
    ( 20.0, 100.0,        '\033[33m'),     # amarelo               20–100 ms
    (  5.0,  20.0,        '\033[93m'),     # amarelo claro          5–20 ms
    (  0.0,   5.0,        '\033[2m'),      # dim                    < 5 ms
]
_RESET = '\033[0m'


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
    """
    Substitui a primeira ocorrência do valor ms na linha pela versão colorida.
    Opera sobre a string com ANSI intacto — encontra o padrão numérico
    no texto limpo e aplica cor ao número.
    """
    color  = _ms_color(ms)
    target = f"{ms:.1f}ms"
    idx    = line.find(target)
    if idx == -1:
        return line
    return line[:idx] + color + target + _RESET + line[idx + len(target):]


# ─── STREAMING ───────────────────────────────────────────────────────────────

def _stream_and_capture(process: subprocess.Popen, marker: str) -> str:
    data_str  = ""
    capturing = False
    try:
        for line in iter(process.stdout.readline, ''):
            if marker in line:
                capturing = True
                parts = line.split(marker)
                if parts[0]:
                    sys.stdout.write(parts[0])
                    sys.stdout.flush()
                data_str += parts[1] if len(parts) > 1 else ""
                continue
            if capturing:
                data_str += line
            else:
                sys.stdout.write(line)
                sys.stdout.flush()
        process.wait()
    except KeyboardInterrupt:
        click.secho("\n[!] Interrupção manual (Ctrl+C). Encerrando sonda...", fg='yellow')
        process.terminate()
        process.wait()
    return data_str.strip()


def _stream_live(process: subprocess.Popen,
                 threshold_ms: float,
                 colorize: bool = True) -> None:
    """
    Streaming do flow_runner com:
      - filtro de threshold (linhas abaixo de threshold_ms descartadas)
      - colorização do valor ms por faixa
      - acumulação de tempo total visível

    Imprime sumário colorido ao final.
    """
    total_ms  = 0.0
    max_ms    = 0.0
    max_line  = ""
    count     = 0

    try:
        for line in iter(process.stdout.readline, ''):
            ms = _line_ms(line)

            if ms is None:
                # Cabeçalho / borda / loop message — sempre passa, sem colorização
                sys.stdout.write(line)
                sys.stdout.flush()
                continue

            if threshold_ms > 0 and ms < threshold_ms:
                continue   # descarta silenciosamente

            # Coloriza o valor ms na linha
            out = _colorize_ms_in_line(line, ms) if colorize else line
            sys.stdout.write(out)
            sys.stdout.flush()

            # Acumula para o sumário
            total_ms += ms
            count    += 1
            if ms > max_ms:
                max_ms   = ms
                max_line = _strip_ansi(line).strip()

        process.wait()
    except KeyboardInterrupt:
        click.secho("\n[!] Interrupção manual (Ctrl+C). Encerrando monitoramento...", fg='yellow')
        process.terminate()
        process.wait()

    _print_summary(total_ms, max_ms, max_line, count, threshold_ms)


def _print_summary(total_ms: float, max_ms: float,
                   max_line: str, count: int, threshold_ms: float):
    """Sumário colorido exibido após o fim do streaming."""
    if count == 0:
        click.echo(
            f"\n   {Style.DIM}(nenhuma linha acima de {threshold_ms} ms registrada){_RESET}"
        )
        return

    total_color = _ms_color(total_ms)
    max_color   = _ms_color(max_ms)

    sep = f"{Style.DIM}{'─' * 80}{_RESET}"
    click.echo(f"\n{sep}")
    click.echo(
        f"   {Style.BRIGHT}Sumário do Fluxo{_RESET}  "
        f"{Style.DIM}({count} linhas exibidas"
        + (f", filtro ≥ {threshold_ms} ms" if threshold_ms > 0 else "")
        + f"){_RESET}"
    )
    click.echo(
        f"   {Style.BRIGHT}Total acumulado:{_RESET}  "
        f"{total_color}{total_ms:.1f} ms{_RESET}"
    )
    click.echo(
        f"   {Style.BRIGHT}Linha mais lenta:{_RESET} "
        f"{max_color}{max_ms:.1f} ms{_RESET}"
        + (f"  {Style.DIM}» {max_line[:60]}{_RESET}" if max_line else "")
    )
    click.echo(sep)


# ─── MODOS ───────────────────────────────────────────────────────────────────

def _run_autopsy(python_exe, script, args, env):
    from ...probes import debug_probe
    print_debug_header(script, "DEBUG")
    cmd = build_probe_command(python_exe, debug_probe.__file__, script,
                              mode='debug', args=args)
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', bufsize=1, env=env,
        )
        click.echo(Fore.YELLOW + "   > Iniciando sonda e rastreando saída em tempo real...\n" + Fore.RESET)
        data_str = _stream_and_capture(process, _MARKER_DEBUG)

        if data_str:
            try:
                data = json.loads(data_str)
                if data.get('status') == 'error':
                    report_crash(data, script)
                else:
                    click.secho("\n✅[ SUCESSO ] Autópsia de variáveis concluída.", fg='green')
                    render_variable_table(data.get('variables'))
            except json.JSONDecodeError:
                click.secho("\n🚨 [ FALHA ] Não foi possível decodificar os dados da sonda.", fg='red', bold=True)
                click.echo(data_str)
        else:
            rc = process.returncode
            if rc is not None and rc != 0:
                click.secho(f"\n🚨[ FALHA DE BOOTSTRAP ] Processo encerrou com código {rc}", fg='red', bold=True)
            else:
                click.secho("\n📡 [ FINALIZADO ] Processo encerrou sem emitir dados.", fg='cyan')
    except Exception as e:
        import sys as _s; from traceback import print_tb as _t
        _, _o, _tb = _s.exc_info()
        print(f"\033[31m ■ {e} ■ {_o}\n"); _t(_tb)
        click.secho(f"\n❌ Erro no Orquestrador: {e}", fg='red')


def _run_profile(python_exe, script, args, env):
    from ...probes import debug_probe
    print_debug_header(script, "PERFIL")
    cmd = build_probe_command(python_exe, debug_probe.__file__, script,
                              mode='profile', args=args)
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', bufsize=1, env=env,
        )
        click.echo(
            Fore.YELLOW + "   > Instrumentando com line-timer + cProfile + tracemalloc...\n" + Fore.RESET
        )
        data_str = _stream_and_capture(process, _MARKER_PROFILE)

        if data_str:
            try:
                data = json.loads(data_str)
                render_profile_report(data, script)
            except json.JSONDecodeError:
                click.secho("\n🚨 [ FALHA ] Não foi possível decodificar o perfil.", fg='red', bold=True)
                click.echo(data_str)
        else:
            rc = process.returncode
            if rc is not None and rc != 0:
                click.secho(f"\n🚨[ FALHA DE BOOTSTRAP ] Processo encerrou com código {rc}", fg='red', bold=True)
            else:
                click.secho("\n📡 [ FINALIZADO ] Processo encerrou sem emitir dados de perfil.", fg='cyan')
    except Exception as e:
        import sys as _s; from traceback import print_tb as _t
        _, _o, _tb = _s.exc_info()
        print(f"\033[31m ■ {e} ■ {_o}\n"); _t(_tb)
        click.secho(f"\n❌ Erro no Orquestrador (perfil): {e}", fg='red')


def _run_live(python_exe, script, watch, bottleneck,
              threshold, no_compress, args, env):
    from ...probes import flow_runner
    mode_label = "VIGILÂNCIA" if watch else "GARGALOS"
    print_debug_header(script, mode_label)

    if threshold > 0:
        click.echo(
            f"   {Fore.YELLOW}> Filtro ativo: exibindo apenas linhas ≥ {threshold} ms{Fore.RESET}"
        )
    if no_compress:
        click.echo(
            f"   {Fore.CYAN}> Iron Gate desativado: todos os loops serão exibidos{Fore.RESET}"
        )
    click.echo("")

    cmd = build_flow_command(
        python_exe, flow_runner.__file__, script,
        watch=watch, bottleneck=bottleneck,
        no_compress=no_compress, args=args,
    )

    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', bufsize=1, env=env,
        )
        _stream_live(process, threshold_ms=threshold, colorize=True)

    except Exception as e:
        import sys as _s; from traceback import print_tb as _t
        _, _o, _tb = _s.exc_info()
        print(f"\033[31m ■ {e} ■ {_o}\n"); _t(_tb)
        click.secho(f"\n❌ Erro no modo live: {e}", fg='red')


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

def execute_debug(script: str, watch: str, bottleneck: bool,
                  threshold: float, no_compress: bool,
                  args: str, profile: bool = False):
    """
    Roteamento:
      -p            → perfil profundo
      -b [-t N]     → bottleneck com filtro e sumário colorido
      --watch VAR   → vigilância em tempo real
      -nc           → desativa Iron Gate (qualquer modo live)
      (nenhum)      → autópsia de variáveis
    """
    if profile and (watch or bottleneck):
        click.secho(
            "\n❌ --profile (-p) é incompatível com --watch e --bottleneck.\n"
            "   Use -p para análise pós-execução ou -b/--watch para tempo real.",
            fg='red', bold=True,
        )
        return

    python_exe = _get_venv_python_executable() or sys.executable
    env        = get_debug_env(script)

    if watch or bottleneck:
        _run_live(python_exe, script, watch, bottleneck,
                  threshold, no_compress, args, env)
    elif profile:
        _run_profile(python_exe, script, args, env)
    else:
        _run_autopsy(python_exe, script, args, env)