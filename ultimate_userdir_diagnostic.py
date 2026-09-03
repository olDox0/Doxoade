# ultimate_userdir_diagnostic.py
"""
🔬 ULTIMATE USERDIR DIAGNOSTIC — Testa todas as hipóteses possíveis.
"""
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
from doxoade.tools.doxcolors import Fore, Style

def test_all_hypotheses():
    exe = LiteXLEngine.find_executable()
    sandbox = LiteXLEngine.get_sandbox_dir()
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🔬 ULTIMATE USERDIR DIAGNOSTIC{Style.RESET_ALL}\n")
    print(f"Executável: {exe}")
    print(f"Sandbox: {sandbox}\n")
    
    # ═══════════════════════════════════════════════════════════
    # TESTE 1: Verifica se o executável é válido
    # ═══════════════════════════════════════════════════════════
    print(f"{Fore.CYAN}TESTE 1: Validade do executável{Fore.RESET}")
    if not exe.exists():
        print(f"{Fore.RED}✖ Executável NÃO existe!{Fore.RESET}")
        return
    
    print(f"   Tamanho: {exe.stat().st_size:,} bytes")
    print(f"   Última modificação: {time.ctime(exe.stat().st_mtime)}")
    
    # Tenta executar com --help (timeout curto)
    try:
        result = subprocess.run(
            [str(exe), "--help"],
            capture_output=True,
            text=True,
            timeout=3,
            encoding="utf-8",
            errors="replace"
        )
        print(f"   {Fore.GREEN}✔ Executável responde a --help{Fore.RESET}")
        
        # Verifica se --userdir está no help
        if "--userdir" in result.stdout:
            print(f"   {Fore.GREEN}✔ Flag --userdir está disponível{Fore.RESET}")
            for line in result.stdout.splitlines():
                if "--userdir" in line:
                    print(f"      {line.strip()}")
        else:
            print(f"   {Fore.RED}✖ Flag --userdir NÃO encontrada no --help{Fore.RESET}")
            print(f"   {Fore.YELLOW}💡 O Lite XL pode ter mudado a sintaxe!{Fore.RESET}")
            
    except subprocess.TimeoutExpired:
        print(f"   {Fore.YELLOW}⚠ --help timeout (o Lite XL pode estar travando){Fore.RESET}")
    except Exception as e:
        print(f"   {Fore.RED}✖ Erro ao executar --help: {e}{Fore.RESET}")
    
    # ═══════════════════════════════════════════════════════════
    # TESTE 2: Caminho simples (sem .doxoade)
    # ═══════════════════════════════════════════════════════════
    print(f"\n{Fore.CYAN}TESTE 2: Caminho simples (sem .doxoade){Fore.RESET}")
    
    simple_dir = Path(os.getenv("TEMP")) / "litexl_test_simple"
    simple_dir.mkdir(parents=True, exist_ok=True)
    
    # Cria init minimalista
    simple_init = simple_dir / "init.lua"
    simple_init.write_text('''
print("[SIMPLE] Init lido!")
local f = io.open(USERDIR .. "/SIMPLE_CANARY.txt", "w")
if f then
    f:write("SIMPLE_INIT_OK\\n")
    f:write("USERDIR=" .. tostring(USERDIR) .. "\\n")
    f:close()
end
''', encoding="utf-8")
    
    print(f"   Diretório: {simple_dir}")
    print(f"   Init: {simple_init}")
    
    # Mata instâncias
    subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
    time.sleep(1.0)
    
    # Lança
    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [str(exe), "--userdir", str(simple_dir)],
        creationflags=CREATE_NEW_CONSOLE
    )
    
    print(f"   PID: {proc.pid}. Aguardando 5s...")
    time.sleep(5)
    
    # Verifica
    simple_canary = simple_dir / "SIMPLE_CANARY.txt"
    if simple_canary.exists():
        print(f"   {Fore.GREEN}✔ SUCESSO: --userdir funciona com caminho simples!{Fore.RESET}")
        print(f"   Conteúdo:")
        print(f"   {simple_canary.read_text(encoding='utf-8')}")
    else:
        print(f"   {Fore.RED}✖ FALHA: --userdir NÃO funciona mesmo com caminho simples{Fore.RESET}")
        print(f"   {Fore.YELLOW}💡 O problema é o Lite XL, não o caminho!{Fore.RESET}")
    
    if proc.poll() is None:
        proc.kill()
    
    # ═══════════════════════════════════════════════════════════
    # TESTE 3: Variável de ambiente LITE_XL_USERDIR
    # ═══════════════════════════════════════════════════════════
    print(f"\n{Fore.CYAN}TESTE 3: Variável de ambiente LITE_XL_USERDIR{Fore.RESET}")
    
    env_dir = Path(os.getenv("TEMP")) / "litexl_test_env"
    env_dir.mkdir(parents=True, exist_ok=True)
    
    env_init = env_dir / "init.lua"
    env_init.write_text('''
print("[ENV] Init lido!")
local f = io.open(USERDIR .. "/ENV_CANARY.txt", "w")
if f then
    f:write("ENV_INIT_OK\\n")
    f:write("USERDIR=" .. tostring(USERDIR) .. "\\n")
    f:close()
end
''', encoding="utf-8")
    
    print(f"   Diretório: {env_dir}")
    
    # Define variável de ambiente
    env = os.environ.copy()
    env["LITE_XL_USERDIR"] = str(env_dir)
    
    # Mata instâncias
    subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
    time.sleep(1.0)
    
    # Lança SEM --userdir, mas com variável de ambiente
    proc = subprocess.Popen(
        [str(exe)],
        env=env,
        creationflags=CREATE_NEW_CONSOLE
    )
    
    print(f"   PID: {proc.pid}. Aguardando 5s...")
    time.sleep(5)
    
    # Verifica
    env_canary = env_dir / "ENV_CANARY.txt"
    if env_canary.exists():
        print(f"   {Fore.GREEN}✔ SUCESSO: LITE_XL_USERDIR funciona!{Fore.RESET}")
        print(f"   {Fore.YELLOW}💡 Use variável de ambiente como workaround!{Fore.RESET}")
    else:
        print(f"   {Fore.RED}✖ FALHA: LITE_XL_USERDIR também não funciona{Fore.RESET}")
    
    if proc.poll() is None:
        proc.kill()
    
    # ═══════════════════════════════════════════════════════════
    # TESTE 4: Verifica versão exata
    # ═══════════════════════════════════════════════════════════
    print(f"\n{Fore.CYAN}TESTE 4: Versão do Lite XL{Fore.RESET}")
    
    # Tenta ler o arquivo de versão (se existir)
    version_file = exe.parent / "version.txt"
    if version_file.exists():
        print(f"   {version_file.read_text(encoding='utf-8').strip()}")
    
    # Tenta executar com --version
    try:
        result = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=3,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode == 0:
            print(f"   {result.stdout.strip()}")
        else:
            print(f"   {Fore.YELLOW}⚠ --version retornou código {result.returncode}{Fore.RESET}")
    except:
        print(f"   {Fore.YELLOW}⚠ Não foi possível obter a versão{Fore.RESET}")
    
    # ═══════════════════════════════════════════════════════════
    # TESTE 5: Verifica se há arquivos de lock
    # ═══════════════════════════════════════════════════════════
    print(f"\n{Fore.CYAN}TESTE 5: Arquivos de lock/IPC{Fore.RESET}")
    
    user_dir = LiteXLEngine.get_user_dir()
    lock_files = [
        user_dir / ".lock",
        user_dir / ".ipc_lock",
        user_dir / ".single_instance",
    ]
    
    for lock in lock_files:
        if lock.exists():
            print(f"   {Fore.YELLOW}⚠ Lock encontrado: {lock}{Fore.RESET}")
            print(f"   {Fore.YELLOW}💡 Tente deletar este arquivo{Fore.RESET}")
    
    # ═══════════════════════════════════════════════════════════
    # RESUMO
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"{Fore.CYAN}{Style.BRIGHT}📋 RESUMO E RECOMENDAÇÕES{Style.RESET_ALL}")
    print(f"{'='*70}\n")
    
    print(f"{Fore.WHITE}Se NENHUM teste funcionou:{Fore.RESET}")
    print(f"  1. O Lite XL pode ter mudado a sintaxe do --userdir")
    print(f"  2. Verifique a documentação oficial: https://lite-xl.com/docs/")
    print(f"  3. Tente reinstalar o Lite XL")
    print(f"  4. Como workaround, use injeção direta no userdir padrão")
    print()
    print(f"{Fore.WHITE}Workaround imediato (injeção direta):{Fore.RESET}")
    print(f"  doxoade lite-xl deploy production --launch")
    print()

if __name__ == "__main__":
    test_all_hypotheses()
