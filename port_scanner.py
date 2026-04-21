#
import socket

def scan_port(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    if s.connect_ex((ip, port)) == 0:
        print(f"[+] Porta {port} aberta")
    s.close()

target = "192.168.1.1"
for port in range(1, 1024):
    scan_port(target, port)
