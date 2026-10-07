# 📜 BLITZPLAN — OTIMIZAÇÃO E QUALIDADE DOS SISTEMAS BÁSICOS (DOXLY V42.0)
* **YMD:** 2026.10.7 - 15:30

---

**Protocolo Normativo:** ProDeNov 1.2.1 | PASC-6.1 (Alta Performance / Zero-Freeze)  
**Módulos Alvo:**  
* `doxoade/commands/lite_xl_systems/template/04_color_and_search_highlight.lua`  
* `doxoade/commands/lite_xl_systems/template/03b_tab_compact_staircase.lua`  
* `doxoade/commands/lite_xl_systems/template/17_khonsu_coroutine.lua`  
* `doxoade/commands/lite_xl_systems/template/10_forensic_engine.lua`  
* `doxoade/commands/lite_xl_systems/template/19b_terminal_console.lua`  
* `doxoade/commands/lite_xl_systems/template/19d_bottom_shelf_hub.lua`  

**Panteões Mobilizados:** Hefesto (Engenharia/Construção), Hórus (Telemetria/Observabilidade), Khonsu (Performance/Pacing), Chronos (Cronometria), Ma'at (Invariantes de Integridade) e Anúbis (Auditoria/Anti-Regressão)  
**Teto Inviolável:** $< 50\text{ KB}$ por arquivo | Zero alocações em hotpath de renderização  

---

## 1. Contexto e Diagnóstico Profundo (W5+ / As 7 Perguntas ProDeNov)

* **O quê (What):**  
  Campanha cirúrgica de consolidação e otimização dos **Sistemas Básicos (Ss.)** do Doxly após o ciclo fundador de 6 semanas, visando:
  1. **Solid Color Baking:** Extirpação de cálculos de canal alfa dinâmico nos loops de renderização de linhas e abas, blindando a taxa de acerto (*cache-hit*) do `rencache.c`.
  2. **Fast-Path $O(1)$ no Buffer de Texto:** Desacoplamento da busca por regex de cores e tokens do ciclo de desenho (`DocView:draw_line_body`), tornando a leitura de estilo instantânea através de memoization atrelada a eventos de mutação (`doc:insert` / `doc:remove`).
  3. **Regime de Sono Reativo nas Corrotinas (Khonsu):** Extinção do polling cego contínuo em repouso nas threads de segundo plano (terminal, telemetria, linter), derrubando o uso de CPU para $0.0\%$ quando ocioso.
  4. **Termodinâmica de Memória (Zero Heap Churn):** Eliminação de tabelas transitórias (`{r, g, b, a}` e `{x, y, w, h}`) alocadas no hotpath gráfico de 60 FPS, evitando pausas de coleta do Garbage Collector do Lua 5.4.
* **Quem (Who):** Engenharia de infraestrutura do ecossistema Doxoade, garantindo estabilidade produtiva sem sobrecarga cognitiva para o desenvolvedor.
* **Onde (Where):** No pipeline contínuo de renderização SDL2/C, na máquina virtual Lua 5.4 do Doxly e nas pontes assíncronas do PTY e telemetria.
* **Quando (When):** A cada ciclo de frame ($16.6\text{ms}$) e em regime de repouso entre interações de teclado/mouse.
* **Quanto (How much — SLAs Invioláveis):**  
  * **Latência de Renderização:** Redução do custo de script do frame de $\approx 14\text{ms}$ para $\le 2.0\text{ms}$.  
  * **Frame Rate:** $60.0\text{ FPS}$ fluidos e estáveis com jitter temporal $< 1.5\text{ms}$.  
  * **CPU em Repouso:** $0.0\%$ de uso de processador quando a janela estiver estática (sem digitação ou stream ativo).  
  * **Taxa de Alocação de Memória:** Queda de $> 85\%$ na geração de lixo transitório por segundo.  
* **Por quê (Why):** Funcionalidade completa sem otimização de base gera microtravamentos (*stuttering*), drena bateria em ambientes móveis e degrada a responsividade em projetos extensos ($> 50.000$ linhas).
* **Origem & Consequências:**  
  * *Origem:* A rápida expansão de recursos ao longo de 6 semanas acumulou pequenos custos em chamadas repetidas por linha e alocações de tabelas.  
  * *Consequências:* Sem essa consolidação, novos recursos sofreriam degradação progressiva de taxa de quadros. Com o saneamento, a base torna-se perene e escalável.

---

## 2. Taxonomia de Complexidade ProDeNov (Regras 0.0 a 0.4)

| Eixo de Complexidade | Classificação | Diretriz & Mitigação ProDeNov |
| :--- | :---: | :--- |
| **0.0 Thirdparty (Lite XL C & SDL2)** | **Alta** | Intervenção via monkey-patching limpo em Lua e uso estrito das APIs C nativas (`rencache`, `renderer`), sem alterar binários. |
| **0.1 Devflow** | **Baixa** | Validação automática contínua usando o comando de teste supervisionado `doxoade doxly deploy test` com *watchdog*. |
| **0.2 Rabbit Hole** | **Média** | Foco estrito na eliminação de complexidade: evitar bibliotecas externas ou refatorações desnecessárias; priorizar código procedural enxuto. |
| **0.3 Sensibilidade (FPS & Jitter)** | **Crítica** | Qualquer função chamada por caractere ou linha deve ser puramente $O(1)$ na VM Lua, sem chamadas `pairs()` ou concatenação de strings. |
| **0.4 Revisitar** | **Baixa** | Estabelecer padrões canônicos para que novos módulos consumam o cache pré-computado sem recriar lógica de estilo. |

---

## 3. Capítulos de Execução (Regra 1.2.1 ProDeNov — Planos A, B e C)

```text
┌────────────────────────────────────────────────────────────────────────┐
│             CAPÍTULO 1: HOTPATH GRÁFICO & SOLID COLOR BAKING          │
│  • Pre-Multiplied Solid Color Baking (Alpha = 255 no Rencache)        │
│  • Memoization O(1) de Linha (Desacoplar Regex do Render Loop)         │
│  • Viewport Culling Estrito sem Omissão de Linhas                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│         CAPÍTULO 2: SONO REATIVO & CONTROLE DE CORROTINAS (KHONSU)     │
│  • Poller Adaptativo em Escada (0.005s ativo ➔ 0.5s repouso)          │
│  • Hard Deadline de 1.5ms por Ciclo de Cooperatividade                │
│  • Despertar Imediato por Eventos de Hardware                          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│          CAPÍTULO 3: TERMODINÂMICA DE MEMÓRIA & ZERO HEAP CHURN        │
│  • Banimento de Alocações {r,g,b,a} e {x,y,w,h} dentro do Draw         │
│  • Substituição Universal de pairs() por Loops Numéricos              │
│  • Preservação de Integridade Contratual (Anti-Regressão)              │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 📖 CAPÍTULO 1: Otimização do Hotpath Gráfico & Solid Color Baking

#### Problema Identificado:
O `rencache` invalida retângulos quando cores translúcidas (`alpha < 255`) sobrepõem o fundo, gerando redesenho redundante de hardware. Além disso, o motor de destaque em `04_color_and_search_highlight.lua` percorria padrões regex em texto a cada redesenho de tela.

#### 🔹 Plano A (Principal — Pré-Mesclagem Sólida e Memoization por Evento)
1. **Solid Color Baking:**  
   Pré-calcular as cores de guias de indentação, marcas de seleção e divisores misturando o canal alfa com a cor de fundo do tema no momento do boot ou troca de tema (`style.background`), gerando retângulos puramente opacos (`alpha = 255`).
2. **Memoization Reativa $O(1)$:**  
   Vincular o cálculo de tokens de cor (`#hex`, `rgba`, etc.) aos métodos de mutação do documento (`Doc:insert` e `Doc:remove`). O método `DocView:draw_line_body` limita-se a ler o array pré-calculado `line_colors[line_idx]`, sem varredura de regex durante o desenho.
3. **Viewport Culling Estrito:**  
   Calcular rigorosamente o intervalo visível:
   $$\text{start\_idx} = \max\left(1, \left\lfloor \frac{\text{scroll.y}}{\text{line\_height}} \right\rfloor\right), \quad \text{end\_idx} = \min\left(\text{total\_lines}, \text{start\_idx} + \left\lceil \frac{\text{view.size.y}}{\text{line\_height}} \right\rceil + 1\right)$$
   Linhas fora desse intervalo não processam cálculos de largura de segmento.

#### 🔹 Plano B (Fallback — LRU Ring Cache com Janela Estática)
Se a interceptação de eventos de mutação do documento conflitar com plugins de terceiros, manter cache LRU estático de 2.000 entradas indexado por hash da linha, recalculando apenas linhas cujos hashes divergirem.

#### 🔹 Plano C (Contingência — Eco Mode Dinâmico)
Caso a máquina apresente taxa de quadros $< 45\text{ FPS}$ em buffers massivos ($> 100.000$ linhas), desativar temporariamente o desenho de guias de indentação cosméticas de 1px e a pré-visualização de cores hexadecimais, mantendo apenas o realce de sintaxe básico.

---

### 📖 CAPÍTULO 2: Sono Reativo & Orçamento Temporal Rígido no Khonsu

#### Problema Identificado:
Corrotinas de segundo plano acordavam em taxa constante de 20ms a 50ms para verificar tabelas vazias, impedindo o loop do SDL2 de entrar em repouso profundo ($0.0\text{ FPS} / 0.0\%\text{ CPU}$).

#### 🔹 Plano A (Principal — Escada de Sono Reativo e Hard Deadline)
1. **Escada de Repouso Adaptativa:**  
   Toda corrotina cooperativa (`TerminalEngine`, `PTYClient`, `Khonsu`, `ForensicEngine`) adota o regime de degraus de sono:
   * *Fluxo ativo (dados fluindo ou digitação):* $\text{yield}(0.005\text{s})$ (5ms para vazão máxima).
   * *Ociosidade leve (1 a 4 ciclos vazios):* $\text{yield}(0.03\text{s})$ (30ms).
   * *Repouso consolidado ($> 5$ ciclos ociosos):* $\text{yield}(0.25\text{s} \dots 0.50\text{s})$ (500ms).
2. **Interrupção de Sono por Evento:**  
   Ao pressionar qualquer tecla, mover o mouse ou receber dados nos pipes do PTY, o timer de sono é resetado no frame zero, garantindo resposta sem latência.
3. **Hard Deadline de 1.5ms:**  
   Impor em `Khonsu.should_yield()` um corte obrigatório se o processamento contínuo exceder $1.5\text{ms}$, preservando o restante da fatia de $16.6\text{ms}$ para a renderização e o compositor do sistema operacional.

#### 🔹 Plano B (Fallback — Desativação Seletiva de Telemetria de Fundo)
Suspender a coleta de estatísticas contínuas do Profiler de 1Hz quando o editor estiver desconectado da tomada ou operando em modo de economia de energia, reativando a telemetria apenas sob demanda explícita (`doxoade doxly profile`).

#### 🔹 Plano C (Contingência — Isolamento de Thread Nativa C)
Se tarefas de verificação em disco gerarem travamentos perceptíveis no Windows, delegar a leitura de arquivos para uma thread nativa C via módulo compilado pelo Vulcan (`SDL_CreateThread`), comunicando o resultado por sinal booleano atômico.

---

### 📖 CAPÍTULO 3: Termodinâmica de Memória, Loops Numéricos & Zero Heap Churn

#### Problema Identificado:
Criação contínua de pequenas tabelas efêmeras nos métodos de desenho (`draw_rect_safe`, `draw_text_safe`, alinhamento de abas) sobrecarregando o coletor de lixo da VM Lua.

#### 🔹 Plano A (Principal — Reutilização de Tabelas e Loops Indexados)
1. **Tabelas de Cor e Geometria Estáticas:**  
   Manter tabelas estáticas de trabalho reutilizáveis (`_SCRATCH_RECT`, `_SCRATCH_COLOR`), alterando apenas seus índices numéricos (`_SCRATCH_RECT[1] = x`, etc.) em vez de instanciar `{ x = ..., y = ... }` a cada chamada.
2. **Substituição de `pairs()` por Loops Numéricos:**  
   Substituir universalmente o iterador genérico `pairs()` por laços numéricos contíguos (`for i = 1, #array do`) em todos os templates de renderização (`03b`, `04`, `13d`, `19d`), aproveitando os opcodes otimizados da VM do Lua 5.4 (`FORPREP` / `FORLOOP`).
3. **Pinning de Upvalues Locais:**  
   Garantir que todas as chamadas a funções globais frequentemente invocadas em loops (`math.floor`, `math.min`, `math.max`, `draw_rect_safe`, `draw_text_safe`) estejam ancoradas em variáveis locais no topo de cada arquivo.

#### 🔹 Plano B (Fallback — Ajuste de Parâmetros do Coletor de Lixo Lua)
Configurar os parâmetros do coletor incremental do Lua 5.4 (`collectgarbage("incremental", pause, stepmul, stepsize)`) com passo estendido durante rolagem contínua para adiar coletas para momentos comprovados de ociosidade do usuário.

#### 🔹 Plano C (Contingência — Coleta Manual em Pitstop)
Acionar coleta manual explícita (`collectgarbage("step", 100)`) exclusivamente no fechamento de abas, minimização de gavetas ou alternância de painéis, blindando a janela ativa contra pausas não planejadas.

---

## 4. Roteiro de Implementação e Testagem (RIT / 5.6.2 ProDeNov)

O ciclo segue a engrenagem obrigatória:  
$$\text{Discussão} \;\longrightarrow\; \text{Implementação Cirúrgica} \;\longrightarrow\; \text{Teste Empírico} \;\longrightarrow\; \text{Auditoria/Fix}$$

### 📋 Tasklist de Execução em Fases

- [ ] **Fase 1: Linha de Base (Baseline Empírico)**
  - [ ] Executar snapshot forense com `doxoade doxly profile -m test`.
  - [ ] Registrar tempos de CPU de `DocView:draw_line_body`, `Node:draw_tabs`, taxa de alocação de memória (KB/s) e FPS ativo.
- [ ] **Fase 2: Intervenção Gráfica no Hotpath (Capítulo 1)**
  - [ ] Implementar pré-mesclagem de cores sólidas (*Solid Color Baking*) em `04_color_and_search_highlight.lua` e `03b_tab_compact_staircase.lua`.
  - [ ] Desacoplar expressões regulares de cor para o gatilho de edição do documento.
  - [ ] Ajustar o enquadramento de linhas (*Viewport Culling*) estrito.
- [ ] **Fase 3: Pacificação de Corrotinas e Sono Reativo (Capítulo 2)**
  - [ ] Aplicar escada de sono adaptativo em `17_khonsu_coroutine.lua`, `19b_terminal_console.lua` e `19b1_pty_client.lua`.
  - [ ] Validar consumo de CPU em repouso ($0.0\%$ comprovado no gerenciador de tarefas).
- [ ] **Fase 4: Otimização de Memória e Loops na VM Lua (Capítulo 3)**
  - [ ] Ancorar *upvalues* locais e reaproveitar tabelas temporárias em `13d_frameless_hud.lua` e `19d_bottom_shelf_hub.lua`.
  - [ ] Substituir laços `pairs()` por loops numéricos indexados contíguos.
- [ ] **Fase 5: Prova de Não-Regressão e Homologação Final**
  - [ ] Executar `doxoade regret` (assegurar zero comandos perdidos, zero atalhos órfãos).
  - [ ] Executar `doxoade doxly check-templates` (100% PASS de integridade estática).
  - [ ] Comparar o novo relatório do `profile` contra a Linha de Base da Fase 1.

---

## 5. Matriz de Casos de Teste (DoD — Definition of Done)

| ID do Teste | Cenário / Entrada | Ação Realizada | Critério Estrito de Sucesso |
| :--- | :--- | :--- | :--- |
| **TC-OPT-01** | Arquivo de código com $> 2.000$ linhas aberto | Rolagem contínua veloz com a rodinha do mouse por 10s | Manutenção contínua de $\ge 58.0\text{ FPS}$; latência de script do frame $\le 2.5\text{ms}$. |
| **TC-OPT-02** | Editor aberto sem interação do usuário por 15s | Medição de telemetria no modo repouso | Taxa registrada de $0.0\text{ FPS}$ e consumo de processador de $0.0\%$. |
| **TC-OPT-03** | Arquivo com centenas de strings hexadecimais (`#FFFFFF`) | Digitação rápida e rolagem ativa | Zero engasgos; cálculo de cores realizado exclusivamente na linha sob edição. |
| **TC-OPT-04** | Terminal com fluxo massivo (ex.: `dir /s` ou log denso) | Exibição e rolagem do buffer PTY | A interface do editor continua respondendo a cliques e digitação em $< 16\text{ms}$. |
| **TC-OPT-05** | Alternância contínua entre 4 projetos no Bottom Shelf | Troca de abas de projeto na gaveta | Transição instantânea sem alocação descontrolada de memória na heap. |
| **TC-OPT-06** | Auditoria geral de integridade pós-otimização | Execução de `doxoade regret` e `check-templates` | **Zero regressões de UX**, integridade sintática e funcionalidade total preservada. |

---

## 6. Critérios de Avaliação & SLAs (Metas Ma'at & Hórus)

| Métrica de Engenharia | Linha de Base Atual (Estimada) | Meta Inviolável Pós-Otimização |
| :--- | :---: | :---: |
| **Tempo de Script do Frame (`draw_line_body`)** | $3.5\text{ms} \dots 5.5\text{ms}$ | $\mathbf{\le 1.80\text{ms}}$ |
| **Taxa de Quadros em Rolagem Ativa** | $45.0 \dots 55.0\text{ FPS}$ | $\mathbf{\ge 59.0\text{ FPS}}$ estáveis |
| **Jitter de Renderização (Variação de Frame)** | $\pm 8.0\text{ms}$ | $\mathbf{\le 1.20\text{ms}}$ |
| **Consumo de CPU em Repouso (Idle)** | $0.5\% \dots 2.0\%$ | $\mathbf{0.0\%}$ (Sono Profundo) |
| **Taxa de Alocação de Memória na Heap** | $\approx 45.0\text{ KB/s}$ | $\mathbf{\le 8.0\text{ KB/s}}$ |
| **Tamanho Máximo por Arquivo Template** | $< 50\text{ KB}$ | $\mathbf{< 50\text{ KB}}$ (Conforme ProDeNov) |

---

## 7. Sistema de Diagnóstico e Auto-Auditoria

O subsistema `10_forensic_engine.lua` e o comando CLI `doxoade doxly profile` atuarão como a balança de validação em tempo real:
* **Exportação Contínua de Telemetria:** Atualização transparente em `.doxoade/diagnostics/profiler_telemetry.json` e `boot_telemetry.json`.
* **Chronos Advisor Integrado:** O comando `doxoade doxly profile -m test` confrontará os dados colhidos contra os SLAs da tabela acima, emitindo aprovação explícita apenas se todos os critérios forem batidos.

---

