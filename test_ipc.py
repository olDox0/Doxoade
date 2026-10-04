# test_ipc.py
import socket
import json
from pathlib import Path

ready_file = Path.home() / '.doxoade' / 'engine' / 'daemon.ready'
print(f"1. Arquivo .ready existe: {ready_file.exists()}")

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    sock.connect(('127.0.0.1', 54321))
    print("2. ✔ Conectado ao Daemon com sucesso!")
    
    request = json.dumps({'argv': ['doxoade', '--version'], 'cwd': '.'})
    sock.sendall(request.encode('utf-8') + b'\n')
    
    data = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk: break
        data += chunk
    sock.close()
    
    if data:
        resp = json.loads(data.decode('utf-8'))
        print(f"3. ✔ Resposta recebida! Exit Code: {resp.get('exit_code')}")
        print(f"   Output: {resp.get('stdout', '')[:100]}")
    else:
        print("3. ✘ Nenhuma dados recebidos do daemon.")
except ConnectionRefusedError:
    print("2. ✘ Conexão recusada (O daemon não está rodando ou a porta está errada).")
except Exception as e:
    print(f"2. ✘ Erro: {e}")
