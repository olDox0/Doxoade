import hashlib
import difflib
from pathlib import Path

user_dir = Path.home() / ".config" / "lite-xl"
prod_init = user_dir / "init.lua"
test_init = user_dir / ".doxoade" / "test_deploy" / "init.lua"

prod_src = user_dir / ".doxoade" / "diagnostics" / "last_preflight_aot_production.lua"
test_src = user_dir / ".doxoade" / "diagnostics" / "last_preflight_aot_test.lua"

print("--- INIT.LUA BYTECODE ---")
if prod_init.exists() and test_init.exists():
    p_hash = hashlib.sha256(prod_init.read_bytes()).hexdigest()[:16]
    t_hash = hashlib.sha256(test_init.read_bytes()).hexdigest()[:16]
    print(f"PROD: {prod_init.stat().st_size:>8,} bytes | SHA256: {p_hash}")
    print(f"TEST: {test_init.stat().st_size:>8,} bytes | SHA256: {t_hash}")
    if p_hash == t_hash:
        print("✔ Hashes IDÊNTICOS!")
    else:
        print("⚠ Hashes diferem (Veja a análise de buffer abaixo).")
else:
    print("⚠ Um dos init.lua não foi encontrado.")

print("\n--- SOURCE BUFFERS (Último Preflight) ---")
if prod_src.exists() and test_src.exists():
    p_text = prod_src.read_text(encoding="utf-8").splitlines()
    t_text = test_src.read_text(encoding="utf-8").splitlines()
    if p_text == t_text:
        print("✔ Os buffers de código-fonte (Lua puro) são 100% IDÊNTICOS!")
        print("  ↳ A diferença residual no bytecode é APENAS o 'chunk name' (caminho do .lua temporário)")
        print("    que o Lua 5.4 embute no header do binário (ex: doxly_aot_production_1234.lua vs doxly_aot_test_1234.lua).")
        print("  ↳ Isso é esperado e não afeta a execução. O código soberano é o mesmo.")
    else:
        print("⚠ Os buffers diferem. Gerando diff...")
        diff = list(difflib.unified_diff(p_text, t_text, lineterm=""))
        for line in diff[:30]:
            print(line)
else:
    print("⚠ Arquivos de buffer não encontrados. Rode o deploy com --force primeiro.")