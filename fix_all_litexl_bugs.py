# fix_all_litexl_bugs.py
"""
🔧 CORREÇÃO TOTAL DE BUGS DO LITE XL
1. Substitui TODOS os 'unpack(' por 'table.unpack(' em TODOS os arquivos .lua do sistema.
2. Corrige a variável 'report_path' indefinida no 10_forensic_engine.lua.
"""
import re
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

def fix_all_litexl_bugs():
    print("🔍 Buscando e corrigindo bugs em TODOS os arquivos Lua do sistema Lite XL...\n")
    
    # 1. Corrigir 'unpack' em TODOS os arquivos .lua do diretório lite_xl_systems
    base_dir = Path("doxoade/commands/lite_xl_systems")
    if not base_dir.exists():
        base_dir = Path(__file__).parent / "doxoade" / "commands" / "lite_xl_systems"
        
    lua_files = list(base_dir.rglob("*.lua"))
    print(f"📂 Analisando {len(lua_files)} arquivos .lua em {base_dir}")
    
    unpack_fixed_count = 0
    for lua_file in lua_files:
        try:
            content = lua_file.read_text(encoding="utf-8")
            # Procura 'unpack(' que não seja 'table.unpack('
            if re.search(r'(?<!table\.)(?<!\w)unpack\s*\(', content):
                new_content = re.sub(r'(?<!table\.)(?<!\w)unpack\s*\(', 'table.unpack(', content)
                lua_file.write_text(new_content, encoding="utf-8")
                print(f"  ✔ {lua_file.relative_to(base_dir)}: 'unpack' corrigido para 'table.unpack'")
                unpack_fixed_count += 1
        except Exception as e:
            print(f"  ⚠ Erro ao ler {lua_file.name}: {e}")
            
    if unpack_fixed_count == 0:
        print("  ℹ Nenhum 'unpack' solto encontrado (já estão corrigidos).")
    else:
        print(f"\n✅ {unpack_fixed_count} arquivo(s) com 'unpack' corrigido(s).")

    # 2. Corrigir 'report_path' indefinido em 10_forensic_engine.lua
    forensic_path = LiteXLEngine.get_template_dir() / "10_forensic_engine.lua"
    if forensic_path.exists():
        content = forensic_path.read_text(encoding="utf-8")
        # Verifica se o bug existe e se ainda não foi corrigido
        if "local f = io.open(report_path, \"w\")" in content and "local report_path = diag_dir" not in content:
            # Insere a definição de report_path antes do io.open
            new_content = content.replace(
                "local function write_forensic_report()\nlocal f = io.open(report_path, \"w\")",
                "local function write_forensic_report()\nlocal report_path = diag_dir .. PATHSEP .. \"forensic_report.txt\"\nlocal f = io.open(report_path, \"w\")"
            )
            forensic_path.write_text(new_content, encoding="utf-8")
            print("  ✔ 10_forensic_engine.lua: Variável 'report_path' indefinida corrigida.")
        else:
            print("  ℹ 10_forensic_engine.lua: 'report_path' já está definido corretamente.")
    else:
        print("  ⚠ 10_forensic_engine.lua não encontrado no diretório de templates.")

    print("\n" + "="*60)
    print("✅ CORREÇÕES CONCLUÍDAS COM SUCESSO!")
    print("="*60)
    print("Agora, regenere o init e lance o Lite XL:")
    print("  doxoade doxly deploy production --launch")
    print("="*60)

if __name__ == "__main__":
    fix_all_litexl_bugs()
