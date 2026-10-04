# doxoade/tools/engine_daemon/client.py
import socket
import json
import sys
import os
import subprocess
import time

IPC_HOST = '127.0.0.1'
IPC_PORT = 54321

def _enable_ansi_windows():
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            pass

def _spawn_daemon_background():
    print("[DEBUG-CLIENT] ⚡ Daemon não encontrado. Iniciando em background...")
    try:
        launcher_path = os.path.join(os.path.dirname(__file__), 'launcher.py')
        if os.name == 'nt':
            subprocess.Popen([sys.executable, launcher_path], creationflags=0x08000000, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen([sys.executable, launcher_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        
        for _ in range(30):
            time.sleep(0.1)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                sock.connect((IPC_HOST, IPC_PORT))
                sock.close()
                return True
            except: continue
        return False
    except: return False

def dispatch_to_daemon(argv: list, cwd: str) -> int | None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect((IPC_HOST, IPC_PORT))
    except:
        if not _spawn_daemon_background(): return None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((IPC_HOST, IPC_PORT))
        except: return None

    try:
        _enable_ansi_windows()
        
        # Envia o comando
        request = json.dumps({'argv': argv, 'cwd': cwd})
        sock.sendall(request.encode('utf-8') + b'\n')
        
        # 🚀 STREAMING LOOP: Lê bytes crus e imprime em tempo real
        # O timeout é alto para comandos longos, mas o output flui instantaneamente
        sock.settimeout(120.0) 
        
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk: 
                    break
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
            except (socket.timeout, ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                break
            except Exception:
                break

        sock.close()
        return 0
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        return None  # Se o daemon caiu, faz fallback limpo
    except Exception as e:
        return None
