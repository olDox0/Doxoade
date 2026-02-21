# Doxoade Internals - Vol. 6: Git e Workflow Seguro

**Versão:** 1.0
**Status:** Ativo

## Filosofia do Workflow
O Doxoade desencoraja o uso direto de comandos `git` manuais para operações de rotina. O objetivo é garantir que **nenhum código quebrado seja comitado** e que todo commit gere aprendizado.

## Comandos Principais

### 1. Save (O Guardião)
`doxoade save "mensagem"`
*   **O que faz:** Roda `check` -> `git add` -> `git commit` -> `learning`.
*   **Segurança:** Se o `check` falhar, o commit é abortado (a menos que use `--force`).
*   **Inteligência:** Compara os erros de antes e depois para alimentar a Gênese.

### 2. Sync (Sincronização)
`doxoade sync`
*   **O que faz:** `git pull --rebase` (ou merge) seguido de `git push`.
*   **Segurança:** Verifica se você está no branch correto e se há upstream configurado.

### 3. Merge (Resolvedor Inteligente)
`doxoade merge [branch]`
*   **O que faz:** Inicia o merge. Se houver conflitos, abre uma interface interativa CLI para escolher "Ours", "Theirs" ou "Both".
*   **Diferencial:** Valida a sintaxe do arquivo mesclado antes de aceitar.

### 4. Rewind (Máquina do Tempo)
`doxoade rewind arquivo.py`
*   **O que faz:** Reverte um arquivo específico para a versão do último commit (HEAD).
*   **Segurança:** Cria um backup `.bak` da versão atual antes de reverter.

### 5. Git-Clean
`doxoade git-clean`
*   **O que faz:** Lê o `.gitignore` e remove do índice (untrack) arquivos que não deveriam estar lá, mas foram comitados por engano.

### 6. Git-New
`doxoade git-new "msg" "url_remota"`
*   **O que faz:** Inicializa repo, adiciona remote, comita e dá push. Automação de "Zero to Hero".