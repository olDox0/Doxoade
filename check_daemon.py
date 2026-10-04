# check_daemon.py
import os
import socket
import json
import subprocess
from pathlib import Path

ready_file = Path.home() / '.doxoade' / 'engine' / 'daemon.ready'
print(f"1. Arquivo .ready existe: {ready_file.exists()}")

if ready_file.exists():
    pid_str = ready_file.read_text().strip()
    print(f"2. PID do Daemon registrado: {pid_str}")
    
    try:
        result = subprocess.run(['tasklist', '/FI', f'PID eq {pid_str}'], capture_output=True, text=True)
        if str(pid_str) in result.stdout:
            print("3. ✔ Processo do Daemon está ATIVO no sistema.")
        else:
            print("3. ✘ Processo do Daemon NÃO ESTÁ RODANDO (crashou e deixou arquivo stale).")
    except Exception as e:
        print(f"3. ? Erro ao verificar processo: {e}")

print("\n4. Tentando conectar na porta 54321...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3.0)  # Aumentado para 3 segundos
    sock.connect(('127.0.0.1', 54321))
    print("5. ✔ Conectado ao Daemon com sucesso!")
    
    request = json.dumps({'argv': ['doxoade', '--help'], 'cwd': '.'})
    sock.sendall(request.encode('utf-8') + b'\n')
    
    data = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk: break
        data += chunk
    sock.close()
    
    if data:
        resp = json.loads(data.decode('utf-8'))
        print(f"6. ✔ Resposta recebida! Exit Code: {resp.get('exit_code')}")
        print(f"   Output: {resp.get('stdout', '')[:100]}")
    else:
        print("6. ✘ Nenhuma dado recebido do daemon.")
except ConnectionRefusedError:
    print("5. ✘ Conexão recusada (Nada ouvindo na porta 54321).")
except socket.timeout:
    print("5. ✘ Timeout na conexão (Daemon travado ou firewall bloqueando).")
except Exception as e:
    print(f"5. ✘ Erro inesperado: {e}")
