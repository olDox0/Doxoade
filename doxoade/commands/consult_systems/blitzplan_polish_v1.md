# 📜 BLITZPLAN — POLISH E EXPANSÃO DO CONSULT (FASE 5)

**Protocolo:** ProDeNov 1.2.1 | PASC-6.1
**Data:** 2026-10-21
**Subsistemas:** Thoth (parsing) / Hades (FTS5) / Apolo (CLI) / Dionísio (Doxly)
**Status:** 📋 Aguardando início

---

## 1. Contexto e Objetivos (W5)

- **O quê:** Resolver os 5 bugs conhecidos (P1–P5) e avaliar 3 expansões opcionais (30 Seconds of Python, PEPs históricas, DevDocs).
- **Quem:** Equipe Doxoade (dev + CI).
- **Onde:** `consult_systems/converters/`, `doc_indexer.py`, `README.md`.
- **Quando:** Após a consolidação do corpus atual (1685 docs).
- **Por quê:** O corpus está 100% funcional, mas há ruído visual (P1), imagens quebradas (P4) e inconsistências de URL (P2). O polish garante **UX consistente** para o `brunnr` e para o dev final.
- **Origem e Consequências:** Bugs surgiram durante a Fase 1–4 por limitações dos HTMLs originais (Furo, Sphinx) e por paths curtos do Git converter.

---

## 2. Taxonomia de Complexidade (Regra 0.0–0.4 ProDeNov)

| Vetor | Classificação | Mitigação |
|---|---|---|
| **0.0 Thirdparty** | Baixa | Apenas `re`/`ast` stdlib. Sem deps externas. |
| **0.1 Devflow** | Média | Cada patch testado isoladamente antes do próximo. |
| **0.2 Rabbit Hole** | Baixa | Polish é cirúrgico; expansão tem plano B. |
| **0.3 Sensibilidade** | Baixa | Nenhuma mudança no hotpath do Doxly. |
| **0.4 Revisitar** | Baixa | Documentação clara para retomada. |

---

## 3. Fases de Execução (Regra 1.2.1)

### 🧹 FASE 5.1 — Polish Cirúrgico (P1–P4)

**Ordem recomendada:** P2 → P4 → P1 → P3.

#### 🔹 P2 — Corrigir URLs do Rich (5 min)
- **Problema:** 4 páginas do Rich (`table.html`, `protocols.html`, `highlighter.html`, `json.html`) falharam no download.
- **Solução:** Ajustar `LIBRARIES["rich"]["pages"]` no `click_rich_pytest_converter.py` — as URLs corretas podem ser:
  - `table.html` → `tables.html`
  - `protocols.html` → `protocol.html`
  - `highlighter.html` → `highlighting.html`
  - `json.html` → `pretty.html#pretty-printing-json` (ou já coberto por `pretty`)
- **DoD:** `ingest automation` retorna `43/43 páginas`.
- **Plano B:** Se os URLs mudaram de novo, buscar o índice (`index.html`) e fazer crawl dinâmico dos `<a href>`.

#### 🔹 P4 — Imagens quebradas do Git (10 min)
- **Problema:** Docs do Git têm `![](./images/github-page.png)` que não renderiza no Doxly.
- **Solução:** No `_clean_markdown` do `git_github_converter.py`, remover as linhas de imagem:
  ```python
  text = re.sub(r'!\[[^\]]*\]\(\./images/[^)]+\)', '', text)
  ```
- **DoD:** `search "git push"` → snippet sem `![](./images/)`.
- **Plano B:** Manter as imagens (o Doxly 19a já tem handler de `[DOX-IMG]`, mas não de `![]()`).

#### 🔹 P1 — Menu Furo do Pytest (30 min)
- **Problema:** Docs do Pytest têm o menu "Skip to content / Light mode / Dark mode" no topo.
- **Solução:** Adicionar método `_clean_navigation_boilerplate` no `click_rich_pytest_converter.py`:
  ```python
  def _clean_navigation_boilerplate(self, md: str) -> str:
      # Remove menu do topo
      md = re.sub(
          r"(?is)^\s*(?:Menu|Expand|Light mode|Dark mode|Skip to content|"
          r"Auto light/dark[^\n]*|pytest documentation|Get Started|"
          r"How to invoke[^\n]*|How to write[^\n]*|How to use[^\n]*|"
          r"How to mark[^\n]*|How to parametrize[^\n]*|"
          r"How to run doctests[^\n]*|How to re-run[^\n]*)\s*\n",
          "", md, flags=re.IGNORECASE
      )
      # Remove "On this page" no final
      md = re.sub(r"(?is)\n(?:On this page|Previous|Copyright ©)[^\n]*\n.*$", "", md)
      return md.strip()
  ```
- **DoD:** `read python/automation/pytest/fixture` começa com `# Fixture Reference`, sem menu.
- **Plano B:** Se a limpeza regex apagar conteúdo válido, reverter para a versão anterior.

#### 🔹 P3 — PTY fallback (opcional, 1h)
- **Problema:** `pty_file_daemon.py` falha sem Admin.
- **Solução:** Já implementada nos patches anteriores (não aplicados). Aplicar apenas se o ambiente rodar sem Admin.
- **DoD:** `doxoade doxly deploy test` num terminal comum → abre `cmd.exe` elevado via UAC.
- **Plano B:** Manter produção sempre em Admin (atual) e documentar no README.

---

### 📈 FASE 5.2 — Expansão Opcional (Cat 5)

Avaliar 3 fontes complementares que **agregam valor sem inflar** o banco:

#### 🔹 Cat 5.1 — 30 Seconds of Python (opcional, 15 min)
- **Fonte:** `github.com/30-seconds/30-seconds-of-python` (arquivado em 2023).
- **Formato:** Markdown com snippets curtos (~150).
- **Ganho:** Snippets de 3-10 linhas para consulta rápida.
- **Converter:** Clone o ZIP e itere sobre `snippets/*.md`.
- **Impacto no banco:** +150 docs, +200 KB.
- **Decisão:** ✅ Se o usuário quiser snippets rápidos.

#### 🔹 Cat 5.2 — PEPs Históricas (opcional, 30 min)
- **Fonte:** `peps.python.org/pep-XXXX` (todas as PEPs Final).
- **Ganho:** Cobertura completa de tipagem, async, decorators.
- **Converter:** Lista fixa de 20–30 PEPs adicionais (PEP 3107, 3155, 435, 442, 492, 519, 526, 544, 585, 591, 593, 604, 612, 646, 647, 655, 673, 675, 695).
- **Impacto:** +30 docs, +600 KB.
- **Decisão:** ⏳ Só se o `brunnr` precisar de contratos históricos.

#### 🔹 Cat 5.3 — DevDocs Scraped Reference (opcional, 1h)
- **Fonte:** `devdocs.io` (HTML parseado).
- **Ganho:** Docs de bibliotecas de terceiros (requests, numpy, pandas, django).
- **Impacto:** +500 docs, +5 MB.
- **Decisão:** ❌ Fase 5.3 fica para depois do polish. Prioriza Cat 5.1.

---

### 🔧 FASE 5.3 — Melhoria de Infraestrutura (opcional)

#### 🔹 P6 — `run_read.py` inline vs `read_doc_as_markdown` (30 min)
- **Problema:** O `08_pot_panel.lua` tem 3 versões do `read_doc_as_markdown` (inline, `cmd_consult` e `doc_indexer`). Se divergirem, o Doxly quebra.
- **Solução:** Extrair a função para `doxoade/tools/consult_reader.py` e usar de todos os lugares.
- **Impacto:** Manutenção simplificada.

#### 🔹 P7 — Compressão dos `.jsonl` canônicos (1h)
- **Problema:** 12 arquivos em `~/.doxoade/consult/canonical/` somam ~15 MB.
- **Solução:** Aplicar `dict_learner.compress_file_for_backup` (já existe) com `zstd + dict`.
- **Impacto:** ~15 MB → ~3 MB. **Não afeta** o FTS5 (que já está descomprimido por design).
- **Decisão:** ⏳ Só se o disco ficar apertado.

---

## 4. Ordem de Execução Recomendada

```
[Fase 5.1 — Polish] → P2 → P4 → P1 → P3 (opcional)
                              │
                              ▼
[Fase 5.2 — Expansão] → Cat 5.1 (30s Python) → Cat 5.2 (PEPs) → Cat 5.3 (DevDocs)
                              │
                              ▼
[Fase 5.3 — Infra]    → P6 (refactor reader) → P7 (compressão)
                              │
                              ▼
[Fase 6 — Consolidação Final] → README v2 + docs oficiais
```

---

## 5. Matriz de Testes (DoD)

| ID | Teste | Comando | Esperado |
|---|---|---|---|
| **T-5.1.1** | Rich: 43 páginas | `doxoade consult ingest automation` | `43/43` |
| **T-5.1.2** | Git: sem imagens quebradas | `doxoade consult search "git push"` | Sem `![](./images/)` |
| **T-5.1.3** | Pytest: sem menu Furo | `doxoade consult read python/automation/pytest/fixture` | Começa com `# Fixture Reference` |
| **T-5.2.1** | 30s Python: 150 snippets | `doxoade consult ingest 30seconds` | `~150` docs |
| **T-5.3.1** | Reader refactor: Doxly abre | `doxoade doxly deploy test` + clicar card | Abre em ≤ 2s |
| **T-5.3.2** | Compressão: ~3 MB | `ls -la ~/.doxoade/consult/canonical/` | < 5 MB total |

---

## 6. Tasklist

### Fase 5.1 — Polish
- [ ] **P2:** Corrigir 4 URLs do Rich em `click_rich_pytest_converter.py`.
- [ ] **P4:** Remover `![]()` de imagens no `git_github_converter.py`.
- [ ] **P1:** Adicionar `_clean_navigation_boilerplate` em `click_rich_pytest_converter.py`.
- [ ] **P3:** (Opcional) Aplicar patches do PTY fallback.

### Fase 5.2 — Expansão (decidir o que incluir)
- [ ] **Cat 5.1:** `30_seconds_converter.py` — 30 Seconds of Python.
- [ ] **Cat 5.2:** Expandir `peps_converter.py` com 20–30 PEPs adicionais.
- [ ] **Cat 5.3:** `devdocs_converter.py` — DevDocs Scraped Reference (futuro).

### Fase 5.3 — Infra
- [ ] **P6:** Extrair `read_doc_as_markdown` para `doxoade/tools/consult_reader.py`.
- [ ] **P7:** Comprimir `.jsonl` com `dict_learner`.

### Fase 6 — Consolidação
- [ ] Atualizar README v2 com Cat 5.1/5.2 se aplicadas.
- [ ] Gerar `chief_dossier_consult.xml` (dossiê completo do subsistema).
- [ ] Documentar no `docs/Research/`.

---

## 7. Critérios de Aceite

- ✅ Zero timeout no Doxly ao abrir qualquer card (`[CONSULT READ] Sucesso em < 3000ms`).
- ✅ Zero menu Furo nos docs de Pytest.
- ✅ Zero imagem quebrada nos docs de Git.
- ✅ `ingest all` completa em < 10 min.
- ✅ Buscas com ranking curado (PEP/livro no top-3).
- ✅ Documentação atualizada (README + Blitzplan).

---

## 8. Referências

- `README.md` (este diretório) — estado atual consolidado.
- `Blitzplan_Consult_Python_v1.md` — plano original da Fase 1.
- `ProDeNov.md` — protocolo de desenvolvimento.
- `doxly_tree.py` — catálogo de falhas.

---

