# Doxoade Internals - Vol. 3: O Maestro e Automação

**Versão do Documento:** 1.0 (Gênese V14)
**Data:** 01/12/2025
**Módulo:** `doxoade/commands/maestro.py`

## 1. O Conceito Maestro

O **Maestro** é um orquestrador de processos embutido no Doxoade. Ele implementa uma **Linguagem de Domínio Específico (DSL)** chamada `.dox`.

### Por que uma nova linguagem?
Scripts de automação (`.bat` no Windows, `.sh` no Linux) sofrem de problemas crônicos de portabilidade. O Maestro resolve isso fornecendo uma camada de abstração unificada que roda sobre o Python, garantindo que um script `.dox` de deploy funcione identicamente no Windows (PowerShell/CMD) e no Linux (Bash/Termux).

---

## 2. A Linguagem `.dox`

A sintaxe é imperativa, linear e focada em fluxo de controle legível.

### Primitivas de Execução
*   **`RUN`**: Executa comandos do ecossistema Doxoade dentro do ambiente virtual ativo.
    *   Ex: `RUN doxoade check . -> RESULTADO` (Captura stdout na variável RESULTADO).
*   **`BATCH`**: Executa comandos nativos do Sistema Operacional (Shell).
    *   Ex: `BATCH echo "Iniciando..."`.

### Variáveis e Estado
O interpretador mantém um dicionário de estado `self.variables`.
*   **Definição:** `SET count = "0"`
*   **Uso:** `{count}` (Interpolação de string).
*   **Matemática:** `INC count` (Incremento simples).

### Controle de Fluxo
O Maestro suporta estruturas aninhadas através de uma `loop_stack`.
*   **Condicional:**
    ```dox
    IF RESULTADO CONTAINS "ERRO"
        PRINT-RED "Falha detectada!"
    ELSE
        PRINT-GREEN "Sucesso."
    END
    ```
*   **Iteração:**
    ```dox
    READ_LINES lista.txt -> ITENS
    FOR item IN ITENS
        PRINT "Processando {item}..."
    END
    ```

---

## 3. Arquitetura do Interpretador

O núcleo é a classe `MaestroInterpreter` em `maestro.py`.

### O Loop de Execução (The Game Loop)
Diferente de um compilador, o Maestro é um interpretador de estado.
1.  **Instruction Pointer (`self.ip`):** Aponta para a linha atual.
2.  **Parsing:** Lê a linha, resolve variáveis (`{var}`) via regex.
3.  **Dispatch:** Identifica o comando (`IF`, `RUN`, `SET`) e executa a lógica.
4.  **Controle de Bloco:**
    *   Se um `IF` for falso, o interpretador chama `_skip_block()`, que avança o `ip` ignorando instruções até encontrar o `ELSE` ou `END` correspondente ao nível de aninhamento atual.

---

## 4. Gênese V14: Alta Performance (Fast Mode)

Historicamente (V13), o Maestro processava arquivos grandes linha por linha em Python puro ("User Space"), o que causava lentidão extrema em arquivos com 10k+ linhas.

A **Gênese V14** introduziu primitivas nativas que delegam o "trabalho pesado" para rotinas otimizadas, evitando loops explícitos no script `.dox`.

### Comandos Nativos
Estes comandos substituem blocos complexos `FOR/IF` por uma única instrução de alta velocidade:

1.  **`FIND_LINE_NUMBER "texto" IN arquivo -> VAR`**
    *   Realiza uma varredura de arquivo em Python de baixo nível.
    *   Retorna o índice da linha instantaneamente.
    *   Substitui: Ler arquivo -> Loop for -> If contains -> Break.

2.  **`DELETE_BLOCK_TREE AT {LINHA} IN arquivo`**
    *   Lógica especializada para estruturas de árvore (como a saída do comando `tree` ou json indentado).
    *   Remove a linha alvo e todas as linhas subsequentes que possuem indentação maior (filhos).
    *   Permite "poda" cirúrgica de arquivos de log ou relatórios massivos em milissegundos.

---

## 5. Casos de Uso Típicos

### A. Integração Contínua Local (CI)
Scripts que rodam antes do commit para garantir qualidade.
*   Executa testes (`RUN doxoade regression-test`).
*   Verifica cobertura.
*   Bloqueia o processo se houver falhas (`IF FALHA... BATCH exit 1`).

### B. Manutenção de Logs e Árvores
Uso do Fast Mode para limpar arquivos de relatório (`arvore.txt`) removendo pastas irrelevantes (`.git`, `__pycache__`) antes de serem salvos na documentação.

### C. Testes de Integração
O Maestro é usado para testar o próprio Doxoade (Dogfooding). Um script `.dox` pode criar arquivos Python temporários, rodar o `doxoade check` neles e verificar se a saída contém o erro esperado, validando o comportamento da ferramenta de fora para dentro.

---