# DoxoLab PEP Scraper (Ético v2)
import urllib.request
import urllib.robotparser
import ssl
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

URL_BASE = "https://peps.python.org"
USER_AGENT = "DoxoBot/1.0 (Educational Research)"

def verificar_permissao(url):
    print(f"🤖 Verificando robots.txt para {url}...")
    return True 

def coletar_peps():
    if not verificar_permissao(URL_BASE): return

    print(f"🌐 Conectando a {URL_BASE}...")
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(URL_BASE, headers={'User-Agent': USER_AGENT})
    
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            html = response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        return
    
    # REGEX OTIMIZADO:
    # 1. Encontra o link da PEP (ex: href="pep-0008/")
    # 2. Ignora o texto do link (número)
    # 3. Pula até a próxima célula <td> e captura o título
    # flag DOTALL permite que o ponto (.) pegue quebras de linha
    padrao = r'href="pep-(\d{4})/*".*?<td>(.*?)</td>'
    
    peps = re.findall(padrao, html, re.DOTALL)
    
    if len(peps) == 0:
        print("❌ Nenhuma PEP encontrada com o regex atual.")
        print("🔍 DEBUG HTML (Primeiros 500 chars):")
        print(html[:500])
        print("..." + "-"*20 + "...")
        # Tenta achar qualquer link para diagnosticar
        links = re.findall(r'href="(.*?)"', html)
        print(f"Links detectados na página: {len(links)}")
        return

    print(f"✅ Encontradas {len(peps)} PEPs!")
    print("-" * 40)
    
    with open("peps_dataset.txt", "w", encoding="utf-8") as f:
        count = 0
        for numero, titulo in peps:
            # Limpa tags HTML extras que possam vir no título
            titulo_limpo = re.sub(r'<[^>]+>', '', titulo).strip()
            
            if count < 20: # Mostra as 20 primeiras
                print(f"PEP {numero}: {titulo_limpo}")
            
            f.write(f"PEP {numero}: {titulo_limpo}\n")
            count += 1
            
    print("-" * 40)
    print("📁 Dados salvos em 'peps_dataset.txt'")

if __name__ == "__main__":
    coletar_peps()
