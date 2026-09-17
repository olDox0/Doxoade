Excelente diretiva. Essa é uma das fundações mais poderosas da arquitetura Doxoade: **Hermes (Comunicação/Telemetria) + Hades (Persistência Profunda) + Anúbis (Forense/Machine Learning)**.

Para registrar **absolutamente tudo** sem que o I/O derrube os 60 FPS do Lite XL e sem criar *development hell*, vamos desenhar a arquitetura no padrão **ProDeNov 1.2.1** com foco em **Zero-Overhead em Memória + Gravação em Lote no Shadow**.

---

# 📜 BLITZPLAN — HADES SHADOW EVENT RECORDER (BLACKBOX FORENSE & ML DATASET)
**Módulo Alvo:** `doxoade/commands/lite_xl_systems/template/00_00_shadow_logger.lua` (ou acoplado ao `00_header`) e `.doxoade/diagnostics/shadow_telemetry.ndjson`  
**Protocolo:** ProDeNov 1.2.1 | PASC-6.1 | Hades, Hermes & Chronos  
**Foco:** Captura atômica de eventos (UI, Comandos, I/O, Teclas, Corrotinas, Erros e GC) em formato estruturado (NDJSON) para diagnóstico, *crash forensics* e treinamento de modelos de ML no futuro.

---

## 1. Contexto e Objetivos (W5)
* **O quê (What):** Uma "Caixa-Preta" (Flight Recorder) em tempo real que escuta e registra todos os eventos atômicos da sessão sem travar o editor.
  * **Eventos Rastreados:**
    1. `BOOT_STAGE`: Tempo, RAM e status de cada módulo no carregamento.
    2. `COMMAND`: Todo comando acionado via teclado, clique ou paleta (`command.perform`).
    3. `KEYPRESS`: Atalhos acionados e tempo de resposta (sem capturar texto confidencial/senhas).
    4. `DOC_LIFECYCLE`: Abertura, salvamento, fechamento e troca de abas/splits (`open_doc`, `save`, `focus`).
    5. `PERF_SAMPLE`: Snapshot a cada $N$ segundos (FPS, latência de frame em ms, tamanho do heap GC em KB, taxa de alocação).
    6. `THREAD_CYCLE`: Nascimento, yields e mortes de corrotinas.
    7. `INCIDENT`: Todos os erros, avisos e capturas de `pcall` com *stacktrace* completo.
  * **Formato de Persistência:** **NDJSON (Newline Delimited JSON)** em `.doxoade/diagnostics/shadow_telemetry.ndjson`.
    * *Por que NDJSON?* Cada linha é um evento independente válido. Se o sistema crashar ou for encerrado abruptamente no SO, **nenhum byte anterior se corrompe**. Além disso, é o formato padrão para ingestão em pipelines de Data Science e Machine Learning (`pandas.read_json(..., lines=True)`).
* **Quem (Who):** Engenheiros investigando bugs intermitentes, motores de auditoria automática (`typhon`, `regret`) e futuros pipelines de Machine Learning.
* **Onde (Where):**
  * `doxoade/commands/lite_xl_systems/template/00_00_shadow_logger.lua` (Estágio 00 no boot Lua).
  * Backend Python de leitura / dataset em `doxoade/tools/forensic/event_ingest.py`.
* **Quando (When):** Em segundo plano contínuo durante a sessão da IDE.
* **Por quê (Why):** Logs em texto plano são difíceis de cruzar e parsear. Sem uma linha do tempo unificada de eventos (*Timeline Correlation*), é impossível saber se um erro na linha 300 ocorreu por um comando disparado 2 segundos antes ou por um vazamento de corrotina.
* **Origem & Consequências (Origin & Consequences):** Hoje o log é fragmentado entre `session_log.txt` e telemetrias esparsas. Unificar em um fluxo de eventos estruturado cria a base para diagnósticos com IA e previsões preditivas de falhas.

---

## 2. Termodinâmica & Regra de Ouro (Zero-Freeze Guarantee)
Gravar eventos no disco a cada clique ou tecla destruiria a taxa de 60 FPS. Portanto, o sistema adota a **Arquitetura de Anel de Memória (Ring Buffer) com Despejo Assíncrono**:
```text
┌────────────────────────────────────────────────────────────┐
│                    FRAME DO SDL2 (HOTPATH)                 │
│  Evento acontece ➔ table.insert em Buffer de Memória O(1)  │
│                   (Custo: ~0.002ms | Zero I/O de disco)    │
└─────────────────────────────┬──────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────┐
│                  SHADOW FLUSHER (CORROTINA)                │
│  A cada 2 segundos OU ao atingir 50 eventos:               │
│  Abre arquivo em modo "a", grava bloco inteiro e fecha.    │
│  Se houver erro CRÍTICO: flush síncrono imediato.          │
└────────────────────────────────────────────────────────────┘
```

---

## 3. Esquema do Evento (Schema NDJSON)
Cada registro possui um contrato estrito:
```json
{"ts": 1726164200.123, "t_iso": "2026-09-12T15:10:00.123Z", "cat": "CMD", "act": "doc:save", "ctx": {"file": "core.lua", "dirty": false}, "fps": 59.8, "mem_kb": 9210.4}
{"ts": 1726164201.050, "t_iso": "2026-09-12T15:10:01.050Z", "cat": "THREAD", "act": "yield_slow", "ctx": {"tid": "17_khonsu:L102", "elapsed_ms": 12.4}, "fps": 58.2, "mem_kb": 9215.1}
{"ts": 1726164202.890, "t_iso": "2026-09-12T15:10:02.890Z", "cat": "ERROR", "act": "crash_intercept", "ctx": {"msg": "attempt to index a nil value", "trace": "..."}, "fps": 60.0, "mem_kb": 9240.0}
```

---

## 4. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Shadow Ring Buffer em NDJSON)
1. Criar `doxoade/commands/lite_xl_systems/template/00_00_shadow_logger.lua` (carregado antes de tudo, logo no índice `00`).
2. Interceptar:
   * `command.perform`
   * `core.log` e `core.error`
   * `core.open_doc`
   * Transições de abas e foco
3. Armazenar em `rawset(_G, "_DOXOADE_SHADOW_EVENTS", ...)`.
4. Corrotina descarrega o lote em `.doxoade/diagnostics/shadow_telemetry.ndjson`.
5. Rotação automática de log: se o arquivo ultrapassar 20 MB, rotaciona para `.bak` para não estourar o disco.

### 🔹 Plano B (Fallback — Despejo Síncrono Apenas em Crash / On-Quit)
* Se a máquina apresentar lentidão de I/O em corrotina, desativar o despejo a cada 2s e manter tudo no *Ring Buffer* de memória (últimos 1.000 eventos), descarregando no disco **apenas ao fechar o editor (`core.on_quit`) ou ao capturar um erro fatal**.

### 🔹 Plano C (Contingência — Kill Switch)
* Se `config.doxoade_shadow_logger = false` for definido no `user_settings.lua`, o sistema bypassa completamente os hooks com custo zero.

---

## 5. Estrutura de Arquivos Planejada (< 50KB)
```
doxoade/
├── commands/lite_xl_systems/template/
│   └── 00_00_shadow_logger.lua     # Capturador universal de eventos NDJSON (~12KB)
└── tools/forensic/
    └── shadow_reader.py            # Utilitário Python para ler, filtrar e exportar para ML (~10KB)
```

---

Entendido perfeitamente. Seguindo à risca a regra **4.2 do ProDeNov** (*"Caso o dev não esteja com a capacidade ou prazo para desenvolvimento seguro no momento, não desenvolva no período — apenas planeje"*).

Vamos consolidar a **especificação arquitetural formal** em um documento autocontido, claro e autoexplicativo, de modo que qualquer desenvolvedor ou agente consiga pegar este plano e implementar o sistema do início ao fim sem ambiguidades.

---

# 📜 BLUEPRINT & ESPECIFICAÇÃO DE ENGENHARIA — HADES SHADOW RECORDER
**Identificador do Documento:** `doxoade/docs/Blueprints/blueprint_shadow_event_recorder.md`  
**Panteões Encarregados:** Hades (Persistência Profunda), Hermes (Telemetria) e Anúbis (Auditoria/ML)  
**Conformidade Normativa:** ProDeNov 1.2.1 | PASC-6.1 | Zero-Freeze Guarantee  
**Data:** 12/09/2026  
**Finalidade:** Guia de implementação de caixa-preta contínua de eventos para diagnóstico, perícia pós-morte (*crash dump*) e datasets de Machine Learning.

---

## 1. Contexto e Objetivos (W5 / As 5 Perguntas)

* **O quê (What):**  
  Um subsistema de auditoria em segundo plano (*Shadow Event Flight Recorder*) que intercepta e registra eventos atômicos da IDE (comandos, transições de estado, I/O, corrotinas, telemetria de FPS/GC e exceções) em formato **NDJSON** (*Newline Delimited JSON*).
* **Quem (Who):**  
  Projetado para ser implementado por desenvolvedores da equipe de infraestrutura e consumido por:
  1. Mantenedores em diagnóstico de erros intermitentes.
  2. Pipelines automatizados (`doxoade typhon`, `doxoade regret`).
  3. Modelos de Machine Learning futuros (detecção de anomalias comportamentais e predição de crashes).
* **Onde (Where):**  
  * **Coletor e Buffer (Lua 5.4):** `doxoade/commands/lite_xl_systems/template/00_00_shadow_logger.lua` (carregado como estágio zero de boot).
  * **Destino em Disco:** `.doxoade/diagnostics/shadow_events.ndjson`.
  * **Ingestor e CLI (Python 3.12):** `doxoade/tools/forensic/shadow_ingest.py` e comando CLI `doxoade doxly events`.
* **Quando (When):**  
  Opera em regime contínuo e transparente durante o ciclo de vida do Doxly/Lite XL, desde o frame zero até o fechamento (`on_quit`).
* **Por quê (Why):**  
  Logs tradicionais em texto plano (`session_log.txt`) perdem correlação temporal, são pesados para parsing e não fornecem dados tabulares para IA. Um formato delimitado por linha garante que mesmo um encerramento abrupto do sistema operacional preserve 100% dos eventos anteriores sem corrupção de arquivo.
* **Origem & Consequências (Origin & Consequences):**  
  A ausência de uma caixa-preta estruturada torna custosa a reprodução de bugs raros que dependem de uma sequência específica de ações do usuário (ex: abrir arquivo $\rightarrow$ disparar comando $X$ $\rightarrow$ GC roda $\rightarrow$ crash). O Shadow Recorder resolve isso transformando o uso em um log de eventos cronológico reproduzível.

---

## 2. Requisitos Não-Funcionais & Leis Invioláveis

1. **Lei do Orçamento de Frame (Regra dos 60 FPS / PASC-6.1):**  
   Nenhuma operação de captura pode exceder **0.05ms** no loop principal de renderização. **É estritamente proibido abrir arquivos no disco (`io.open`) dentro de eventos de hotpath** (`DocView:draw`, cliques ou digitação).
2. **Lei do Isolamento de Memória (Ring Buffer):**  
   Os eventos residem em um buffer circular na RAM com teto máximo de 2.000 entradas. Se a corrotina de persistência atrasar, eventos antigos de baixa prioridade são descartados (*drop on overflow*), prevenindo estouro do Garbage Collector.
3. **Privacidade e Proteção de Dados (Sanitização Atômica):**  
   **Nunca** gravar o conteúdo bruto do texto digitado pelo usuário (`text_input`). Registra-se apenas o tipo de evento (ex: `"char_typed"`, tamanho, ou identificador do comando), garantindo conformidade com sigilo de senhas e código confidencial.
4. **Teto de Arquivo do ProDeNov:**  
   Nenhum arquivo do módulo pode ultrapassar **50 KB**.

---

## 3. Arquitetura da Solução

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        ESPAÇO DA UI / SDL2 (HOTPATH)                   │
│                                                                        │
│   [Comando Acionado] ──┐                                              │
│   [Mudança de Aba]   ──┼─► Shadow.record(category, action, context)    │
│   [Exceção / Erro]   ──┤            │                                  │
│   [Frame Spike]      ──┘            ▼ (Custo O(1): ~2 microssegundos)  │
│                        ┌───────────────────────────────┐               │
│                        │   Ring Buffer em Memória Lua  │               │
│                        │   table.insert(_SHADOW_RING)  │               │
│                        └──────────────┬────────────────┘               │
└───────────────────────────────────────┼────────────────────────────────┘
                                        │
                                        ▼ (A cada 2.0s ou Lote de 50 itens)
┌────────────────────────────────────────────────────────────────────────┐
│                     PROCESSO DE FUNDO (SHADOW FLUSHER)                 │
│                                                                        │
│   coroutine de flush ──► Serializa tabela em NDJSON                    │
│                      ──► io.open("shadow_events.ndjson", "a")          │
│                      ──► Despejo síncrono em lote + io.flush()         │
│                      ──► Rotação de arquivo se tamanho > 20 MB         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Contrato de Dados (Schema NDJSON)

Cada linha gravada no arquivo `.doxoade/diagnostics/shadow_events.ndjson` deve ser um JSON válido sem quebras de linha internas:

```json
{"ts": 1726168000.412, "cat": "CMD", "act": "core:open-file", "ctx": {"file": "engine.py"}, "fps": 60.0, "ram_kb": 8920.5}
{"ts": 1726168002.105, "cat": "VIEW", "act": "split_focus", "ctx": {"split": "right", "view": "DocView"}, "fps": 59.8, "ram_kb": 8940.1}
{"ts": 1726168005.820, "cat": "PERF", "act": "frame_spike", "ctx": {"duration_ms": 22.4, "subsystem": "tabs"}, "fps": 44.6, "ram_kb": 9100.0}
{"ts": 1726168010.012, "cat": "INCIDENT", "act": "pcall_catch", "ctx": {"error": "attempt to index nil", "source": "15_audit.lua:88"}, "fps": 60.0, "ram_kb": 9150.2}
```

### Dicionário de Campos:
| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| **`ts`** | `number` | Unix Timestamp com precisão de microssegundos (`os.time() + fractional`). |
| **`cat`** | `string` | Categoria: `BOOT`, `CMD`, `KEY`, `VIEW`, `PERF`, `THREAD`, `INCIDENT`. |
| **`act`** | `string` | Ação ou evento específico disparado. |
| **`ctx`** | `table` | Metadados contextuais (nome do arquivo, tempo gasto, identificadores). |
| **`fps`** | `number` | Taxa de quadros ativa no instante do evento. |
| **`ram_kb`** | `number` | Memória ocupada no Heap da VM Lua (`collectgarbage("count")`). |

---

## 5. Planos de Execução para a Equipe de Implementação (ProDeNov 1.2.1)

### 🔹 Plano A (Principal — Ingestão Contínua com Buffer Circular)
1. **Fase Lua (`00_00_shadow_logger.lua`):**
   * Inicializar tabela global `_DOXOADE_SHADOW_RECORDER`.
   * Envelopar métodos centrais:
     * `command.perform`: captura nomes dos comandos disparados.
     * `core.open_doc`: captura ciclo de arquivos abertos.
     * `core.error`: captura exceções e adiciona *stacktrace* compactado.
   * Disparar corrotina (`core.add_thread`) com ciclo de debounce/intervalo de `2.0s` para descarregar o buffer no arquivo `.ndjson`.
2. **Fase Python (`shadow_ingest.py`):**
   * Criar classe `ShadowDataset` com métodos para carregar os eventos:
     * `load_dataframe()`: converte o NDJSON direto para DataFrame (`pandas`).
     * `get_incident_timeline(radius_seconds=5)`: cruza um erro ocorrido e exibe os 10 eventos antecedentes imediatos.
3. **Fase CLI Click (`cmd_lite_xl.py`):**
   * Adicionar comando: `doxoade doxly events [--tail N] [--cat CATEGORIA] [--export-csv]`.

### 🔹 Plano B (Fallback — Despejo Síncrono Apenas em Encerramento e Crashes)
* Se em ambientes de teste de estresse o I/O da corrotina acusar qualquer overhead, o gravador mantém todos os registros estritamente na memória RAM.
* O despejo no disco é realizado unicamente em dois gatilhos:
  1. Gancho `core.on_quit`: descarrega a sessão inteira antes de sair.
  2. Gancho fatal `core.error`: descarrega imediatamente os últimos 100 eventos para compor a necropsia.

### 🔹 Plano C (Contingência — Kill Switch & Modo Invisível)
* Se `config.doxoade_shadow_recorder == false` for adicionado no `user_settings.lua`, todas as funções de captura retornam sem executar nenhuma ação (custo $0$ de CPU).
* Opção de exclusão ou expurgo com 1 comando: `doxoade doxly events --purge`.

---

## 6. Roteiro de Testes para os Futuros Desenvolvedores (DoD - Definition of Done)

Para o sistema ser aceito e homologado, a equipe precisará validar os 4 testes da matriz:

| ID do Teste | Ação Executada | Resultado Esperado |
| :--- | :--- | :--- |
| **TC-SHADOW-01** | Abrir o Doxly, disparar comandos aleatórios e fechar. | Arquivo `shadow_events.ndjson` deve existir e conter linhas JSON válidas. |
| **TC-SHADOW-02** | Medir latência do frame com `doxoade doxly profile`. | A latência de `draw_line_body` deve permanecer $< 3.0\text{ms}$ (sem queda de FPS). |
| **TC-SHADOW-03** | Simular encerramento forçado do processo (`taskkill /F /IM lite-xl.exe`). | As linhas gravadas até o último ciclo de 2s devem permanecer íntegras e sem corrupção. |
| **TC-SHADOW-04** | Rodar `doxoade regret`. | Nenhuma regressão de chave, comando ou método deve ser apontada nos templates. |

---

Este blueprint está completo, estruturado nos padrões da sua base e arquivado conceitualmente. Quando a equipe futura for implementar, terá todas as diretrizes técnicas e salvaguardas prontas para execução imediata.


