# 📜 BLITZPLAN — ARQUITETURA GRÁFICA SOBERANA & PIPELINE ZERO-STUTTER (DOXLY V22.0)

**Documento de Engenharia:** `doxoade/commands/lite_xl_systems/blitzplan_gpu_zero_stutter.md`  
**Protocolo de Conformidade:** ProDeNov 1.2.1 | PASC-6.1 (Alta Performance / Zero-Freeze)  
**Panteões Mobilizados:** Horus (Observabilidade Gráfica), Hefesto (Construção/Batching), Vulcan (C Nativo/SDL_Thread) e Chronos (Time-Slicing & Pacing)  
**Data:** 18/09/2026 | **Teto de Arquivo:** `< 50 KB` por módulo

---

## 1. Contexto e Diagnóstico Profundo (W5 / As 5 Perguntas ProDeNov)

* **O quê (What):**  
  Reforma estrutural do pipeline de desenho do Doxly/Lite XL para extinguir o *stuttering* (engasgos de 67ms a 89ms no `Render/SDL2`), substituindo o desenho ingênuo imediato (*Immediate Mode*) com *alpha-blending* dinâmico por um pipeline de **Batch Rendering**, **Delta Time ($\Delta t$)**, isolamento de processos via **`SDL_Thread` (Vulcan)** e **Time-Slicing universal (Khonsu)**.
* **Quem (Who):**  
  * *Núcleo Gráfico:* `10_forensic_engine.lua`, `04_color_and_search_highlight.lua`, `03b_tab_compact_staircase.lua`, `06_tree_manager.lua`, `13_toolbar_doxoade.lua`.
  * *Backend C Nativo:* `doxoade/tools/vulcan_systems/` (Bridges SDL2/C).
  * *Orquestrador Python:* `profiler_engine.py` e `cmd_lite_xl.py`.
* **Onde (Where):**  
  No hotpath contínuo de renderização do SDL2 (`RootView:draw`, `Node:draw`, `DocView:draw`), nas rotinas de background e no swapchain de vídeo.
* **Quando (When):**  
  A cada frame de renderização e durante a execução de tarefas pesadas em segundo plano (indexação, linter, profiler de 1Hz).
* **Quanto (How much):**  
  * **Meta Inviolável de Render:** Reduzir `Render/SDL2` de **84.15ms** para **$< 8.0ms$** em tela cheia.
  * **Meta de Fluidez:** Elevar o frame rate de 3.0 FPS para **60.0 FPS fluidos** com **Jitter $< 1.5ms$**.
  * **Tamanho de Código:** Manter todos os templates abaixo do teto de **50 KB**.
* **Por quê (Why):**  
  A lógica Lua já foi otimizada para 1.2ms, mas o usuário experimenta microtravamentos (*stuttering*) perceptíveis porque o renderizador SDL2 e o `rencache` entram em colapso tentando recalcular centenas de retângulos translúcidos e executando tarefas pesadas na mesma thread da interface.
* **Origem & Consequências (Origin & Consequences):**  
  A introdução de dezenas de novos recursos visuais (guias de indentação, badges no rodapé, tints de diff, terminal integrado) gerou *Cache Thrashing* no `rencache` (o cache incremental foi invalidado, forçando redesenho completo de hardware a cada frame).

---

## 2. Taxonomia de Complexidade (Regra 0.0 – 0.4 ProDeNov)

| Vetor de Complexidade | Classificação | Mitigação ProDeNov |
| :--- | :---: | :--- |
| **0.0 Thirdparty (SDL2 & Lite XL Core)** | **Alta** | Não alterar o binário C do Lite XL diretamente; intervir via hooks Lua blindados e bridges C compilados pelo Vulcan. |
| **0.1 Devflow** | **Média** | Garantir que o `--no-khonsu` (plain mode) continue funcional para testes rápidos sem depender de compilação AOT. |
| **0.2 Rabbit Hole** | **Alta** | Não tentar reescrever o SDL2. Atacar a causa raiz: reduzir a quantidade de comandos enviados ao `rencache` e evitar alpha blending dinâmico. |
| **0.3 Sensibilidade (FPS & Jitter)** | **Crítica** | Qualquer função chamada por linha ou por caractere no `draw` deve ser puramente $O(1)$ sem alocação de tabelas na heap. |
| **0.4 Revisitar** | **Média** | Centralizar o cálculo de cores sólidas e métricas para que novos plugins herdem a alta performance automaticamente. |

---

## 3. Arquitetura da Solução em 3 Capítulos

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      CAPÍTULO 1: DECOMPOSIÇÃO FORENSE TOTAL                     │
│  • Instrumentação isolada da TreeView lateral, StatusView, Toolbar e Shelf.     │
│  • Desacoplamento da medição de Swap de Hardware (SDL_RenderPresent).           │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
┌────────────────────────────────────────▼────────────────────────────────────────┐
│                   CAPÍTULO 2: ENGENHARIA ZERO-STUTTER & RENCACHE                │
│  • Pre-Multiplied Solid Baking: Extirpar alpha blending em hotpaths de linha.   │
│  • Batch Rendering de Guias e Gutter: Agrupamento contíguo de retângulos.       │
│  • Delta Time (Δt) Frame Pacing: Animações independentes de taxa de quadros.    │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
┌────────────────────────────────────────▼────────────────────────────────────────┐
│              CAPÍTULO 3: TIME-SLICING & MULTITHREADING C (VULCAN)               │
│  • Khonsu Hard Deadline: Tarefa pesada cede controle se exceder 2.0ms.          │
│  • Worker em Thread C Real (SDL_CreateThread via Vulcan): I/O e telemetria      │
│    despejados em segundo plano sem tocar na thread de renderização da UI.       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Especificação dos Capítulos de Execução (Regra 1.2.1 ProDeNov)

---

### 📖 CAPÍTULO 1: Decomposição Forense Total da Interface

#### Problema:
Atualmente, `GPU / Swap` agrupa cegamente a TreeView, StatusView, ShelfHub e a troca de buffers do SDL2. Não sabemos com precisão cirúrgica quem está consumindo os 69ms.

#### 🔹 Plano A (Principal — Sondas Cirúrgicas por Componente)
1. Injetar sondas em `10_forensic_engine.lua` para medir individualmente:
   * `TreeView:draw` (árvore lateral).
   * `StatusView:draw` (barra de status e badges do rodapé).
   * `RootView:draw` overhead residual (molduras, divisores e background).
   * `rencache.end_frame` / GPU Swap real.
2. A telemetria passará a exibir o raio-x completo:
   ```text
   ■ CUSTO REAL POR SUBSISTEMA GRÁFICO (Frame):
     ├─ Abas de Arquivo (Tabs) :  1.58ms
     ├─ Corpo do Código (Doc)  :  2.42ms
     ├─ Marcadores do Gutter   :  0.00ms
     ├─ Árvore Lateral (Tree)  :  X.XXms
     ├─ Barra de Status (HUD)  :  X.XXms
     └─ GPU / Swap de Buffers  :  X.XXms
   ```

#### 🔹 Plano B (Fallback — Sonda de Top-Level Views)
Se o hook direto nos métodos das views falhar devido a metatables protegidas, medir os filhos diretos de `core.root_view.root_node` iterando a lista de views visíveis.

#### 🔹 Plano C (Contingência — Profiling por Amostragem Temporal)
Ativar a medição por amostragem acumulada apenas a cada 60 frames para não inserir overhead de instrumentação.

---

### 📖 CAPÍTULO 2: Engenharia Anti-Stutter & Blindagem do Rencache

#### Problema:
O uso de transparências com canal alfa dinâmico (`color = {r, g, b, 30}`) invalida o cache do `rencache` e obriga a CPU/GPU a fazer mistura de cores (*alpha blending*) pixel a pixel em centenas de retângulos a cada frame.

#### 🔹 Plano A (Principal — Pre-Multiplied Solid Color Baking)
1. **Solid Color Baking:** Extirpar o canal alfa de todos os hotpaths de renderização. 
   * As cores translúcidas de guias de indentação e tints de diff serão pré-misturadas com a cor de fundo do tema no momento da inicialização ou troca de tema (`mix_color(bg, accent, alpha)`), gerando uma cor sólida RGB opaca (`alpha = 255`).
2. **Reativação do Rencache Cache-Hit:**
   * Retângulos com cores sólidas idênticas e posições fixas geram **Cache Hit imediato no `rencache.c`**, reduzindo o custo de envio para a GPU a praticamente **zero nanossegundos**.
3. **Delta Time ($\Delta t$) para Cursores e Animações:**
   * O piscar do cursor e transições visuais utilizarão `dt = os.clock() - last_time`, eliminando redesenhos contínuos desnecessários em repouso.

#### 🔹 Plano B (Fallback — Teto Dinâmico de Linhas Visíveis)
Se o cálculo de cores sólidas não reduzir a carga suficientemente em buffers com mais de 50.000 linhas, aplicar *Viewport Culling* estrito: desenhar apenas as linhas estritamente contidas entre `view.scroll.y` e `view.scroll.y + view.size.y`, ignorando linhas fora da visão.

#### 🔹 Plano C (Contingência — Modo Gráfico de Baixo Consumo / Eco Mode)
Se a máquina estiver operando em hardware integrado com latência $> 40\text{ms}$, desativar automaticamente as guias de indentação de 1px mantendo apenas os recuos de texto.

---

### 📖 CAPÍTULO 3: Time-Slicing Universal & Multithreading C Nativo

#### Problema:
Tarefas de background (como a corrotina de 1Hz do Profiler, a checagem de integridade de arquivos do linter e a gravação de telemetria) rodam na mesma thread do SDL2. Quando executam `io.open()` ou iteram tabelas grandes, o redesenho congela por até 60ms (*Micro-Stuttering*).

#### 🔹 Plano A (Principal — Khonsu Hard Deadline + Despejo em Lote)
1. **Orçamento Temporal Rígido no Khonsu:**
   * Toda corrotina de background deve consultar `Khonsu.should_yield(t0, 1.5)`. Se o processamento passar de **1.5ms**, a corrotina é obrigada a ceder (`coroutine.yield()`).
2. **I/O em Lote Fora do Hotpath:**
   * O despejo de JSONs (`profiler_telemetry.json`, `boot_telemetry.json`) só pode ocorrer em momentos em que o editor estiver comprovadamente em repouso (`now - last_user_activity > 0.5s`), nunca durante rolagem ou digitação ativa.

#### 🔹 Plano B (Fallback — Vulcan C Threading via `SDL_CreateThread`)
Para tarefas massivas (como busca global regex em todo o projeto ou compilação de imagens RLE):
* Delegar o trabalho para um worker nativo compilado pelo Vulcan que roda em uma thread real do sistema operacional via `SDL_CreateThread`.
* A thread da interface gráfica continua desenhando a 60 FPS estáveis enquanto o worker C processa os arquivos em paralelo no outro núcleo da CPU.

#### 🔹 Plano C (Contingência — Processo Filho com Pipe)
Executar o trabalho pesado via processo filho Python assíncrono (Hermes), lendo os dados prontos via pipe não-bloqueante.

---

## 5. Roteiro de Implementação e Testagem (RIT / Ritual ProDeNov)

```text
  [ RITUAL DE DESENVOLVIMENTO NOVÍSSIMO ]
  1. Discussão & Alinhamento Arquitetural (Este documento)
  2. Implementação do Capítulo 1 (Decomposição fina das sondas de GUI)
  3. Teste Empírico com `doxoade doxly profile -m test`
  4. Implementação do Capítulo 2 (Solid Color Baking & Eliminação de Alpha Thrashing)
  5. Teste Empírico & Verificação de Redução dos 69ms
  6. Implementação do Capítulo 3 (Time-Slicing Rígido & I/O Diferido)
  7. Prova de Não-Regressão com `doxoade regret`
```

### 📋 Tasklist Detalhada de Engenharia

- [ ] **Capítulo 1: Sondas de Subsistemas Restantes (`10_forensic_engine.lua`)**
  - [ ] Instrumentar `TreeView.draw` para expor a fatia de tempo da árvore de arquivos.
  - [ ] Instrumentar `StatusView.draw` para expor a fatia de tempo da barra inferior.
  - [ ] Atualizar `profiler_engine.py` para renderizar `TreeView` e `StatusView` na tabela.
- [ ] **Capítulo 2: Solid Color Baking & Blindagem Rencache (`04_color...` e `03_tab...`)**
  - [ ] Substituir tints com alpha em guias de indentação por cores pré-mescladas sólidas (`alpha = 255`).
  - [ ] Substituir cores de diff translúcidas por cores sólidas contrastadas.
  - [ ] Medir a queda imediata do tempo de GPU/Swap no Profiler.
- [ ] **Capítulo 3: Time-Slicing Rígido no Khonsu e Profiler**
  - [ ] Impor teto de 1.5ms em todas as corrotinas de segundo plano.
  - [ ] Bloquear escrita de telemetria no disco enquanto o usuário estiver interagindo (`is_user_active`).
- [ ] **Capítulo 4: Prova de Não-Regressão & Homologação**
  - [ ] Validar com `doxoade regret` (assegurar zero regressões de UX).
  - [ ] Confirmar FPS $\ge 55.0$ e latência de frame $< 16.6\text{ms}$ em rolagem contínua.

---

## 6. Próximo Passo Imediato

Seguindo a **Regra 5.6.2 do ProDeNov** (*um passo de cada vez*), o plano está aprovado para iniciarmos pelo **Capítulo 1 (Instrumentação da TreeView e StatusView no `10_forensic_engine.lua` para dissecar os 69ms)**?

---

# 📜 CAPÍTULO 1: DECOMPOSIÇÃO FORENSE TOTAL DA GPU & SUBSISTEMAS DE GUI
**Subsistema Alvo:** `doxoade/commands/lite_xl_systems/template/10_forensic_engine.lua` e `doxoade/tools/lua_systems/profiler/profiler_engine.py`  
**Protocolo:** ProDeNov 1.2.1 | PASC-6.1 (Alta Performance / Zero-Freeze) | W5  
**Panteões:** Horus (Observabilidade Gráfica) & Chronos (Cronometria de Microssubdivisões)  
**Meta do Capítulo:** Destrinchar a caixa-preta de **`67ms ~ 89ms`** atualmente rotulada como `GPU / Swap de Buffers` em métricas empíricas isoladas para cada subsistema visual e de hardware.

---

## 1. Contexto e Diagnóstico Profundo (W5 / As 5 Perguntas)

* **O quê (What):**  
  Implementar sondas analíticas de alta resolução no `10_forensic_engine.lua` para fatiar o tempo gasto no `RootView:draw` que hoje é agrupado cegamente no `frame_gpu`. Medir individualmente:
  1. **`TreeView` (Árvore de Arquivos lateral):** Custo de desenhar diretórios, nós, indentação e ícones.
  2. **`StatusView` (Barra de Status inferior):** Custo de desenhar badges de status, seleções, contadores e divisores.
  3. **`CommandView` (Prompt de Comandos):** Custo de enquadramento da caixa de entrada e listas de sugestão suspensas.
  4. **`RootView Structural`:** Desenho das molduras de nós (`Node:draw`), divisores (`divider_size`) e fundo de painéis.
  5. **`Swap Real de Hardware (VSync / Driver)`:** Medição isolada do tempo gasto no `renderer.present()` / `rencache.end_frame()` (onde a thread principal espera o monitor e o compositor DWM do Windows).
* **Quem (Who):**  
  Desenvolvedores e mantenedores que precisam saber se os 70ms vêm de excesso de nós na TreeView, sobrecarga de badges na barra inferior, ou se a thread está bloqueada pelo VSync do monitor de 60Hz.
* **Onde (Where):**  
  * `doxoade/commands/lite_xl_systems/template/10_forensic_engine.lua` (Sondas Lua de frame).
  * `doxoade/tools/lua_systems/profiler/profiler_engine.py` (Exibição da decomposição no terminal e Advisor).
* **Quando (When):**  
  Em tempo real durante cada frame de renderização ($O(1)$ sem alocação de tabelas).
* **Quanto (How much):**  
  * **Overhead Máximo das Sondas:** $< 0.05\text{ms}$ por frame (apenas leitura de `os.clock()` nativo).
  * **Limite de Arquivos:** Manter `10_forensic_engine.lua` $< 50\text{ KB}$ e `profiler_engine.py` $< 50\text{ KB}$.
* **Por quê (Why):**  
  Otimização às cegas gera frustração (*development hell*). Não podemos tentar otimizar a GPU se os 69ms estiverem sendo gastos na TreeView desenhando 30 pastas, ou na StatusView formatando strings de badges. Precisamos de dados incontestáveis.
* **Origem & Consequências (Origin & Consequences):**  
  A conta original era uma subtração ingênua: $\text{frame\_gpu} = \max(0, \text{total} - (\text{tabs} + \text{doc} + \text{gutter}))$. Qualquer nova GUI adicionada caía na fatia de "GPU", distorcendo o laudo do Chronos Advisor.

---

## 2. Taxonomia & Sistema de Diagnóstico (Anti-Development Hell)

Para evitar congelamentos ou impacto na taxa de 60 FPS, o Capítulo 1 nasce com salva-guardas estritas:

| ID de Diagnóstico | Alvo / Vetor | Condição de Falha | Mitigação ProDeNov |
| :--- | :--- | :--- | :--- |
| **`DIAG-PROBE-RECURSION`** | Hooks em Views | View chamando outra View e medindo tempo 2x | Flags locais booleanas de contexto (`_in_tree_draw`, `_in_status_draw`) impedindo contagem duplicada. |
| **`DIAG-ORPHAN-VIEW`** | TreeView ou StatusView ausentes | Plugin desativado ou View nula no boot | Checagem prévia `if ViewClass and ViewClass.draw then` com fallback $O(1)$. |
| **`DIAG-CLOCK-PRECISION`** | `os.clock()` no Windows | Resolução de timer do Windows (1ms a 15ms) | Amostragem acumulada por janela deslizante exponencial (EMA) com proteção contra deltas negativos. |

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Sondas Cirúrgicas por Componente e Isolamento de Swap)
1. **Instrumentação de Views Modulares:**
   * Injetar hooks leves em:
     * `TreeView.draw` (via módulo `plugins.treeview` ou `core.treeview`).
     * `StatusView.draw` (via `core.statusview`).
     * `CommandView.draw` (via `core.commandview`).
   * Medir tempo delta de cada componente em microssegundos:
     $$\Delta t = (\text{os.clock}() - t_0) \times 1000$$
2. **Isolamento do Swap de Vídeo:**
   * No final de `RootView:draw`, descontar os tempos acumulados de todos os componentes medidos:
     $$\text{componentes\_totais} = \text{tabs} + \text{doc} + \text{gutter} + \text{tree} + \text{status} + \text{command}$$
     $$\text{swap\_real\_gpu} = \max(0, \text{t\_draw\_total} - \text{componentes\_totais})$$
3. **Persistência Suave no JSON (`profiler_telemetry.json`):**
   * Atualizar `Profiler.subsystems`:
     ```json
     "subsystems": {
       "tabs_ms": 1.58,
       "body_ms": 2.42,
       "gutter_ms": 0.00,
       "tree_ms": 3.10,
       "status_ms": 1.20,
       "rencache_ms": 32.50
     }
     ```
4. **Atualização do Visualizador Python (`profiler_engine.py`):**
   * Exibir a tabela detalhada com 6 subsistemas.
   * O Chronos Advisor emitirá laudos cirúrgicos: se a `TreeView` estiver pesada, ele recomendará *Viewport Culling*; se o `rencache_ms` estiver alto, ele prescreverá investigação de VSync.

### 🔹 Plano B (Fallback — Medição de Filhos de `core.root_view.root_node`)
* Caso os módulos da `TreeView` ou `StatusView` tenham metatables congeladas ou não permitam monkey-patching em runtime, o `RootView:draw` mede a iteração direta dos nós filhos (`self.root_node.a` e `self.root_node.b`), separando o painel esquerdo (Tree) do painel direito (Editores).

### 🔹 Plano C (Contingência — Isolamento Estático sem Hooks Adicionais)
* Se a instrumentação de múltiplas views introduzir qualquer perda de FPS perceptível ($> 0.2\text{ms}$), desativar as sondas de `StatusView` e `CommandView`, mantendo apenas a separação binária: **Árvore Lateral vs Painel Central vs Swap**.

---

## 4. Arquivos Impactados e Limite de Tamanho (< 50KB)

```
doxoade/
├── commands/lite_xl_systems/template/
│   └── 10_forensic_engine.lua   # [ATUALIZAR] Sondas de TreeView, StatusView e Swap (~24KB)
└── tools/lua_systems/profiler/
    └── profiler_engine.py       # [ATUALIZAR] Display dos 6 subsistemas e Advisor (~25KB)
```
*Ambos os arquivos respeitam rigorosamente a meta de tamanho do ProDeNov.*

---

## 5. Especificação Técnica da Engenharia

### 5.1. Estrutura dos Hooks no `10_forensic_engine.lua`
```lua
-- Variáveis voláteis do ciclo de frame (Zero alocação na heap)
local _frame_tabs_ms = 0.0
local _frame_body_ms = 0.0
local _frame_gutter_ms = 0.0
local _frame_tree_ms = 0.0
local _frame_status_ms = 0.0

-- Sonda da TreeView
pcall(function()
  local TreeView = require "plugins.treeview" or require "core.treeview"
  if TreeView and TreeView.draw then
    local orig = TreeView.draw
    TreeView.draw = function(self, ...)
      local t0 = os.clock()
      local res = orig(self, ...)
      _frame_tree_ms = _frame_tree_ms + ((os.clock() - t0) * 1000)
      return res
    end
  end
end)

-- Sonda da StatusView
pcall(function()
  local StatusView = require "core.statusview"
  if StatusView and StatusView.draw then
    local orig = StatusView.draw
    StatusView.draw = function(self, ...)
      local t0 = os.clock()
      local res = orig(self, ...)
      _frame_status_ms = _frame_status_ms + ((os.clock() - t0) * 1000)
      return res
    end
  end
end)
```

### 5.2. Cálculo no `RootView:draw` com Média Móvel Exponencial (EMA)
```lua
function RootView:draw(...)
  _frame_tabs_ms = 0.0
  _frame_body_ms = 0.0
  _frame_gutter_ms = 0.0
  _frame_tree_ms = 0.0
  _frame_status_ms = 0.0

  local t0 = os.clock()
  original_rootview_draw(self, ...)
  local t_draw_total = (os.clock() - t0) * 1000

  local measured = _frame_tabs_ms + _frame_body_ms + _frame_gutter_ms + _frame_tree_ms + _frame_status_ms
  local frame_gpu_swap = math.max(0, t_draw_total - measured)

  -- EMA Suave (70% histórico / 30% frame atual)
  Profiler.subsystems.tabs_ms    = math.floor((Profiler.subsystems.tabs_ms * 0.7 + _frame_tabs_ms * 0.3) * 100) / 100
  Profiler.subsystems.body_ms    = math.floor((Profiler.subsystems.body_ms * 0.7 + _frame_body_ms * 0.3) * 100) / 100
  Profiler.subsystems.gutter_ms  = math.floor((Profiler.subsystems.gutter_ms * 0.7 + _frame_gutter_ms * 0.3) * 100) / 100
  Profiler.subsystems.tree_ms    = math.floor((Profiler.subsystems.tree_ms * 0.7 + _frame_tree_ms * 0.3) * 100) / 100
  Profiler.subsystems.status_ms  = math.floor((Profiler.subsystems.status_ms * 0.7 + _frame_status_ms * 0.3) * 100) / 100
  Profiler.subsystems.rencache_ms= math.floor((Profiler.subsystems.rencache_ms * 0.7 + frame_gpu_swap * 0.3) * 100) / 100

  Profiler.cycle.last_draw_ms = t_draw_total
  -- ...
end
```

---

## 6. Roteiro de Implementação e Testagem (RIT / Ritual ProDeNov)

### 📋 Tasklist do Capítulo 1
- [ ] **Etapa 1.1: Injeção das Sondas de GUI (`10_forensic_engine.lua`)**
  - [ ] Adicionar acumuladores `_frame_tree_ms` e `_frame_status_ms`.
  - [ ] Instalar hooks em `TreeView.draw` e `StatusView.draw` protegidos com `pcall`.
  - [ ] Atualizar `RootView:draw` para descontar `tree_ms` e `status_ms` do residual.
  - [ ] Exportar `tree_ms` e `status_ms` no bloco `"subsystems"` do JSON.
- [ ] **Etapa 1.2: Atualização do Visualizador Python (`profiler_engine.py`)**
  - [ ] Atualizar a tabela `■ CUSTO REAL POR SUBSISTEMA GRÁFICO` com as linhas de Árvore e Barra de Status.
  - [ ] Ajustar o `ChronosAdvisor` para analisar se a Árvore ou a Barra de Status estão estourando o orçamento de 2ms.
- [ ] **Etapa 1.3: Deploy e Prova Empírica**
  - [ ] Executar `doxoade doxly deploy test --no-khonsu`.
  - [ ] Executar `doxoade doxly profile -m test`.
  - [ ] **Critério de Aceite (DoD):** A soma de todos os subsistemas deve bater com o `Render/SDL2` total, e o residual de GPU/Swap deve refletir apenas o custo de hardware.

---

O plano do **Capítulo 1** está estruturado. Se aprovado, partiremos para a **Etapa 1.1** no código.
