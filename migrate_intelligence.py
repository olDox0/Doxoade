# migrate_intelligence.py
import os
import re
import shutil
from pathlib import Path

print("🛡️  [PASSO 1] Aplicando Regra de Segurança (--run) no refactor...")
cmd_path = Path("doxoade/commands/refactor_systems/refactor_command.py")
if cmd_path.exists():
    text = cmd_path.read_text(encoding="utf-8")
    
    # 1. Trocar a flag --dry-run por --run
    text = text.replace(
        "@click.option('--dry-run', is_flag=True, help=\"Apenas mostra o que seria feito, sem alterar arquivos.\")",
        "@click.option('--run', is_flag=True, help=\"Executa a refatoração. Por padrão, apenas simula (dry-run).\")"
    )
    
    # 2. Ajustar as funções de modificação para usar 'run' e definir dry_run = not run
    targets = [
        "refactor_move", "refactor_rename", "refactor_fix_imports", 
        "refactor_repair", "refactor_headers", "refactor_syntax_fix"
    ]
    for func in targets:
        # Troca o parâmetro dry_run por run na assinatura
        text = re.sub(rf"(def {func}\([^)]*?)dry_run([^)]*\):)", r"\1run\2", text)
        # Injeta a lógica de segurança no início da função
        pattern = rf"(def {func}\([^)]*\):)\n"
        replacement = r"\1\n    dry_run = not run\n"
        text = re.sub(pattern, replacement, text)
        
    cmd_path.write_text(text, encoding="utf-8")
    print("✔ refactor_command.py patcheado. Securança ativada.")
else:
    print("⚠️  refactor_command.py não encontrado.")

print("\n📦 [PASSO 2] Migrando intelligence para intelligence_systems...")
moves = [
    ("doxoade/commands/intelligence.py", "doxoade/commands/intelligence_systems/intelligence.py"),
    ("doxoade/commands/intelligence_utils.py", "doxoade/commands/intelligence_systems/intelligence_utils.py")
]

for src, dst in moves:
    src_p, dst_p = Path(src), Path(dst)
    if src_p.exists():
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_p), str(dst_p))
        print(f"✔ Movido: {src} -> {dst}")

print("\n🔗 [PASSO 3] Atualizando imports no projeto (Cura de Topologia)...")
# Mapeamento de substituição de imports
replacements = {
    r"from doxoade\.commands\.intelligence import": "from doxoade.commands.intelligence_systems.intelligence import",
    r"from doxoade\.commands\.intelligence_utils import": "from doxoade.commands.intelligence_systems.intelligence_utils import",
    r"import doxoade\.commands\.intelligence\b": "import doxoade.commands.intelligence_systems.intelligence",
    r"import doxoade\.commands\.intelligence_utils\b": "import doxoade.commands.intelligence_systems.intelligence_utils",
    # Ajustes para imports relativos/curtos dentro dos próprios arquivos movidos
    r"from intelligence_utils import": "from doxoade.commands.intelligence_systems.intelligence_utils import",
    r"from intelligence_systems\.": "from doxoade.commands.intelligence_systems.",
}

files_updated = 0
for py_file in Path("doxoade").rglob("*.py"):
    try:
        content = py_file.read_text(encoding="utf-8")
        original = content
        for pattern, repl in replacements.items():
            content = re.sub(pattern, repl, content)
        if content != original:
            py_file.write_text(content, encoding="utf-8")
            files_updated += 1
    except Exception:
        pass

print(f"✔ {files_updated} arquivos tiveram os imports atualizados.")
print("\n✅ Migração concluída! O Doxoade está seguro e organizado.")