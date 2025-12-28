# fix_agent_test.py
import os

new_method = r'''
    def generate_test_cases(self, func_name):
        fn = func_name.lower()
        # Testes de Matemática (O que ele já sabe)
        if fn in ["soma", "add", "plus"]: return [f"assert {func_name}(1, 1) == 2", f"assert {func_name}(10, 5) == 15"]
        if fn in ["sub", "diff"]: return [f"assert {func_name}(10, 5) == 5"]
        if fn in ["mult", "prod"]: return [f"assert {func_name}(3, 3) == 9"]
        
        # [NOVO] Testes de I/O (O que ele precisa provar)
        if any(x in fn for x in ["salvar", "save", "escrever", "write", "arquivo", "file"]):
            return [
                "import os",
                f"try: os.remove('teste_io.txt')\n    except: pass", # Limpa antes
                f"{func_name}('teste_io.txt', 'Ola Doxoade')", # Executa
                f"assert os.path.exists('teste_io.txt') or os.path.exists('file.txt')", # Verifica existência
                "with open('teste_io.txt' if os.path.exists('teste_io.txt') else 'file.txt', 'r') as f: assert 'Ola' in f.read()" # Verifica conteúdo
            ]

        return [f"print('Teste genérico para {func_name}')"]
'''

path = 'doxoade/commands/agent.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Substituição "burra" mas eficaz: trocamos o método antigo pelo novo
# Identificamos o antigo pelo cabeçalho até o primeiro return conhecido
import re
pattern = r"def generate_test_cases\(self, func_name\):[\s\S]+?return \[f\"print\('Teste genérico para \{func_name\}'\)\"\]"

if re.search(pattern, content):
    new_content = re.sub(pattern, new_method.strip(), content)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("✅ [SUCESSO] Professor atualizado. O Agente agora exige prova de I/O.")
else:
    print("❌ [ERRO] Não encontrei a função original para substituir. Verifique o arquivo.")