# canary_test.py
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
import shutil

sandbox = LiteXLEngine.get_sandbox_dir()
sovereign = LiteXLEngine.get_init_lua_path()
sandbox_init = sandbox / "init.lua"

# 1. Copia o init soberano completo
shutil.copy2(sovereign, sandbox_init)

# 2. INJETA O CANÁRIO NO TOPO (primeiro código a executar)
canary = '''-- 🐤 BOOT CANARY: prova síncrona de execução + revela o USERDIR real
local _c = io.open((USERDIR or ".") .. (PATHSEP or "/") .. "BOOT_CANARY.txt", "w")
if _c then
  _c:write("BOOT_OK " .. os.date("%Y-%m-%d %H:%M:%S") .. "\\nUSERDIR=" .. tostring(USERDIR))
  _c:close()
end
'''
content = sandbox_init.read_text(encoding="utf-8")
sandbox_init.write_text(canary + "\n" + content, encoding="utf-8")

# 3. Limpa canário antigo
old = sandbox / "BOOT_CANARY.txt"
if old.exists(): old.unlink()

print("✔ Canário injetado no topo do init do sandbox.")
print("\n👉 Agora feche TODO Lite XL e lance MANUALMENTE:")
print(f'   "{LiteXLEngine.find_executable()}" --userdir "{sandbox}"')
print("\n👉 Espere a janela abrir, e SEM FECHAR, rode em OUTRO terminal:")
print(f'   python -c "from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine; s=LiteXLEngine.get_sandbox_dir(); print(\'CANARIO:\', (s/\'BOOT_CANARY.txt\').exists()); print(open(s/\'BOOT_CANARY.txt\').read() if (s/\'BOOT_CANARY.txt\').exists() else \'NAO CRIOU\')"')
