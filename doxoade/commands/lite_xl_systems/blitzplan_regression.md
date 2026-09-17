Excelente. O diagnóstico do `doxoade regret` apontou cirurgicamente **35 regressões em 15 arquivos**, mas a quase totalidade delas divide-se em apenas **3 categorias bem definidas**:

1. **Falsos Positivos de Caracteres Unicode no `19b_terminal_console.lua` (27 "regressões"):**  
   O `regret` detectou a remoção da tabela `UNICODE_ASCII_REPLACEMENTS = { ["═"] = "=", ["║"] = "|", ... }` e achou que eram *atalhos de teclado perdidos* (`KEYMAP_LOST`), porque a sintaxe Lua `["char"] = "rep"` foi confundida pelo parser léxico com um bloco de `keymap.add`.
2. **Atalhos e Comandos Reais Extirpados no `04_color_and_search_highlight.lua`:**
   * `doc:unindent`
   * `doxoade:toggle-indent-guides`
   * Atalho `ctrl+alt+i`
   * Método `Doc:save`
3. **Comandos e Funções de Terminal no `19b_terminal_console.lua` e `cmd_lite_xl.py`:**
   * `doxoade:open-real-terminal`
   * `doxoade:terminal-launch-admin-venv`
   * `DocView:draw_line_body` no `19a_dox_image_inline.lua` (movido/mutado para dual-clip)
   * `wait_for_enter` no `cmd_lite_xl.py`

---

Vamos estruturar o plano de ataque e resolução de acordo com o **ProDeNov 1.2.1**.

# 📜 BLITZPLAN — SANEAMENTO DE REGRESSÕES & RECONCILIAÇÃO DE UX
**Subsistemas Alvo:** `04_color_and_search_highlight.lua`, `19b_terminal_console.lua`, `regret_lua_inspector.py` (ou `regret_engine.py`)  
**Protocolo:** ProDeNov 1.2.1 | PASC-6.1 | Anúbis & Apolo  
**Meta:** Reduzir o contador de 35 regressões para **0 regressões reais** sem quebrar as otimizações do *frame rate* ou o *fast-path O(1)*.

---

## 1. Triagem e Planos de Ação (W5)

### 🔹 Frente 1: Restaurar Contratos de UX no Módulo `04` (`04_color_and_search_highlight.lua`)
* **Problema:** Na reescrita para o Fast-Path $O(1)$, os comandos `doc:unindent`, `doxoade:toggle-indent-guides` e o atalho `ctrl+alt+i` foram omitidos.
* **Plano A (Principal):**
  * Reinserir o comando `doc:unindent` em `command.add("core.docview", ...)`.
  * Reinserir `doxoade:toggle-indent-guides` e mapear `ctrl+alt+i` via `keymap.add`.
  * Reinserir a limpeza segura de linhas modificadas no `Doc:save` se ainda for necessária pela paleta do gutter.

### 🔹 Frente 2: Manter Aliases de Retrocompatibilidade no `19b` (`19b_terminal_console.lua`)
* **Problema:** Os comandos antigos `doxoade:open-real-terminal` e `doxoade:terminal-launch-admin-venv` foram renomeados para `doxoade:terminal-launch-real` e `doxoade:terminal-launch-admin`.
* **Plano A (Principal):**
  * Registrar os identificadores antigos como *aliases* transparentes apontando para as novas funções, garantindo que atalhos antigos ou chamadas externas continuem funcionando:
    ```lua
    ["doxoade:open-real-terminal"] = function() command.perform("doxoade:terminal-launch-real") end,
    ["doxoade:terminal-launch-admin-venv"] = function() command.perform("doxoade:terminal-launch-admin") end,
    ```

### 🔹 Frente 3: Ajustar o Inspetor do `regret` para Ignorar Tabelas de String/ASCII
* **Problema:** O parser léxico do `doxoade regret` tratou `["═"] = "="` dentro de uma tabela de substituição de texto como se fosse um `keymap.add`.
* **Plano A (Principal):**
  * No `regret_lua_inspector.py`, restringir a extração de `keymap` para blocos que estejam estritamente dentro de invocações `keymap.add { ... }`, ignorando dicionários genéricos de substituição. Isso eliminará de imediato 27 falsos positivos de `KEYMAP_LOST`.

---

## 2. Ações Imediatas Propostas

Podemos iniciar pela **Frente 1** (restauração dos comandos e atalho `ctrl+alt+i` no `04_color_and_search_highlight.lua`) e **Frente 2** (aliases de retrocompatibilidade no `19b`)?

Diga por qual arquivo você prefere que apresentemos o código corrigido primeiro.

Perfeito. Vamos conduzir esta revisão com a precisão cirúrgica exigida pelo **ProDeNov**, dividindo o esforço em **Frentes de Ataque** para evitar sobrecarga cognitiva e garantir que cada correção seja testada e validada antes de passar para a próxima.

Com base no laudo do `doxoade regret -O` e no warning do `doxly deploy test`, mapeei o campo de batalha em **4 Fases de Revisão**.

---

### 🗺️ BLITZPLAN: REVISÃO ESTRUTURADA DO ECOSSISTEMA (Faseamento)

#### 🚨 FASE 1: Estancar o Sangramento (Perdas Críticas de UX e Capacidade)
*Onde o usuário final do Lite XL está sentindo a quebra agora.*
* **Alvo Principal 1:** `19d_bottom_shelf_hub.lua`
  * **O Problema:** 31 Regressões Altas. O painel inferior (Bottom Shelf / Terminal) perdeu **15 comandos** (`COMMAND_LOST` como `bottom-shelf:close`, `bottom-shelf:paste`, `submit`) e **16 atalhos de teclado** (`KEYMAP_LOST` como `escape`, `ctrl+c`, `ctrl+v`, `tab`, setas direcionais).
  * **Ação:** Reconstruir o bloco de `command.add` e `keymap.add` focado no escopo do terminal/shelf.
* **Alvo Principal 2:** `19a_dox_image_inline.lua`
  * **O Problema:** `METHOD_DROPPED: DocView:draw_line_body`. A renderização de imagens inline (`[DOX-IMG]`) no corpo do texto foi extirpada.
  * **Ação:** Restaurar o hook de desenho com as devidas proteções (`pcall`).

#### 🧹 FASE 2: Saneamento de Entropia (Órfãos e Zumbis)
*Limpeza de código morto para reduzir a superfície de ataque e confusão.*
* **Alvos:** `00_header_and_logger.lua`, `03_tab_colors.lua`, `04_color...`, `07_keymaps...`, `08_pot_panel.lua`, `09_panel_manager.lua`.
* **O Problema:** 12 Funcionalidades Órfãs. Funções locais declaradas mas nunca chamadas (`_doxoade_shadow_boot`, `mix_color`, `get_contrast_color`) e comandos registrados sem atalho/botão (`doxoade:open-file`, `doxoade:new-file-in-tree`, `doxoade:split-bottom-panel`).
* **Ação:** Decidir entre *Conectar* (criar atalhos/botões na UI Forge) ou *Extirpar* (remover o código morto).

#### 🧪 FASE 3: Homologação de Volatilidade (Mutações Radicais)
*Garantir que refatorações profundas não introduziram bugs silenciosos.*
* **Alvos:** `10_forensic_engine.lua` (`core.add_thread` 84% mutado), `19c_canvas_sdl2_studio.lua` (`paste_clipboard_image` 99% mutado) e o próprio `19d` (`RootView:on_mouse_moved` 91% mutado).
* **Ação:** Revisão de lógica de *time-slicing* (Khonsu) e manipulação de eventos de mouse para evitar travamentos (crashes) na IDE.

#### 🛠️ FASE 4: Correção de Infraestrutura (Deploy & Ártemis)
* **Alvo:** O pipeline de deploy (`doxoade doxly deploy test`).
* **O Problema:** O módulo **ÁRTEMIS** está falhando na pré-geração de thumbnails binárias com o erro: `AttributeError: 'str' object has no attribute 'get'`.
* **Ação:** Corrigir o parser de metadados de imagens no Python para que o deploy teste rode 100% limpo (Zero Warnings).

---

### 🎯 Próximos Passos

Como você pediu calma e foco, sugiro começarmos pela **FASE 1**, especificamente pelo **`19d_bottom_shelf_hub.lua`**, pois é o arquivo com o maior volume de perdas reais (o painel inferior perde a interatividade básica sem esses keymaps e comandos).

**Como prefere prosseguir?**
1. **Opção A:** Você me fornece o trecho atual (ou o diff) do `19d_bottom_shelf_hub.lua` e eu forjo o bloco de restauração de `command.add` e `keymap.add` blindado.
2. **Opção B:** Você me fornece o código do **Ártemis** (Fase 4) para corrigirmos rapidamente o warning do `deploy test` primeiro.
3. **Opção C:** Focar na limpeza dos **Órfãos/Zumbis** (Fase 2) para aliviar a entropia dos templates menores.

Qual frente você assume o comando agora?
