# stress_test_daemon.py
import socket
import json
import time
import concurrent.futures

IPC_HOST = '127.0.0.1'
IPC_PORT = 54321

def send_request(i):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((IPC_HOST, IPC_PORT))
        
        # Pede um --help (comando leve, mas que carrega o grafo do Click)
        request = json.dumps({'argv': ['doxoade', '--help'], 'cwd': '.'})
        sock.sendall(request.encode('utf-8') + b'\n')
        
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk: break
            data += chunk
        sock.close()
        
        resp = json.loads(data.decode('utf-8'))
        return i, resp.get('exit_code'), len(data)
    except Exception as e:
        return i, -1, str(e)

def main():
    print("🔥 INICIANDO TESTE DE ESTRESSE DO DAEMON")
    print("   Disparando 50 requisições concorrentes...")
    
    start = time.perf_counter()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(send_request, i) for i in range(50)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
    elapsed = (time.perf_counter() - start) * 1000
    
    success = sum(1 for _, code, _ in results if code == 0)
    failed = sum(1 for _, code, _ in results if code != 0)
    
    print(f"\n{'='*50}")
    print(f"  ✔ Sucessos: {success}/50")
    print(f"  ✘ Falhas:   {failed}/50")
    print(f"  ⏱ Tempo Total: {elapsed:.2f} ms")
    print(f"  ⚡ Throughput: {50 / (elapsed/1000):.1f} req/s")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
