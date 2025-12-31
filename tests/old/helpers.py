# tests/helpers.py

file_content = """
# Este arquivo conterá funções auxiliares para a suíte de testes.
# Por exemplo, funções para criar estruturas de projeto falsas,
# manipular arquivos temporários, etc.

def create_fake_project():
    \"\"\"Placeholder para uma futura função auxiliar.\"\"\"
    pass
"""

with open("tests/helpers.py", "w", encoding="utf-8") as f:
    f.write(file_content.strip())

print("Arquivo 'tests/helpers.py' criado com sucesso.")