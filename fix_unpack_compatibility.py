# fix_unpack_compatibility.py
"""
🔧 CORREÇÃO DE COMPATIBILIDADE: unpack → table.unpack
O Lite XL 2.1.8 (Lua 5.4) removeu 'unpack' do _G.
Este script corrige todos os templates automaticamente.
"""
import re
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

def fix_unpack_in_templates():
    template_dir = LiteXLEngine.get_template_dir()
    templates = list(template_dir.glob("*.lua"))
    
    print(f"🔧 Corrigindo compatibilidade unpack → table.unpack")
    print(f"📂 Diretório: {template_dir}")
    print(f"📄 Templates encontrados: {len(templates)}\n")
    
    total_fixes = 0
    fixed_files = []
    
    for template in templates:
        content = template.read_text(encoding="utf-8")
        original_content = content
        
        # Regex para encontrar 'unpack(' mas NÃO 'table.unpack('
        # Usa negative lookbehind para evitar substituir 'table.unpack'
        pattern = r'(?<!table\.)(?<!\w)unpack\('
        
        # Conta ocorrências antes de substituir
        matches = re.findall(pattern, content)
        if matches:
            # Substitui unpack( por table.unpack(
            content = re.sub(pattern, 'table.unpack(', content)
            
            # Salva de volta
            template.write_text(content, encoding="utf-8")
            
            total_fixes += len(matches)
            fixed_files.append((template.name, len(matches)))
            
            print(f"  ✔ {template.name}: {len(matches)} correção(ões)")
    
    print(f"\n{'='*60}")
    if total_fixes > 0:
        print(f"✅ CORREÇÃO CONCLUÍDA: {total_fixes} substituições em {len(fixed_files)} arquivos")
        print(f"\n📋 Arquivos corrigidos:")
        for fname, count in fixed_files:
            print(f"   • {fname} ({count}x)")
    else:
        print("✅ Nenhum 'unpack' encontrado. Todos os templates já estão compatíveis.")
    print(f"{'='*60}\n")
    
    return total_fixes

if __name__ == "__main__":
    fix_unpack_in_templates()