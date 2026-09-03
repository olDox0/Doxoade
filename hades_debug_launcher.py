# hades_debug_launcher.py
"""
🔍 HADES DEBUG LAUNCHER — Diagnóstico completo do boot do init soberano.
"""
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

def run_debug():
    user_dir = LiteXLEngine.get_user_dir()
    prod_init = user_dir / "init.lua"
    backup_init = user_dir / "init.lua.debug_backup"
    sandbox_init = LiteXLEngine.get_sandbox_dir() / "init.lua"
    exe = LiteXLEngine.find_executable()
    
    print("🔍 HADES DEBUG LAUNCHER — Diagnóstico de Boot")
    print(f"📂 Userdir: {user_dir}")
    print(f"📄 Executável: {exe}")
    print(f"📄 Init Sandbox: {sandbox_init}\n")
    
    # 1. VERIFICA SE O EXECUTÁVEL EXISTE
    if not exe or not exe.exists():
        print("✖ Executável do Lite XL NÃO ENCONTRADO!")
        return
    
    print(f"✔ Executável encontrado: {exe}")
    print(f"   Tamanho: {exe.stat().st_size} bytes\n")
    
    # 2. VERIFICA SE O INIT SOBERANO EXISTE
    if not sandbox_init.exists():
        print("✖ Init do sandbox NÃO EXISTE!")
        print("   Rode 'doxoade lite-xl typhon test-deploy' primeiro.")
        return
    
    print(f"✔ Init do sandbox encontrado: {sandbox_init}")
    print(f"   Tamanho: {sandbox_init.stat().st_size} bytes\n")
    
    # 3. TESTE 1: LANÇA LITE XL SEM INIT (para verificar se o exe funciona)
    print("=" * 70)
    print("🧪 TESTE 1: Lite XL SEM init.lua (verifica se o executável funciona)")
    print("=" * 70)
    
    test_dir = user_dir / ".doxoade" / "debug_empty"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Remove qualquer init do diretório de teste
    test_init = test_dir / "init.lua"
    if test_init.exists():
        test_init.unlink()
    
    print(f"Lançando Lite XL em: {test_dir}")
    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
    
    proc1 = subprocess.Popen(
        [str(exe), "--userdir", str(test_dir)],
        creationflags=CREATE_NEW_CONSOLE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    
    print("Aguardando 3 segundos...")
    time.sleep(3)
    
    poll1 = proc1.poll()
    if poll1 is None:
        print("✔ TESTE 1: Lite XL abriu com sucesso (sem init)")
        proc1.kill()
    else:
        print(f"✖ TESTE 1: Lite XL crashou (exit code: {poll1})")
        stdout1, stderr1 = proc1.communicate()
        if stderr1:
            print(f"   STDERR: {stderr1[:500]}")
    
    print()
    
    # 4. TESTE 2: LANÇA COM INIT SOBERANO (captura erro)
    print("=" * 70)
    print("🧪 TESTE 2: Lite XL COM init soberano (captura erro de boot)")
    print("=" * 70)
    
    # Backup do init de produção
    if prod_init.exists():
        shutil.copy2(prod_init, backup_init)
        print(f"✔ Backup criado: {backup_init}")
    
    # Injeta o init soberano
    shutil.copy2(sandbox_init, prod_init)
    print(f"✔ Init soberano injetado: {prod_init}")
    
    # Limpa logs antigos
    error_txt = user_dir / "error.txt"
    session_log = user_dir / "session_log.txt"
    if error_txt.exists():
        error_txt.unlink()
    if session_log.exists():
        session_log.unlink()
    
    print("\nLançando Lite XL com init soberano...")
    proc2 = subprocess.Popen(
        [str(exe)],
        creationflags=CREATE_NEW_CONSOLE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    
    print("Aguardando 5 segundos para boot...")
    time.sleep(5)
    
    poll2 = proc2.poll()
    
    print("\n" + "=" * 70)
    print("🦅 RELATÓRIO DE DIAGNÓSTICO")
    print("=" * 70)
    
    if poll2 is None:
        print("✔ Lite XL está rodando (não crashou no boot)")
        print("   Pressione Ctrl+C para encerrar e restaurar o backup.")
        try:
            proc2.wait()
        except KeyboardInterrupt:
            proc2.kill()
    else:
        print(f"✖ Lite XL CRASHOU no boot (exit code: {poll2})")
        
        # Captura stdout/stderr
        stdout2, stderr2 = proc2.communicate()
        if stdout2:
            print(f"\n📄 STDOUT (primeiras 500 chars):")
            print(stdout2[:500])
        if stderr2:
            print(f"\n📄 STDERR (primeiras 500 chars):")
            print(stderr2[:500])
    
    # Verifica error.txt
    if error_txt.exists():
        print(f"\n💥 ERROR.TXT ENCONTRADO (causa raiz do crash):")
        print("-" * 70)
        print(error_txt.read_text(encoding="utf-8", errors="replace"))
        print("-" * 70)
    else:
        print("\n✅ Nenhum error.txt gerado")
    
    # Verifica session_log
    if session_log.exists():
        print(f"\n📜 SESSION_LOG (últimas 30 linhas):")
        print("-" * 70)
        lines = session_log.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines[-30:]:
            print(f"   {line}")
        print("-" * 70)
    else:
        print("\n⚠ session_log.txt não foi gerado")
    
    # 5. RESTAURA BACKUP
    print("\n🔄 Restaurando init de produção original...")
    if backup_init.exists():
        shutil.copy2(backup_init, prod_init)
        backup_init.unlink()
        print("✔ Rollback concluído.")
    else:
        print("⚠ Backup não encontrado. Execute 'doxoade lite-xl rollback' manualmente.")

if __name__ == "__main__":
    run_debug()