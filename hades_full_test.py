# hades_full_test.py
"""
💀 HADES FULL TEST — Injeção do Init Soberano Completo + Hooks de Caos.
Garante que o Lite XL abra com TODOS os sistemas Doxoade ativos.
"""
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder

def run_full_test():
    user_dir = LiteXLEngine.get_user_dir()
    prod_init = user_dir / "init.lua"
    backup_init = user_dir / "init.lua.hades_backup"
    sandbox_dir = LiteXLEngine.get_sandbox_dir()
    sandbox_init = sandbox_dir / "init.lua"
    exe = LiteXLEngine.find_executable()
    
    print("💀 HADES FULL TEST — Init Soberano Completo + Hooks de Caos")
    print(f"📂 Userdir: {user_dir}")
    print(f"📄 Init Produção: {prod_init}")
    print(f"📄 Sandbox Dir: {sandbox_dir}\n")
    
    # 1. REGENERA O INIT SOBERANO COMPLETO (com todos os 22 templates)
    print("🔨 Regenerando init soberano completo (22 templates)...")
    sovereign_init = LiteXLInitBuilder.generate_sovereign_init()
    
    # 2. ADICIONA HOOKS DE DETECÇÃO DE CAOS
    hooks_code = '''
-- =============================================================================
-- 🛡️ HOOKS DE DETECÇÃO DE CAOS (Runtime Monitoring)
-- =============================================================================
local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)
if core then
    core.log("🛡️ [HOOKS] Hooks de detecção ativados.")
    
    -- Hook no pcall para logar erros engolidos
    local original_pcall = pcall
    _G.pcall = function(fn, ...)
        local results = {original_pcall(fn, ...)}
        if not results[1] then
            core.log("👻 [HOOK] pcall capturou erro: " .. tostring(results[2]))
        end
        return unpack(results)
    end
    
    -- Monitor de globais vazadas
    local _tracked_globals = {}
    for k in pairs(_G) do _tracked_globals[k] = true end
    
    core.add_thread(function()
        while true do
            coroutine.yield(5.0)
            for k in pairs(_G) do
                if not _tracked_globals[k] and not k:match("^_") then
                    core.log("👻 [HOOK] Global vazada detectada: " .. k)
                    _tracked_globals[k] = true
                end
            end
        end
    end)
    
    core.log("🛡️ [HOOKS] Todos os hooks ativos.")
end
'''
    
    full_init = sovereign_init + "\n" + hooks_code
    sandbox_init.write_text(full_init, encoding="utf-8")
    print(f"✔ Init completo gerado: {len(full_init)} chars, {full_init.count('_doxoade_safe_boot')} módulos\n")
    
    # 3. VALIDAÇÃO
    if not sandbox_init.exists():
        print("✖ Init do sandbox não foi criado!")
        return
    
    if not prod_init.exists():
        print("✖ Init de produção não encontrado!")
        return
    
    # 4. BACKUP DE SEGURANÇA
    print("💾 Criando backup do init de produção...")
    shutil.copy2(prod_init, backup_init)
    print(f"✔ Backup salvo em: {backup_init}\n")
    
    # 5. INJEÇÃO
    print("💉 Injetando init soberano completo no userdir padrão...")
    shutil.copy2(sandbox_init, prod_init)
    print("✔ Injeção concluída.\n")
    
    # 6. EXORCISMO
    print("🔪 Encerrando instâncias antigas do Lite XL...")
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
    time.sleep(1.5)
    print("✔ Instâncias encerradas.\n")
    
    # 7. LANÇAMENTO
    print("⚡ Lançando Lite XL com o init soberano completo...")
    print("👀 A janela vai abrir com TODOS os sistemas Doxoade:")
    print("   - Abas coloridas por projeto (03_tab_colors)")
    print("   - Dock de Open Editors (16_open_editors_dock)")
    print("   - Painel Dumppot (08_pot_panel)")
    print("   - TreeView compacta (06_tree_manager)")
    print("   - E todos os outros 18 módulos!\n")
    print("🧪 TESTE AS FUNCIONALIDADES:")
    print("   - Ctrl+Alt+E (Dock de Open Editors)")
    print("   - Ctrl+Alt+Shift+F (Busca Global)")
    print("   - Clique direito na aba (Menu de Contexto)")
    print("   - Ctrl+Alt+D (Mover aba para painel oposto)\n")
    print("⏳ Quando terminar, FECHE A JANELA DO LITE XL para restaurar o backup.\n")
    
    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
    proc = subprocess.Popen([str(exe), str(user_dir)], creationflags=CREATE_NEW_CONSOLE)
    
    # 8. AGUARDAR FECHAMENTO E RESTAURAR
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.kill()
    
    print("\n🔄 Restaurando init de produção original...")
    if backup_init.exists():
        shutil.copy2(backup_init, prod_init)
        backup_init.unlink()
        print("✔ Rollback concluído com sucesso! Seu init original está de volta.")
    else:
        print("🚨 ERRO CRÍTICO: Backup não encontrado! Execute 'doxoade lite-xl rollback' manualmente.")

if __name__ == "__main__":
    run_full_test()
