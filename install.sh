#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}--- Instalador Universal Doxoade para Linux/Termux ---${NC}"

# 1. Encontra o diretório raiz do projeto Doxoade
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 2. Cria/verifica o ambiente virtual
VENV_DIR="$PROJECT_ROOT/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv "$VENV_DIR"
fi

# 3. Instala as dependências
echo "Instalando dependências via pip..."
"$VENV_DIR/bin/python" -m pip install -r "$PROJECT_ROOT/requirements.txt"

# 4. Cria o script wrapper inteligente
RUNNER_DIR="$HOME/.local/bin"
mkdir -p "$RUNNER_DIR"
RUNNER_PATH="$RUNNER_DIR/doxoade"

echo "Criando o script wrapper em $RUNNER_PATH..."
cat > "$RUNNER_PATH" << EOF
#!/bin/bash
DOXOADE_DIR="$PROJECT_ROOT"

# Logica do Dispatcher
if [ "\$1" == "python" ]; then
    "\$DOXOADE_DIR/install-python.sh"
else
    "\$DOXOADE_DIR/venv/bin/python" "\$DOXOADE_DIR/doxoade/doxoade.py" "\$@"
fi
EOF

chmod +x "$RUNNER_PATH"

# 5. Guia o usuário para configurar o PATH
echo ""
echo -e "${GREEN}--- Guia de Instalação Universal ---${NC}"
echo "A instalação está quase completa. Adicione a seguinte linha ao seu arquivo de configuração do shell:"
echo ""
echo -e "${YELLOW}   export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
echo ""
echo "Execute um dos seguintes comandos:"
echo "  - Para Bash: echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
echo "  - Para Zsh:  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc && source ~/.zshrc"
echo ""
echo -e "${GREEN}Instalação concluída! O comando 'doxoade' agora está disponível.${NC}"