#!/bin/bash
echo "--- Instalador Universal Doxoade (Moderno) ---"

# Verifica se Python está instalado
if ! command -v python &> /dev/null; then
    echo "[ERRO] Python não encontrado. Instale o Python primeiro."
    exit 1
fi

# Instalação via PIP (o método correto que gera os binários)
echo "Instalando via pip em modo editável..."
python -m pip install -e .

if [ $? -eq 0 ]; then
    echo ""
    echo "[SUCESSO] Doxoade instalado."
    echo "Se o comando 'doxoade' não for encontrado, adicione este caminho ao seu PATH:"
    python -m site --user-base | sed 's/$/\/bin/'
else
    echo "[ERRO] Falha na instalação via pip."
    exit 1
fi