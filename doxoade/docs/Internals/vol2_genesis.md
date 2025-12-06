# Doxoade Internals - Vol. 2: O Motor Gênese

**Versão do Documento:** 1.0 (Gênese V14)
**Data:** 01/12/2025
**Módulo:** `learning.py`, `save.py`, `database.py`

## 1. O Conceito Gênese

A **Gênese** é a arquitetura de inteligência artificial simbólica (não-generativa) do Doxoade. Enquanto ferramentas comuns usam regras fixas, a Gênese evolui observando como o desenvolvedor resolve problemas.

O objetivo não é apenas "consertar", mas **abstrair soluções** para que um erro corrigido hoje seja um erro prevenido (ou corrigido automaticamente) amanhã.

### A Escala Evolutiva
O motor passou por vários estágios de desenvolvimento (registrados nas Knowledge Notes):
*   **V2 (Risco):** Aprendizado rígido baseado em Regex.
*   **V3 (Abdução):** Capacidade de inferir o que falta (ex: *imports*), não apenas corrigir o que está lá.
*   **V4 (Antifragilidade):** Integração de erros de Runtime (`run`) ao banco de aprendizado.
*   **V8 (Indução Flexível):** Capacidade de generalizar Diffs (transformar `del x` em `REMOVE_LINE`).
*   **V9 (Convergência):** Unificação de falhas estáticas e dinâmicas no mesmo fluxo.

---

## 2. O Ciclo de Aprendizado (The Learning Loop)

O aprendizado ocorre de forma assíncrona, acionado principalmente pelo comando `doxoade save`.

### Passo 1: O Registro da Falha (`open_incidents`)
Quando `check` ou `run` encontram um erro, eles o registram na tabela `open_incidents` com:
*   `finding_hash`: Identificador único do erro (Arquivo + Linha + Mensagem).
*   `message`: O erro bruto (ex: `undefined name 'json'`).
*   `category`: O tipo (ex: `RUNTIME-RISK`, `DEADCODE`).

### Passo 2: A Resolução Humana
O desenvolvedor corrige o arquivo (manualmente ou via `--fix`). O arquivo é salvo no disco e adicionado ao *staging area* do Git.

### Passo 3: O Momento da Captura (`save.py`)
Ao rodar `doxoade save "mensagem"`, o sistema:
1.  Verifica quais arquivos estão sendo comitados.
2.  Cruza com a tabela `open_incidents`.
3.  Se um arquivo tinha incidentes abertos que **desapareceram** na nova versão, o sistema entende que houve uma **Solução**.

### Passo 4: Abstração e Indução (`learning.py`)
O sistema compara o "Antes" (registrado no incidente) com o "Depois" (conteúdo atual).
1.  **Extração de Diff:** O que mudou? (ex: Foi adicionada a linha `import json`).
2.  **Generalização:** O sistema substitui termos específicos por placeholders.
    *   Concreto: `undefined name 'json'` -> Solução: `import json`
    *   Abstrato: `undefined name '<VAR>'` -> Solução: `ADD_IMPORT_OR_DEFINE`
3.  **Persistência:** A regra é salva em `solution_templates`.

---

## 3. Mecanismos de Inteligência

### A. Abdução (Inferência de Dependências)
Localizada em `check.py` (`_analyze_dependencies`).
Diferente da indução (que aprende com o passado), a abdução tenta adivinhar o presente.
*   **Lógica:** Se o erro é `undefined name 'Fore'` e o sistema sabe (via sua base interna `ALL_KNOWN_MODULES`) que `Fore` pertence ao pacote `colorama`.
*   **Ação:** Sugere proativamente: `from colorama import Fore`.

### B. Antifragilidade (Mineração de Runtime)
Localizada em `run.py` e `shared_tools.py` (`_mine_traceback`).
Resolve o "Paradoxo do Aprendizado Cego". Erros que só acontecem rodando (ex: `ZeroDivisionError`) não aparecem no linter estático.
*   **Mecanismo:** O comando `run` captura o `stderr` do processo filho.
*   **Mineração:** Regex extrai Arquivo, Linha e Tipo de Erro do traceback Python.
*   **Convergência:** Esses dados são injetados no DB como se fossem erros de linter, permitindo que o sistema aprenda com crashes reais.

---

## 4. Esquema de Memória (Database)

A inteligência reside nas relações entre estas tabelas SQLite:

### `open_incidents` (Dívida Técnica Atual)
| Coluna | Descrição |
| :--- | :--- |
| `finding_hash` | ID único do problema. |
| `message` | Mensagem de erro original. |
| `file_path` | Onde está o erro. |
| `category` | Categoria para agrupamento de templates. |

### `solutions` (Histórico Bruto)
| Coluna | Descrição |
| :--- | :--- |
| `finding_hash` | ID do problema resolvido. |
| `stable_content` | O código **após** a correção (O "Estado Desejado"). |
| `commit_hash` | Em qual commit isso foi resolvido. |

### `solution_templates` (Conhecimento Refinado)
| Coluna | Descrição |
| :--- | :--- |
| `problem_pattern` | Regex do problema (ex: `undefined name '<VAR>'`). |
| `solution_template` | Ação abstrata (ex: `REPLACE_WITH_UNDERSCORE`). |
| `confidence` | Pontuação. Aumenta cada vez que o template funciona. |
| `diff_pattern` | (V14) Instruções precisas de edição para o `fixer.py`. |

---

## 5. Princípios de Segurança do Motor

1.  **Lei da Reversibilidade:** O Autofix (consumidor da Gênese) nunca deleta código permanentemente. Ele usa templates como `REMOVE_LINE` que, na verdade, comentam a linha (`# [DOX-UNUSED]`).
2.  **Confiança Incremental:** Templates novos começam com `confidence = 1`. Apenas templates com alta confiança são aplicados automaticamente.
3.  **Isolamento de Contexto:** O aprendizado de um projeto (`project_path`) pode influenciar a base global, mas os incidentes são isolados por projeto para evitar contaminação cruzada de regras específicas.

---