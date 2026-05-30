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
import os
import json
import click
from doxoade.tools.doxcolors import Fore, Style
from .debug_utils import get_debug_env, build_probe_command, build_flow_command
from .debug_io import print_debug_header, render_variable_table, report_crash, render_profile_report
from doxoade.tools.filesystem import _get_venv_python_executable
from doxoade.tools.aegis.warden import apply_resource_limits

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
    """Captura a saída, exibe logs em tempo real e extrai o JSON final."""
    import signal
    data_buffer = []
    capturing = False
    
    # Shield para Ctrl+C
    original_sigint = signal.getsignal(signal.SIGINT)
    def sigint_handler(signum, frame):
        signal.signal(signal.SIGINT, original_sigint)
    signal.signal(signal.SIGINT, sigint_handler)

    try:
        for line in iter(process.stdout.readline, ''):
            # Procura pelo marcador de início de dados
            if marker in line:
                capturing = True
                # Captura o que estiver na mesma linha após o marcador
                parts = line.split(marker)
                if len(parts) > 1 and parts[1].strip():
                    data_buffer.append(parts[1])
                continue
            
            if capturing:
                data_buffer.append(line)
            else:
                # Exibe a saída do comando interno (check, etc) para o usuário
                sys.stdout.write(line)
                sys.stdout.flush()
                
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
    finally:
        signal.signal(signal.SIGINT, original_sigint)

    # Limpeza Forense: Isola o primeiro '{' e o último '}' para garantir JSON puro
    raw_content = "".join(data_buffer).strip()
    if "{" in raw_content and "}" in raw_content:
        start_idx = raw_content.find("{")
        end_idx = raw_content.rfind("}") + 1
        return raw_content[start_idx:end_idx]
    
    return raw_content

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
    sep = f"{Style.DIM}{'─' * 80}{_RESET}"
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

def _run_live(python_exe, script, args, env, watch, bottleneck, threshold=0.0, no_compress=False):
    """Executa o monitoramento em tempo real com rastro visual (MATRIX MODE)."""
    from ...probes import flow_runner
    import subprocess
    import sys

    # --- BLOCO DE DIAGNÓSTICO VERBOSO (Aegis Shield) ---
    if not isinstance(env, dict):
        click.secho(f"--- [ERRO CRÍTICO DE TIPO] ---", fg='red', bold=True)
        click.echo(f"O objeto 'env' não é um dicionário. Tipo atual: {type(env)}")
        return

    # Validação rigorosa de tipos para o Windows
    for k, v in env.items():
        if not isinstance(k, str) or not isinstance(v, str):
             click.secho(f"--- [DETALHES DO ERRO DE AMBIENTE] ---", fg='red', bold=True)
             click.echo(f"Chave/Valor inválido detectado no Windows Environment.")
             click.echo(f"K: {k} ({type(k)}) | V: {v} ({type(v)})")
             return

    # Construtor do comando de rastro
    cmd = build_flow_command(python_exe, flow_runner.__file__, script, 
                             watch=watch, bottleneck=bottleneck, 
                             no_compress=no_compress, args=args) # threshold=threshold,
    
    try:
        # PASC-6.4: I/O de stream para o modo Live (Matrix)
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=sys.stderr, 
            text=True, encoding='utf-8', errors='replace', env=env, bufsize=1
        )
        _stream_live(process, threshold)
    except Exception as e:
        import traceback
        click.secho(f'\n❌ Falha catastrófica ao iniciar subprocesso:', fg='red', bold=True)
        click.echo(f'Erro: {e}')
        click.echo('\n--- TRACEBACK DO ERRO ---')
        click.echo(traceback.format_exc())

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

def execute_debug(script, is_internal=False, **kwargs):
    """Orquestrador de Debug v95.5."""
    import os
    import sys
    from doxoade.tools.filesystem import _get_venv_python_executable
    from doxoade.tools.aegis.warden import apply_resource_limits

    # 1. Aplica Célula de Carga (Warden)
    limits = {
        'cpu': kwargs.get('processing_limiter'),
        'ram': kwargs.get('ram_limiter'),
        'disk': kwargs.get('disk_limiter')
    }
    apply_resource_limits(limits)

    # 2. Prepara Ambiente e Interpretador
    python_exe = _get_venv_python_executable() or sys.executable
    env_raw = get_debug_env(script)
    env = {str(k): str(v) for k, v in env_raw.items()}

    # 3. Decisao de Motor de Rastro (Prioridade ao Flow)
    is_flow = any([kwargs.get('flow_val'), kwargs.get('flow_import'), kwargs.get('flow_func')])

    if is_flow:
        _run_flow_mode_v2(python_exe, script, is_internal, env, kwargs)
        return
    if any([kwargs.get('flow_val'), kwargs.get('flow_import'), kwargs.get('flow_func')]):
        _run_flow_mode_v2(python_exe, script, is_internal, env, kwargs)
        return # Garante que o retorno do flow-mode encerre o comando pai limpo
    if kwargs.get('profile'):
        _run_profile(python_exe, script, kwargs.get('target_args'), env)
    elif kwargs.get('memory'):
        _run_memory(python_exe, script, kwargs.get('target_args'), env)
    else:
        _run_autopsy(python_exe, script, kwargs.get('target_args'), env)

    # 1. ALVO (Prioridade Zero: Define antes de usar!)
    if is_internal:
        from ...probes import command_wrapper
        script_to_probe = command_wrapper.__file__
        args_str = script 
    else:
        script_to_probe = script
        args_str = kwargs.get('args', '')

    # 2. AMBIENTE (Blindagem contra TypeError no Windows)
    try:
        env_raw = get_debug_env(script_to_probe)
        if env_raw is None: 
            env_raw = os.environ.copy()
    except Exception:
        env_raw = os.environ.copy()
    
    # Sanitização: Força tudo para String para evitar 'environment must be dictionary'
    env = {str(k): str(v) for k, v in env_raw.items() if v is not None}

    # 3. PARÂMETROS
    profile = kwargs.get('profile', False)
    memory = kwargs.get('memory', False)
    watch = kwargs.get('watch')
    bottleneck = kwargs.get('bottleneck', False)
    raw_th = kwargs.get('threshold')
    threshold = float(raw_th) if raw_th is not None else 0.0
    no_compress = kwargs.get('no_compress', False)

    # 4. VALIDAÇÃO DE CONFLITOS
    if (profile or memory) and (watch or bottleneck):
        click.secho('\n❌ Erro: Mistura de modos profundos e tempo real.', fg='red')
        return

    # 5. EXECUÇÃO
    python_exe = _get_venv_python_executable() or sys.executable

    if memory:
        _run_memory(python_exe, script_to_probe, args_str, env)
    elif profile:
        _run_profile(python_exe, script_to_probe, args_str, env)
    elif watch or bottleneck:
        _run_live(python_exe, script_to_probe, args_str, env, watch, bottleneck, threshold, no_compress)
    else:
        _run_autopsy(python_exe, script_to_probe, args_str, env)
        
def _run_flow_mode_v2(python_exe, script, is_internal, env, kwargs):
    """Executa o rastro e aciona Lazarus no PAI se o FILHO crashar."""
    from .debug_io import print_debug_header
    from doxoade.rescue import activate_protocol
    
    print_debug_header(script, mode="NEXUS FLOW")
    kwargs['is_internal'] = is_internal
    cmd = build_flow_command(python_exe, None, script, args=kwargs.get('target_args'), **kwargs)
    
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
        text=True, encoding='utf-8', errors='replace', env=env, bufsize=1
    )
    
    full_output = []
    for line in iter(process.stdout.readline, ''):
        full_output.append(line)
        sys.stdout.write(line)
        sys.stdout.flush()
    
    process.wait()
    
    # Se o processo filho crashou, o PAI assume o Lazarus com o log capturado
    if process.returncode != 0:
        activate_protocol("".join(full_output))