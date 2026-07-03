import sys
import re
import json

def validate(file_path):
    print(f"🔍 [NEXUS VALIDATOR] Analisando: {file_path}\n")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    errors = 0

    # 1. VERIFICAÇÃO DE TAGS XML (O Qwen exige tags coladas: <tag>)
    bad_tags = re.findall(r'<\w+\s+>', content)
    bad_params = re.findall(r'<parameter=\w+\s+>', content)
    if bad_tags or bad_params:
        print(f"❌ FALHA 1 (XML Spaces): Tags com espaços detectados.")
        print(f"   Exemplos: {bad_tags[:3]} {bad_params[:3]}")
        print(f"   -> Causa: O formatador no intelligence.py ainda está injetando espaços.\n")
        errors += 1
    else:
        print("✅ PASSO 1: Tags XML limpas (Formato Tool-Call Nativo OK).")

    # 2. VERIFICAÇÃO DE JSON (Chaves não podem ter espaços)
    bad_json_keys = re.findall(r'"\w+\s+":', content)
    if bad_json_keys:
        print(f"❌ FALHA 2 (JSON Keys): Chaves JSON com espaços detectados.")
        print(f"   Exemplos: {bad_json_keys[:3]}")
        print(f"   -> Causa: Falta usar separators=(',', ':') no json.dumps().\n")
        errors += 1
    else:
        print("✅ PASSO 2: JSON estruturalmente válido.")

    # 3. VERIFICAÇÃO DE CORRUPELA DO HERMES (O teste de fogo!)
    hermes_artifacts = ['Exe cutor', 'hermes _systems', 'impor t', 'f ile', 'b uilder']
    found = [a for a in hermes_artifacts if a in content]
    if found:
        print(f"❌ FALHA 3 (Hermes Interference): O Hermes está comendo o código-fonte!")
        print(f"   Artefatos encontrados: {found}")
        print(f"   -> Causa: O intelligence.py ou cmd_hermes.py NÃO estão na HERMES_BLACKLIST.\n")
        errors += 1
    else:
        print("✅ PASSO 3: Código-fonte íntegro (Hermes Blacklist funcionando).")

    print("-" * 50)
    if errors == 0:
        print("🎉 DOSSIÊ APROVADO! O Qwen conseguirá ler e processar perfeitamente.")
        print("   Pode me mandar o conteúdo do <think> e do <tool_call> que eu faço a análise.")
    else:
        print(f"⚠️  {errors} erro(s) crítico(s) encontrado(s). O Qwen rejeitará este XML.")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "chief_dossier_qwen.xml"
    validate(target)