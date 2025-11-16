#!/bin/bash

# Cores para a saída
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Sem Cor

echo -e "${GREEN}[DOXOADE PYTHON INSTALLER FOR LINUX/TERMUX]${NC}"
echo ""

# Verifica se estamos no Termux
if [ -n "$TERMUX_VERSION" ]; then
    echo -e "${YELLOW}Ambiente Termux detectado.${NC}"
    echo "Atualizando a lista de pacotes (pkg update)..."
    pkg update -y
    echo "Instalando Python e Pip (pkg install python)..."
    pkg install python -y
    echo ""
    echo -e "${GREEN}SUCESSO: Python e Pip foram instalados!${NC}"
    echo "Por favor, reinicie o Termux para garantir que as mudancas tenham efeito."

# Fallback para sistemas baseados em Debian/Ubuntu (usando apt)
elif command -v apt &> /dev/null; then
    echo -e "${YELLOW}Ambiente baseado em APT (Debian/Ubuntu) detectado.${NC}"
    echo "Atualizando a lista de pacotes (apt update)..."
    sudo apt update
    echo "Instalando Python e Pip (apt install python3 python3-pip)..."
    sudo apt install python3 python3-pip -y
    echo ""
    echo -e "${GREEN}SUCESSO: Python e Pip foram instalados!${NC}"
    echo "Execute 'python3 --version' para confirmar."

# Fallback para outros sistemas
else
    echo -e "${RED}ERRO: Sistema operacional ou gerenciador de pacotes nao reconhecido.${NC}"
    echo "Por favor, instale o Python 3 usando o gerenciador de pacotes da sua distribuicao."
fi