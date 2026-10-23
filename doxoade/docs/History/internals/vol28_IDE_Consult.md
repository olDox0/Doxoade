# 📖 Doxoade Consult — Consultor Offline de Python

**Subsistema:** Thoth (conhecimento) + Hades (persistência FTS5) + Apolo (UX/CLI)
**Status:** ✅ Fase 1–4 concluídas | 🟡 Polish pendente
**Última atualização:** 2026-10-21

---

## Visão Geral

O `doxoade consult` é um consultor offline de documentação Python que combina:

- **Documentação oficial do CPython** (Stdlib + Language Reference + C-API)
- **Livros canônicos** (A Byte of Python, Automate the Boring Stuff, PY4E, 30 Days of Python)
- **Referência rápida** (Python Cheatsheet, Typeshed stubs)
- **Especificações** (PEPs fundamentais: 8, 20, 257, 484, 544, 557, 572, 634–636, 646, 675)
- **Algoritmos** (TheAlgorithms: data_structures, searches, sorts, ciphers, hashes)
- **Arquitetura** (Cosmic Python, Python Design Patterns)
- **Automação** (Click, Rich, Pytest)
- **Versionamento** (10 Days of Git and GitHub)

Tudo armazenado em **SQLite FTS5** com **ranking curado** por categoria de documento.

---

## Corpus Final

| Categoria | Fonte | Docs | Tamanho |
|---|---|---|---|
| **CPython** | Stdlib oficial (3.12.4) | 519 | ~25 MB |
| **Cat 1 (Básico)** | A Byte of Python | 16 | ~180 KB |
| | 30 Days of Python | 30 | ~450 KB |
| | Automate the Boring Stuff (2e) | 21 | ~1 MB |
| | PY4E | 16 | ~380 KB |
| | Python Cheatsheet | 68 | ~150 KB |
| **Cat 2 (Avançado)** | PEPs fundamentais | 18 | ~600 KB |
| | TheAlgorithms (Python) | 265 | ~500 KB |
| | Cosmic Python | 16 | ~300 KB |
| | Python Design Patterns | 40 | ~150 KB |
| | Typeshed stdlib stubs | 644 | ~600 KB |
| **Cat 3 (Automação)** | Click + Rich + Pytest | 39 | ~500 KB |
| **Cat 4 (Git)** | 10 Days of Git | 9 | ~20 KB |
| **TOTAL** | | **1685** | **40.24 MB** |

---

## Pipeline de Ingestão

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 1. DOWNLOAD (converters/*.py)                                            │
│    • Baixa HTML/Markdown/ZIP de fontes externas                           │
│    • Converte HTML → Markdown (reusa html_to_markdown do doc_indexer)     │
│    • Salva em ~/.doxoade/consult/canonical/<fonte>.jsonl                  │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────────────────┐
│ 2. INDEX (doc_indexer.py)                                                │
│    • Lê *.jsonl de canonical/                                             │
│    • Insere em docs (B-Tree) + docs_fts (FTS5)                            │
│    • Aplica snippet de 60 tokens com markers \x02/\x03                    │
│    • Roda PRAGMA optimize no FTS5                                         │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────────────────┐
│ 3. CONSULT (cmd_consult.py + Doxly)                                      │
│    • search: FTS5 com ranking por CASE (PEPs/livros > índices)            │
│    • read: renderiza Markdown com syntax highlight (Rich no CLI, custom no Doxly) │
│    • Doxly: ConsultSearchView + ConsultDocReaderView com tema              │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Comandos CLI

```bash
# Baixar e indexar uma fonte
doxoade consult ingest <fonte>   # peps, typeshed, the_algorithms, automate,
                                  # 30days, py4e, byte_of_python, cheatsheet,
                                  # cosmic, patterns, automation, git
doxoade consult ingest all        # Todas as fontes

# Reconstruir o índice unificado
doxoade consult index -f

# Buscar por palavra-chave
doxoade consult search "walrus operator"
doxoade consult search "Protocol structural subtyping"
doxoade consult search "binary search tree"

# Ler um documento específico
doxoade consult read python/peps/pep_0572
doxoade consult read git/github/day_02
doxoade consult read library/json.html

# Listar palavras reservadas
doxoade consult keywords
doxoade consult symbols
```

---

## Arquitetura de Arquivos

```
doxoade/commands/consult_systems/
├── README.md                        # Este arquivo
├── cmd_consult.py                   # CLI (Zeus)
├── doc_indexer.py                   # Ingestão + FTS5 + Markdown renderer (Hades)
├── consult_engine.py                # pydoc bridge (Dionísio)
├── consult_renderer.py              # Rich renderer CLI (Dionísio)
├── canonical_db.py                  # Schema SQLite (Hades)
├── dataset_ingestor.py              # Legacy JSONL ingestor
├── converters/
│   ├── base_converter.py            # Classe base (HTTP + JSONL)
│   ├── peps_converter.py            # PEPs (Thoth)
│   ├── the_algorithms_converter.py  # TheAlgorithms (Thoth)
│   ├── typeshed_converter.py        # Typeshed stubs (Thoth)
│   ├── cosmic_python_converter.py   # Cosmic Python (Thoth)
│   ├── design_patterns_converter.py # faif/python-patterns (Thoth)
│   ├── click_rich_pytest_converter.py # Cat 3 (Thoth)
│   ├── git_github_converter.py      # Cat 4 (Thoth)
│   ├── automate_boring_stuff_converter.py
│   ├── byte_of_python_converter.py
│   ├── thirty_days_converter.py
│   └── py4e_converter.py
└── cheatsheet_converter.py          # Legacy (registry shim)
```

---

## Banco de Dados

Localização: `~/.doxoade/consult_docs_fts5.db`

```sql
CREATE TABLE docs (
    path TEXT PRIMARY KEY,
    category TEXT,
    title TEXT,
    keywords TEXT,
    content TEXT
);

CREATE VIRTUAL TABLE docs_fts USING fts5(
    path UNINDEXED,
    title,
    keywords,
    content,
    tokenize='porter unicode61'
);

CREATE TABLE doc_metadata (
    path TEXT PRIMARY KEY,
    last_modified REAL
);
```

### Ranking Curado

O `search()` aplica `CASE` para priorizar fontes didáticas sobre metadados:

| Tier | Fonte | Exemplo |
|---|---|---|
| 0 | PEPs, livros, algoritmos, arquitetura, patterns | `python/peps/*`, `python/basic/*` |
| 1 | Typeshed, cheatsheet | `python/typeshed/*`, `python/cheatsheet/*` |
| 2 | CPython tutorial/library/howto | `tutorial/*`, `library/*`, `howto/*` |
| 3 | CPython reference, c-api | `reference/*`, `c-api/*` |
| 5 | CPython misc | Fallback |
| 7 | FAQ | `faq/*` |
| 8 | Guias de uso | `using/*` |
| 9 | Metadados, índices, changelogs | `genindex-*`, `whatsnew-*`, `contents.html` |

---

## Integração com Doxly

O Doxly usa dois componentes Lua:

- **`18_search_results_dock.lua`**: painel de resultados com destaque de hits (`\x02`/`\x03`) e snippet de 60 tokens.
- **`08_pot_panel.lua`**: `ConsultSearchView` (cards) + `ConsultDocReaderView` (leitor Markdown com headers coloridos, inline code, syntax highlight).

### Fluxo Doxly → Python

1. Usuário digita query → `execute_docs_search_interactive()` gera `run_consult.py` inline.
2. `system.exec(python run_consult.py)` → Python lê FTS5 e escreve `consult_search.lua`.
3. Lua `dofile()` → `open_in_right_panel(ConsultSearchView(query, data))`.
4. Usuário clica card → `open_selected()` gera `run_read.py` inline.
5. `system.exec(python run_read.py)` → Python lê `docs.content` e escreve `consult_active_doc.md`.
6. `core.add_thread` poll até o `.md` existir → cria `ConsultDocReaderView(md_lines)`.

---

## Bugs Conhecidos (Polish Pendente)

| ID | Problema | Onde | Prioridade |
|---|---|---|---|
| **P1** | Menu "Skip to content / Light mode" do Furo aparece nos docs do Pytest. | `click_rich_pytest_converter.py` | Média |
| **P2** | 4 páginas do Rich falharam no download (`table.html`, `protocols.html`, `highlighter.html`, `json.html`). | `click_rich_pytest_converter.py` | Baixa |
| **P3** | `pty_file_daemon.py` falha sem Admin (produção roda Admin, OK). | `pty_file_daemon.py` | Baixa |
| **P4** | Imagens quebradas (`![](./images/...)`) nos docs do Git. | Cosmético | Baixa |
| **P5** | `consult read "git/day_02"` retorna vazio (Doxly já resolve via fallback LIKE). | `doc_indexer.py` | Baixa |

---

## Como Contribuir

### Adicionar nova fonte

1. Criar `converters/<nome>_converter.py` herdando `BaseCanonicalConverter`.
2. Implementar `convert(source_url) -> Path`.
3. Registrar em `cmd_consult._get_converter_registry()`.
4. Rodar `doxoade consult ingest <nome>` + `doxoade consult index -f`.
5. Atualizar este README na seção "Corpus Final".

### Regenerar índice completo

```bash
doxoade consult ingest all
doxoade consult index -f
```

### Verificar integridade

```bash
# Contagem
doxoade consult search "def" | head -5

# Ranking (top-3 deve ser PEP/livro)
doxoade consult search "walrus operator"
```

---

## Referências

- `Blitzplan_Consult_Python_v1.md` — plano original da Fase 1
- `doxly_tree.py` — catálogo de falhas (para o Phanto Crisis)
- `prodenov.md` — protocolo de desenvolvimento

---

**Status final:** Consult 100% funcional para uso em produção. Corpus de 1685 documentos indexados, busca com ranking curado, leitor Markdown com syntax highlight no CLI e no Doxly.
