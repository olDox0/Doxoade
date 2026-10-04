# doxoade/tools/engine_daemon/server.py
import os
import sys
import json
import socket
import threading
import ctypes
from pathlib import Path

IPC_HOST = '127.0.0.1'
IPC_PORT = 54321

# Carrega a DLL/SO do Hermes
NATIVE_DIR = Path(__file__).parent.parent / 'hermes_systems' / 'native'
LIB_NAME = 'hermes_async_log.dll' if os.name == 'nt' else 'hermes_async_log.so'
LIB_PATH = NATIVE_DIR / LIB_NAME

hermes_lib = None
if LIB_PATH.exists():
    try:
        hermes_lib = ctypes.CDLL(str(LIB_PATH))
        if hasattr(hermes_lib, 'hermes_log_py_init'):
            hermes_lib.hermes_log_py_init.argtypes = []
            hermes_lib.hermes_log_py_init.restype = None
            hermes_lib.hermes_log_py_init()

        if hasattr(hermes_lib, 'hermes_log_py_push_raw'):
            hermes_lib.hermes_log_py_push_raw.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
            hermes_lib.hermes_log_py_push_raw.restype = None

        if hasattr(hermes_lib, 'hermes_log_set_output_fd'):
            hermes_lib.hermes_log_set_output_fd.argtypes = [ctypes.c_int]
            hermes_lib.hermes_log_set_output_fd.restype = None
    except Exception as e:
        print(f"[DAEMON] ⚠ Falha ao carregar hermes_lib: {e}")
        hermes_lib = None

class SocketStream:
    """
    🌊 Stream Direto de Socket: Imune a Errno 9 e aceita str ou bytes.
    """
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.encoding = 'utf-8'
        self.errors = 'replace'

    def write(self, data):
        if not data:
            return
        try:
            # Se for str, codifica em bytes. Se já for bytes/bytearray, envia direto!
            if isinstance(data, str):
                payload = data.encode(self.encoding, errors=self.errors)
            elif isinstance(data, (bytes, bytearray)):
                payload = bytes(data)
            else:
                payload = str(data).encode(self.encoding, errors=self.errors)
            
            self.sock.sendall(payload)
        except (OSError, BrokenPipeError, ConnectionResetError):
            pass

    def flush(self):
        pass

    def isatty(self):
        return True

def warm_up_environment(project_root: str):
    print("[DAEMON] 🔥 Aquecendo motores (Aegis, Hermes, Vulcan)...")
    os.environ['DOXOADE_MODE'] = 'complete'
    os.environ['DOXOADE_QUIET_BOOT'] = '1'
    
    try:
        from doxoade.tools.hermes_systems.hermes_init import init_hermes_bootstrap
        init_hermes_bootstrap(Path(project_root), compile_if_missing=False)
    except Exception as e:
        print(f"[DAEMON] ⚠ Hermes warm-up falhou: {e}")
        
    print("[DAEMON] ✔ Ambiente Quente (Warm Start) pronto.")

def handle_client(conn: socket.socket, project_root: str):
    """📨 Recebe os argv e executa no contexto quente com streaming via socket."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        data = b""
        while b'\n' not in data:
            chunk = conn.recv(4096)
            if not chunk:
                return
            data += chunk

        request = json.loads(data.decode('utf-8').strip())
        argv = request.get('argv', [])
        cwd = request.get('cwd', os.getcwd())

        try:
            os.chdir(cwd)
        except Exception:
            pass

        # Garante que '--no-daemon' não chegue ao Click se foi passado
        argv_clean = [a for a in argv if a != '--no-daemon']

        # 🚀 Stream direto e imune a [Errno 9]
        stream = SocketStream(conn)
        sys.stdout = stream
        sys.stderr = stream

#        exit_code = 0
        # Dentro de handle_client em server.py:
        from doxoade.chronos import chronos_recorder
        import click
        
        # Cria um contexto limpo para o Chronos nesta thread
        chronos_recorder.session_uuid = str(uuid.uuid4())
        chronos_recorder.main_thread_id = threading.get_ident() # 🎯 Captura a thread do worker!
        
        ctx = click.Context(cli, info_name=argv_clean[0] if argv_clean else 'doxoade')
        chronos_recorder.start_command(ctx)

        try:
            cli(standalone_mode=False)
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else 0
        finally:
            # Força o flush da telemetria antes de fechar o socket
            duration_ms = (time.perf_counter() - chronos_recorder._perf_start) * 1000
            chronos_recorder.end_command(exit_code=exit_code, duration_ms=duration_ms)


    except Exception as e:
        pass
    finally:
        # Restaura os canais originais sempre
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        try:
            conn.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        conn.close()

def start_daemon():
    project_root = str(Path(__file__).resolve().parents[3])
    warm_up_environment(project_root)
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((IPC_HOST, IPC_PORT))
    server_socket.listen(5)
    server_socket.settimeout(1.0)
    
    ready_file = Path.home() / '.doxoade' / 'engine' / 'daemon.ready'
    ready_file.parent.mkdir(parents=True, exist_ok=True)
    ready_file.write_text(str(os.getpid()))
    
    print(f"[DAEMON] 🎧 Ouvindo em: {IPC_HOST}:{IPC_PORT}")
    
    try:
        while True:
            try:
                conn, addr = server_socket.accept()
                threading.Thread(target=handle_client, args=(conn, project_root), daemon=True).start()
            except socket.timeout:
                continue
    except KeyboardInterrupt:
        print("\n[DAEMON] 🛑 Encerrando daemon...")
    finally:
        if ready_file.exists(): ready_file.unlink()
        server_socket.close()
        if hermes_lib: hermes_lib.hermes_log_py_shutdown()

if __name__ == '__main__':
    start_daemon()
