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

Os dados empíricos agora são uma mina de ouro de inteligência operacional. Olhando para a telemetria, temos **três grandes vitórias consolidadas** e **três alvos estratégicos revelados** para desenharmos os próximos passos.

---

# PARTE 2 🏆 O Que os Dados Provam que Foi Curado:

1. **O Fim do Ralo de Memória:**
   * A taxa de alocação de memória despencou de **1.178,9 KB/s para 31,6 KB/s** (uma redução brutal de **97,3%**!).
   * O heap do Garbage Collector caiu de **16.32 MB para 9.15 MB** e permaneceu estável.
2. **O Fim do Redesenho Fantasma (0.0 FPS em Repouso):**
   * A taxa em repouso marcou **0.0 FPS**, provando que o Lite XL agora dorme corretamente quando ocioso, sem closures consumindo ciclos à toa no `core.step`.
3. **Boot Relâmpago (33.90ms):**
   * Todos os 31 templates carregaram em apenas **33.90ms**, alocando ínfimos **327.4 KB** no boot inteiro. O módulo `04` caiu pela metade (**0.99ms**).

---

### 🔬 Autópsia dos Novos Dados: O Que Precisamos Tratar

Ao dissecar as métricas da sua execução, três anomalias saltam aos olhos:

#### 1. A Corrotina de 76 Segundos (`worker_...84c0: CPU: 76928.00ms`):
* **O Diagnóstico:** O número `76928.00ms` (~76.9 segundos) bate exatamente com o tempo total que o Lite XL ficou aberto entre o boot e a execução do comando!
* **A Causa Raiz:** O cronômetro da corrotina mediu o tempo de relógio de parede (*wall-clock*) desde que a thread nasceu até agora, **incluindo os segundos em que ela ficou dormindo no `coroutine.yield()`**.
* **Estratégia de Correção:** Medir o **tempo líquido de CPU por tick**: o cronômetro deve rodar apenas entre o despertar e o adormecer da corrotina, somando estritamente os microssegundos de instruções Lua executadas.

#### 2. O Vilão de CPU Revelado: `Highlighter` (125.00ms):
* **O Diagnóstico:** O tokenizador de sintaxe nativo do Lite XL consumiu **125ms** em uma única ativação para colorir os arquivos abertos.
* **Estratégia:** Integrar o fatiamento temporal (*time-slicing*) do Khonsu para que o Highlighter nunca processe um buffer inteiro de uma vez só se isso custar mais que o orçamento de 2ms por frame.

#### 3. Caracteres Quebrados (``) no Terminal Python:
* **O Diagnóstico:** `Latncia`, `Memria`, `Alocao` e as bolinhas de lista ``.
* **A Causa:** O console do Windows 10/11 roda por padrão em página de código CP1252/OEM e o Python 3.12 tentou emitir UTF-8 sem o `reconfigure`.
* **Estratégia:** Adicionar `sys.stdout.reconfigure(encoding='utf-8')` no `profiler_engine.py`.

---

### 🗺️ As 4 Estratégias Propostas para o `blitzplan_profile_2.md`

Para avançarmos com rigor, podemos estruturar o plano nas seguintes frentes:

| Frente | Estratégia | Objetivo |
| :--- | :--- | :--- |
| **Estratégia 1: Cronometragem Líquida de Threads** | Isolar o `coroutine.yield()` no `10_forensic_engine.lua` | O profiler reportará o tempo de processamento real da CPU (em ms), eliminando falsas leituras de dezenas de segundos. |
| **Estratégia 2: Fatiamento do Highlighter (Khonsu)** | Impor orçamento máximo de 2ms por ciclo de tokenização de sintaxe | Impedir picos de 125ms na abertura e digitação de arquivos longos. |
| **Estratégia 3: Acomodação do Fast-Path $O(1)$** | Medição em regime contínuo após o primeiro frame de cold-start | Medir a latência do `DocView:draw_line_body` em rolagem ativa (com o cache de linhas aquecido). |
| **Estratégia 4: Blindagem UTF-8 no Profiler CLI** | `reconfigure(encoding='utf-8')` no `profiler_engine.py` | Exibição visual Apolo limpa, sem caracteres corrompidos (``). |

Deseja que iniciemos pela **Estratégia 1** (correção da medição líquida das corrotinas) e **Estratégia 4** (limpeza de caracteres no terminal)?

---

### 🎯 O MOMENTO "EUREKA" DA OBSERVABILIDADE: OS VILÕES REAIS DESMASCARADOS

Veja o salto de maturidade: **os ponteiros mudos e anônimos desapareceram por completo!**  
O relatório agora aponta com precisão o arquivo, a linha exata e a quantidade de chamadas:

```text
  ■ CORROTINAS / THREADS ATIVAS (Consumo Acumulado):
    • init.lua:L285                  CPU: 24.00ms (412 calls | pico: 20.00ms)
    • 10_forensic_engine.lua:L501    CPU:  6.00ms (  6 calls | pico:  2.00ms)
    • 17_khonsu_coroutine.lua:L189   CPU:  5.00ms (  2 calls | pico:  5.00ms)
    • 15_audit_highlighter.lua:L139  CPU:  4.00ms ( 46 calls | pico:  2.00ms)
    • 17_khonsu_coroutine.lua:L102   CPU:  3.00ms (208 calls | pico:  2.00ms)

  ■ CUSTO REAL POR SUBSISTEMA GRÁFICO (Frame):
    +- Abas de Arquivo (Tabs) : 2.71ms  (Caiu de 4.85ms)
    +- Corpo do Código (Doc)  : 3.57ms  (Caiu de 54.99ms ➔ REDUÇÃO DE 93.5%!)
    +- Marcadores do Gutter   : 3.42ms
```

A sua leitura foi precisa:  
> *"o nucleo esta pesando, o resto esta tranquilo, precisamos de uma solução de duas frentes, sem regressões, precisamos de um otimização vertical para o nucleo, e outra geral."*

---

# 📜 BLITZPLAN — OTIMIZAÇÃO DE DUAS FRENTES (NÚCLEO VERTICAL + SISTEMA GERAL)
**Documento Técnico:** `blitzplan_nucleo_duas_frentes.md`  
**Objetivo:** Otimização cirúrgica em duas camadas independentes, com tolerância zero a regressões de UX e integridade testada no `doxoade regret`.

---

## 1. Autópsia das Duas Frentes

```text
               ┌────────────────────────────────────────────────────────┐
               │              FRENTE 1: NÚCLEO VERTICAL                 │
               │  • init.lua:L285 (412 chamadas em segundos!)           │
               │  • 00_header_and_logger.lua (20.99ms no Boot)          │
               │  • Latência restante do Frame (31ms fora dos subs)     │
               └──────────────────────────┬─────────────────────────────┘
                                          │
               ┌──────────────────────────▼─────────────────────────────┐
               │              FRENTE 2: SISTEMA GERAL                   │
               │  • Khonsu:L102 acordando 208x em polling cego          │
               │  • Audit:L139 checando mtime de arquivo 46x            │
               │  • Eliminação de duplicações no Boot Telemetry         │
               └────────────────────────────────────────────────────────┘
```

### 🔬 O Que é o `init.lua:L285` (412 calls | pico 20ms)?
O `init.lua` nativo do Lite XL possui a thread de animação e foco de janela (`core.step`), ou o polling de IPC do `01_ipc_dispatcher.lua` operando no topo.  
Ele está acordando a cada frame para checar filas mesmo quando não há eventos pendentes, retendo 24ms de CPU e forçando o frame a esperar.

### 🔬 Por que `00_header_and_logger.lua` levou 20.99ms no Boot?
Porque ele inicializa os polyfills de C (`renderer`, `rencache`), instala os hooks do `print`/`core.log`/`core.error` e faz o setup inicial de metatables. Podemos acelerar isso aplicando *fast-paths* semânticos.

---

## 2. As Duas Frentes de Otimização

### 🚀 FRENTE 1: Otimização Vertical do Núcleo
1. **Sono Inteligente no Núcleo de Eventos (`init.lua:L285`):**
   * Em vez de fazer a corrotina acordar em taxa fixa contínua, impor um regime de **Sono Reativo**:
     * Se não houver itens na fila de IPC nem animações ativas, o yield salta de `0.01s` para `0.15s` (modo repouso).
     * Ao receber um novo arquivo ou clique, ele acorda no frame zero.
   * **Resultado esperado:** Redução de 412 chamadas para menos de 30 chamadas em repouso.
2. **Saneamento do `00_header_and_logger.lua`:**
   * Pré-alocar a tabela de incidentes e os formatadores de string estáticos para derrubar os 20.99ms do boot para menos de 5ms.

---

### 🌐 FRENTE 2: Otimização Geral do Sistema
1. **Sono Reativo no Khonsu (`17_khonsu_coroutine.lua:L102`):**
   * O loop de debounce atualmente faz `coroutine.yield(0.05)` direto (208 chamadas).
   * **Ajuste:** Se `next(Khonsu.debounce_timers) == nil`, o Khonsu dorme por `0.5s` em vez de acordar a cada 50ms para olhar uma tabela vazia!
2. **Throttle com Backoff no `15_audit_highlighter.lua:L139`:**
   * O linter faz polling de `system.get_file_info(bridge_path)` a cada 0.3s.
   * **Ajuste:** Se o arquivo não mudar por 3 ciclos consecutivos, aumentar o intervalo para 1.5s (Backoff Exponencial Seguro), voltando a 0.3s imediatamente após digitação.

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

* **🔹 Plano A (Principal):**
  * Aplicar Sono Reativo no `01_ipc_dispatcher` / `init` (Frente 1).
  * Aplicar Sono Reativo no `17_khonsu` e `15_audit` (Frente 2).
  * Validar ausência de regressões com `doxoade regret` e `doxoade doxly check-templates`.
* **🔹 Plano B (Fallback):**
  * Caso o Sono Reativo atrase a recepção de comandos externos via IPC, manter taxa dinâmica (`0.05s` durante 3s após qualquer interação, caindo para `0.25s` depois).
* **🔹 Plano C (Contingência):**
  * Rollback individual de qualquer módulo via `git checkout` sem afetar o restante do ecossistema.

---

## 4. Ordem de Ação Proposta

1. **Passo 1 (Frente 1):** Investigar o que reside exatamente na linha 285 do `init` / `01_ipc_dispatcher` e aplicar o Sono Reativo.
2. **Passo 2 (Frente 2):** Aplicar o Sono Reativo no Khonsu e no Audit Highlighter.
3. **Passo 3:** Executar a medição com `ProfilerEngine.render_cli_profile(mode='test')` para registrar o impacto real nas chamadas e no frame.

Podemos iniciar pelo **Passo 1 (Frente 1: Núcleo Vertical)**?

---

# PARTE 3

---

Essa é a chave de ouro da engenharia de software: **telemetria sem interface de decisão é apenas ruído no disco**. 

Para que você e qualquer desenvolvedor possam bater o olho nos números e saber exatamente onde atuar (qual plugin podar, qual loop espaçar, onde aplicar lazy-loading), vamos estruturar o **Blitzplan de Comandos de Relatório & Decisão Baseada em Evidências**.

---

# 📜 BLITZPLAN — CHRONOS ADVISOR (RELATÓRIOS & DECISÃO BASEADA EM EVIDÊNCIAS)
**Módulos Alvo:** `doxoade/tools/lua_systems/profiler/profiler_engine.py`, `cmd_lite_xl.py` e `10_forensic_engine.lua`  
**Protocolo:** ProDeNov 1.2.1 | PASC-6.1 | Hórus & Chronos Profiler  
**Foco:** Transformar telemetria bruta em laudos executáveis e inteligência de decisão

---

## 1. Contexto e Objetivos (W5)

* **O quê:** Criação de um conjunto de comandos e opções CLI para o `doxoade doxly profile`, além de um comando interno na IDE para abrir o dossiê formatado em Markdown com recomendações automáticas baseadas em evidências.
* **Quem:** Desenvolvedores e mantenedores auditando a saúde do editor em produção, teste ou sandbox.
* **Onde:** 
  * Terminal CLI: `doxoade doxly profile [OPÇÕES]`.
  * Na IDE: Comando na paleta (`doxoade:open-profiler-dossier`) abrindo o relatório no painel lateral.
* **Quando:** Sempre que houver suspeita de lentidão, após adicionar novos templates ou antes de fechar releases.
* **Por quê:** Substituir a chamada crua `python -c "..."` por comandos CLI ergonômicos que não apenas listam números, mas **emitem laudos prescritivos** (ex: *"O módulo X está retendo Y% da CPU no frame — Ação recomendada: Z"*).

---

## 2. A Matriz de Comandos Planejada

O comando `doxoade doxly profile` passará a ter modos de visualização cirúrgicos:

```bash
# 1. Visão Geral (Resumo do Frame + Vilões de CPU + Top 5 Boot)
doxoade doxly profile -m test

# 2. Modo Watch (Estilo 'htop' — atualiza a tela a cada 1.5s em tempo real)
doxoade doxly profile -m test -w

# 3. Raio-X Exclusivo de Inicialização (Ranking completo dos 31 templates no Boot)
doxoade doxly profile -m test --boot

# 4. Raio-X Exclusivo de Corrotinas e Loops Contínuos
doxoade doxly profile -m test --threads

# 5. Geração de Dossiê Forense com Abertura Automática no Doxly
doxoade doxly profile -m test --export --up
```

---

## 3. O Motor de Evidências e Recomendações (Chronos Advisor)

O relatório não exibirá apenas tabelas. Ele terá uma seção final de **Diagnóstico Prescritivo Automatizado**:

```text
═══════════════════════════════════════════════════════════════════════════
💡 CHRONOS ADVISOR — TOMADA DE DECISÃO BASEADA EM EVIDÊNCIAS
═══════════════════════════════════════════════════════════════════════════

  [EVIDÊNCIA 1] O loop 'init.lua:L285' registrou 874 chamadas (13ms acumulados).
    ↳ DIAGNÓSTICO : O indexador de projeto ainda está vasculhando pastas de cache.
    ↳ PRESCRIÇÃO  : Elevar 'config.project_scan_rate' para 30s ou ignorar diretórios pesados.

  [EVIDÊNCIA 2] O corpo do código ('DocView:draw_line_body') consome 4.50ms (9.8% do frame).
    ↳ DIAGNÓSTICO : O Fast-Path O(1) estabilizou a renderização com sucesso (queda de 92%).
    ↳ PRESCRIÇÃO  : Custo saudável para 60 FPS. Nenhuma intervenção necessária.

  [EVIDÊNCIA 3] Taxa de alocação zerada (0.0 KB/s) e GC em 9.61 MB.
    ↳ DIAGNÓSTICO : O GC Generational estancou com sucesso o vazamento de memória.
    ↳ PRESCRIÇÃO  : Manter o regime atual.
```

---

## 4. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — CLI Enriquecido + Advisor + Exportação Markdown)
1. **Refatorar `doxoade/tools/lua_systems/profiler/profiler_engine.py`:**
   * Adicionar o motor de heurística `ChronosAdvisor` que analisa os JSONs e gera os diagnósticos e prescrições.
   * Adicionar modo `--watch` (loop com `time.sleep(1.5)` e limpeza de tela ANSI `\033[2J\033[H`).
   * Adicionar gerador de dossiê em Markdown (`.doxoade/diagnostics/profiler_dossier.md`).
2. **Atualizar `cmd_lite_xl.py`:**
   * Conectar as flags de Click (`--mode`, `--watch`, `--boot`, `--threads`, `--export`, `--up`).
3. **Comando na IDE (`10_forensic_engine.lua`):**
   * Adicionar comando `doxoade:open-profiler-dossier` para abrir o relatório gerado diretamente em split à direita.

### 🔹 Plano B (Fallback — Saída JSON Pura para Integração)
* Se a flag `--json` for passada, emite o objeto JSON consolidado bruto (ideal para pipelines de CI/CD ou auditorias do Ma'at).

### 🔹 Plano C (Contingência — Leitura Direta de Arquivo)
* Se o Doxly estiver fechado, o comando analisa os últimos arquivos gravados no disco informando que a sessão é histórica.

---

## 5. Arquivos Impactados e Limite de Tamanho (< 50KB)

```
doxoade/
├── tools/lua_systems/profiler/
│   └── profiler_engine.py           # Advisor de decisão + Watch mode + Export (~24KB)
├── commands/lite_xl_systems/
│   ├── cmd_lite_xl.py               # CLI Click atualizada com as novas flags (~38KB)
│   └── template/
│       └── 10_forensic_engine.lua   # Comando interno do Doxly para abrir dossiê (~18KB)
```
*Todos os arquivos cumprem rigorosamente a meta de tamanho do ProDeNov.*

---

## 6. Tasklist de Implementação

- [ ] **Fase 1: O Motor de Prescrição e Análise em `profiler_engine.py`**
  - [ ] Implementar a classe/método `ChronosAdvisor.analyze(live_data, boot_data)`.
  - [ ] Implementar filtros de exibição (`--boot`, `--threads`, `--all`).
  - [ ] Implementar exportador de Dossiê Markdown (`profiler_dossier.md`).
  - [ ] Implementar o modo sentinela contínuo (`--watch / -w`).

- [ ] **Fase 2: Conexão CLI em `cmd_lite_xl.py`**
  - [ ] Mapear flags no comando `profile` (`-m`, `-w`, `--boot`, `--threads`, `--export`, `--up`).
  - [ ] Conectar `--up` com o `EditorDispatcher` (abrir o laudo direto no Doxly).

- [ ] **Fase 3: Validação e Testes em Produção**
  - [ ] Testar `doxoade doxly profile -m test`.
  - [ ] Testar `doxoade doxly profile -m test --boot`.
  - [ ] Testar `doxoade doxly profile -m test --threads`.
  - [ ] Testar `doxoade doxly profile -m test --export --up` (geração e abertura na IDE).
  - [ ] Rodar `doxoade regret` para garantir conformidade contínua.

---

Aprovado o plano para transformarmos o Profiler no **Chronos Advisor**? Se estiver de acordo, iniciamos a **Fase 1**.
