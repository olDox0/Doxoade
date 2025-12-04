# Doxoade Internals - Vol. 8: Utilitários e IDE

**Versão:** 1.0
**Foco:** Produtividade

## Ambiente Mobile (Termux)

### 1. IDE (Editor Integrado)
`doxoade ide`
*   Editor de texto TUI (Text User Interface) leve.
*   Recursos: Explorador de arquivos, execução rápida (`F5`), integração Git.

### 2. Android Sync
`doxoade android`
*   **Export:** Envia projeto para `Downloads/DoxoadeExports` (ignora `venv`, `.git`).
*   **Import:** Traz projetos do armazenamento compartilhado.

## Manipulação de Arquivos

### 1. Moddify (O Cirurgião)
`doxoade moddify [cmd] [arquivo]`
*   **add:** Insere linhas.
*   **remove:** Deleta linhas.
*   **replace:** Substitui texto (String ou Regex).
*   **Uso:** Ideal para scripts de automação (`maestro`) ou correções rápidas sem abrir editor.

### 2. Mk (Make)
`doxoade mk caminho/arquivo.py`
*   Cria arquivos e toda a árvore de diretórios necessária em um comando.

## Gestão de Ambiente

### 1. Install / Doctor
*   **`install`:** Gerencia dependências (`pip install`).
*   **`doctor`:** Diagnostica o projeto atual. Verifica se `venv` existe, se está ativo e se `requirements.txt` está sincronizado.

### 2. Venv-Up
`doxoade venv-up`
*   Abre um novo shell com o ambiente virtual ativado automaticamente.