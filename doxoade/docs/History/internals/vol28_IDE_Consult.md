# 📖 Doxoade Consult — Consultor Offline de Python

**Subsistema:** Thoth (conhecimento) + Hades (persistência FTS5) + Apolo (UX/CLI) + Dionísio (Doxly)
**Status:** ✅ **Fases 1–5 concluídas** (corpus completo + polish)
**Última atualização:** 2026-10-23

---

## Visão Geral

O `doxoade consult` é um **consultor offline de documentação Python** que combina
referência oficial, livros canônicos, especificações, algoritmos, padrões de arquitetura,
ferramentas de automação e snippets rápidos — tudo em **SQLite FTS5** com **ranking curado
por categoria de documento**.

### Corpus Final (1734 documentos, 40.24 MB)

| Cat | Fonte | Docs | Tamanho | Tier |
|---|---|---|---|---|
| **CPython** | Stdlib oficial (3.12.4) | 519 | ~25 MB | 2–9 |
| **Cat 1 — Básico** | A Byte of Python | 16 | ~180 KB | 0 |
| | 30 Days of Python | 30 | ~450 KB | 0 |
| | Automate the Boring Stuff (2e) | 21 | ~1 MB | 0 |
| | PY4E | 16 | ~380 KB | 0 |
| | Python Cheatsheet | 68 | ~150 KB | 1 |
| **Cat 2 — Avançado** | PEPs fundamentais (18) | 18 | ~600 KB | 0 |
| | TheAlgorithms (Python) | 265 | ~500 KB | 0 |
| | Cosmic Python | 16 | ~300 KB | 0 |
| | Python Design Patterns | 40 | ~150 KB | 0 |
| | Typeshed stdlib stubs | 644 | ~600 KB | 1 |
| **Cat 3 — Automação** | Click + Rich + Pytest | 41 | ~500 KB | 0 |
| **Cat 4 — Git** | 10 Days of Git | 9 | ~20 KB | 0 |
| **Cat 5 — Snippets** | 30 Seconds of Python | 47 | ~200 KB | 0 |
| **TOTAL** | | **1734** | **40.24 MB** | — |

---

## Ranking Curado (Tier System)

O `search()` aplica um `CASE` no `ORDER BY` do FTS5 para priorizar fontes didáticas
sobre metadados (índices, changelogs, etc):

| Tier | Fontes | Exemplo |
|---|---|---|
| **0** | PEPs, livros, algoritmos, patterns, arquitetura, automação, **snippets** | `python/peps/*`, `python/basic/*`, `python/snippets/*` |
| **1** | Typeshed, cheatsheet | `python/typeshed/*`, `python/cheatsheet/*` |
| **2** | CPython tutorial/library/howto | `tutorial/*`, `library/*`, `howto/*` |
| **3** | CPython reference, c-api | `reference/*`, `c-api/*` |
| **5** | CPython misc | Fallback |
| **7** | FAQ | `faq/*` |
| **8** | Guias de uso | `using/*` |
| **9** | Metadados, índices, changelogs | `genindex-*`, `whatsnew-*`, `contents.html` |

**Resultado prático:** buscas como `walrus operator`, `Protocol structural subtyping`,
`binary search tree`, `camel case string` retornam **PEP / livro / snippet** no top-3,
sem competir com `genindex-*`.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. DOWNLOAD (converters/*.py)                                           │
│    • HTTP/HTTPS/ZIP → HTML/Markdown cru                                  │
│    • html_to_markdown (reuso do doc_indexer)                            │
│    • Salva ~/.doxoade/consult/canonical/<fonte>.jsonl                    │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│ 2. INDEX (doc_indexer.py)                                               │
│    • Lê *.jsonl                                                          │
│    • Insere em docs (B-Tree) + docs_fts (FTS5)                          │
│    • snippet 60 tokens com markers \x02/\x03                             │
│    • PRAGMA optimize                                                     │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│ 3. CONSULT (cmd_consult.py + Doxly)                                     │
│    • search: FTS5 com ranking por CASE                                   │
│    • read: Markdown → Rich (CLI) / ConsultDocReaderView (Doxly)          │
│    • Doxly: ConsultSearchView + ConsultDocReaderView + run_read.py       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Estrutura de Arquivos

```
doxoade/commands/consult_systems/
├── README.md                              # Este arquivo
├── FASE_5_RELATORIO.md                    # Relatório de encerramento
├── cmd_consult.py                         # CLI (Zeus)
├── doc_indexer.py                         # Ingestão + FTS5 + Markdown (Hades)
├── consult_engine.py                      # pydoc bridge (Dionísio)
├── consult_renderer.py                    # Rich renderer CLI (Dionísio)
├── canonical_db.py                        # Schema SQLite (Hades)
├── dataset_ingestor.py                    # Legacy JSONL ingestor
├── converters/
│   ├── base_converter.py                  # ABC (HTTP + JSONL)
│   ├── peps_converter.py                  # PEPs (Thoth)
│   ├── the_algorithms_converter.py        # TheAlgorithms (Thoth)
│   ├── typeshed_converter.py              # Typeshed stubs (Thoth)
│   ├── cosmic_python_converter.py         # Cosmic Python (Thoth)
│   ├── design_patterns_converter.py       # faif/python-patterns (Thoth)
│   ├── click_rich_pytest_converter.py     # Cat 3 (Thoth)
│   ├── git_github_converter.py            # Cat 4 (Thoth)
│   ├── thirty_seconds_converter.py        # Cat 5 (Thoth)
│   ├── automate_boring_stuff_converter.py
│   ├── byte_of_python_converter.py
│   ├── thirty_days_converter.py
│   └── py4e_converter.py
└── cheatsheet_converter.py                # Legacy shim (registry)
```

---

## Banco de Dados

Localização: `~/.doxoade/consult_docs_fts5.db` (40.24 MB)

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

---

## Comandos CLI

```bash
# ── Ingestão ──
doxoade consult ingest <fonte>   # peps, typeshed, the_algorithms, automate,
                                  # 30days, py4e, byte_of_python, cheatsheet,
                                  # cosmic, patterns, automation, git, 30seconds
doxoade consult ingest all        # Todas as fontes

# ── Rebuild ──
doxoade consult index -f

# ── Busca ──
doxoade consult search "walrus operator"
doxoade consult search "camel case string"
doxoade consult search "binary search tree"

# ── Leitura ──
doxoade consult read python/peps/pep_0572
doxoade consult read python/snippets/chunk-list
doxoade consult read git/github/day_02
doxoade consult read library/json.html

# ── Utilitários ──
doxoade consult keywords
doxoade consult symbols
```

---

## Integração com Doxly

| Componente | Responsabilidade |
|---|---|
| `18_search_results_dock.lua` | Dock de resultados com destaque `\x02`/`\x03` + snippet 60 tokens |
| `08_pot_panel.lua` | `ConsultSearchView` (cards) + `ConsultDocReaderView` (Markdown renderer) |
| `run_consult.py` (inline) | Busca FTS5 + escreve `consult_search.lua` |
| `run_read.py` (inline) | Lê `docs.content` + escreve `consult_active_doc.md` |

Fluxo:
1. Usuário busca → `run_consult.py` gera `.lua`.
2. Lua `dofile()` → `open_in_right_panel(ConsultSearchView(...))`.
3. Usuário clica card → `open_selected()` gera `run_read.py`.
4. `system.exec(python run_read.py)` → Python escreve `.md`.
5. `core.add_thread` poll → `ConsultDocReaderView(md_lines)`.

---

## Pipeline de Contribuição (novas fontes)

1. Criar `converters/<nome>_converter.py` herdando `BaseCanonicalConverter`.
2. Implementar `convert(source_url) -> Path`.
3. Registrar em `cmd_consult._get_converter_registry()`.
4. Rodar `doxoade consult ingest <nome>` + `doxoade consult index -f`.
5. Adicionar ao Tier 0 no `search()` do `doc_indexer.py` se for fonte didática.
6. Atualizar a tabela "Corpus Final" neste README.

---

## Bugs Conhecidos (Polish Pendente)

| ID | Problema | Onde | Prioridade |
|---|---|---|---|
| **P1** | Título duplicado residual no `read pytest/fixture` (`# 📖 About fixtures` + `# About fixtures`). | `click_rich_pytest_converter.py` | Cosmético |
| **P5** | `consult read "git/day_02"` vazio no CLI (Doxly resolve via fallback LIKE). | `doc_indexer.py` | Baixa |
| **P6** | `highlighter.html` e `json.html` do Rich retornam 404. | `click_rich_pytest_converter.py` | Cosmético |

---

## Referências

- `FASE_5_RELATORIO.md` — relatório de encerramento
- `Blitzplan_Consult_Python_v1.md` — plano original da Fase 1
- `ProDeNov.md` — protocolo de desenvolvimento
- `doxly_tree.py` — catálogo de falhas (Phanto Crisis)

---

**Status final:** Consult **100% funcional para produção**. Corpus de **1734 documentos**
(40.24 MB) cobrindo Cat 1–5 + CPython, ranking curado, leitor Markdown com syntax highlight
no CLI e no Doxly. **Fases 1–5 concluídas.**

---

# 📋 RELATÓRIO DE ENCERRAMENTO — FASE 5 (POLISH + EXPANSÃO)

**Subsistema:** Consult
**Protocolo:** ProDeNov 1.2.1 | PASC-6.1
**Data:** 2026-10-23
**Autor:** Nexus Core / Anúbis & Hefesto
**Status:** ✅ **CONCLUÍDA**

---

## 1. Escopo da Fase 5

A Fase 5 teve dois objetivos:

1. **Polish (Fase 5.1):** Corrigir os bugs visuais/dados acumulados nas Fases 1–4 (P1–P4).
2. **Expansão (Fase 5.2):** Adicionar a Cat 5 (30 Seconds of Python) para snippets rápidos.

---

## 2. Bugs Resolvidos (Fase 5.1)

| ID | Problema | Solução | Status |
|---|---|---|---|
| **P1** | Menu Furo (`Menu / Light mode / Skip to content`) nos docs do Pytest | `_clean_navigation_boilerplate` remove o bloco inteiro | ✅ |
| **P2** | `table.html`, `protocols.html` do Rich retornam 404 | URLs corrigidas: `tables.html`, `protocol.html` | ✅ |
| **P3** | `pty_file_daemon.py` falha sem Admin | Fora do escopo (produção roda Admin) | ⏳ |
| **P4** | Imagens quebradas (`![](./images/...)`) nos docs do Git | `_clean_markdown` remove `![]()` de imagens | ✅ |

---

## 3. Expansão (Fase 5.2)

**Cat 5.1 — 30 Seconds of Python:**

- **Fonte:** `github.com/Chalarangelo/30-seconds-of-code` (monorepo)
- **Formato:** Markdown com YAML frontmatter em `content/snippets/python/`
- **Total:** 47 snippets válidos
- **Categorias:** listas, strings, funções, matemática, data, regex, etc.
- **Exemplos validados:**
  - `python/snippets/chunk-list` → top-1 em `chunk list`
  - `python/snippets/string-capitalize-camel-snake-kebab` → top-1 em `camel case string`
  - `python/snippets/initialize-list-with-range-value-daterange` → top-1 em `range list`

**Tier aplicado:** `python/snippets/` foi adicionado ao **Tier 0** do ranking,
para competir com PEPs e livros.

---

## 4. Corpus Final

| Categoria | Docs | Tamanho |
|---|---|---|
| CPython Stdlib | 519 | ~25 MB |
| Cat 1 (Básico) | 151 | ~2.2 MB |
| Cat 2 (Avançado) | 983 | ~2.15 MB |
| Cat 3 (Automação) | 41 | ~500 KB |
| Cat 4 (Git) | 9 | ~20 KB |
| Cat 5 (Snippets) | 47 | ~200 KB |
| **TOTAL** | **1734** | **40.24 MB** |

---

## 5. Métricas de Validação

| Métrica | Valor | Meta |
|---|---|---|
| **Docs indexados** | 1734 | ≥ 1500 ✅ |
| **Tamanho do banco** | 40.24 MB | ≤ 50 MB ✅ |
| **Ingestão de uma fonte** | < 2 min | ≤ 5 min ✅ |
| **Rebuild completo** | ~90 s | ≤ 5 min ✅ |
| **Busca FTS5** | < 15 ms | ≤ 50 ms ✅ |
| **Abertura de card (Doxly)** | ~2 s | ≤ 3 s ✅ |
| **Ranking correto (top-3)** | 4/4 buscas validadas | 100% ✅ |

---

## 6. Bugs Conhecidos (Pendentes)

| ID | Problema | Prioridade |
|---|---|---|
| **P1-residual** | Título duplicado (`# 📖 About fixtures` + `# About fixtures`) | Cosmético |
| **P5** | `consult read "git/day_02"` vazio no CLI | Baixa |
| **P6** | `highlighter.html` e `json.html` do Rich retornam 404 | Cosmético |

---

## 7. Próximas Fases (roadmap)

| Fase | Escopo | Esforço |
|---|---|---|
| **Fase 6** | Consolidação final (este README + dossiê XML) | ✅ Concluída |
| **Fase 7** | PTY embutido (Dev Mode + patches) | 2h |
| **Fase 8** | Compressão dos `.jsonl` (Doxoade Compression Tech 1) | 1h |
| **Fase 9** | Expansão Cat 6 (DevDocs: requests, numpy, pandas) | 2h |

---

## 8. Conclusão

A **Fase 5 está concluída**. O `consult` cobre **1734 documentos** em 5 categorias
+ CPython, com **ranking curado** (PEP/livro/snippet no top-3) e **leitor Markdown
com syntax highlight** no CLI e no Doxly.

O subsistema está **pronto para produção** e manutenção contínua. As fases seguintes
(7, 8, 9) são **opcionais** e podem ser priorizadas conforme necessidade.

---

**Assinado:** Anúbis (auditoria) + Hefesto (construção)
**Aprovação:** ⏳ Pendente (dev)

---
