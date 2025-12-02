---

# Doxoade Internals - Vol. 1: Fundação e Arquitetura

**Versão do Documento:** 1.0 (Gênese V14)
**Data:** 01/12/2025
**Status:** Documentação Viva

## 1. Visão Geral e Filosofia

O **Doxoade** (olDox222 Advanced Development Environment) não é apenas uma CLI de linting; é uma **Plataforma de Engenharia Cognitiva**. Diferente de ferramentas estáticas tradicionais, o Doxoade foi projetado como um "Engenheiro Sênior Automatizado" que opera em um ciclo fechado de melhoria contínua.

### O Ciclo Cognitivo (The Loop)
O sistema opera perpetuamente em quatro estágios:
1.  **Diagnóstico:** Identifica problemas via análise estática, sondas de risco ou execução instrumentada (`check`, `run`).
2.  **Registro:** Persiste o estado "quebrado" no banco de dados (`open_incidents`).
3.  **Resolução:** O usuário (ou o `autofix`) corrige o problema.
4.  **Aprendizado (Gênese):** O sistema detecta que o erro sumiu, analisa o *diff* da correção e gera um template de solução para o futuro.

### Princípios de Engenharia
*   **Protocolo Fênix (Anti-Fragilidade):** O sistema deve ser capaz de diagnosticar e consertar seu próprio ambiente (`doctor`, `global-health`).
*   **Isolamento de Processos (Sondas):** Análises pesadas ou perigosas (como importar código do usuário ou executar scripts) rodam em subprocessos isolados (`probes/`), garantindo que o núcleo nunca trave.
*   **Reversibilidade:** Automações preferem comentar código antigo (`# [DOX-UNUSED]`) a deletá-lo destrutivamente.
*   **Introspecção Total:** A ferramenta deve ser capaz de ler seu próprio código, buscar em sua própria documentação (`pedia`) e diagnosticar a si mesma.

---

## 2. Arquitetura de Componentes

O projeto segue uma arquitetura modular de **Núcleo Orquestrador com Plugins**, facilitando a expansão sem risco de regressão no core.

```text
doxoade/
│
├── cli.py                  # [NÚCLEO] Entry Point.
│                             - Gerencia o Click Group principal.
│                             - Tratamento de exceções globais.
│                             - Telemetria de inicialização.
│
├── database.py             # [PERSISTÊNCIA] Camada de Dados.
│                             - Gerencia o SQLite (~/.doxoade/doxoade.db).
│                             - Executa migrações de schema automáticas.
│
├── shared_tools.py         # [UTILITÁRIOS] A Fonte da Verdade.
│                             - Logger de execução estruturado.
│                             - Análise de AST e Complexidade.
│                             - Integração com Git e Sistema de Arquivos.
│
├── learning.py             # [CÉREBRO] Motor Gênese.
│                             - Abdução (Inferência de imports).
│                             - Indução (Criação de templates via diffs).
│
├── fixer.py                # [MÃOS] Motor de Correção.
│                             - Aplicação cirúrgica de patches no código.
│
├── commands/               # [INTERFACE] Plugins de Comando.
│   ├── check.py            # O Auditor (Pipeline de análise principal).
│   ├── run.py              # O Executor (Instrumentação de runtime).
│   ├── maestro.py          # O Orquestrador (Interpretador de scripts .dox).
│   ├── save.py             # O Guardião (Commit seguro + Aprendizado).
│   └── ... (30+ outros comandos especializados).
│
├── probes/                 # [SENSORES] Sondas Isoladas (Subprocessos).
│   ├── syntax_probe.py     # Fail-Fast para erros de sintaxe.
│   ├── static_probe.py     # Wrapper isolado para Pyflakes.
│   ├── hunter_probe.py     # Análise semântica de riscos e segurança (AST).
│   ├── clone_probe.py      # Detecção de duplicatas (DRY) e normalização.
│   └── flow_runner.py      # Visualizador de execução em tempo real (Matrix).
│
└── docs/
    └── articles.json       # Base de conhecimento estática (Doxoadepédia).
```

---

## 3. Fluxo de Dados Crítico: O Pipeline "Check"

O comando `check` é o coração da análise. Ele não é monolítico, mas sim um pipeline de filtros sucessivos:

1.  **Coleta e Cache:** Identifica arquivos alvo respeitando `.gitignore` e verifica hashes para evitar reprocessamento desnecessário.
2.  **Sonda de Sintaxe (Fast Fail):** Verifica se o arquivo é parseável. Se falhar aqui, aborta análises mais profundas.
3.  **Sonda Estática:** Executa linting tradicional (variáveis não usadas, erros de digitação).
4.  **Sonda de Risco (Hunter):** Analisa a AST em busca de padrões perigosos (ex: `except:` genérico, `eval()`, argumentos mutáveis).
5.  **Sonda DRY (Clone Probe):** Normaliza a estrutura do código (ignorando nomes de variáveis) para detectar lógica duplicada entre arquivos.
6.  **Motor de Abdução:** Cruza erros de "undefined name" com a base de conhecimento de bibliotecas para sugerir imports automaticamente.
7.  **Gestão de Incidentes:**
    *   Novos erros -> Gravados na tabela `open_incidents`.
    *   Erros desaparecidos -> Movidos para a tabela `solutions` para alimentar o aprendizado.

---

## 4. O Ecossistema Maestro

O **Maestro** (`maestro.py`) é um interpretador de linguagem de script dedicado (`.dox`) embutido no Doxoade. Ele permite criar automações complexas que o `bash` ou `bat` não conseguem lidar de forma portável.

**Capacidades:**
*   **Lógica:** Suporta `IF/ELSE`, `FOR loops`.
*   **Alta Performance:** Comandos nativos como `FIND_LINE_NUMBER` e `DELETE_BLOCK_TREE` executam operações em milissegundos, contornando a lentidão de loops interpretados.
*   **Integração:** Pode chamar comandos do SO (`BATCH`) ou comandos internos (`RUN`) e capturar sua saída em variáveis.

---

## 5. Persistência (Memória Sapiens)

O estado do sistema reside em `~/.doxoade/doxoade.db` (SQLite).

**Tabelas Críticas:**
*   `events`: Histórico de execução (telemetria).
*   `findings`: Logs detalhados de problemas encontrados em cada execução.
*   `open_incidents`: O "Backlog de Dívida Técnica". Problemas que existem *agora* no código.
*   `solutions`: O "Histórico de Resolução". O que foi consertado, quando e como.
*   `solution_templates`: O "Conhecimento Abstraído". Regras regex aprendidas para aplicar autofix.

---
