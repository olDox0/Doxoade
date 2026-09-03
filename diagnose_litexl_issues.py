# -*- coding: utf-8 -*-
# diagnose_litexl_issues.py
"""
🔍 DIAGNÓSTICO COMPLETO DOS PROBLEMAS DO LITE XL
1. Verifica se --userdir está funcionando
2. Identifica por que 'lite-xl' está sendo interceptado pelo doxoade
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

def diagnose_userdir_issue():
    """Diagnostica se o --userdir está sendo respeitado."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}🔍 DIAGNÓSTICO 1: --userdir{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'='*70}{Style.RESET_ALL}\n")
    
    sandbox = LiteXLEngine.get_sandbox_dir()
    exe = LiteXLEngine.find_executable()
    
    if not exe:
        print(f"{Fore.RED}✖ Executável do Lite XL não encontrado!{Fore.RESET}")
        return
    
    print(f"{Fore.WHITE}Executável:{Fore.RESET} {exe}")
    print(f"{Fore.WHITE}Sandbox:{Fore.RESET} {sandbox}\n")
    
    # 1. Verifica versão do Lite XL
    print(f"{Fore.CYAN}1. Verificando versão do Lite XL...{Fore.RESET}")
    try:
        result = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode == 0:
            print(f"{Fore.GREEN}✔ Versão: {result.stdout.strip()}{Fore.RESET}")
        else:
            print(f"{Fore.YELLOW}⚠ --version retornou código {result.returncode}{Fore.RESET}")
            print(f"   STDOUT: {result.stdout[:200]}")
            print(f"   STDERR: {result.stderr[:200]}")
    except Exception as e:
        print(f"{Fore.RED}✖ Falha ao executar --version: {e}{Fore.RESET}")
    
    # 2. Testa --help para ver as flags disponíveis
    print(f"\n{Fore.CYAN}2. Verificando flags disponíveis (--help)...{Fore.RESET}")
    try:
        result = subprocess.run(
            [str(exe), "--help"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace"
        )
        if "--userdir" in result.stdout:
            print(f"{Fore.GREEN}✔ Flag --userdir está disponível{Fore.RESET}")
            # Extrai a linha do --userdir
            for line in result.stdout.splitlines():
                if "--userdir" in line:
                    print(f"   {line.strip()}")
        else:
            print(f"{Fore.RED}✖ Flag --userdir NÃO encontrada no --help{Fore.RESET}")
            print(f"   Flags disponíveis:")
            for line in result.stdout.splitlines():
                if line.strip().startswith("--"):
                    print(f"   {line.strip()}")
    except Exception as e:
        print(f"{Fore.RED}✖ Falha ao executar --help: {e}{Fore.RESET}")
    
    # 3. Testa --userdir com init minimalista
    print(f"\n{Fore.CYAN}3. Testando --userdir com init minimalista...{Fore.RESET}")
    sandbox_init = sandbox / "init.lua"
    
    # Backup do init atual
    if sandbox_init.exists():
        backup = sandbox / "init.lua.backup"
        shutil.copy2(sandbox_init, backup)
        print(f"   Backup criado: {backup.name}")
    
    # Cria init minimalista com canário
    minimal_init = '''
-- 🐤 TESTE DE --userdir
local f = io.open(USERDIR .. "/USERDIR_TEST.txt", "w")
if f then
    f:write("USERDIR_FUNCIONA\\n")
    f:write("USERDIR=" .. tostring(USERDIR) .. "\\n")
    f:write("TIME=" .. os.date("%Y-%m-%d %H:%M:%S") .. "\\n")
    f:close()
    print("[TEST] Canário gravado em: " .. USERDIR .. "/USERDIR_TEST.txt")
else
    print("[TEST] FALHA AO GRAVAR canário!")
end
'''
    sandbox_init.write_text(minimal_init, encoding="utf-8")
    print(f"   Init minimalista criado: {sandbox_init}")
    
    # Remove canário antigo
    canary = sandbox / "USERDIR_TEST.txt"
    if canary.exists():
        canary.unlink()
    
    # Lança com --userdir
    print(f"\n   Lançando Lite XL com --userdir...")
    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
    
    # Mata instâncias antigas
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
    
    import time
    time.sleep(1.0)
    
    try:
        proc = subprocess.Popen(
            [str(exe), "--userdir", str(sandbox)],
            creationflags=CREATE_NEW_CONSOLE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        print(f"   PID: {proc.pid}")
        print(f"   Aguardando 5 segundos...")
        time.sleep(5)
        
        # Verifica se o canário foi criado
        if canary.exists():
            print(f"\n{Fore.GREEN}✔ SUCESSO: --userdir está funcionando!{Fore.RESET}")
            print(f"   Canário encontrado em: {canary}")
            print(f"   Conteúdo:")
            for line in canary.read_text(encoding="utf-8").splitlines():
                print(f"     {line}")
        else:
            print(f"\n{Fore.RED}✖ FALHA: --userdir NÃO está funcionando!{Fore.RESET}")
            print(f"   Canário NÃO foi criado em: {canary}")
            
            # Verifica se foi criado no userdir padrão
            default_userdir = LiteXLEngine.get_user_dir()
            default_canary = default_userdir / "USERDIR_TEST.txt"
            if default_canary.exists():
                print(f"\n{Fore.YELLOW}⚠ ALERTA: O canário foi criado no userdir PADRÃO!{Fore.RESET}")
                print(f"   Caminho: {default_canary}")
                print(f"   Isso indica que o Lite XL está ignorando o --userdir")
        
        # Encerra o processo
        if proc.poll() is None:
            proc.kill()
            print(f"\n   Processo encerrado.")
        
        # Captura stdout/stderr se houver
        try:
            stdout, stderr = proc.communicate(timeout=2)
            if stdout:
                print(f"\n{Fore.CYAN}STDOUT:{Fore.RESET}")
                print(stdout[:500])
            if stderr:
                print(f"\n{Fore.YELLOW}STDERR:{Fore.RESET}")
                print(stderr[:500])
        except:
            pass
        
    except Exception as e:
        print(f"{Fore.RED}✖ Falha ao lançar Lite XL: {e}{Fore.RESET}")
    
    # Restaura o init original
    if sandbox_init.exists():
        backup = sandbox / "init.lua.backup"
        if backup.exists():
            shutil.copy2(backup, sandbox_init)
            backup.unlink()
            print(f"\n   Init original restaurado.")

def diagnose_command_interception():
    """Diagnostica por que 'lite-xl' está sendo interceptado pelo doxoade."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}🔍 DIAGNÓSTICO 2: Interceptação do comando 'lite-xl'{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'='*70}{Style.RESET_ALL}\n")
    
    # 1. Verifica onde o comando 'lite-xl' está sendo resolvido
    print(f"{Fore.CYAN}1. Localizando o comando 'lite-xl' no PATH...{Fore.RESET}")
    litexl_path = shutil.which("lite-xl")
    if litexl_path:
        print(f"{Fore.GREEN}✔ Encontrado: {litexl_path}{Fore.RESET}")
        
        # Verifica se é um script Python ou o executável real
        if litexl_path.endswith(".exe"):
            print(f"   Tipo: Executável nativo (.exe)")
        elif litexl_path.endswith(".py") or litexl_path.endswith(".bat") or litexl_path.endswith(".cmd"):
            print(f"   Tipo: Script/Wrapper")
            print(f"\n{Fore.YELLOW}⚠ ALERTA: O comando 'lite-xl' está apontando para um script!{Fore.RESET}")
            print(f"   Isso explica por que o doxoade está interceptando.")
            
            # Lê o conteúdo do script
            try:
                content = Path(litexl_path).read_text(encoding="utf-8", errors="replace")
                print(f"\n   Conteúdo do script (primeiras 500 chars):")
                print(f"   {'-'*60}")
                for line in content.splitlines()[:20]:
                    print(f"   {line}")
                print(f"   {'-'*60}")
            except Exception as e:
                print(f"   Erro ao ler o script: {e}")
        else:
            print(f"   Tipo: Desconhecido")
    else:
        print(f"{Fore.RED}✖ Comando 'lite-xl' NÃO encontrado no PATH{Fore.RESET}")
    
    # 2. Verifica o PATH completo
    print(f"\n{Fore.CYAN}2. Analisando o PATH do sistema...{Fore.RESET}")
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    print(f"   Total de diretórios no PATH: {len(path_dirs)}")
    
    # Procura diretórios que podem conter wrappers do doxoade
    suspect_dirs = []
    for d in path_dirs:
        if "doxoade" in d.lower() or "venv" in d.lower() or "scripts" in d.lower():
            suspect_dirs.append(d)
    
    if suspect_dirs:
        print(f"\n{Fore.YELLOW}⚠ Diretórios suspeitos encontrados no PATH:{Fore.RESET}")
        for d in suspect_dirs:
            print(f"   • {d}")
            
            # Verifica se há um 'lite-xl' nesse diretório
            litexl_in_dir = Path(d) / "lite-xl.exe"
            if not litexl_in_dir.exists():
                litexl_in_dir = Path(d) / "lite-xl"
            if not litexl_in_dir.exists():
                litexl_in_dir = Path(d) / "lite-xl.bat"
            if not litexl_in_dir.exists():
                litexl_in_dir = Path(d) / "lite-xl.cmd"
            
            if litexl_in_dir.exists():
                print(f"     {Fore.RED}✖ Contém wrapper: {litexl_in_dir.name}{Fore.RESET}")
    
    # 3. Verifica aliases (se houver)
    print(f"\n{Fore.CYAN}3. Verificando aliases do terminal...{Fore.RESET}")
    if sys.platform == "win32":
        print(f"   No Windows, aliases são definidos via:")
        print(f"   • DOSKEY (temporário)")
        print(f"   • Registro do Windows (persistente)")
        print(f"   • Scripts .bat/.cmd no PATH")
        print(f"\n   Para verificar aliases ativos, execute:")
        print(f"   {Fore.WHITE}doskey /macros:all{Fore.RESET}")
    else:
        print(f"   No Linux/macOS, verifique:")
        print(f"   • ~/.bashrc, ~/.zshrc, ~/.profile")
        print(f"   • Execute: {Fore.WHITE}alias{Fore.RESET}")
    
    # 4. Testa o comando diretamente
    print(f"\n{Fore.CYAN}4. Testando o comando 'lite-xl --version' diretamente...{Fore.RESET}")
    try:
        result = subprocess.run(
            ["lite-xl", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace"
        )
        print(f"   Código de retorno: {result.returncode}")
        if result.stdout:
            print(f"   STDOUT (primeiras 300 chars):")
            print(f"   {result.stdout[:300]}")
        if result.stderr:
            print(f"   STDERR (primeiras 300 chars):")
            print(f"   {result.stderr[:300]}")
    except Exception as e:
        print(f"   {Fore.RED}✖ Falha ao executar: {e}{Fore.RESET}")

def main():
    """Executa todos os diagnósticos."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🔍 DIAGNÓSTICO COMPLETO DOS PROBLEMAS DO LITE XL{Style.RESET_ALL}")
    print(f"{Fore.LIGHTBLACK_EX}Data: {os.popen('date /t').read().strip() if sys.platform == 'win32' else os.popen('date').read().strip()}{Fore.RESET}")
    
    diagnose_userdir_issue()
    diagnose_command_interception()
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📋 RESUMO E RECOMENDAÇÕES{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'='*70}{Style.RESET_ALL}\n")
    
    print(f"{Fore.WHITE}Para resolver o problema da interceptação do comando 'lite-xl':{Fore.RESET}")
    print(f"  1. Identifique qual script/wrapper está no PATH")
    print(f"  2. Remova ou renomeie o wrapper problemático")
    print(f"  3. Ou use o caminho completo do executável:")
    print(f"     {Fore.GREEN}\"C:\\Program Files\\Lite XL\\lite-xl.exe\" --userdir <dir>{Fore.RESET}")
    print()
    print(f"{Fore.WHITE}Para testar o --userdir manualmente:{Fore.RESET}")
    print(f"  1. Feche TODAS as instâncias do Lite XL")
    print(f"  2. Execute no terminal:")
    print(f"     {Fore.GREEN}\"C:\\Program Files\\Lite XL\\lite-xl.exe\" --userdir \"C:\\Users\\olDox222\\.config\\lite-xl\\.doxoade\\sandbox\"{Fore.RESET}")
    print(f"  3. Verifique se o canário USERDIR_TEST.txt foi criado no sandbox")
    print()

if __name__ == "__main__":
    main()
