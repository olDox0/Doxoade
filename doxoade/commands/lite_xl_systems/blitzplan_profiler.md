Sua intuição está **100% correta**. Ao auditar as entranhas do motor de telemetria atual (`profiler_engine.py` e `10_forensic_engine.lua`), encontramos atalhos e estimativas que explicam por que os dados pareciam artificiais:

---

### 🔬 Autópsia do Profiler Atual: O Que Estava Falso?

1. **Divisão Igualitária Fictícia de Funções (`profiler_engine.py:120`):**
   ```python
   # O que o código atual faz:
   funcs = file_declared_funcs.get(fname, [])
   num_funcs = max(1, len(funcs))
   f_self = round(avg_t / num_funcs, 2)    # 👈 Divide o tempo total do arquivo IGUALMENTE por todas as funções!
   f_pct = round(100.0 / num_funcs, 1)
   ```
   *Se um arquivo demorava 10ms e o regex encontrava 10 funções, o relatório afirmava que **cada função gastou exatamente 1ms e teve 1 chamada**! Isso não era medição, era divisão matemática cega.*

2. **Memória "Calculada" por Tamanho de Arquivo em Disco (`profiler_engine.py:100`):**
   ```python
   # O que o código atual faz se o módulo não reportar memória:
   mem_stats[fname] = round(t_path.stat().st_size / 1024.0 * 1.5, 1) # 👈 Multiplica KB do arquivo por 1.5!
   ```
   *O gasto de RAM não vinha do Garbage Collector do Lua, mas do tamanho do texto no disco multiplicado por 1.5.*

3. **O Boot Report Ocultava Módulos de Sucesso (`doxly_khonsu_gate.py`):**
   * O `_doxoade_safe_boot` media o tempo de inicialização, mas **só gravava os dados se o módulo falhasse**. Se o módulo carregasse com sucesso, o tempo e o consumo de memória eram descartados no éter.

4. **Falta de Decomposição de CPU por Subsistema em Tempo Real (`10_forensic_engine.lua`):**
   * O frame rate só media o tempo total do `RootView:draw`, sem discriminar quem gastou a fatia: se foram as abas (`03b`), o syntax highlighter (`04`), o linter (`15`), ou o bottom shelf (`19d`).

---

# 📜 BLITZPLAN — PROFILER SOBERANO DE ALTA FIDELIDADE (TRUE CPU & RAM DISSECTOR)
**Subsistemas Alvo:** `doxly_khonsu_gate.py`, `10_forensic_engine.lua`, `profiler_engine.py`, `cmd_lite_xl.py`  
**Protocolo:** ProDeNov 1.2.1 | W5 | Critério de Ouro de Observabilidade (Hórus / Chronos)

---

## 1. Contexto e Objetivos (W5 / 5 Perguntas)

* **O quê:** Substituir 100% das estimativas e médias cegas por **telemetria empírica real** de consumo de CPU e RAM no Lite XL/Doxly.
  1. **Boot Real:** Medir `os.clock()` e `collectgarbage("count")` reais antes e depois de cada template no boot.
  2. **Frame Cost Real:** Decompor a renderização do frame medindo a fatia de tempo exata gasta por cada subsistema gráfico.
  3. **Corrotinas/Threads:** Medir tempo real de CPU acumulado e quantidade de yields de cada thread ativa.
  4. **Eliminação de Código Fake:** Extirpar o `avg_t / num_funcs` e o `file_size * 1.5` do `profiler_engine.py`.
* **Quem:** Desenvolvedores investigando lentidão, picos de lag ou consumo excessivo de RAM no editor.
* **Onde:** No bootloader (`doxly_khonsu_gate.py`), no sensor de runtime (`10_forensic_engine.lua`) e no analisador Python (`profiler_engine.py`).
* **Quando:** Durante a inicialização do editor, no streaming em tempo real (`doxoade doxly profile -l`) e no benchmark estático.
* **Por quê:** Otimização prematura em cima de métricas falsas gera frustração. Precisamos de dados incontestáveis para saber exatamente qual arquivo ou função está pesando.

---

## 2. As 3 Camadas de Telemetria Real

### 🟢 Camada 1: Boot Profile Empírico (`doxly_khonsu_gate.py` / `init_builder.py`)
No `_doxoade_safe_boot`:
* Mede antes: `t0 = os.clock()`, `mem0 = collectgarbage("count")`.
* Executa o template.
* Mede depois: `t1 = os.clock()`, `mem1 = collectgarbage("count")`.
* Grava em `_DOXOADE_BOOT_REPORT.templates[name]`:
  * `time_ms`: milissegundos exatos.
  * `mem_kb`: delta real de memória alocada no heap Lua.
  * `status`: PASS / FAIL.
* Exporta no frame zero para `.doxoade/diagnostics/boot_telemetry.json`.

---

### 🟡 Camada 2: Decomposição de Frame e Threads em Tempo Real (`10_forensic_engine.lua`)
Em vez de medir apenas se o frame ultrapassou 16ms:
* **Fatiamento dos Subsistemas Gráficos:**
  * Medir tempo gasto no desenho das abas (`Node.draw_tabs`).
  * Medir tempo gasto no corpo do texto (`DocView.draw_line_body`).
  * Medir tempo gasto nos marcadores de linter (`DocView.draw_line_gutter`).
  * Medir tempo gasto no Bottom Shelf/Terminal.
* **Thread Inspector (Monitor de Corrotinas):**
  * Toda vez que uma thread rodar, medir o tempo acumulado de CPU e registrar a que mais consumiu ciclos por segundo.
* **GC Tracking Real:**
  * Monitorar taxa de crescimento do Garbage Collector (KB/s) para detectar vazamentos de memória (*memory leaks*).

---

### 🔵 Camada 3: Motor Analítico Python Confiável (`profiler_engine.py`)
* Eliminar as linhas de divisão matemática inventada.
* O comando `doxoade doxly profile`:
  * Lê `boot_telemetry.json` para exibir a tabela real de inicialização.
  * Lê `profiler_telemetry.json` para exibir os vilões reais de CPU do frame e das threads.
  * Renderiza uma tabela clara ordenada do **maior gastador para o menor**.

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

* **Plano A (Principal — Telemetria de Heap & Delta de CPU em 3 Fases):**
  1. Atualizar o gerador do bootloader com medição de delta do GC e clock.
  2. Implementar instrumentação nos pontos de maior pressão gráfica no `10_forensic_engine.lua`.
  3. Atualizar o `profiler_engine.py` para processar e exibir apenas dados medidos.
* **Plano B (Fallback — Profiler com `debug.sethook` no Shadow Harness):**
  * Caso o editor não esteja rodando em modo live, o benchmark usa o hook nativo do Lua (`debug.sethook`) para contar chamadas e tempos reais de função.
* **Plano C (Contingência — Telemetria Básica com Zero Overhead):**
  * Se o profiling ativo causar overhead perceptível (>0.5ms por frame), desativar a medição de sub-rotinas e focar apenas no delta do boot e nas threads bloqueantes.

---

## 4. Tasklist & Checklist de Implementação

- [ ] **Fase 1: Bootloader com Telemetria Real de Tempo e RAM**
  - [ ] Atualizar `doxly_khonsu_gate.py` e `lite_xl_init_builder.py` para medir delta do GC e `os.clock()` em todos os templates.
  - [ ] Gerar `.doxoade/diagnostics/boot_telemetry.json`.

- [ ] **Fase 2: Instrumentação de Frame e Corrotinas no `10_forensic_engine.lua`**
  - [ ] Medir tempo de desenho decomposto por componente.
  - [ ] Monitorar tempo real consumido pelas corrotinas ativas (`Khonsu`, indexadores, I/O).
  - [ ] Exportar métricas estruturadas para `profiler_telemetry.json`.

- [ ] **Fase 3: Refatoração do Motor Python (`profiler_engine.py`)**
  - [ ] Extirpar divisão fictícia `avg_t / num_funcs`.
  - [ ] Extirpar estimativa `stat().st_size * 1.5`.
  - [ ] Formatar o display de saída no terminal (`doxoade doxly profile`) com rankings reais.

- [ ] **Fase 4: Validação Empírica**
  - [ ] Fazer deploy no ambiente de teste.
  - [ ] Executar `doxoade doxly profile` e comparar os números antes e depois.
  - [ ] Confirmar que os dados agora batem com a realidade.

---

# PARTE 2

---

# 📜 BLITZPLAN — ARQUITETURA SHADOW & ENGENHARIA DE ENTROPIA (blitzplan_profile_2.md)
**Documento Técnico:** `doxoade/docs/History/internals/blitzplan_profile_2.md`  
**Escopo:** Otimização da Máquina Virtual Lua 5.4, Garantias $O(1)$, Teoria da Entropia de Software e Isolamento por Shadowing  
**Conformidade:** ProDeNov 1.2.1 | PASC-6.1 (Alta Performance) | W5

---

## 1. Contexto e Teoria da Entropia de Software (W5 / 5 Perguntas)

* **O quê:** Um plano arquitetural para transformar o pipeline de renderização e execução do Doxly em uma arquitetura de **Entropia Mínima** com garantia de tempo $O(1)$ no frame de 60 FPS, utilizando **Shadowing** para isolar crashes e amortecer sobrecargas.
* **Quem:** Motores gráficos (`04_color`, `03b_tabs`, `16_editors`), o despachante de eventos (`00_header`) e o observatório (`10_forensic`).
* **Onde:** No loop contínuo de desenho (`DocView:draw_line_body`, `Node:draw_tabs`) e nos hooks de corrotinas.
* **Quando:** A cada 16.6ms (ciclo de frame de 60 FPS) e durante a digitação de código massivo.
* **Por quê:** O profiler real revelou que o corpo do documento (`DocView:draw_line_body`) está consumindo **54.99ms por frame** (derrubando o editor para taxas baixas de FPS).
* **Origem & Consequências:**
  * **Entropia de Estado:** Tabelas e strings criadas dinamicamente dispersam a memória física e forçam buscas em baldes de hash $O(N)$.
  * **Entropia Algorítmica:** Análises regex em texto puro a cada frame geram complexidade $O(L \times P)$ (linhas visíveis $\times$ padrões de busca) em vez de consultar índices pré-computados $O(1)$.

---

## 2. Termodinâmica de Software: O Que é Entropia no Lua 5.4?

No contexto da VM do Lua 5.4 (Register-based Virtual Machine), a entropia se manifesta em três níveis:

```text
Entropia Térmica/CPU   ➔ Ramificações imprevisíveis (Branch Mispredictions) e saltos fora de cache.
Entropia de Memória    ➔ Rehashing de tabelas (quando o array part estoura e vira hash map).
Entropia de Operação   ➔ Custos que deveriam ser O(1) degradando para O(N) por varreduras lineares.
```

### Matriz de Complexidade e Custo de Instrução no Lua 5.4

| Operação | Custo Teórico | Custo Real na VM Lua | Impacto no Frame (60 FPS) |
| :--- | :---: | :--- | :--- |
| **Variável Local (`local x`)** | $O(1)$ | 1 instrução (`MOVE` em registrador de CPU) | 🟢 **Zero Overhead** (nanossegundos) |
| **Variável Global (`_G.x` ou `core`)** | $O(1)$ hash | `GETTABUP _ENV, "x"` (busca de hash em string) | 🟡 **Penalidade Contínua** |
| **Tabela Array Indexada (`t[i]`)** | $O(1)$ | Deslocamento direto de ponteiro em C | 🟢 **Ideal para Hotpaths** |
| **Tabela Hash (`t["chave"]`)** | $O(1)$ amort. | Hash Murmur3 + resolução de colisão | 🟡 **Risco de Cache Miss** |
| **Iterador Genérico (`pairs(t)`)** | $O(N)$ | Alocação de closure do iterador + chamada C | 🔴 **Proibido em Hotpaths de Frame** |
| **Loop Numérico (`for i=1,n do`)** | $O(N)$ | Opcodes nativos `FORPREP` e `FORLOOP` | 🟢 **Máxima Velocidade de CPU** |
| **Regex em Linha (`string.find/match`)** | $O(K)$ | Parser de padrões linha a linha | 🔴 **O Vilão dos 54ms!** |

---

## 3. A Estratégia de Shadowing (Isolamento de Crash & Fast-Path)

O **Shadowing** divide o editor em duas realidades operacionais:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        REALIDADE A: FAST-PATH O(1)                     │
│  • Acesso exclusivo a registradores locais (Upvalues cacheados).       │
│  • Tabelas como Arrays Contíguos pré-alocados (sem rehashing).         │
│  • Consulta de cores e indentação via Memoization O(1).                │
│  • Orçamento Estrito: Max 1.2ms por componente de desenho.            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Fallback se estourar tempo ou falhar
┌───────────────────────────────────▼────────────────────────────────────┐
│                   REALIDADE B: SHADOW ISOLATION HARNESS                │
│  • Execução assíncrona protegida via Khonsu Time-Slicing.             │
│  • Parsing pesado de regex (cores, markdown, audit) em background.     │
│  • Se um módulo der crash, o Shadow absorve o erro, isola a falha e   │
│    mantém a IDE desenhando a 60 FPS estáveis com fallback neutro.      │
└────────────────────────────────────────────────────────────────────────┘
```

### As 5 Leis do Fast-Path $O(1)$

1. **Lei do Cache Local (Local Upvalues):**
   * Nenhum módulo pode chamar `core.*`, `style.*` ou `system.*` dentro de um loop de desenho sem antes fazer o *pinning* local:
     ```lua
     -- Ruim (Busca na tabela global _ENV a cada linha):
     style.syntax["keyword"]
     
     -- Perfeito O(1) (Acesso direto a registrador):
     local style_syntax = style.syntax
     ```
2. **Lei do Array Contíguo (Tabelas sem Buracos):**
   * Listas que sofrem iteração no frame devem ser arrays sequenciais (`1..N`), sem chaves esparsas, para evitar que a VM acione a tabela de hash secundária.
3. **Lei do Loop Numérico:**
   * Substituição de `pairs()` por `for i = 1, #array do` em todas as rotinas de renderização.
4. **Lei da Imunidade de Regex em Tempo Real:**
   * O `DocView:draw_line_body` **nunca deve executar `gmatch` de regex** no momento em que o frame está sendo pintado. A tokenização deve ser consultada a partir do cache pré-computado do documento.
5. **Lei do Circuito Tripwire:**
   * Se um componente ultrapassar seu *Frame Budget* (ex: mais de 3ms), ele desativa recursos cosméticos temporariamente e sinaliza o Shadow para processamento em background.

---

## 4. Diagnóstico Cirúrgico dos 54.99ms em `DocView:draw_line_body`

Por que o corpo do documento demorou 55ms?

No `04_color_and_search_highlight.lua`:
1. **Varredura Tripla de Regex por Linha:**
   ```lua
   for s, hex in line_text:gmatch("()#([0-9a-fA-F]+)") do ... end
   for s, func_name, args in line_text:gmatch("()(rgba?)%s*%((.-)%)") do ... end
   for s, inner in line_text:gmatch("(){%s*(%d+%s*,%s*%d+%s*,%s*%d+[%s,%d]*)%s*}") do ... end
   ```
   *Mesmo com cache, se o buffer contiver linhas que ainda não estão no cache ou se o cache estourar (`MAX_CACHE_ENTRIES = 2500`), o motor roda três regex completas em dezenas de linhas a cada redesenho de tela.*
2. **Consulta de Busca Ativa em Todos os Frames:**
   ```lua
   local function get_active_highlight_query()
     local view = core.active_view
     local doc = view and view.doc
     ...
     local query = doc:get_text(l1, c1, l2, c2)
     ...
   ```
   *Em todo redesenho de cada linha, ele reconstrói a string de busca através da API do documento.*

---

## 5. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Fast-Path $O(1)$ + Shadow Memoization)
* **No Módulo 04 (`04_color_and_search_highlight.lua`):**
  * Substituir o parsing dinâmico de cores durante o desenho por **Memoization atrelada ao evento de edição** (`Doc:insert` e `Doc:remove`). 
  * A cor de uma linha só é calculada quando o texto daquela linha for **digitado ou modificado**, nunca quando a tela apenas rola ou pisca o cursor.
  * O `DocView:draw_line_body` apenas lê um array simples indexado pela linha: `line_colors[line_idx]`, transformando a operação em puro **$O(1)$**.
* **Isolamento de Crash por Shadowing:**
  * Wrappers nos métodos de renderização capturam qualquer falha e acionam um fallback visual seguro (linha de texto simples) sem derrubar o frame ou a janela.

### 🔹 Plano B (Fallback — LRU Estático Limitado)
* Se a indexação por eventos de edição falhar em buffers dinâmicos, um cache LRU estático indexado pelo hash da linha limita as buscas a no máximo 1 cálculo por segundo.

### 🔹 Plano C (Contingência — Degradador Gracioso)
* Se a latência do frame ultrapassar 20ms, o motor desliga temporariamente o preview de cores `#hex` e as guias de indentação, mantendo o editor a 60 FPS fluidos até a carga normalizar.

---

## 6. Tasklist & Checklist de Implementação do `blitzplan_profile_2.md`

- [ ] **Fase 1: Fast-Path $O(1)$ no `04_color_and_search_highlight.lua`**
  - [ ] Transformar `parse_colors_in_line` em cálculo acionado por evento (somente em `doc:insert` e `doc:remove`), nunca no `draw_line_body`.
  - [ ] Garantir que o `draw_line_body` apenas faça leitura direta indexada $O(1)$: `line_colors[line_idx]`.
  - [ ] Fazer *pinning* local de variáveis (`local math_floor = math.floor`, `local draw_rect = draw_rect_safe`).

- [ ] **Fase 2: Otimização das Abas (`03b_tab_compact_staircase.lua`)**
  - [ ] Trocar `pairs(rows)` por loop numérico indexado contíguo.
  - [ ] Eliminar alocações temporárias na passagem de preenchimento de abas.

- [ ] **Fase 3: Calibração das Corrotinas no `10_forensic_engine.lua`**
  - [ ] Medir tempo de CPU **líquido** (descontando o tempo em que a thread está no `coroutine.yield()`), eliminando as falsas leituras de 3000ms e 76000ms.

- [ ] **Fase 4: Prova Empírica no Profiler**
  - [ ] Deploy no ambiente de teste.
  - [ ] Executar `ProfilerEngine.render_cli_profile(mode='test')`.
  - [ ] **Meta Numérica Inviolável:** Derrubar `DocView:draw_line_body` de **54.99ms** para **abaixo de 3.0ms**, elevando a taxa de quadros para **60 FPS**.

---

