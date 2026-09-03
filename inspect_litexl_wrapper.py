# inspect_litexl_wrapper.py
"""
🔍 INSPECT LITE-XL WRAPPER — Analisa o wrapper que está interceptando o comando.
"""
import os
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style

def inspect_wrapper():
    # 1. Localiza o wrapper
    wrapper_paths = [
        Path(r"C:\Users\olDox222\Documents\A20251122\DOSSIER\Altonomo\Projetos_E_Programas\Projeto OADE\doxoade\venv\Scripts\lite-xl.CMD"),
        Path(r"C:\Users\olDox222\Documents\A20251122\DOSSIER\Altonomo\Projetos_E_Programas\Projeto OADE\doxoade\venv\Scripts\lite-xl.cmd"),
        Path(r"C:\Users\olDox222\Documents\A20251122\DOSSIER\Altonomo\Projetos_E_Programas\Projeto OADE\doxoade\venv\Scripts\lite-xl.bat"),
    ]
    
    print(f"{Fore.CYAN}{Style.BRIGHT}🔍 INSPEÇÃO DO WRAPPER LITE-XL{Style.RESET_ALL}\n")
    
    wrapper = None
    for p in wrapper_paths:
        if p.exists():
            wrapper = p
            break
    
    if not wrapper:
        print(f"{Fore.RED}✖ Wrapper não encontrado nos caminhos esperados.{Fore.RESET}")
        print(f"   Tentando localizar via shutil.which...")
        import shutil
        found = shutil.which("lite-xl")
        if found:
            wrapper = Path(found)
            print(f"   ✔ Encontrado: {wrapper}")
        else:
            print(f"   {Fore.RED}✖ Nenhum wrapper encontrado.{Fore.RESET}")
            return
    
    print(f"{Fore.GREEN}✔ Wrapper encontrado: {wrapper}{Fore.RESET}")
    print(f"   Tamanho: {wrapper.stat().st_size} bytes\n")
    
    # 2. Lê o conteúdo
    print(f"{Fore.CYAN}📄 CONTEÚDO DO WRAPPER:{Fore.RESET}")
    print(f"{'='*70}")
    try:
        content = wrapper.read_text(encoding="utf-8", errors="replace")
        print(content)
        print(f"{'='*70}\n")
        
        # 3. Analisa o que o wrapper faz
        print(f"{Fore.CYAN}🔬 ANÁLISE:{Fore.RESET}")
        if "python" in content.lower():
            print(f"   {Fore.YELLOW}⚠ O wrapper chama Python{Fore.RESET}")
        if "doxoade" in content.lower():
            print(f"   {Fore.YELLOW}⚠ O wrapper menciona 'doxoade'{Fore.RESET}")
        if "lite-xl.exe" in content or "lite-xl\"" in content:
            print(f"   {Fore.GREEN}✔ O wrapper chama o executável real{Fore.RESET}")
        if "--userdir" in content:
            print(f"   {Fore.YELLOW}⚠ O wrapper manipula --userdir{Fore.RESET}")
        
    except Exception as e:
        print(f"   {Fore.RED}✖ Erro ao ler: {e}{Fore.RESET}")
    
    # 4. Sugere solução
    print(f"\n{Fore.CYAN}{Style.BRIGHT}💡 SOLUÇÃO:{Style.RESET_ALL}")
    print(f"   1. Renomeie o wrapper para evitar interceptação:")
    print(f"      {Fore.WHITE}rename \"{wrapper}\" \"lite-xl.cmd.bak\"{Fore.RESET}")
    print(f"\n   2. Ou use o caminho completo do executável real:")
    print(f"      {Fore.WHITE}\"C:\\Program Files\\Lite XL\\lite-xl.exe\" --userdir <dir>{Fore.RESET}")

if __name__ == "__main__":
    inspect_wrapper()
