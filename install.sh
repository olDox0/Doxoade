#!/usr/bin/env bash
# doxoade/install.sh
# Instalador Universal Doxoade — Termux / Linux / WSL

set -e

echo "=== 🚀 Instalador Universal Doxoade (Multiplataforma) ==="

# 1. Detecção de Ambiente Termux (Android)
IS_TERMUX=0
if [ -n "$TERMUX_VERSION" ] || [ -d "/data/data/com.termux" ]; then
    IS_TERMUX=1
    echo "📱 Ambiente detectado: Termux (Android)"
fi

# 2. Provisionamento de pacotes nativos no Termux
if [ "$IS_TERMUX" -eq 1 ]; then
    echo "📦 Instalando dependências nativas via pkg (clang, python, python-psutil)..."
    pkg update -y
    pkg install -y python clang libxml2 libxslt python-psutil git
fi

# 3. Atualização do pip e ferramentas de empacotamento
echo "⚙️ Atualizando pip, setuptools e wheel..."
python -m pip install --upgrade pip setuptools wheel

# 4. Instalação em Modo Editável
echo "🔨 Instalando Doxoade em modo editável (-e .)..."
if [ "$IS_TERMUX" -eq 1 ]; then
    # No Termux, instala sem isolamento de build para aproveitar o python-psutil nativo
    python -m pip install --no-build-isolation -e .
else
    python -m pip install -e .
fi

echo "✅ Instalação concluída com sucesso!"
echo "💡 Execute: doxoade --help"
