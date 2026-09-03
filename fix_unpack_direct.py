# fix_unpack_direct.py
"""
🔧 CORREÇÃO CIRÚRGICA DE 'unpack' -> 'table.unpack'
Corrige o init.lua de produção que está travando e atualiza todos os templates.
"""
import re
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

def fix_all_unpacks():
    print("🔧 CORREÇÃO DIRETA DE 'unpack' -> 'table.unpack'")
    print("=" * 60)
    
    # 1. Corrigir o init.lua de PRODUÇÃO atual (o que está causando o crash)
    init_path = LiteXLEngine.get_init_lua_path()
    if init_path.exists():
        content = init_path.read_text(encoding="utf-8")
        # Regex robusta: captura 'unpack' seguido de '(' (com ou sem espaço), 
        # desde que não seja precedido por 'table.' ou outra palavra
        new_content, count = re.subn(r'(?<!table\.)(?<!\w)unpack\s*\(', 'table.unpack(', content)
        
        if count > 0:
            backup = init_path.with_suffix(".lua.backup_antes_fix_unpack")
            init_path.rename(backup)
            init_path.write_text(new_content, encoding="utf-8")
            print(f"✅ [PRODUÇÃO] {count} ocorrência(s) corrigida(s) no init.lua")
            print(f"   💾 Backup salvo em: {backup.name}")
        else:
            print("ℹ️ [PRODUÇÃO] Nenhum 'unpack' solto encontrado no init.lua atual.")
    else:
        print("⚠️ [PRODUÇÃO] init.lua não encontrado.")

    # 2. Corrigir TODOS os templates para garantir que o próximo deploy seja 100% limpo
    template_dir = LiteXLEngine.get_template_dir()
    templates_fixed = 0
    for template in sorted(template_dir.glob("*.lua")):
        content = template.read_text(encoding="utf-8")
        new_content, count = re.subn(r'(?<!table\.)(?<!\w)unpack\s*\(', 'table.unpack(', content)
        if count > 0:
            template.write_text(new_content, encoding="utf-8")
            print(f"  ✔ [TEMPLATE] {template.name}: {count} correção(ões)")
            templates_fixed += 1
            
    if templates_fixed > 0:
        print(f"\n✅ {templates_fixed} template(s) atualizado(s). O próximo deploy será limpo.")
    else:
        print("\nℹ️ Todos os templates já estão limpos.")
        
    print("\n" + "=" * 60)
    print("💡 PRÓXIMO PASSO:")
    print("   Tente abrir o Lite XL novamente com o deploy de produção:")
    print("   doxoade lite-xl deploy production --launch")
    print("=" * 60)

if __name__ == "__main__":
    fix_all_unpacks()
