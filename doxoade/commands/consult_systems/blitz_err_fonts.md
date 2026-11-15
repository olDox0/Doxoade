# 📜 BLITZPLAN — EXPANSÃO DO CONSULT (ERROS + VERSÕES) E CTROL+F NO LEITOR

**Protocolo:** ProDeNov 1.2.1 | PASC-6.1 | W5H
**Subsistemas:** Thoth (chunking) · Hades (FTS5) · Anúbis (auditoria de fontes) · Apolo (UI do reader)
**Foco:** (1) Ingestão de fontes práticas de **erros comuns Python/C** e **mudanças entre versões**; (2) corrigir **Ctrl+F** no `ConsultDocReaderView` (`08_pot_panel.lua`).

---

## 1. Diagnóstico W5H

| Pergunta | Definição Tática |
|:---|:---|
| **O quê?** | Adicionar ~8 fontes de alta densidade em erros/versões (Python + C) ao FTS5 existente, sem inflar o banco. Corrigir busca interna no leitor de docs (Ctrl+F/F3 hoje é no-op). |
| **Onde?** | `doxoade/commands/consult_systems/converters/` (novos converters), `cmd_consult.py` (registry), `doc_indexer.py` (prioridades), `template/08_pot_panel.lua` (Ctrl+F). |
| **Por quê?** | Hoje você pesquisa **contrato de linguagem** (cheatsheet, PEPs, livros), mas **não** pesquisa "por que `-Werror=implicit-function-declaration` virou erro no GCC 14", "o que o 3.12 removeu", "como diagnosticar `double free`". O `consult` não é útil para **resolver** — só para **aprender**. |
| **Como?** | Novos converters seguindo `BaseCanonicalConverter`. Chunker Markdown/HTML reaproveitando o que já existe (`cheatsheet_converter` e `doc_indexer.html_to_markdown`). Paths semânticos com versão embutida (`c/gcc/porting/gcc-14`, `python/whatsnew/3.12`). |
| **Quanto?** | **+~15 MB** no DB (de ~35 para ~50 MB). Ingestão < 5 min. RAM pico < 80 MB. |
| **Quem?** | Thoth (chunker) · Hades (FTS5 batch) · Anúbis (validação de amostras por query) · Apolo (Ctrl+F). |

---

## 2. Estado Atual vs. Lacunas (verificado no código)

**Já existe (14 fontes):** cheatsheet · byte_of_python · 30days · py4e · the_algorithms · automate · peps · cosmic · patterns · typeshed · automation · git · 30seconds · ecosystem

**Já indexado mas DEPRIORIZADO** (via `doc_indexer.py: CASE WHEN`):
- `whatsnew/%` → prioridade **9** (a mais baixa) — mas é *exatamente* o que você quer
- `deprecations.html` → cai em `ELSE 5`
- `library/exceptions.html` → já entra por `library/%`

**Faltando por completo:**
- ❌ Nenhum material sobre **C** no DB
- ❌ Nenhuma **referência de diagnóstico de compilador** (GCC/Clang)
- ❌ Nenhuma referência cruzada de **porting entre versões** (GCC, Python)
- ❌ Nenhuma referência de **linters/tipos** (mypy, ruff)

---

## 3. Fontes Propostas (4 buckets, priorizadas por ROI)

### 🟥 BUCKET A — Diagnóstico C (o que estava em branco) — **prioridade máxima**

| # | Fonte | URL / origem | Formato | Chunking | Volume DB |
|:-:|:--|:--|:-:|:--|:-:|
| A1 | **Clang Diagnostics Reference** | `raw.githubusercontent.com/llvm/llvm-project/main/clang/docs/DiagnosticsReference.md` | MD único (~500 KB) | por `### ` (cada `-Wxxx`) | ~700 KB |
| A2 | **GCC Diagnostics** (subset) | `gcc.gnu.org/onlinedocs/gcc-XX/gcc-html.tar.gz` → filtrar `Diagnostics.html`, `Invoking-GCC.html`, `Warning-Options.html` | HTML | por `<h3>`/`<h4>` | ~2.5 MB |
| A3 | **GCC Porting per version** | `gcc.gnu.org/gcc-XX/changes.html` + `gcc-XX/porting_to.html` (13, 14, 15, 16, 17 se houver) | HTML | 1 doc por versão | ~400 KB |
| A4 | **cppreference C** | `github.com/PeterFeicht/cppreference-doc` (zip HTML, ou scrape `en/c/` via sitemap) | HTML | por página | ~6 MB |

**Uso típico pós-ingestão:**
- `consult search "implicit function declaration"` → A1 + A3 + A4
- `consult search "undefined reference to"` → A1 (linker) + A4
- `consult read c/gcc/porting/gcc-14` → toda a página "Porting to GCC 14"
- `consult search "strict aliasing gcc 13 vs 17"` → A3 (13, 14, 15, 16, 17 lado a lado)

### 🟧 BUCKET B — Diagnóstico Python (erros + versões)

| # | Fonte | Origem | Formato | Chunking | Volume |
|:-:|:--|:--|:-:|:--|:-:|
| B1 | **What's New 3.10–3.14** | CPython docs zip (`whatsnew/N.N.html`) — **já no DB, só boost de prioridade** | HTML | já fatiado | 0 KB novo |
| B2 | **Deprecations** | `docs.python.org/3/deprecations/` — idem boost | HTML | já fatiado | 0 KB novo |
| B3 | **PEPs version-related** (extensão) | Adicionar: **3151** (OS exceptions), **3155** (qualnames em traceback), **657** (fine-grained traceback), **654** (traceback exception groups), **678** (PEP em warning), **691** (JSON in pyproject) | HTML | já existe o converter | ~250 KB |
| B4 | **mypy error code list** | `mypy.readthedocs.io/en/stable/error_code_list.html` + `error_code_list2.html` | HTML | por `##` | ~400 KB |
| B5 | **Ruff rules index** | `docs.astral.sh/ruff/rules/` — ~700 regras, 1 página cada | HTML | por página | ~3 MB |
| B6 | **pyupgrade README + 2to3** | `github.com/asottile/pyupgrade` README.md + `docs.python.org/3/library/2to3.html` | MD/HTML | 2 docs | ~150 KB |

**Uso típico:**
- `consult search "deprecation distutils 3.12"` → B1
- `consult search "AttributeError NoneType object has no attribute"` → B1 + B4
- `consult search "TID ruff"` → B5
- `consult search "PEP 657 traceback"` → B3

### 🟨 BUCKET C — Sanitizers e UB (análise de runtime C)

| # | Fonte | Origem | Formato | Volume |
|:-:|:--|:--|:-:|:-:|
| C1 | **UBSan** | `clang.llvm.org/docs/UndefinedBehaviorSanitizer.html` | HTML 1pg | ~100 KB |
| C2 | **ASan** | `clang.llvm.org/docs/AddressSanitizer.html` | HTML 1pg | ~100 KB |
| C3 | **MSan** | `clang.llvm.org/docs/MemorySanitizer.html` | HTML 1pg | ~80 KB |

**Uso:** `consult search "heap-use-after-free asan"`, `consult search "double free asan"`.

### 🟩 BUCKET D — Fundamento C (para fechar o ciclo)

| # | Fonte | Origem | Formato | Volume |
|:-:|:--|:--|:-:|:-:|
| D1 | **Modern C** (Jens Gustedt, free) | `icube.u-strasbg.fr/~jgustedt/modern-c/modern-c.pdf` (ou `hal.science/hal-02383654`) | PDF → md | ~1 MB (chunk por capítulo) |
| D2 | **C Standard drafts** (opcional) | N2176 (C17), N3096 (C23 draft) — `open-std.org/jtc1/sc22/wg14/www/docs/` | PDF | ~500 KB (só notas de mudança) |

---

## 4. Plano Técnico — Implementação

### 4.1 Ajustes cirúrgicos (10 min, sem novo converter)

**`doc_indexer.py` — subir prioridade de versão/deprecação:**
```python
-- ANTES:
WHEN path LIKE 'whatsnew/%' THEN 9
WHEN path LIKE 'using/%'    THEN 8
-- DEPOIS (versão vira prioridade 2, igual a tutorial/library):
WHEN path LIKE 'whatsnew/%'            THEN 2
WHEN path LIKE 'deprecations%'         THEN 2
WHEN path LIKE 'reference/%'           THEN 2
```

**`cmd_consult.py::_get_converter_registry()`** — só adicionar entradas conforme converters forem criados.

**`peps_converter.py::PEPS`** — adicionar as 6 PEPs (3151, 3155, 657, 654, 678, 691).

### 4.2 Novos converters (5 arquivos)

Todos seguem o padrão `BaseCanonicalConverter`. Paths propostos:

```
c/clang/diag/<flag_name>            (A1 chunkado por ###)
c/gcc/manual/<secao>                (A2)
c/gcc/porting/gcc-13                (A3, um doc por versão)
c/gcc/porting/gcc-14
c/gcc/porting/gcc-15
c/gcc/porting/gcc-16
c/gcc/porting/gcc-17
c/cppreference/<area>/<symbol>      (A4)
c/sanitizer/ubsan                   (C1)
c/sanitizer/asan                    (C2)
c/sanitizer/msan                    (C3)
c/books/modern_c/<chapter>          (D1)
python/mypy/codes/<code>            (B4)
python/ruff/rules/<code>            (B5)
python/migration/pyupgrade          (B6)
python/migration/2to3               (B6)
```

Cada converter precisa:
1. `category = "c_diagnostics"` (ou `"c_cppreference"`, `"python_linters"` etc.)
2. `canonical_filename = "<name>.jsonl"`
3. Implementar `convert(self, source_url=None) -> Path`
4. Extrair `keywords` (reutiliza `BaseCanonicalConverter.extract_keywords`)

**Destaques de implementação:**

- **A1 (Clang DiagnosticsReference)** — o mais fácil e mais valioso. Um único GET de `raw.githubusercontent.com`. Chunking por `### `:
  ```python
  # Cada seção começa com "### -W<flag>" ou "### -W<flag><sub>"
  # O título é a flag; o corpo é a explicação + exemplos.
  # Path: c/clang/diag/Wimplicit_function_declaration
  ```
  Volume estimado de chunks: ~400 (todas as flags de C e C++). Filtrar `C++ only` para ficar em ~250 chunks.

- **A3 (GCC Porting)** — ouro para sua dúvida direta "gcc 13 vs 17". Cada `porting_to.html` tem seções `## C language issues` com bullets curtos e diretos. Chunking 1 doc por versão (não por seção) — porque a comparação entre versões fica trivial:
  ```python
  # Path: c/gcc/porting/gcc-13  (title: "Porting to GCC 13 - Issues")
  # Path: c/gcc/porting/gcc-14  (title: "Porting to GCC 14 - Issues")
  # search "implicit function declaration" → retorna gcc-13 e gcc-14
  ```
  Se o `porting_to.html` de uma versão não existir (13 tem; 14 tem; 15 começou a ter), fallback para `changes.html` filtrado (só a seção "Caveats/Porting").

- **A4 (cppreference)** — tenta o `cppreference-doc` zip primeiro (offline); se estiver desatualizado ou ausente, Plano B é scrape via sitemap. **Filtrar só `en/c/`** (não `en/cpp/`) para poupar volume.

- **A2 (GCC manual)** — do tarball `gcc-XX.Y.Z/gcc-html.tar.gz` (~3 MB), extrair **apenas**:
  ```
  Invoking-GCC.html
  Warning-Options.html
  Diagnostics.html
  Optimize-Options.html    (só -O/-fanalyzer)
  Analyzer-Options.html    (-fanalyzer)
  ```
  Ignorar o resto (o manual completo é ~15 MB e 90% irrelevante).

- **B4 (mypy) / B5 (ruff)** — ambos são estáveis, HTML estruturado. B5 é grande (700 páginas) mas trivial por página; ~3 MB.

- **D1 (Modern C)** — PDF difícil de converter; **Plano B** é o HTML mirror de `icube.u-strasbg.fr` ou `inria.hal.science`. Se PDF for a única via, usar `pdftotext` via subprocess (não é dependência Python; é binário do sistema). Alternativa: descartar D1 na Fase 1 e reaproveitar `cppreference`.

### 4.3 Integração com `cmd_ingest`

Após criar os converters, `doxoade consult ingest all` já os pega. Para granularidade:

```bash
doxoade consult ingest clang_diag
doxoade consult ingest gcc_porting
doxoade consult ingest gcc_manual
doxoade consult ingest cppreference
doxoade consult ingest sanitizers
doxoade consult ingest ruff
doxoade consult ingest mypy
```

Cada um é idempotente (o `_ingest_one` já faz `db.ingest_jsonl`).

---

## 5. Plano Ctrl+F no Leitor de Docs (`08_pot_panel.lua`)

### 5.1 Diagnóstico

O `Ctrl+F` global está bound a `find-replace:find`, que roda em `core.docview` e depende de `core.active_view.doc`. Mas o **`ConsultDocReaderView`** (e o **`ConsultSearchView`**) são `View:extend()`, **não** `DocView:extend()`. Portanto:

- Não têm `doc` → `find-replace:find` silenciosamente não faz nada
- O texto é renderizado linha a linha via `draw_text_safe` dentro de `:draw()` → não há buffer para o `find-replace` varrer

**Resultado:** Ctrl+F "não aplica" — nada acontece (exatamente o sintoma que você relatou).

### 5.2 Estratégia — Mini-search local (Plano A)

Não converter para `DocView` (perderia a renderização markdown/box da árvore do FTS5). Em vez disso:

1. **Adicionar estado no `ConsultDocReaderView`:**
   ```lua
   self.search_query = ""
   self.search_matches = {}         -- [line_idx, ...]
   self.search_match_positions = {} -- [line_idx] = { {s,e}, {s,e}, ... }
   self.search_current = 0
   self.search_active = false
   ```

2. **Três métodos:**
   ```lua
   function ConsultDocReaderView:perform_search(query)   -- popula matches + scroll_to_line(first)
   function ConsultDocReaderView:search_next()           -- avança current + scroll_to_line
   function ConsultDocReaderView:search_prev()           -- volta current + scroll_to_line
   function ConsultDocReaderView:clear_search()          -- reseta estado
   ```
   Reaproveita `self:scroll_to_line()` (herdado de `View`).

3. **Highlight no `:draw()`** — depois do clip_rect e antes do loop de desenho das linhas, para cada `line_idx` com matches:
   ```lua
   if self.search_active and self.search_match_positions[line_idx] then
     for _, span in ipairs(self.search_match_positions[line_idx]) do
       local rx = self:get_col_x_offset(line_idx, span[1])  -- se disponível, senão approx
       draw_rect_safe(x + 18 + rx, cur_y, span[2]-span[1]+1 * char_w, self.line_h,
                      { 250, 204, 21, 90 })
     end
   end
   ```
   *`get_col_x_offset` provavelmente não existe em `View` (é de `DocView`). Plano B: usar `font:get_width(line:sub(1, start-1))` para calcular offset em pixels, já que o texto é renderizado com um `code_font` só.*

4. **Barra visual** — quando `search_active`, desenhar um overlay compacto no header_h:
   ```
   ┌──────────────────────────────────────────────────┐
   │ ⬅ Voltar │ [raw] │ [copiar] │ 🔍 dataclass  (3/17) [x] │
   └──────────────────────────────────────────────────┘
   ```
   O "(3/17)" mostra `search_current / #search_matches`.

5. **Dispatcher universal de Ctrl+F** — resolve o conflito com `find-replace:find` sem hack:
   ```lua
   command.add(nil, {
     ["doxoade:universal-find"] = function()
       local v = core.active_view
       if v and v.is and v:is(ConsultDocReaderView) then
         core.command_view:enter("🔍 Buscar neste documento:", {
           text = v.search_query or "",
           submit = function(text) v:perform_search(text) end
         })
       else
         command.perform("find-replace:find")
       end
     end,
     ["doxoade:universal-find-next"] = function()
       local v = core.active_view
       if v and v.is and v:is(ConsultDocReaderView) then
         v:search_next()
       else
         command.perform("find-replace:repeat-find")
       end
     end,
     ["doxoade:universal-find-prev"] = function()
       local v = core.active_view
       if v and v:is and v:is(ConsultDocReaderView) then
         v:search_prev()
       else
         command.perform("find-replace:previous-find")
       end
     end,
   })

   keymap.add {
     ["ctrl+f"] = "doxoade:universal-find",   -- sobrescreve o global (via overwrite=true)
     ["f3"]     = "doxoade:universal-find-next",
     ["shift+f3"] = "doxoade:universal-find-prev",
     ["escape"] = "doxoade:consult-search-clear",
   }, true  -- segundo argumento de keymap.add força overwrite
   ```
   *Nota: `keymap.add(map, true)` — o segundo arg é `overwrite`, conforme documentação do Lite XL. Já é usado em `100_keymap_manager.lua`.*

6. **Um detalhe de UX**: ao fechar a busca com `Escape`, limpar `search_active` e chamar `core.redraw = true`.

7. **Aplicar o mesmo padrão ao `ConsultSearchView`** (a lista de resultados) — é útil quando há 25 cards e você quer filtrar por "asyncio". Mesmo código, ~20 linhas a mais.

### 5.3 Fallback (Plano B) — se o cálculo de offset der erro

Se `get_col_x_offset` não existir em `View`, computar o offset usando a mesma métrica do render:
```lua
local font = style.code_font or style.font
local prefix_w = font:get_width(line_text:sub(1, span[1]-1))
local match_w = font:get_width(line_text:sub(span[1], span[2]))
draw_rect_safe(x + 18 + prefix_w, cur_y, match_w, self.line_h, { 250, 204, 21, 90 })
```

### 5.4 Plano C — desistir do mini-search se `< 30ms` não bater

Se o regex `find(lower_q, start, true)` em docs longos (> 5.000 linhas, raro no consult) causar lag, fazer a busca em `core.add_thread()` e mostrar spinner no header até completar. Idempotente, não muda UX.

---

## 6. Budget de Tamanho e Priorização

### 6.1 DB projetado pós-Fase 2

| Categoria | Volume |
|:--|:--:|
| Existente (14 fontes) | ~35 MB |
| Bucket A (C diag + porting + cppreference) | ~9.5 MB |
| Bucket B (mypy + ruff + pyupgrade + PEPs) | ~3.8 MB |
| Bucket C (sanitizers) | ~280 KB |
| Bucket D (Modern C — opcional) | ~1 MB |
| **Total** | **~50 MB** ✅ |

Bem dentro do limite de 80 MB que você mesmo definiu no `Blitzplan_Consult_Python_v1.md` para a Fase 1.

### 6.2 Priorização sugerida

| Fase | Entrega | Tempo | Valor |
|:--:|:--|:--:|:--:|
| **0** | Boost `whatsnew`/`deprecations` no `doc_indexer.py` + 6 PEPs no `peps_converter.py` | 10 min | ⭐⭐⭐⭐⭐ |
| **1** | `clang_diag_converter.py` (A1) + `gcc_porting_converter.py` (A3) | 40 min | ⭐⭐⭐⭐⭐ |
| **2** | `gcc_manual_converter.py` (A2) | 30 min | ⭐⭐⭐⭐ |
| **3** | `ctrl+f` no leitor + `Ctrl+F` dispatcher | 25 min | ⭐⭐⭐⭐⭐ |
| **4** | `cppreference_converter.py` (A4) | 1h | ⭐⭐⭐⭐ |
| **5** | `sanitizers_converter.py` (C) | 15 min | ⭐⭐⭐ |
| **6** | `ruff_converter.py` + `mypy_converter.py` (B4/B5) | 30 min | ⭐⭐⭐ |
| **7** | `modern_c_converter.py` (D1) — só se PDF→md funcionar limpo | 40 min | ⭐⭐ |

**Recomendação forte:** Fases 0, 1 e 3 primeiro — são as de maior ROI imediato e cobrem "gcc 13 vs 17" e "ctrl+f" diretamente.

---

## 7. Tasklist Detalhada (DoD por fase)

### Fase 0 — Ajustes cirúrgicos
- [ ] `doc_indexer.py`: boost de `whatsnew/%`, `deprecations%`, `reference/%` para prioridade 2
- [ ] `peps_converter.py`: adicionar PEPs 3151, 3155, 657, 654, 678, 691 à lista `PEPS`
- [ ] `doxoade consult ingest peps` (reingest só dos PEPs — DB mantém os outros)
- [ ] Verificar: `consult search "deprecation 3.12"` retorna resultado top-5 de `whatsnew/`

### Fase 1 — Clang + GCC Porting
- [ ] Criar `converters/clang_diag_converter.py` (chunk por `### `)
- [ ] Criar `converters/gcc_porting_converter.py` (loop de 13–17, tolerante a ausentes)
- [ ] Registrar no `_get_converter_registry()`
- [ ] `doxoade consult ingest clang_diag && doxoade consult ingest gcc_porting`
- [ ] **DoD verificável:**
  - `consult search "implicit function declaration"` → pelo menos 1 hit de `c/gcc/porting/gcc-14`
  - `consult search "undefined reference to"` → hit de `c/clang/diag` + `c/cppreference` (quando A4 entrar)
  - `consult read c/gcc/porting/gcc-14` → markdown renderiza no Doxly

### Fase 3 — Ctrl+F no reader
- [ ] Adicionar campos de search no `ConsultDocReaderView:new`
- [ ] Adicionar `perform_search`, `search_next`, `search_prev`, `clear_search`
- [ ] Adicionar highlight no `:draw()` (offset por `font:get_width` do prefixo)
- [ ] Adicionar mini-bar no header com `(N/M)` e `[x]`
- [ ] Registrar `doxoade:universal-find` (dispatcher Ctrl+F) + F3/Shift+F3
- [ ] Aplicar o mesmo padrão ao `ConsultSearchView`
- [ ] **DoD verificável:**
  - Abrir um doc no reader (`consult read python/peps/pep_0008`)
  - Pressionar `Ctrl+F` → prompt abre → digitar `indent` → **scroll para primeira linha e highlight visível**
  - `F3` → próximo match com scroll
  - `Escape` → highlights somem
  - Em editor normal (`.py` aberto), `Ctrl+F` continua abrindo `find-replace:find` normalmente

### Fase 2/4/5/6/7 — conforme prioridade

---

## 8. Planos B / C

- **Plano B (Clang):** se o arquivo MD for renomeado no upstream (`DiagnosticsReference.md` → outra estrutura), fallback é scrape `clang.llvm.org/docs/DiagnosticsReference.html` (mesmo conteúdo).
- **Plano B (cppreference):** se o zip oficial não vier, usar sitemap `cppreference.com/sitemap.xml` filtrado por `en/c/`.
- **Plano B (GCC tarball):** se o `gcc-html.tar.gz` for grande demais para stream em Celeron N2808, baixar e extrair seletivamente via `tarfile.open(..., 'r|gz')` com filter por membro.
- **Plano C (Ctrl+F):** se `View` não expuser nada útil para calcular offset, renderizar highlight como **barra lateral no gutter** (retângulo de 3px à esquerda da linha) em vez de highlight in-line — mais simples, menos pixels calculados, ainda identifica visualmente.
- **Plano C (DB > 80 MB):** se estourar, cortar A4 (cppreference) para apenas `en/c/language/` e `en/c/types/` (sem `en/c/preprocessor/`).

---


