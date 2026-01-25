# Arquitetura do Núcleo (Doxoade Core)

A partir da versão v66.40, o Doxoade migrou de um script monolítico para uma arquitetura modular robusta.

## Estrutura de Diretórios

### `doxoade/tools/` (A Caixa de Ferramentas)
Substituiu o antigo `shared_tools.py`.
*   **`git.py`**: Wrappers seguros para comandos Git.
*   **`filesystem.py`**: Manipulação de caminhos, config (TOML) e detecção de Venv.
*   **`analysis.py`**: Análise estática, AST, Hashing e Mineração de Traceback.
*   **`logger.py`**: Sistema de log centralizado.
*   **`db_utils.py`**: Camada de acesso ao SQLite (`open_incidents`, `events`).
*   **`display.py`**: Lógica de apresentação (UI/UX) e cores.
*   **`genesis.py`**: IA Simbólica para sugestão de correções e abdução de imports.
*   **`governor.py`**: Cérebro ALB para modulação de carga de CPU/RAM/Disco.
*   **`streamer.py`**: (UFS) Sistema unificado de streaming de arquivos com cache em RAM.
*   **`memory_pool.py`**: Arena de alocação controlada para objetos efêmeros.
*   **`db_utils.py`**: Persistência assíncrona com Batch Commits adaptativos.

### `doxoade/dnm.py` (Directory Navigation Module)
O **DNM** é a autoridade única sobre "quais arquivos fazem parte do projeto".
*   Lê `.gitignore` e `pyproject.toml`.
*   Filtra pastas de sistema (`venv`, `__pycache__`).
*   Deve ser usado por qualquer comando que precise varrer o disco (`check`, `stats`, etc.).

### `doxoade/shared_tools.py` (Fachada)
Mantido apenas para retrocompatibilidade. Ele importa tudo de `doxoade/tools/` e re-exporta. Novos comandos devem importar direto de `tools/`.

