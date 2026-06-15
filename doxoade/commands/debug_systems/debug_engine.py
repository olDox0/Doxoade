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

from .debug_utils import get_debug_env, build_probe_command, build_flow_command
from .debug_io import print_debug_header, render_variable_table, report_crash, render_profile_report

from doxoade.tools.horus        import horus_trace
from doxoade.tools.doxcolors    import Fore, Style
from doxoade.tools.filesystem   import _get_venv_python_executable
from doxoade.tools.aegis.warden import apply_resource_limits

_MARKER_DATA = '---DOXOADE-DATA-BLOCK---' 
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

@horus_trace
def _stream_and_capture(process, marker):
    import json, sys
    data_buffer = []
    full_log = [] # Captura tudo para caso de falha
    capturing = False

    while True:
        line = process.stdout.readline()
        if not line: break
        full_log.append(line)
        
        if marker in line:
            capturing = True
            parts = line.split(marker)
            if len(parts) > 1: data_buffer.append(parts[1])
            continue
            
        if capturing:
            data_buffer.append(line)
        else:
            sys.stdout.write(line)
            sys.stdout.flush()

    process.wait()
    raw = "".join(data_buffer).strip()
    
    if "{" in raw and "}" in raw:
        try:
            return json.loads(raw[raw.find("{"):raw.rfind("}")+1])
        except Exception as e:
            import sys as _dox_sys, os as _dox_os
            from traceback import print_tb as exc_trace
            exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
            f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_n = exc_tb.tb_lineno
            exc_trace(exc_tb)
            print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _stream_and_capture\033[0m")
            print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
            return None
        
    # [PLATINUM] Se não achou JSON, mas o processo deu erro, mostra o log de erro
    if process.returncode != 0:
        click.secho("\n✘ A sonda nativa colapsou durante a execução.", fg='red', bold=True)
        # O Hórus FUNCTION_ERROR capturará os detalhes
    return None

def _stream_live(process, threshold_ms, colorize=True):
#def _stream_live(process: subprocess.Popen, threshold_ms: float, colorize: bool=True) -> None:
    total_ms = 0.0
    max_ms = 0.0
    max_line = ''
    count = 0
    captured_debug_data = None
    try:
        for line in iter(process.stdout.readline, ''):
            # [CHIEF-GOLD] Interceptação de Dados Forenses em tempo real
            if _MARKER_DEBUG in line:
                try:
                    raw_json = line.split(_MARKER_DEBUG)[1].strip()
                    captured_debug_data = json.loads(raw_json)
                    captured_data = json.loads(raw_json)
                except Exception as e:
                    import sys as exc_sys
                    from traceback import print_tb as exc_trace
                    _, exc_obj, exc_tb = exc_sys.exc_info()
                    exc_trace(exc_tb)
                continue

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
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)

    _print_summary(total_ms, max_ms, max_line, count, threshold_ms)
    if captured_debug_data and 'variables' in captured_debug_data:
        render_variable_table(captured_debug_data['variables'])
        
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
            except Exception as e:
                import sys as exc_sys
                from traceback import print_tb as exc_trace
                _, exc_obj, exc_tb = exc_sys.exc_info()
                exc_trace(exc_tb)

        else:
            rc = process.returncode
            if rc is not None and rc != 0:
                click.secho(f'\n🚨[ FALHA OU ABORTO ] Processo encerrou com código {rc}', fg='red', bold=True)
            else:
                click.secho('\n📡 [ FINALIZADO ] Processo encerrou sem emitir dados.', fg='cyan')
    except Exception as e:
        click.secho(f'\n❌ Erro no Orquestrador: {e}', fg='red')
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)

def _run_profile(python_exe, script_to_probe, args_str, env):
    from .debug_utils import build_probe_command
    from .debug_io import render_profile_report # [FIX] Importação local
    
    probe_script = os.path.join(os.path.dirname(__file__), "../../probes/debug_probe.py")
    cmd = build_probe_command(python_exe, probe_script, script_to_probe, "profile", args_str)
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                               text=True, encoding='utf-8', env=env, shell=False)
    
    data = _stream_and_capture(process, "---DOXOADE-PROFILE-DATA---")
    
    # [PLATINUM FIX] Sincronia de Argumentos (Data + Script)
    if data and isinstance(data, dict) and data.get('status') == 'success':
        render_profile_report(data, script_to_probe)
    else:
        click.echo(Fore.RED + f"✘ Perfil: Sonda falhou ou não retornou dados. ({data.get('error') if data else 'Vazio'})")
        
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
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)
#        click.echo(traceback.format_exc())

def _run_memory(python_exe, script_to_probe, args_str, env):
    from .debug_utils import build_probe_command
    from .debug_io import render_memory_forensics # [FIX] Função correta para modo -m
    
    probe_script = os.path.join(os.path.dirname(__file__), "../../probes/debug_probe.py")
    cmd = build_probe_command(python_exe, probe_script, script_to_probe, "memory", args_str)
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                               text=True, encoding='utf-8', env=env, shell=False)
    
    data = _stream_and_capture(process, "---DOXOADE-MEMORY-DATA---")
    
    # [PLATINUM FIX] Sincronia de Argumentos (Data + Script)
    if data and isinstance(data, dict) and data.get('status') == 'success':
        render_memory_forensics(data, script_to_probe)
    else:
        click.echo(Fore.RED + "✘ Memória: Sonda encerrou sem dados válidos.")

def execute_debug(target, is_internal, test_mode=False, **kwargs):
    """Orquestrador de Debug v98.6 - Estabilidade Aegis."""
    import os, sys, shlex, click
    from doxoade.tools.filesystem import _get_venv_python_executable
    from doxoade.tools.aegis.warden import apply_resource_limits
    from .debug_utils import get_debug_env

    # 1. Resolução do Interpretador e Alvos
    python_exe = _get_venv_python_executable() or sys.executable
    target_clean = target.replace('\\', '/')
    
    if is_internal:
        from ...probes import command_wrapper
        script_to_probe = command_wrapper.__file__.replace('\\', '/')
        args_str = target_clean 
    else:
        script_to_probe = os.path.abspath(target_clean).replace('\\', '/')
        args_str = kwargs.get('target_args', '')

    # 2. Construção Única do Ambiente (ENV)
    # Pegamos o env base e injetamos as autorizações
    env = get_debug_env(script_to_probe) or os.environ.copy()
    
    env['PYTHONIOENCODING'] = 'utf-8' 
    
    if test_mode:
        env['DOXOADE_TEST_MODE'] = '1'
        env['DOXOADE_AUTHORIZED_RUN'] = '1' 
        # click.secho("🛡️ [AEGIS] Autorização de Teste ativa.", fg="cyan", dim=True)

    # 3. Aplicação de Limites (Warden)
    apply_resource_limits({
        'cpu': kwargs.get('processing_limiter'), 
        'ram': kwargs.get('ram_limiter'), 
        'disk': kwargs.get('disk_limiter')
    })

    # 4. Matriz de Decisão de Execução
    profile = kwargs.get('profile', False)
    memory = kwargs.get('memory', False)
    is_flow = any([
        kwargs.get('flow_val'), 
        kwargs.get('flow_import'), 
        kwargs.get('flow_func'), 
        kwargs.get('bottleneck')
    ])
    
    if is_flow:
        _run_flow_mode_v2(python_exe, script_to_probe, is_internal, env, kwargs)
    elif memory:
        _run_memory(python_exe, script_to_probe, args_str, env)
    elif profile:
        _run_profile(python_exe, script_to_probe, args_str, env)
    else:
        _run_autopsy(python_exe, script_to_probe, args_str, env)

def build_probe_command(target: str, is_internal: bool, probe_name: str, **kwargs) -> list:
    import os, sys, shlex
    from pathlib import Path
    
    # v111.0: Caminhos sempre em POSIX (/)
    probe_dir = Path(__file__).resolve().parents[2] / "probes"
    probe_path = (probe_dir / probe_name).as_posix()

    if is_internal:
        wrapper_path = (probe_dir / "command_wrapper.py").as_posix()
        # Passamos a lista. O Popen (com shell=False) vai proteger os espaços.
        return [sys.executable, wrapper_path, target]
    else:
        # Modo arquivo normal
        args_list = shlex.split(kwargs.get('target_args', ''))
        return [sys.executable, probe_path, 'file', target] + args_list

def _run_flow_mode_v2(python_exe, script_to_probe, is_internal, env, kwargs):
    """Orquestrador de Fluxo Platinum - Resolve o Silêncio do Bottleneck."""
    from .debug_utils import build_flow_command
    import subprocess
    
    # 1. Constrói o comando como lista (O SO cuida das aspas automaticamente)
    cmd, _ = build_flow_command(script_to_probe, is_internal, kwargs)
    
    click.echo(Fore.CYAN + '   > Rastreando gargalos de performance (Bottleneck Mode)...\n')

    try:
        # [VITAL] shell=False garante que o Windows não quebre caminhos com espaços
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            encoding='utf-8', 
            env=env, 
            bufsize=1, 
            shell=False
        )

        # 2. Captura os dados emitidos pelo flow_runner.py
        data = _stream_and_capture(process, "---DOXOADE-DATA-BLOCK---")
        
        if data and 'line_hotspots' in data:
            from .debug_io import render_line_hotspots
            # Aqui calculamos o tempo total real do rastro
            total_ms = sum(s['total_ms'] for s in data['line_hotspots'])
            render_line_hotspots(data['line_hotspots'], total_ms)
        else:
            # Se chegarmos aqui, o Hórus vai nos dizer o que o _stream_and_capture retornou
            click.echo(Fore.YELLOW + "   [!] Sonda finalizada. Nenhum gargalo significativo detectado.")

    except Exception as e:
        click.echo(Fore.RED + f"✘ Falha ao iniciar rastro: {e}")
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)


@horus_trace
def _stream_and_capture(process, marker):
    """Capturador Universal com Filtro de Ruído (Anti-Extra-Data)."""
    import json, sys
    data_buffer = []
    capturing = False

    while True:
        line = process.stdout.readline()
        if not line: break
        
        # [CHIEF-GOLD] Sincronia de Marcador e Dados na mesma linha
        if marker in line:
            capturing = True
            parts = line.split(marker)
            # Se houver JSON após o marcador na mesma linha, captura!
            if len(parts) > 1 and "{" in parts[1]:
                data_buffer.append(parts[1])
            continue
            
        if capturing:
            data_buffer.append(line)
        else:
            # Repassa logs normais para o usuário
            sys.stdout.write(line)
            sys.stdout.flush()

    process.wait()
    raw = "".join(data_buffer).strip()
    
    # [PLATINUM] Captura multilinhas do JSON
    if "{" in raw and "}" in raw:
        json_clean = raw[raw.find("{") : raw.rfind("}") + 1]
        try:
            return json.loads(json_clean)
        except Exception as e:
            # O Horus capturará este erro se o JSON estiver incompleto
            raise RuntimeError(f"Erro no parser de stream: {e}")
    return None

def _stream_and_capture_multiple(process, marker):
    """Captura Múltiplos blocos JSON do stdout."""
    blobs = []
    current_blob = []
    capturing = False
    
    while True:
        line = process.stdout.readline()
        if not line: break

        if marker in line:
            if capturing: # Final de um bloco
                try:
                    blobs.append(json.loads("".join(current_blob)))
                except Exception as e:
                    import sys as exc_sys
                    from traceback import print_tb as exc_trace
                    _, exc_obj, exc_tb = exc_sys.exc_info()
                    exc_trace(exc_tb)

                current_blob = []
            capturing = True
            parts = line.split(marker)
            if len(parts) > 1: current_blob.append(parts[1])
            continue
        
        if capturing:
            current_blob.append(line)
        else:
            sys.stdout.write(line)
            sys.stdout.flush()
            
    if current_blob: # Pega o último bloco
        try:
            blobs.append(json.loads("".join(current_blob)))
        except Exception as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            exc_trace(exc_tb)

    process.wait()
    return blobs

def run_debug_in_process(target, **kwargs):
    """v125.0: In-Process Execution sem Alucinação de Path."""
    import os, sys, shlex
    from doxoade.tools.aegis.aegis_utils import restricted_safe_exec

    # Se o target tem espaços, é uma cadeia de comando da incepção
    if " " in target.strip():
        # Apenas ignoramos o open() e deixamos a incepção fluir pelo run.py
        return 

    # Se for um arquivo real, vacinamos e rodamos
    abs_path = os.path.abspath(target).replace('\\', '/')
    if os.path.exists(abs_path):
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        restricted_safe_exec(content, {'__name__': '__main__', '__file__': abs_path}, allow_imports=True)
