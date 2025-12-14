# DoxoLab Crawler Prototype
import sys
import urllib.request
import time
import ssl 

def fetch(url):
    print(f"[*] Acessando {url}...")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(
            url, 
            data=None, 
            headers={'User-Agent': 'DoxoBot/1.0'}
        )
        with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
            # FIX: errors='ignore' evita crash com caracteres estranhos
            html = response.read().decode('utf-8', errors='ignore')
            print(f"[+] Sucesso! {len(html)} bytes recebidos.")
            return html
    except Exception as e:
        print(f"[-] Falha: {e}")
        raise e

if __name__ == "__main__":
    target = "https://www.google.com"
    fetch(target)
