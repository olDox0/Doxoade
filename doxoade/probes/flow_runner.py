# doxoade/doxoade/probes/flow_runner.py
import sys, os, time, argparse, warnings, json, linecache, shlex

try:
    import doxoade
except ImportError:
    _candidate = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _root = os.path.dirname(_candidate)
    if _root not in sys.path:
        sys.path.insert(0, _root)
except Exception as e:
    import sys as exc_sys
    from traceback import print_tb as exc_trace
    _, exc_obj, exc_tb = exc_sys.exc_info()
    exc_trace(exc_tb)

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
import flow_utils as utils
#from .flow_utils import render_flow_table
try:
    import flow_utils as utils
    from debug_probe import _LineTimer, _capture_locals, _MARKER_DEBUG
except ImportError:
    from doxoade.probes import flow_utils as utils
    from doxoade.probes.debug_probe import _LineTimer, _capture_locals, _MARKER_DEBUG

    import sys as exc_sys
    from traceback import print_tb as exc_trace
    _, exc_obj, exc_tb = exc_sys.exc_info()
    exc_trace(exc_tb)
    from doxoade.rescue import activate_protocol
    import traceback
    activate_protocol(traceback.format_exc())

#from .debug_probe import _LineTimer, _capture_locals, _MARKER_DEBUG

warnings.filterwarnings('ignore', category=RuntimeWarning)
C_RESET = '\x1b[0m'
C_CYAN, C_YELLOW, C_WHITE = ('\x1b[96m', '\x1b[93m', '\x1b[97m')
C_BORDER, C_MAGENTA, C_GREEN = ('\x1b[90m', '\x1b[95m', '\x1b[92m')
C_BOLD, C_DIM, C_RED, SEP = ('\x1b[1m', '\x1b[2m', '\x1b[91m', '\x1b[90m│\x1b[0m')
_STATE = {'last_time': time.perf_counter(), 'last_locals': {}, 'project_root': '', 'target_file': None, 'indent_level': 0, 'flow_base': False, 'flow_val': False, 'flow_import': False, 'flow_func': False, 'history': [], 'active_pattern': None, 'pattern_idx': 0, 'hidden_count': 0, 'no_compress': False}

def _flush_iron_gate():
    if _STATE['hidden_count'] > 0:
        p_len = len(_STATE['active_pattern'])
        reps = _STATE['hidden_count'] // p_len
        p_desc = ' ➔ '.join([str(id[1]) for id in _STATE['active_pattern']])
        print(f'{C_BORDER}│{C_RESET} {C_DIM}         [ 🔄 LOOP: {p_desc} repetido {reps + 1:03}x omitido ]{C_RESET}')
    _STATE['active_pattern'] = None
    _STATE['hidden_count'] = 0
    _STATE['pattern_idx'] = 0
    _STATE['history'] = []

def _handle_compression(current_id):
    if _STATE['active_pattern']:
        expected = _STATE['active_pattern'][_STATE['pattern_idx']]
        if current_id == expected:
            _STATE['hidden_count'] += 1
            _STATE['pattern_idx'] = (_STATE['pattern_idx'] + 1) % len(_STATE['active_pattern'])
            return True
        else:
            _flush_iron_gate()
    _STATE['history'].append(current_id)
    h = _STATE['history']
    if len(h) > 20:
        h.pop(0)
    for size in range(1, 7):
        if len(h) >= size * 2:
            pattern = h[-size:]
            previous = h[-size * 2:-size]
            if pattern == previous:
                _STATE['active_pattern'] = pattern
                _STATE['pattern_idx'] = 1 % size
                _STATE['hidden_count'] = 1
                return True
    return False

def static_trace_calls(frame, event, arg):
    """Tratador de eventos de rastro (Refatorado v81.8)."""
    filename = frame.f_code.co_filename
    lineno = frame.f_lineno
    if _should_skip_trace(filename):
        return None
    if event == 'line' and (not _STATE['no_compress']) and _handle_compression((filename, lineno)):
        return static_trace_calls
    _render_trace_event(frame, event)
    return static_trace_calls

def _should_skip_trace(filename: str) -> bool:
    """Filtro de Foco Nexus - Bloqueia Libs e foca no Projeto."""
    norm = filename.replace('\\', '/').lower()
    
    # 1. BLOQUEIO DE LIBS (O que você pediu)
    if 'site-packages' in norm or 'dist-packages' in norm:
        return True
    
    # 2. BLOQUEIO DE INTERNOS DO PYTHON
    if '/lib/' in norm and 'doxoade' not in norm:
        return True

    # 3. LISTA DE RUÍDO SISTÊMICO
    noise = ['<frozen', 'importlib', 'abc.py', 'typing.py', 'functools.py', 'glob.py', 'pathlib.py']
    if any(x in norm for x in noise):
        return True
        
    return False

def _render_trace_event(frame, event):
    """Especialista de Renderização UI (PASC 8.5)."""
    filename = frame.f_code.co_filename
    lineno = frame.f_lineno
    line = linecache.getline(filename, lineno).strip()
    if _STATE['flow_func']:
        if event == 'call':
            _flush_iron_gate()
            func = frame.f_code.co_name
            print(f"{C_BORDER}│{C_RESET} {'  ' * _STATE['indent_level']}{C_MAGENTA}➔ CALL: {C_BOLD}{func}{C_RESET}")
            _STATE['indent_level'] += 1
            return
        elif event == 'return':
            _flush_iron_gate()
            _STATE['indent_level'] = max(0, _STATE['indent_level'] - 1)
            print(f"{C_BORDER}│{C_RESET} {'  ' * _STATE['indent_level']}{C_GREEN}⇠ RETN: {C_BOLD}{frame.f_code.co_name}{C_RESET}")
            return
    if event != 'line':
        return
    if _STATE['flow_import'] and ('import ' in line or 'from ' in line):
        print(f"{C_BORDER}│{C_RESET} {' ' * 7}ms {SEP} {C_YELLOW}[ MÓDULO ] {C_WHITE}{os.path.basename(filename)}:{lineno}{SEP} {line}")
    if _STATE['flow_base'] or _STATE['flow_val']:
        now = time.perf_counter()
        ms = (now - _STATE['last_time']) * 1000
        _STATE['last_time'] = now
        diffs = []
        if _STATE['flow_val']:
            for k, v in list(frame.f_locals.items()):
                if k.startswith('__') or k in ['self', 'cls']:
                    continue
                if _STATE['last_locals'].get(k) != v:
                    diffs.append(f'{C_CYAN}{k}{C_DIM}={C_YELLOW}{_safe_to_string(v)}{C_RESET}')
            _STATE['last_locals'] = frame.f_locals.copy()
        loc = f"{'  ' * _STATE['indent_level']}{os.path.basename(filename)}:{lineno}".ljust(25)
        print(f"{C_BORDER}│{C_RESET} {ms:7.1f}ms {SEP} {C_WHITE}{loc}{SEP} {line[:50].ljust(50)} {SEP} {', '.join(diffs)}")

def run_flow(target_path, **kwargs):
    """Orquestrador de rastro Platinum v136.0."""
    abs_path = os.path.abspath(target_path).replace('\\', '/')
    # Âncora de projeto resiliente
    project_root = os.path.dirname(abs_path)
    if 'tests' in abs_path: project_root = os.path.dirname(project_root)
    
    code = open(abs_path, 'r', encoding='utf-8', errors='ignore').read()
    
    # Se for bottleneck, desativa o rastro Matrix para não poluir o tempo/pipe
    is_b = kwargs.get('bottleneck', False)
    timer = _LineTimer(abs_path, project_root, live_flow=not is_b)
    
    sys.settrace(timer.tracer)
    try:
        os.environ['DOXOADE_AUTHORIZED_RUN'] = '1'
        restricted_safe_exec(code, {'__file__': abs_path, '__name__': '__main__'}, allow_imports=True)
    except Exception as e:
        # Captura forense em caso de crash
        tb = sys.exc_info()[2]
        while tb and tb.tb_next: tb = tb.tb_next
        if tb:
            data = {"error": str(e), "variables": _capture_locals(tb.tb_frame.f_locals), "line": tb.tb_lineno}
            sys.stdout.write(f"\n{_MARKER_DEBUG}{json.dumps(data)}\n")
        raise e
    finally:
        sys.settrace(None)
        # EMISSÃO ÚNICA DE DADOS DE PERFORMANCE
        stats = timer.top_lines(limit=15)
        sys.stdout.write(f"\n---DOXOADE-DATA-BLOCK---\n{json.dumps({'line_hotspots': stats})}\n")
        sys.stdout.flush()

def _bootstrap_package(script_path):
    abs_path = os.path.abspath(script_path)
    current = os.path.dirname(abs_path)
    parts = []
    while os.path.exists(os.path.join(current, '__init__.py')):
        parts.insert(0, os.path.basename(current))
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    if current not in sys.path:
        sys.path.insert(0, current)
    return ('.'.join(parts), current)

def _safe_to_string(val):
    try:
        if 'importlib' in getattr(type(val), '__module__', ''):
            return '<Internal>'
        s = str(val).replace('\n', ' ')
        return s[:25] + '...' if len(s) > 28 else s
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)

        print(f'\x1b[0;33m _safe_to_string - Exception: {e}')
        return '<Error>'

def run_flow(target_path, shadow_src=None, **kwargs):
    """
    Orquestrador de rastro v100.0. 
    Aceita path ou código fonte direto (Shadow).
    """
    import os
    clean_path = str(target_path).strip('"\' ').replace('\\', '/')
    abs_path = os.path.abspath(clean_path).replace('\\', '/')
    project_root = os.path.dirname(abs_path)

    if shadow_src:
        code = shadow_src
    else:
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Alvo não localizado: {abs_path}")
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()

    if not os.path.exists(abs_path):
        # Tenta uma última vez resolver se o path veio concatenado errado
        abs_path = abs_path.split('"')[-1] 

    with open(abs_path, 'r', encoding='utf-8') as f:
        code = f.read()

    timer = _LineTimer(target_file=abs_path, project_root=project_root)
    sys.settrace(timer.tracer)
    
    try:
        # Define autorização para o Aegis
        os.environ['DOXOADE_AUTHORIZED_RUN'] = '1'
        globs = {'__file__': abs_path, '__name__': '__main__'}
        restricted_safe_exec(code, globs, allow_imports=True, filename=abs_path)
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)
    finally:
        sys.settrace(None)
        # Agora a função abaixo já foi definida e o Python a encontrará
        _render_flow_results(timer)

def _render_flow_results(timer):
    stats = timer.top_lines(limit=15)
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}🌊 NEXUS FLOW: Tabela de Performance (Top 15){Style.RESET_ALL}")
    print(f"{Fore.WHITE}{'MS TOTAL':>10} | {'LOCALIZAÇÃO':<30} | {'CONTEÚDO'}{Style.RESET_ALL}")
    for s in stats:
        file_short = os.path.basename(s['file'])
        t_color = Fore.RED if s['total_ms'] > 10 else Fore.CYAN
        print(f"{t_color}{s['total_ms']:>8.2f}ms {Fore.WHITE}│ {Fore.YELLOW}{file_short}:{s['line']:<25} {Fore.WHITE}│ {s['content'][:60]}{Style.RESET_ALL}")

def run_flow(target_path, **kwargs):
    abs_path = os.path.abspath(target_path).replace('\\', '/')
    project_root = os.path.dirname(abs_path)
    
    with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()

    # bottleneck mode desativa rastro Matrix para não interferir no tempo
    timer = _LineTimer(abs_path, project_root, live_flow=not kwargs.get('bottleneck'))
    
    globs = {'__file__': abs_path, '__name__': '__main__'}
    os.environ['DOXOADE_AUTHORIZED_RUN'] = '1'
    
    sys.settrace(timer.tracer)
    try:
        restricted_safe_exec(code, globs, allow_imports=True, filename=abs_path)
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)

        # Captura forense de variáveis no momento do crash
        tb = sys.exc_info()[2]
        while tb.tb_next: tb = tb.tb_next
        
        debug_data = {
            "error": str(e),
            "variables": _capture_locals(tb.tb_frame.f_locals),
            "line": tb.tb_lineno
        }
        sys.stdout.write(f"\n{_MARKER_DEBUG}{json.dumps(debug_data)}\n")
        sys.stdout.flush()
        raise e
    finally:
        sys.settrace(None)
        _render_flow_results(timer)

if __name__ == '__main__':
    # [PLATINUM] Suporte a SpacePath e Flags
    if len(sys.argv) < 2: sys.exit(1)
    
    script_to_run = sys.argv[1]
    is_bottleneck = '--bottleneck' in sys.argv
    
    abs_path = os.path.abspath(script_to_run).replace('\\', '/')
    project_root = os.path.dirname(abs_path)
    
    with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
        code = f.read()

    # O timer agora é alimentado com o marcador unificado
    timer = _LineTimer(abs_path, project_root, live_flow=not is_bottleneck)
    sys.settrace(timer.tracer)
    
    try:
        os.environ['DOXOADE_AUTHORIZED_RUN'] = '1'
        restricted_safe_exec(code, {'__file__': abs_path, '__name__': '__main__'}, allow_imports=True)
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)
    finally:
        sys.settrace(None)
        # EMITE O RESULTADO EM JSON PARA O PAI
        stats = timer.top_lines(limit=15)
        # O marcador deve ser o mesmo que o _stream_and_capture procura
        print(f"\n---DOXOADE-DATA-BLOCK---\n{json.dumps({'line_hotspots': stats})}\n")
        sys.stdout.flush()

def run_flow_internal(callback):
    """Execução de rastro v125.0 - Injeção Direta."""
    import sys, os
    from .debug_probe import _LineTimer
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Criamos o timer e o tornamos acessível para o bloco finally
    internal_timer = _LineTimer(
        target_file="internal_cmd",
        project_root=project_root,
        internal_mode=True, live_flow=True
    )

    sys.settrace(static_trace_calls)
    try:
        callback()
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)
    finally:
        sys.settrace(None)
        # v125.0 FIX: Passagem obrigatória do objeto timer
        _render_flow_results(internal_timer)

def run_flow_direct(target, watch_vars=False, is_internal=False):
    from .debug_probe import _LineTimer
    from .flow_utils import render_flow_table
    import os, sys, shlex

    os.environ['DOXOADE_HORUS_ACTIVE'] = '0'
    os.environ['DOXOADE_RESCUE'] = '0'
    project_root = os.getcwd()
    
    if is_internal:
        # [OURO] Rastro de Comando Interno
        from doxoade.cli import cli
        timer = _LineTimer("internal_cmd", project_root, live_flow=True, 
                           watch_vars=watch_vars, internal_mode=True)
        # Sincroniza argv para o comando interno
        sys.argv = ['doxoade'] + shlex.split(target)
        sys.settrace(timer.tracer)
        try:
            cli(standalone_mode=False)
        except SystemExit: pass # Click chama exit(0) ao final, capturamos aqui
        except Exception as e:
            print(f"\n\x1b[31m✘ Falha no comando interno: {e}\x1b[0m")
        finally:
            sys.settrace(None)
            render_flow_table(timer)
    else:
        # [OURO] Rastro de Arquivo .py
        abs_path = os.path.abspath(target).replace('\\', '/')
        if not os.path.exists(abs_path):
            print(f"\x1b[31m✘ Erro: Arquivo não encontrado: {abs_path}\x1b[0m")
            return
            
        timer = _LineTimer(abs_path, project_root, live_flow=True, watch_vars=watch_vars)
        code = open(abs_path, 'r', encoding='utf-8', errors='ignore').read()
        sys.settrace(timer.tracer)
        from doxoade.tools.aegis.aegis_core import nexus_exec
        
        try:
            nexus_exec(code, {'__name__': '__main__', '__file__': abs_path})
        finally:
            sys.settrace(None)
            render_flow_table(timer)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('script')
    p.add_argument('--base', action='store_true')
    p.add_argument('--val', action='store_true')
    p.add_argument('--import', dest='imp', action='store_true')
    p.add_argument('--func', action='store_true')
    p.add_argument('--target', default=None)
    p.add_argument('--no-compress', dest='no_compress', action='store_true', help='Desativa compressão de loops (Iron Gate).')
    p.add_argument('-b', '--bottleneck', action='store_true')
    #args, remaining = p.parse_known_args()
    args, _ = p.parse_known_args()
    sys.argv = [os.path.abspath(args.script)] + remaining

    if len(sys.argv) < 2: sys.exit(1)
    script = sys.argv[1]
    is_val = '--val' in sys.argv
    run_flow_direct(args.script, watch_vars=args.val, live_flow=not args.bottleneck)
    script_to_run = sys.argv[1]
    is_bottleneck = '--bottleneck' in sys.argv or '-b' in sys.argv
    #sys.argv = [script_to_run] + [arg for arg in sys.argv[2:] if not arg.startswith('-')]
    
#    run_flow(args.script, **vars(args))
    sys.argv = [args.script]
    run_flow(args.script, bottleneck=args.bottleneck)
    