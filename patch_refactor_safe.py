# patch_refactor_safe.py
import re
from pathlib import Path

file_path = Path("doxoade/commands/refactor_systems/refactor_command.py")
if not file_path.exists():
    print("❌ refactor_command.py não encontrado.")
    exit(1)

content = file_path.read_text(encoding="utf-8")

# Lista de funções que precisam de ajuste
target_funcs = [
    "refactor_move", "refactor_rename", "refactor_fix_imports", 
    "refactor_headers", "refactor_repair", "refactor_syntax_fix"
]

print("🛡️  [PASSO 1] Unificando assinaturas e injetando lógica de segurança...")
for func in target_funcs:
    # 1. Corrigir a assinatura para aceitar ambos os parâmetros
    func_pattern = rf"(def {func}\s*\([^)]*)(\)\s*(?:->[^:]+)?:)"
    match = re.search(func_pattern, content, re.DOTALL)
    if match:
        params_part = match.group(1)
        suffix = match.group(2)
        
        if "dry_run" not in params_part:
            params_part += ", dry_run=False"
        if "run" not in params_part:
            params_part += ", run=False"
            
        new_def = params_part + suffix
        content = content.replace(match.group(0), new_def)
        
    # 2. Injetar a lógica de segurança no início da função
    body_pattern = rf"(def {func}\s*\([^)]*\)\s*(?:->[^:]+)?:\n)"
    body_match = re.search(body_pattern, content)
    if body_match:
        if "dry_run = not run" not in content[body_match.end():body_match.end()+200]:
            injection = "    dry_run = not run\n"
            content = content[:body_match.end()] + injection + content[body_match.end():]

print("🔄 [PASSO 2] Atualizando decorators do CLI (--dry-run -> --run)...")
# Substituição global para os decorators de dry-run
content = content.replace(
    "@click.option('--dry-run', is_flag=True, help=\"Apenas mostra o que seria feito, sem alterar arquivos.\")",
    "@click.option('--run', is_flag=True, help=\"Executa a refatoração. Por padrão, apenas simula (dry-run).\")"
)
content = content.replace(
    "@click.option('--dry-run', is_flag=True, help='Apenas mostra o que seria feito, sem alterar arquivos.')",
    "@click.option('--run', is_flag=True, help='Executa a refatoração. Por padrão, apenas simula (dry-run).')"
)

file_path.write_text(content, encoding="utf-8")
print("✅ refactor_command.py reparado com sucesso. A regra de segurança está ativa.")