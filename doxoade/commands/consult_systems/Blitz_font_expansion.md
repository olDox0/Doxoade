# 📋 BLITZPLAN — Indexação Soberana: Núcleo Python (Fase 1)

**Documento:** `doxoade/docs/Blitzplans/Blitzplan_Consult_Python_v1.md`  
**Conformidade:** `ProDeNov.md` (Itens 1.0 a 1.4, 2.1 e 5.6)  
**Subsistemas:** `Thoth` (Conhecimento e AST) / `Hades` (Persistência FTS5) / `Zeus` (Orquestração CLI)  
**Foco:** **Exclusivamente Python** (Standard Library, Sintaxe, Algoritmos e Idiomas)  
**Status do Doxly:** **Congelado** (o motor de busca e os docks `.lua` permanecem 100% intactos).

---

## 1. Diagnóstico Forense & W5H (ProDeNov §1.1)

| Pergunta | Definição Tática |
| :--- | :--- |
| **O quê? (What)** | Ingestão e indexação offline de um corpus Python de alta precisão (Docs oficiais da Stdlib + Algoritmos canônicos + Cheatsheet de sintaxe moderna). |
| **Onde? (Where)** | No banco SQLite existente `~/.doxoade/consult_docs_fts5.db` na tabela `docs_fts`, consumido pelo CLI `doxoade consult` e renderizado no Doxly/Lite XL sem alterações no frontend. |
| **Por quê? (Why)** | O Python é a espinha dorsal do Doxoade e das ferramentas do desenvolvedor. Validar o pipeline de busca apenas com Python primeiro evita ruído de múltiplos schemas (C, Asm) e garante que o banco fique leve (< 100MB) e ultra-rápido em máquinas modestas. |
| **Como? (How)** | Via ingestão direta de fontes estruturadas (HTML higienizado da documentação oficial e Markdown fatiado), usando streaming HTTP/disco sem clonar históricos `.git`. |
| **Quanto? (Cost/Impact)** | **Espaço em disco:** < 80MB (banco final FTS5 compactado).<br>**RAM em pico de ingestão:** < 120MB (em lotes de 1.000 transações WAL).<br>**Tempo de consulta:** < 15ms por termo. |
| **Quem? (Who)** | Subsistema `Hades` (gravação em lote) e `Thoth` (tokenização e higienização de texto). |

---

## 2. O Que (What — O Corpus de Conhecimento Python)

Para a Fase 1, limitamos a base em **3 camadas complementares**, eliminando redundâncias:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      CORPUS PYTHON FASE 1 (< 80MB)                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌──────────────────┐      ┌──────────────────┐       ┌──────────────────┐
│  CAMADA 1: STDLIB│      │CAMADA 2: SYNTAX  │       │CAMADA 3: ALGO    │
│  (Contrato Oficial)     │ (Cheatsheet/Guia)│       │ (Como Implementar)
├──────────────────┤      ├──────────────────┤       ├──────────────────┤
│ • Biblioteca CPython    │ • python-cheatsheet      │ • TheAlgorithms  │
│ • Built-ins & Tipos     │ • Idiomas Python 3.12+   │   (Python puro)  │
│ • asyncio, socket, os   │ • Type Hints, Decors,    │ • Estruturas de  │
│ • ctypes, sys, gc       │   Context Managers       │   dados e grafos │
└──────────────────┘      └──────────────────┘       └──────────────────┘
```

1. **Camada 1 — Referência Oficial CPython (Stdlib & Built-ins):**
   * *Origem:* Pacote oficial HTML compactado do CPython (apenas as seções `library/`, `reference/` e `c-api/` básica).
   * *Propósito:* Resposta definitiva sobre argumentos de funções, exceções lançadas e comportamento nativo.
2. **Camada 2 — Dicionário de Sintaxe Rápida (Python Cheatsheet):**
   * *Origem:* Repositório `gto76/python-cheatsheet` (Markdown).
   * *Propósito:* Snippets rápidos e práticos para consulta imediata no painel lateral do Doxly durante a codificação.
3. **Camada 3 — Algoritmos Canônicos (TheAlgorithms/Python):**
   * *Origem:* Seleção cirúrgica de `sorts/`, `data_structures/`, `searches/` e `maths/`.
   * *Propósito:* Exemplos reais de implementação para consulta de lógica pura sem internet.

---

## 3. Onde (Where — Topologia e Armazenamento)

* **Diretório Temporário de Extração:**  
  `~/.doxoade/consult/cache/python/` (usado apenas durante o download/descompactação e purgado logo em seguida).
* **Banco de Dados FTS5 (Persistência Hades):**  
  `~/.doxoade/consult_docs_fts5.db`  
  * Tabela virtual FTS5: `docs_fts(path UNINDEXED, title, content, tokenize='porter unicode61')`
* **Padronização da Coluna `path`:**  
  Para manter o resultado limpo no dock do Doxly, cada registro seguirá uma URI semântica:
  * `python/stdlib/asyncio.events`
  * `python/syntax/context_managers`
  * `python/algo/data_structures/binary_tree`

---

## 4. Como (How — Pipeline de Ingestão)

Para evitar consumo excessivo de memória RAM em máquinas como o Celeron N2808:

1. **Download em Stream (Zero Git Clone):**
   * Em vez de `git clone` (que baixa centenas de megabytes de `.git`), o sistema fará o download do arquivo `.zip`/tarball do release limpo ou via API direta do GitHub/Python.org.
2. **Parser Incremental de Chunks:**
   * Páginas HTML gigantescas (como `asyncio.html`) não são jogadas como um bloco monolítico.
   * O parser fatia por cabeçalhos `<h1>`, `<h2>` e blocos `<dl><dt>` (definições de funções/classes). Cada função vira um documento autônomo no FTS5.
   * *Benefício no Doxly:* Quando você pesquisar `create_task`, o snippet mostrará exatamente a assinatura de `asyncio.create_task()` e sua descrição, e não uma página genérica de 200KB.
3. **Comando de Invocação:**
   Criaremos uma receita de ingestão acionável em uma única linha:
   ```bash
   doxoade consult ingest --preset python-core
   ```

---

## 5. Por Quê (Why — Vantagens Táticas Desta Abordagem)

1. **Anti-Fragmentação:** Começar por C ou Assembly agora forçaria a lidar com manpages do GCC, headers POSIX e sintaxes de compilador antes de consolidar a granularidade do banco.
2. **Impacto Imediato no Doxly:** O desenvolvedor ganha instantaneamente um "Copilot Offline" para Python: abriu o Doxly, apertou a tecla de busca do dock, e a biblioteca inteira do Python 3.12 está disponível com busca instantânea.
3. **Blindagem de Memória:** Mantém a promessa do ProDeNov de rodar com conforto em 4GB de RAM sem concorrer com a execução dos scripts.

---

## 6. Plano de Ação em 3 Fases (Tasklist)

```
[Fase 1: Coleta & Higienização]
   ├── T1.1: Baixar e extrair o HTML da documentação oficial Python (stdlib) sem o .git.
   ├── T1.2: Baixar os Markdowns do python-cheatsheet e pastas selecionadas do TheAlgorithms.
   └── T1.3: Higienizar tags HTML e converter tabelas para texto limpo/Markdown.

[Fase 2: Fatiamento & Ingestão no Hades]
   ├── T2.1: Implementar o chunker por símbolo (fatiar por classe/função).
   ├── T2.2: Gravar no SQLite em lotes de 1.000 entradas com PRAGMA synchronous = OFF temporário.
   └── T2.3: Executar 'optimize' no índice FTS5 ao final do processo.

[Fase 3: Teste de Fogo no Terminal e no Doxly]
   ├── T3.1: Teste CLI: 'doxoade consult search "socket non-blocking"'.
   ├── T3.2: Teste CLI: 'doxoade consult read python/stdlib/json'.
   └── T3.3: Abrir o Doxly e verificar a renderização visual nos docks Lua (08_pot_panel e 18_search_results_dock).
```

---

### 1. Fontes Essenciais (O "Contrato" da Linguagem)

#### Fonte 1.1: Documentação Oficial CPython (Stdlib + Language Reference)
* **O que extrair:**
  * `Doc/library/*.html` (Toda a biblioteca padrão: `asyncio`, `socket`, `ctypes`, `threading`, `multiprocessing`, `sqlite3`, `struct`, `os`, `sys`, etc.).
  * `Doc/reference/*.html` (Modelo de dados, métodos mágicos dunder `__enter__`, `__exit__`, `__getitem__`, execução de bytecode).
* **Por que é vital:** É a fonte primária e incontestável para quem está criando ferramentas de sistema (como o próprio Doxoade).
* **Tamanho bruto:** ~15 MB compactado (.zip) / ~45 MB HTML puro.
* **Tamanho no FTS5:** ~25 a 30 MB (após remover cabeçalhos/rodapés/tags visuais e fatiar por função).
* **Como obter sem Git:** Download direto do arquivo HTML distribuído oficialmente pela PSF:
  `https://docs.python.org/3/archives/python-3.12.8-docs-html.zip` (ou versão estável alvo).

---

#### Fonte 1.2: Python Cheatsheet Completo (`gto76/python-cheatsheet`)
* **O que extrair:** O arquivo único em Markdown com cheatsheet abrangente cobrindo:
  * Geradores, Decorators, Context Managers, Metaclasses.
  * Regex avançado, Manipulação de Bytes (`bytes`, `bytearray`, `memoryview`).
  * `dataclasses`, `typing` (Generics, TypeVar, Protocol), `itertools`, `functools`.
* **Por que é vital:** Dá respostas instantâneas de 3 a 10 linhas. Se você estiver no Doxly e esquecer como tipar um `@contextmanager` ou como usar `struct.unpack`, a resposta vem no primeiro snippet sem você ter que ler 3 páginas de documentação.
* **Tamanho bruto:** ~250 KB (Markdown puro).
* **Tamanho no FTS5:** ~300 KB.
* **Como obter:** Raw direto do GitHub via HTTP GET.

---

### 2. Fontes Práticas de Engenharia (O "Como Implementar")

#### Fonte 2.1: TheAlgorithms / Python (Seleção Cirúrgica)
* **O que extrair:** **Apenas** os diretórios de estruturas e algoritmos fundamentais:
  * `data_structures/` (Árvores AVL/B-Tree, Heap/Priority Queue, Ring Buffer, Trie, Grafos).
  * `searches/` e `sorts/` (Busca binária, ordenações fundamentais).
  * `ciphers/` e `hashes/` (Lógicas de checksum, sha256 puro, xor).
* **Por que é vital:** No desenvolvimento offline de ferramentas ou compiladores, muitas vezes você precisa implementar uma fila circular com lock ou uma árvore de busca sem poder rodar `pip install`.
* **Tamanho bruto:** ~4 MB (somente os arquivos `.py` dessas pastas, sem históricos e sem testes pesados).
* **Tamanho no FTS5:** ~5 MB (código limpo com docstrings).
* **Como obter:** Download do ZIP da tag principal do repositório, filtrando apenas as pastas de interesse durante a extração.

---

### 3. Fontes Opcionais / Para Avaliarmos

#### Opção A: Documentação de Bibliotecas do Ecossistema Doxoade
O Doxoade usa fortemente três bibliotecas externas fundamentais em seu ecossistema:
1. `Click` (CLI / Argument parsing).
2. `Rich` (Renderização de terminal, tabelas, progress bars).
3. `Pytest` (Testes e assertivas).

> **Pergunta:** Vale a pena incluir a documentação de referência dessas 3 bibliotecas já nesta Fase 1, ou mantemos estritamente a biblioteca padrão do Python?
> *Impacto:* Acrescentaria apenas ~5 a 8 MB ao banco.

#### Opção B: PEPs Fundamentais (Python Enhancement Proposals)
Não baixar todas as 700 PEPs, mas incluir apenas as que definem a arquitetura do Python moderno:
* PEP 8 (Style Guide), PEP 257 (Docstrings).
* PEP 484 / 526 / 544 (Type Hints & Protocols).
* PEP 572 (Assignment Expressions `:=`).
* PEP 634 / 635 / 636 (Structural Pattern Matching).

---

### 4. O que Recomendo Descartar na Fase 1 (Evitar Inchaço)

1. **Livros para Iniciantes ("A Byte of Python", "Automate the Boring Stuff"):**
   * *Motivo:* Focam em conceitos elementares (*o que é print*, *o que é if/else*), que geram falso-positivos em buscas avançadas e não agregam valor a quem está arquitetando sistemas.
2. **CodeSearchNet / The Stack:**
   * *Motivo:* São datasets na casa de gigabytes/terabytes voltados para treinar redes neurais do zero. Tentar colocar isso no SQLite FTS5 de uma máquina modesta vai travar a indexação e estourar o disco.
3. **PEPs históricas ou rejeitadas:**
   * *Motivo:* Discussões de 2003 sobre sintaxes obsoletas que só ocupam espaço.

---

### Proposta de Fechamento da Lista (Fase 1)

Se você concordar, nosso "pacote ouro" da Fase 1 terá:

| # | Fonte | Formato de Origem | Volume FTS5 Estimado |
|---|---|---|---|
| **1** | **CPython 3.12+ Stdlib & Reference** | HTML Oficial (Docs PSF) | ~30 MB |
| **2** | **Python Cheatsheet** | Markdown | ~0.3 MB |
| **3** | **TheAlgorithms (Estruturas & Algoritmos Core)** | Arquivos `.py` selecionados | ~5 MB |
| **4** | *(Opcional)* **Click + Rich Docs** | HTML/Markdown | ~5 MB |
| **Total** | | | **~35 a 40 MB** |

---


### Fase 1: Chunker de Markdown e Ingestão do Cheatsheet (Fonte 1.2)

O objetivo desta fase é ensinar o `consult` a fatiar documentos Markdown estruturados.

* **O que construir:**
  * Um parser de seções Markdown no `dataset_ingestor.py` que reconhece cabeçalhos (`#`, `##`, `###`).
  * Em vez de tentar ler JSON, ele detecta se a fonte é `.md` ou Markdown.
  * Cada tópico do cheatsheet (ex: *Decorators*, *Generators*, *Itertools*, *Dataclasses*, *Context Managers*) se torna um registro independente no `docs_fts`.
* **Identificação na busca:**
  * `path`: `python/cheatsheet/<secao>` (ex: `python/cheatsheet/context_managers`)
  * `title`: `Python Cheatsheet — Context Managers`
  * `content`: o código e explicação do bloco.
* **Critério de Sucesso:**
  * Executar `doxoade consult ingest cheatsheet`.
  * Rodar `doxoade consult search "lru_cache"` ou `"dataclass"` e ver o snippet pronto com exemplo.

---

### Fase 2: Coleta e Parser de Código Python Puro (TheAlgorithms)

O objetivo desta fase é ingerir implementações canônicas de algoritmos sem clonar o repositório Git inteiro.

* **O que construir:**
  * Um extrator de arquivos `.py` direcionado (via download de arquivo ZIP do branch principal ou tarball).
  * Filtro estrito de pastas para não inchar o banco:
    * `data_structures/` (árvores, heaps, filas, grafos, buffers).
    * `searches/` e `sorts/` (busca binária, ordenações clássicas).
    * `ciphers/` e `hashes/` (implementações puras de hashing/criptografia).
  * Um parser de módulos `.py` que extrai:
    * O nome do arquivo/módulo como título.
    * A docstring do topo como resumo.
    * As funções/classes com suas assinaturas e lógica.
* **Identificação na busca:**
  * `path`: `python/algorithms/data_structures/trie`
  * `title`: `Algoritmo: Trie (Prefix Tree)`
* **Critério de Sucesso:**
  * Executar `doxoade consult ingest algorithms`.
  * Rodar `doxoade consult search "binary search tree"` e ver a implementação funcional.

---

### Fase 3: Orquestração e Presets no CLI (`cmd_consult.py`)

Unificar o pipeline para que o desenvolvedor (ou uma nova máquina clonada) sincronize tudo com facilidade.

* **Comandos integrados:**
  ```bash
  # Ingestão granular
  doxoade consult ingest cheatsheet
  doxoade consult ingest algorithms

  # Ingestão de todo o pacote da Fase 1
  doxoade consult ingest --preset python-core
  ```
* **Otimização Hades ao final:**
  * Disparo automático de `INSERT INTO docs_fts(docs_fts) VALUES('optimize');` para compactar os segmentos FTS5 e reconstruir os índices WAL.

---

### Fase 4: Teste de Integridade & Validação Doxly (Zero Impacto Visual)

Garantir que a ingestão não quebre a experiência do Doxly/Lite XL:

1. **Validação do Output Lua:**
   * Testar `doxoade consult search --lua "asyncio"` e verificar se o JSON/Lua gerado bate perfeitamente com o esperado pelo `18_search_results_dock.lua`.
2. **Validação do Output Markdown:**
   * Testar `doxoade consult search --md "binary search"` e verificar o layout do `08_pot_panel.lua`.
3. **Telemetria com o ShadowProfiler:**
   * Executar com `-P` (`doxoade consult search -P "heap"`) para garantir que o consumo de memória durante as buscas permaneça em patamares baixos (< 25MB) e tempo de busca < 10ms.

---

# 📜 RIT — REGISTRO DE INTENÇÃO TÉCNICA
**Identificador:** `RIT-CONSULT-001`  
**Título:** Motor de Chunking Markdown & Ingestão do Cheatsheet Python  
**Fase:** 1 de 4 (Corpus Soberano Python)  
**Data:** 15/10/2026  
**Subsistemas:** `Thoth` (Chunking & Parsing Semântico) / `Hades` (Persistência FTS5) / `Zeus` (CLI)  
**Conformidade:** `ProDeNov.md` (§1.1, §1.2, §2.1) — Limite de RAM < 120MB, Zero dependências externas  

---

### 1. Diagnóstico da Falha & Motivação

#### Estado Atual
O subsistema `consult` possui o comando `doxoade consult ingest cheatsheet` mapeado para a URL do repositório `gto76/python-cheatsheet` (`README.md`). Contudo, o método `_process_and_index()` em `dataset_ingestor.py` foi construído com a premissa exclusiva de arquivos **JSONL**:

```python
# Trecho atual de dataset_ingestor.py:
for line_num, line in enumerate(f, 1):
    try:
        data = json.loads(line)  # <-- FALHA CRÍTICA: Arquivo .md gera JSONDecodeError em 100% das linhas!
```

#### Consequência
Qualquer tentativa de ingerir documentação em Markdown resulta em `JSONDecodeError` contínuo, descartando todo o conteúdo e deixando o banco vazio (`0 registros adicionados, N linhas inválidas ignoradas`).

---

### 2. Escopo da Intervenção

#### O que ENTRA no escopo:
1. **Detecção Inteligente de Formato:** O `dataset_ingestor.py` identificará se a fonte é **JSONL** (legado mantido) ou **Markdown** (`.md` ou cabeçalhos `#`).
2. **Parser Semântico de Markdown por Chunks:**
   * Fatiamento por cabeçalhos de níveis 2 e 3 (`##` e `###`).
   * Manutenção de blocos de código (` ```python ... ``` `) íntegros dentro de cada seção correspondente.
   * Geração de slugs limpos para a coluna `path` (ex: `python/cheatsheet/context_managers`).
3. **Padronização de Títulos e Metadados:**
   * Título composto: `Python Cheatsheet — <Nome da Seção>`.
4. **Persistência Hades Otimizada:**
   * Gravação em lote (*batch insert*) com transação atômica.
   * Execução de `optimize` no índice FTS5 ao término da ingestão.

#### O que NÃO ENTRA no escopo:
* Alterações no frontend Lua do Doxly (`08_pot_panel.lua` e `18_search_results_dock.lua` permanecem congelados).
* Ingestão de repositórios de algoritmos em C ou `.py` (reservado para a Fase 2 - TheAlgorithms).
* Instalação de bibliotecas externas (parsers como `markdown2` ou `mistune` são **proibidos**; usaremos regex puro da biblioteca padrão).

---

### 3. Design da Arquitetura & Algoritmo Proposto

#### Fluxo do Pipeline (Fase 1):

```
┌───────────────────────────────┐
│  Fonte (Local ou HTTP Stream) │ ➔ https://raw.githubusercontent.com/.../README.md
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│     Format Detector & Read    │ ➔ Identifica se é JSONL ou Markdown
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│      Markdown Chunker         │ ➔ Fatia em seções (H2 / H3)
│   (Regex / State-Machine)     │   Preserva fences ```code```
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│   Tuplas (path, title, body)  │ ➔ path: "python/cheatsheet/regex"
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│  Hades Batch Ingest (FTS5)    │ ➔ docs_fts (INSERT em lote) + PRAGMA WAL
└───────────────────────────────┘
```

#### Regras do Algoritmo de Fatiamento (Chunker):
* **Início de Chunk:** Ocorre ao encontrar `^#{1,3}\s+(.+)`.
* **Slugificação:** O título da seção é convertido para minúsculas, caracteres especiais removidos e espaços substituídos por underscores (ex: `## Context Manager` ➔ `context_manager`).
* **Conteúdo Mínimo:** Seções vazias ou sumários (índices com links do tipo `[TOC]`) são descartados para não sujar o banco de busca.
* **Corpo do Documento:** Contém a explicação teórica daquela seção acompanhada de seus blocos de código de exemplo intactos.

---

### 4. Arquivos Impactados

| Arquivo | Ação | Responsabilidade |
| :--- | :--- | :--- |
| `doxoade/commands/consult_systems/dataset_ingestor.py` | **Refatoração** | Adicionar `_is_markdown()`, `_chunk_markdown()` e bifurcar o processamento no `_process_and_index()`. |
| `doxoade/commands/consult_systems/cmd_consult.py` | **Ajuste Menor** | Garantir que o comando `ingest` aceite presets de forma transparente e acione o profiler de telemetria. |

---

### 5. Critérios de Aceite & Checklist de Homologação (DoD)

- [ ] **CA-1 (Zero Erro de Sintaxe):** O `dataset_ingestor.py` processa o arquivo `README.md` completo do Cheatsheet sem disparar `JSONDecodeError`.
- [ ] **CA-2 (Densidade de Dados):** O banco `consult_docs_fts5.db` recebe entre **30 e 60 seções atômicas** de alta qualidade.
- [ ] **CA-3 (Qualidade de Busca):**
  * `doxoade consult search "dataclass"` retorna o bloco de Dataclasses com snippet de código funcional.
  * `doxoade consult search "lru_cache"` retorna o bloco de Memoization/Decorators.
- [ ] **CA-4 (Compatibilidade Doxly):**
  * `doxoade consult search --lua "context manager"` gera tabela Lua sintaticamente válida.
  * `doxoade consult search --md "decorators"` gera Markdown renderizável no painel lateral.
- [ ] **CA-5 (Anti-Inchaço):** O arquivo de banco não deve crescer mais do que **2 MB** após esta fase.

---

### A Prioridade é o python basico, assim erros comuns de syntax e contratos são resolvidos pelo usuario ou pelo brunnr

- Cat 1. python basico
  * A Byte of Python  * 
  * Automate the Boring Stuff  * 
  * PY4E  * 
  * DevDocs Scraped Reference  * 
  * TheAlgorithms  * 
  * https://github.com/asabeneh/30-days-of-python  * 

- Cat 2. desenvolvimento python avançado
  * Python Design Patterns  * 
  * PEP  * 
  * Cosmic python  * 
  * 30 Seconds of Python  * 
  * Python std libs  * 
  * Typeshed Stdlib Stubs  * 

- Cat 3. automação
  * Click  * 
  * Rich  * 
  * Pytest  * 
  * Unittest  * 

- Cat 4. Outrem
  * https://github.com/Asabeneh/10-days-of-git-and-github  * 
  * https://github.com/fernandofeltrin/PYTHON  * 

---

Sistema de render de markdown e PDF para o litexl.


fontes que podem ser procesadas.

https://github.com/EbookFoundation/free-programming-books/blob/main/books/free-programming-books-pt_BR.md#python
https://github.com/vinta/awesome-python/tree/master

---

dados uteis:

batch(windows)


bash/shell


engenharia reversa


lua


computação e eng. sistemas

https://github.com/codecrafters-io/build-your-own-x
