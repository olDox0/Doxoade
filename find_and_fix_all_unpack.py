# find_and_fix_all_unpack.py
"""
🔍 FIND & FIX ALL UNPACK — Busca cirúrgica de TODOS os 'unpack' nos templates.
"""
import re
from pathlib import Path
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder

def find_all_unpack():
    template_dir = LiteXLEngine.get_template_dir()
    templates = sorted(template_dir.glob("*.lua"))
    
    print("🔍 BUSCA CIRÚRGICA DE 'unpack' EM TODOS OS TEMPLATES")
    print(f"📂 Diretório: {template_dir}\n")
    
    all_occurrences = []
    
    for template in templates:
        lines = template.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            # Procura 'unpack' que NÃO seja 'table.unpack'
            # Remove comentários primeiro
            clean = re.sub(r'--.*$', '', line)
            clean = re.sub(r'"[^"]*"', '""', clean)
            clean = re.sub(r"'[^']*'", "''", clean)
            
            # Busca unpack( mas não table.unpack(
            if re.search(r'(?<!table\.)(?<!\w)unpack\s*\(', clean):
                all_occurrences.append({
                    "file": template.name,
                    "line": i,
                    "content": line.strip(),
                    "clean": clean.strip()
                })
    
    print(f"📊 Total de ocorrências encontradas: {len(all_occurrences)}\n")
    
    for occ in all_occurrences:
        print(f"  📄 {occ['file']}:{occ['line']}")
        print(f"     {occ['content']}")
        print()
    
    # Agora verifica no init gerado
    print("=" * 70)
    print("📋 VERIFICAÇÃO NO INIT GERADO")
    print("=" * 70)
    
    sovereign_init = LiteXLInitBuilder.generate_sovereign_init()
    init_lines = sovereign_init.splitlines()
    
    # Procura unpack no init gerado
    init_occurrences = []
    for i, line in enumerate(init_lines, 1):
        clean = re.sub(r'--.*$', '', line)
        clean = re.sub(r'"[^"]*"', '""', clean)
        clean = re.sub(r"'[^']*'", "''", clean)
        
        if re.search(r'(?<!table\.)(?<!\w)unpack\s*\(', clean):
            # Encontra qual template é responsável
            template_name = "UNKNOWN"
            for j in range(i - 1, -1, -1):
                if "[TEMPLATE:" in init_lines[j]:
                    template_name = init_lines[j].strip()
                    break
            
            init_occurrences.append({
                "init_line": i,
                "template": template_name,
                "content": line.strip()
            })
    
    print(f"\n📊 Ocorrências de 'unpack' no init gerado: {len(init_occurrences)}\n")
    
    for occ in init_occurrences:
        print(f"  📍 Linha {occ['init_line']} do init → {occ['template']}")
        print(f"     {occ['content']}")
        print()
    
    # CORREÇÃO AUTOMÁTICA
    if all_occurrences:
        print("=" * 70)
        print("🔧 APLICANDO CORREÇÕES AUTOMÁTICAS")
        print("=" * 70)
        
        total_fixes = 0
        for template in templates:
            content = template.read_text(encoding="utf-8")
            original = content
            
            # Substituição mais agressiva: qualquer 'unpack(' que não seja 'table.unpack('
            # Passo 1: Substitui unpack( por table.unpack(
            content = re.sub(r'(?<!table\.)(?<!\w)unpack\s*\(', 'table.unpack(', content)
            
            if content != original:
                template.write_text(content, encoding="utf-8")
                fixes = len(re.findall(r'table\.unpack\(', content)) - len(re.findall(r'table\.unpack\(', original))
                total_fixes += fixes
                print(f"  ✔ {template.name}: {fixes} correção(ões) aplicada(s)")
        
        print(f"\n✅ Total de correções: {total_fixes}")
    else:
        print("✅ Nenhum 'unpack' problemático encontrado nos templates.")
        print("⚠ O problema pode estar no código gerado pelo generate_sovereign_init()")

if __name__ == "__main__":
    find_all_unpack()