# Arquivo de configuração para o sistema de testes de regressão "Cânone".

# Define o diretório base para os projetos de teste ("pacientes zero").
fixtures_dir = "fixtures"

# Define o diretório onde os "snapshots" canônicos serão armazenados.
canon_dir = "canon"

# --- Casos de Teste de Regressão ---

[[test_case]]
# Um identificador único para este teste.
id = "check_finds_syntax_error"

# O comando doxoade a ser executado.
command = "doxoade check ."

# O nome do projeto "paciente" a ser usado, localizado em 'fixtures_dir'.
project = "project_syntax_error"