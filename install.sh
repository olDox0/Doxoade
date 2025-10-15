#!/bin/bash

# --- Script de Instalação Universal para Doxoade ---
# Este script automatiza o processo de instalação em ambientes baseados em Linux (incluindo Termux).

echo "--- Iniciando a instalação da Doxoade ---"

# Passo 1: Verificação de Dependências do Sistema (para Termux)
if [ -n "$TERMUX_VERSION" ]; then
    echo "Ambiente Termux detectado. Verificando dependências de compilação..."
    pkg install -y python clang libxml2 libxslt
fi

# Passo 2: Instalação das Dependências Python
echo -e "\n--- Passo 1: Instalando dependências do Python via pip... ---"
if pip install -r requirements.txt; then
    echo "[OK] Dependências do Python instaladas com sucesso."
else
    echo "[ERRO] Falha ao instalar as dependências do Python. Abortando."
    exit 1
fi

# Passo 3: Instalação da Doxoade em Modo Editável
echo -e "\n--- Passo 2: Instalando a Doxoade em modo editável... ---"
if pip install -e .; then
    echo "[OK] Doxoade instalada com sucesso."
else
    echo "[ERRO] Falha ao executar 'pip install -e .'. Abortando."
    exit 1
fi

# Passo 4: Configuração do Alias Universal (O Coração da Solução)
echo -e "\n--- Passo 3: Configurando o alias universal... ---"

# Encontra o caminho absoluto para o run_doxoade.py
RUNNER_PATH=$(find "$PWD" -name "run_doxoade.py")

if [ -z "$RUNNER_PATH" ]; then
    echo "[ERRO] Não foi possível encontrar 'run_doxoade.py'. A instalação pode estar corrompida."
    exit 1
fi

# Detecta o shell do usuário (bash ou zsh)
if [ -n "$BASH_VERSION" ]; then
    SHELL_CONFIG_FILE=~/.bashrc
elif [ -n "$ZSH_VERSION" ]; then
    SHELL_CONFIG_FILE=~/.zshrc
else
    SHELL_CONFIG_FILE=~/.profile # Fallback
fi

ALIAS_COMMAND="alias doxoade='python $RUNNER_PATH'"

# Verifica se o alias já existe para não duplicá-lo
if grep -qF -- "$ALIAS_COMMAND" "$SHELL_CONFIG_FILE"; then
    echo "[OK] O alias 'doxoade' já está configurado em seu $SHELL_CONFIG_FILE."
else
    echo "Adicionando o alias ao seu $SHELL_CONFIG_FILE..."
    echo "" >> "$SHELL_CONFIG_FILE"
    echo "# Alias para a ferramenta de P&D Doxoade" >> "$SHELL_CONFIG_FILE"
    echo "$ALIAS_COMMAND" >> "$SHELL_CONFIG_FILE"
    echo "[OK] Alias adicionado com sucesso."
fi

echo -e "\n--- Instalação Concluída! ---"
echo "Por favor, execute o seguinte comando ou REINICIE SEU TERMINAL para que o comando 'doxoade' funcione:"
echo "source $SHELL_CONFIG_FILE"