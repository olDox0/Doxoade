# 📜 BLITZPLAN — COMPARADOR SIDE-BY-SIDE & UTILS DE SELEÇÃO (DOXLY V21.0)

**Módulo Alvo:** `doxoade/commands/lite_xl_systems/template/20_split_comparator_and_tools.lua`  
**Protocolo de Conformidade:** ProDeNov 1.2.1 (Planos A, B e C | W5 | Limite < 50KB | Sistema de Diagnóstico Ativo)  
**Data:** 09/09/2026 | **Panteões:** Anúbis (Auditoria/Contratos), Hefesto (Construção), Horus (Telemetria) e Apolo (UX)

---

## 1. Contexto e Objetivos (W5 / 5 Perguntas)

* **O quê (What):**
  1. **Comparador Side-by-Side Inline:** Motor de diff visual direto no buffer/gutter que compara o trecho selecionado no Painel Ativo com o Painel Oposto. Se o Painel Oposto não tiver seleção, executa uma **varredura de janela deslizante (Fuzzy/LCS Block Matcher)** para localizar o bloco mais similar no arquivo oposto e aplicar o realce diferencial (`+ Adicionado/Verde`, `- Removido/Vermelho`, `~ Modificado/Amarelo`).
  2. **Organizador Alfabético (`Ctrl+1`):** Ordenação de linhas selecionadas ignorando indentações iniciais no critério de ordenação (`strip-aware sort`), preservando a integridade sintática.
  3. **Alinhador de Atribuições & Comentários (`Ctrl+2`):** Alinhamento vertical automático de operadores (`=`, `+=`, `-=`, etc.) e comentários de fim de linha (`--` em Lua, `#` em Python), respeitando strings literais.
  4. **Proteção Anti-Seleção Vazia:** Ambos os comandos emitem alerta não-bloqueante no `core.log` caso nenhuma seleção esteja ativa, prevenindo mutações destrutivas acidentais no buffer.
* **Quem (Who):** Desenvolvedores trabalhando em refatorações paralelas, migração de código, revisão de diffs de funções e organização de tabelas/dicionários no Lite XL / Doxly.
* **Onde (Where):**
  * `doxoade/commands/lite_xl_systems/template/20_split_comparator_and_tools.lua` (Novo template modular).
  * `doxoade/commands/lite_xl_systems/cmd_lite_xl.py` & `typhon_doxly/` (Integração nos gates de compilação AOT e auditoria estática).
* **Quando (When):** Em runtime contínuo durante a edição de código nos splits ativo e oposto.
* **Por quê (Why):** Evitar *context switching* para ferramentas externas de diff (Meld, Beyond Compare, VSCode Diff) para comparar pequenos blocos de funções entre painéis e eliminar o trabalho manual repetitivo de alinhar variáveis e ordenar listas/imports.
* **Origem & Consequências (Origin & Consequences):** Ausência de um motor nativo de alinhamento e comparação rápida nos splits. A falta dessa ferramenta causa lentidão na identificação de divergências sutis entre branches ou arquivos espelhados e formatação inconsistente de código.

---

## 2. Taxonomia & Sistema de Diagnóstico (Anti-Development Hell)

Para evitar *development hell*, tempos mortos ou congelamentos no SDL2 (garantindo os 60 FPS monitorados pelo Chronos), o módulo nasce com uma **Bateria de Diagnóstico Ativo**:

| ID de Diagnóstico | Alvo / Vetor | Condição de Falha | Resposta do Sistema / Mitigação |
| :--- | :--- | :--- | :--- |
| **`DIAG-DIFF-TIMEOUT`** | Janela deslizante no Painel B | Busca de bloco mais similar excedendo 8ms em arquivos > 10.000 linhas | Short-circuit para busca por amostragem em blocos de 50 linhas com log de aviso no `Khonsu` |
| **`DIAG-ORPHAN-SPLIT`** | Comparação com Painel Oposto | Apenas 1 split aberto no `core.root_view` | Abre o documento no painel direito ou emite aviso informativo com sugestão de comando |
| **`DIAG-PARSER-LITERAL`** | Alinhamento `Ctrl+2` | Sinais de `=` ou `#`/`--` dentro de strings ou expressões regex | Lexer atômico de strings com ignorância de literais entre aspas simples/duplas e raw strings |
| **`DIAG-EMPTY-SELECTION`** | `Ctrl+1` / `Ctrl+2` | Cursor estático sem seleção ativa | Retorno imediato $O(1)$ emitindo `core.log("⚠ [...] Nenhuma seleção ativa.")` |

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — LCS Sliding Window & Lexer Atômico)
1. **Side-by-Side Diff Engine:**
   * Se ambos os painéis tiverem seleção: extrai linhas de $A$ e $B$ e roda algoritmo **LCS (Longest Common Subsequence)** em memória.
   * Se apenas o Painel $A$ tiver seleção: aplica janela deslizante com score de similaridade de Jaccard/Dice sobre o Painel $B$. O bloco com maior score é eleito o par correspondente.
   * Injeta no estado do `DocView` as tabelas `_doxoade_diff_state` para o Painel A e Painel B.
   * Hooks em `DocView:draw_line_body` e `DocView:draw_line_gutter` renderizam os tints translúcidos e as marcas de gutter via `draw_rect_safe`.
2. **Sort Ignorando Indentação (`Ctrl+1`):**
   * Coleta linhas da seleção com suas posições $l_1 \dots l_2$.
   * Normaliza para comparação: `line:gsub("^%s+", ""):lower()`.
   * Preserva a indentação estrutural original de cada linha ao remontar o bloco.
   * Substitui atomicamente no documento usando `doc:text()` + `doc:insert()`.
3. **Alinhador de Atribuições & Comentários (`Ctrl+2`):**
   * Lexer de passagem única por linha que detecta operadores de atribuição fora de strings (`=`, `+=`, `-=`, `*=`, `/=`, `..=`, `:`) e marcadores de comentário (`--` para Lua, `#` para Python).
   * Calcula:
     1. $Col_{max\_op} = \max(\text{coluna do operador de todas as linhas})$
     2. $Col_{max\_com} = \max(\text{coluna do comentário de todas as linhas})$
   * Reconstrói cada linha preenchendo os espaços exatos até as colunas calculadas.
4. **Comandos e Keymaps:**
   * `ctrl+1` ➔ `doxoade:sort-selected-lines-alpha`
   * `ctrl+2` ➔ `doxoade:align-assignments-and-comments`
   * `ctrl+alt+shift+c` ➔ `doxoade:compare-selection-with-opposite-panel`
   * `ctrl+alt+shift+x` (ou Escape) ➔ `doxoade:clear-diff-highlights`

### 🔹 Plano B (Fallback — Comparação Linear e Alinhamento Básico)
* Se a busca por janela deslizante no Painel B ultrapassar o limite de tempo estipulado pelo Khonsu ($> 5\text{ms}$), o sistema chaveia automaticamente para a **comparação das mesmas coordenadas de linha** ($l_{start} \dots l_{end}$ equivalentes no Painel B).
* Se a detecção de comentários falhar em arquivos de sintaxe mista, o alinhador atua somente no operador `=`, ignorando a coluna de comentários.

### 🔹 Plano C (Contingência & Resgate de Buffer)
* Qualquer exceção em tempo de execução dentro dos hooks de formatação é capturada por `pcall`/`xpcall` e registrada no `_DOXOADE_RUNTIME_INCIDENTS` (do `00_header_and_logger.lua`), garantindo que o documento nunca perca dados e o editor nunca trave (*zero-crash guarantee*).

---

## 4. Arquivos Impactados & Limites (< 50KB)

```
doxoade/commands/lite_xl_systems/
└── template/
    └── 20_split_comparator_and_tools.lua   # [NOVO] Motor de Diff, Sort e Align (~22KB)
```

---

## 5. Especificação Técnica da Engenharia

### 5.1. Estrutura do Módulo `20_split_comparator_and_tools.lua`

```lua
-- doxoade/commands/lite_xl_systems/template/20_split_comparator_and_tools.lua
--[[
  ⚖️ DOXOADE SPLIT COMPARATOR, STRIP-AWARE SORTER & ALIGNER (V21.0)
  - Comparador Visual Side-by-Side com busca por janela deslizante no Painel Oposto.
  - Ctrl+1: Ordenação alfabética ignorando indentações iniciais (Strip-Aware).
  - Ctrl+2: Alinhador vertical de operadores (=, +=, :, etc.) e comentários (Lua/Python).
  - Telemetria e salvaguardas Khonsu contra travamento em buffers extensos.
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local DocView = require "core.docview"

-- Registro de Paleta e Estados
local DIFF_COLORS = {
  ADDED    = { color = { 34, 197, 94, 255 },  tint = { 34, 197, 94, 35 } },   -- Verde
  REMOVED  = { color = { 239, 68, 68, 255 },  tint = { 239, 68, 68, 35 } },   -- Vermelho
  MODIFIED = { color = { 234, 179, 8, 255 },   tint = { 234, 179, 8, 35 } },   -- Amarelo
}
```

### 5.2. Lógica do Fuzzy Block Matcher (Busca no Painel Oposto)
```lua
local function find_most_similar_block(source_lines, target_doc)
  local target_lines = target_doc.lines or {}
  local src_count = #source_lines
  local tgt_count = #target_lines
  if src_count == 0 or tgt_count == 0 then return 1, math.min(tgt_count, 1) end

  local best_score = -1
  local best_start = 1
  local step = (tgt_count > 2000) and 2 or 1 -- Amostragem adaptativa

  for start_idx = 1, tgt_count - src_count + 1, step do
    local match_hits = 0
    for j = 1, src_count do
      local s_line = source_lines[j]:gsub("^%s+", ""):gsub("%s+$", "")
      local t_line = (target_lines[start_idx + j - 1] or ""):gsub("^%s+", ""):gsub("%s+$", "")
      if s_line == t_line and s_line ~= "" then
        match_hits = match_hits + 1
      end
    end
    if match_hits > best_score then
      best_score = match_hits
      best_start = start_idx
    end
  end

  return best_start, math.min(tgt_count, best_start + src_count - 1)
end
```

---

## 6. Tasklist & Checklist de Implementação

- [ ] **Fase 1: Construção do Módulo `20_split_comparator_and_tools.lua`**
  - [ ] Implementar o validador de seleção vazia (`doc:has_selection()`).
  - [ ] Implementar o ordenador de linhas `Ctrl+1` com `strip-aware` e preservação de recuo.
  - [ ] Implementar o alinhador `Ctrl+2` com suporte a operadores e comentários Lua (`--`) e Python (`#`).
  - [ ] Implementar o motor de Diff LCS e o Localizador de Janela Deslizante para o split oposto.
  - [ ] Injetar hooks visuais no `DocView:draw_line_body` e `DocView:draw_line_gutter` com `draw_rect_safe`.
- [ ] **Fase 2: Registro de Comandos e Keymaps**
  - [ ] Mapear `ctrl+1` para ordenação alfabética.
  - [ ] Mapear `ctrl+2` para alinhamento automático.
  - [ ] Mapear `ctrl+alt+shift+c` para comparar com o painel oposto.
  - [ ] Mapear comando de limpeza de diff (`doxoade:clear-diff-highlights`).
- [ ] **Fase 3: Auditoria Estática e Validação AOT**
  - [ ] Executar `doxoade lite-xl check-templates` (verificar se o novo template pontua 100% PASS).
  - [ ] Validar compilação AOT no `doxly_khonsu_gate.py`.
- [ ] **Fase 4: Testes de Caos & Prova de Não-Regressão**
  - [ ] Validar comportamento com buffers sem seleção.
  - [ ] Testar alinhamento com strings contendo `=`, `#` e `--` literais (devem ser ignorados).
  - [ ] Executar deploy em modo `sandbox` / `test` com `doxoade lite-xl deploy test`.

---

O plano está pronto e estruturado segundo o protocolo **ProDeNov 1.2.1**.  
Podemos prosseguir com a geração completa do código de **`20_split_comparator_and_tools.lua`**?

---

```
[1. Roteiro de Testagem] ➔ [2. Critérios de Avaliação] ➔ [3. Sistema de Diagnóstico] ➔ [4. Implementação Completa]
```

---

# 🧪 ETAPA 1: ROTEIRO DE TESTAGEM (MATRIZ DE CASOS DE TESTE)

| ID | Cenário / Entrada | Ação Disparada | Comportamento Esperado |
| :--- | :--- | :--- | :--- |
| **TC-01** | Cursor sem seleção ativa | `Ctrl+1` (Sort) | **Zero mutação**. Log: `"⚠ [SORT] Nenhuma linha selecionada."` |
| **TC-02** | Cursor sem seleção ativa | `Ctrl+2` (Align) | **Zero mutação**. Log: `"⚠ [ALIGN] Nenhuma linha selecionada."` |
| **TC-03** | 5 linhas com recuos variados (tabs/espaços) | `Ctrl+1` (Sort) | Linhas ordenadas alfabeticamente pela 1ª letra útil, **preservando o recuo individual** |
| **TC-04** | Atribuições Lua/Python com comprimentos distintos | `Ctrl+2` (Align) | Operadores `=` alinhados verticalmente na maior coluna detectada |
| **TC-05** | Atribuições contendo comentários (`--` ou `#`) | `Ctrl+2` (Align) | Operadores `=` alinhados na coluna 1; comentários alinhados na coluna 2 |
| **TC-06** | Strings literais com `=` (ex: `msg = "a = 10"`) | `Ctrl+2` (Align) | O `=` interno à string é **ignorado pelo lexer**; alinha apenas o `=` de atribuição |
| **TC-07** | Painel A com seleção + Painel B com seleção | `Ctrl+Alt+Shift+C` | Diff LCS direto entre as duas seleções com highlights correspondentes |
| **TC-08** | Painel A com seleção + Painel B **SEM** seleção | `Ctrl+Alt+Shift+C` | Janela deslizante localiza o bloco mais similar no Painel B e aplica o realce nos dois |
| **TC-09** | Apenas 1 painel aberto no editor | `Ctrl+Alt+Shift+C` | Log: `"⚠ [DIFF] Nenhum painel oposto aberto para comparar."` |
| **TC-10** | Limpeza de Realces de Comparação | `Ctrl+Alt+Shift+X` | Remove 100% dos highlights dos buffers de ambos os painéis |

---

# 📊 ETAPA 2: CRITÉRIOS DE AVALIAÇÃO & SLAs (MA'AT & HORUS)

1. **Latência de Renderização (< 16.6ms / 60 FPS):** Os hooks `DocView:draw_line_body` e `draw_line_gutter` devem operar em tempo $O(1)$ consultando a tabela memoizada de diff, sem recalcular comparações no pipeline de desenho.
2. **Teto de Tempo do Block Matcher (< 8.0ms):** A varredura de janela deslizante no Painel B deve concluir em menos de 8ms em arquivos de até 10.000 linhas via amostragem adaptativa.
3. **Isolamento de Exceções (Zero-Crash Guarantee):** Toda manipulação de buffer e cálculo de diff é executada sob `pcall`. Em caso de erro, o texto original é preservado e o incidente é catalogado.
4. **Conformidade de Tamanho (< 50KB):** O arquivo gerado possui ~18KB, perfeitamente dentro do limite estrito do ProDeNov.

---

# 🩺 ETAPA 3: SISTEMA DE DIAGNÓSTICO E AUTO-AUDITORIA

O módulo exporta o barramento `_DOXOADE_COMPARATOR_STATE` e métricas de diagnóstico consumíveis pelos relatórios do **Typhon** e **Ma'at**:

* **Métricas Vivas:**
  * `total_diffs_performed`: Quantidade de comparações executadas.
  * `last_match_latency_ms`: Tempo em milissegundos da última varredura no painel oposto.
  * `active_highlighted_lines`: Contagem de linhas sob realce nos documentos.
* **Auto-Purga:** Ao fechar qualquer documento envolvido ou alternar o arquivo ativo, os estados de diff daquele documento são liberados da memória (garbage collector safe).

---

