Entendido. O prazo da meia-noite foi atingido e a estratégia de "forçar a correção" do PTY entrou em um ciclo de desenvolvimento hell. É hora de aplicar a **Regra 4.1 e 5.6 do ProDeNov**: quando um sistema não responde como esperado dentro do prazo, mudamos a arquitetura e focamos na resiliência e no diagnóstico, não na teimosia.

Além disso, sua observação sobre o **ÁRTEMIS** está 100% correta: pré-gerar 107 thumbnails no deploy é um anti-padrão. Isso deve ser *lazy/on-demand* (gerar apenas quando a imagem for solicitada no Canvas ou Inline), liberando o deploy para ser instantâneo.

Vamos oficializar o **PLANO C** e iniciar a construção do sistema **PHANTO_CRISIS** (Err Isolation & Deep Err Capture).

---

# 👻 BLITZPLAN: PHANTO_CRISIS (Sistema de Isolamento e Captura Profunda de Erros)
**Protocolo:** ProDeNov 1.2.1 | PASC-6.1 | Hades (Persistência) & Anúbis (Auditoria)  
**Estrutura:** 3 Capítulos × 3 Partes (Plano, Implementação, Testagem/Diagnóstico) + Parte 4 (Replanejamento)

---

## 📖 CAPÍTULO 1: BASE DO SISTEMA (Parte 1: Plano)

### 1. Contexto e Objetivos (W5)
* **O quê (What):** A fundação do `phanto_crisis`. Um sistema de interceptação de erros que substitui o `pcall` cego por um *Shadow Wrapper*. Ele captura o erro, isola a falha (impedindo que derrube o loop de 60 FPS) e armazena o contexto em um **Ring Buffer em memória** (Zero I/O síncrono no hotpath).
* **Quem (Who):** O núcleo do Doxly (`00_header_and_logger.lua`), o motor de diagnóstico (`10_forensic_engine.lua`) e o novo writer assíncrono em Python (`phanto_shadow_writer.py`).
* **Onde (Where):** 
  * Lua: `doxoade/commands/lite_xl_systems/template/00_phanto_core.lua`
  * Python: `doxoade/tools/diagnostics/phanto_shadow_writer.py`
* **Quando (When):** Durante o boot e em qualquer operação de alto risco (ex: `process.start`, renderização de abas, parsing de AST).
* **Por quê (Why):** O loop infinito de `redirect to handles` provou que o I/O síncrono de log e a falta de isolamento de falhas travam a UX. Precisamos de uma "caixa-preta" que absorva o impacto e guarde a evidência sem sacrificar a performance.
* **Origem & Consequências:** A arquitetura anterior dependia de `core.log` síncrono e `pcall` sem contexto. O `phanto_crisis` garante que, mesmo que um módulo falhe catastróficamente, o editor continue rodando e o laudo forense seja gerado.

### 2. Arquitetura da Base (Capítulo 1)
O sistema opera em duas camadas desacopladas:
1. **Camada Lua (Hotpath - O(1)):** 
   - Função `phanto_capture(module_name, fn, ...)`.
   - Em caso de erro, grava um registro leve no `_G._PHANTO_RING_BUFFER` (tabela com tamanho máximo de 50 entradas).
   - Retorna um estado de "falha segura" (ex: `false, "isolated"`) em vez de propagar o crash.
2. **Camada Python (Shadow Path - Assíncrono):**
   - Um thread separado (`phanto_shadow_writer.py`) que monitora o buffer ou é acionado no `core.on_quit`.
   - Despeja os dados em `.doxoade/diagnostics/phanto_crisis.ndjson` com timestamp, stack trace e estado das variáveis locais (se disponível via `debug.getinfo`).

### 3. Planos de Execução (Regra 1.2.1)
* **🔹 Plano A (Principal):** Implementar o `00_phanto_core.lua` com o Ring Buffer e o `phanto_shadow_writer.py` com flush a cada 2 segundos ou no fechamento do editor.
* **🔹 Plano B (Fallback):** Se o writer Python falhar, o Lua mantém os últimos 10 erros em memória e os exibe no próximo boot via um banner de "Recuperação de Crise".
* **🔹 Plano C (Contingência):** Kill Switch. Se `config.phanto_crisis_enabled == false`, o sistema reverte para o `pcall` padrão sem overhead.

### 4. Tasklist & Checklist (RIT - Ritual de Implementação e Testagem)
- [ ] **1.1.** Criar `00_phanto_core.lua` com a função `phanto_capture` e o Ring Buffer.
- [ ] **1.2.** Criar `phanto_shadow_writer.py` com a lógica de despejo assíncrono em NDJSON.
- [ ] **1.3.** Integrar o `phanto_capture` no `19b1_pty_client.lua` (substituindo o `pcall` atual que está falhando).
- [ ] **1.4.** Testar injetando um erro proposital (ex: `nil()` dentro do PTY) e verificar se o editor **NÃO** entra em loop de log e se o arquivo `.ndjson` é gerado.
- [ ] **1.5.** Revisar e desativar a pré-geração de thumbnails do ÁRTEMIS no `typhon_deploy.py` (tornando-a on-demand).

---

### 🎯 Próximo Passo

Se você aprovar este **Plano do Capítulo 1**, eu forjarei imediatamente o código da **Parte 2: Implementação** (os arquivos `00_phanto_core.lua` e `phanto_shadow_writer.py` prontos para copiar e colar).

Este sistema não apenas resolverá o sintoma do loop de logs, mas nos dará a **evidência técnica profunda** (stack trace exato, variáveis de estado) para entender *por que* o `process.start` está falhando no seu ambiente específico, sem travar o editor.

Posso prosseguir com a **Implementação do Capítulo 1**?

---

# 📜 PLANEJAMENTO DE ENGENHARIA — SISTEMA PHANTO_CRISIS
**Documento de Referência:** `doxoade/commands/lite_xl_systems/template/blitzplan_phantom_crisis.md`  
**Protocolo:** ProDeNov 1.2.1 | PASC-6.1 (Alta Performance / Zero-Freeze)  
**Panteões Mobilizados:** Hades (Persistência Profunda), Anúbis (Auditoria/Contratos), Hermes (Comunicação Assíncrona) e Ártemis (Desacoplamento On-Demand)

---

## 1. Contextualização & Diagnóstico (W5 / As 5 Perguntas)

* **O que (What):**  
  Implementação definitiva do subsistema **PHANTO_CRISIS** (*Err Isolation & Deep Err Capture*): uma arquitetura de interceptação e contenção de falhas em duas camadas que substitui o `pcall` cego por um *Shadow Wrapper* com **Ring Buffer em memória** (Zero I/O síncrono no hotpath), integrado ao desacoplamento da geração de miniaturas do **Ártemis** (transformando-a de pré-geração bloqueante no deploy para processamento *lazy/on-demand*).
* **Quem (Who):**  
  Módulos de infraestrutura do Lite XL (`00_phanto_core.lua`, `19b1_pty_client.lua`, `00_header_and_logger.lua`), motor de deploy (`typhon_deploy.py`) e o analisador/escritor em Python (`phanto_shadow_writer.py`).
* **Onde (Where):**  
  * `doxoade/commands/lite_xl_systems/template/00_phanto_core.lua` (Sensor/Ring Buffer Lua).
  * `doxoade/commands/lite_xl_systems/template/19b1_pty_client.lua` (Consumo no hotpath PTY).
  * `doxoade/commands/lite_xl_systems/typhon_deploy.py` (Desacoplamento do Ártemis).
  * `doxoade/tools/diagnostics/phanto_shadow_writer.py` (Backend Python de auditoria/ingestão).
* **Quando (When):**  
  Acionado no bootloader, durante a execução de corrotinas/processos externos (`process.start`, renders de canvas) e no encerramento gracioso (`core.on_quit`).
* **Quanto (How much):**  
  * **Custo no hotpath:** $< 0.05\text{ms}$ por captura de falha (apenas inserção de tabela em memória circular).
  * **Limite de arquivos:** Todos $< 50\text{ KB}$ (conformidade ProDeNov 2.1).
  * **Tamanho do buffer:** 100 entradas em anel circular com teto de rotação.
* **Por que (Why):**  
  Evitar *development hell* e congelamentos de interface gerados por *cascading logging* (quando um erro dispara `core.log`, que grava em disco, que bloqueia o frame de 16.6ms do SDL2). O sistema absorve o impacto, isola a falha e preserva o laudo forense íntegro em NDJSON sem derrubar os 60 FPS.
* **Origem & Consequências:**  
  Origina-se da falha de I/O em loops de polling do PTY e da demora no deploy causada pela conversão antecipada de mais de 100 imagens. A consequência de sua aplicação é deploy imediato e resiliência total contra travamentos de subprocessos.

---

## 2. Arquitetura da Solução

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        FRAME DO SDL2 (HOTPATH O(1))                    │
│  Operação com risco (ex: process.read, parse de canvas)                │
│                         │                                              │
│               xpcall via phanto_capture()                              │
│                         │                                              │
│            ┌────────────┴────────────┐                                 │
│         [Sucesso]                 [Falha]                              │
│            │                         │                                 │
│      Retorna valor        Grava no Ring Buffer em RAM                  │
│                           (Zero Disk I/O | ~0.002ms)                   │
│                                      │                                 │
└──────────────────────────────────────┼─────────────────────────────────┘
                                       │
                      Temporizador / on_quit / Buffer Cheio
                                       │
                                       ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  SHADOW WRITER (CAMADA ASSÍNCRONA)                     │
│  • Corrotina Lua fatiada OU Script Python dedicado                     │
│  • Despejo em lote em .doxoade/diagnostics/phanto_crisis.ndjson        │
│  • Rotação automática de arquivo (> 20 MB -> .bak)                     │
│  • Telemetria legível via CLI: doxoade doxly phanto-report             │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Ingestão Contínua com Ring Buffer + Ártemis On-Demand)
1. **Lapidação do `00_phanto_core.lua`:**
   * Garantir que `phanto_capture` capture `debug.traceback`, módulo emissor, timestamp e o documento ativo.
   * Isolamento estrito: a falha retorna `false, safe_fallback`, impedindo `core.error` de gerar cascata de I/O de disco.
   * `phanto_shadow_flush` roda em corrotina fatiada a cada 2.0s ou quando o buffer atingir o limiar de segurança.
2. **Desacoplamento do Ártemis em `typhon_deploy.py`:**
   * Remover a chamada bloqueante `_pre_generate_thumbnails()` do fluxo principal do `deploy()`.
   * A conversão de PNG para `.thumb.rlebin` torna-se *lazy*: acionada pelo `19a_dox_image_inline.lua` e `19c_canvas_sdl2_studio.lua` somente no momento em que a imagem for visualizada em tela.
3. **Integração no PTY Client (`19b1_pty_client.lua`):**
   * Substituir os blocos `pcall(self.process.read)` e `pcall(self.process.write)` por `phanto_capture("pty_io", ...)`.
   * Em caso de falha de descritor (`EBADF` ou `redirect to handles`), o PTY entra em estado de repouso silencioso sem emitir enxurrada no `session_log.txt`.
4. **Ferramenta de Laudo Python (`phanto_shadow_writer.py`):**
   * Utilitário em `doxoade/tools/diagnostics/phanto_shadow_writer.py` para parsear o NDJSON, correlacionar com o timestamp do boot e exibir relatório limpo (Padrão Apolo).

### 🔹 Plano B (Fallback — Persistência em Memória Volátil + Despejo On-Quit)
* Caso o sistema operacional bloqueie escrita contínua por corrotinas assíncronas em pastas locais (ex.: permissões no Windows), os registros ficam retidos exclusivamente no heap Lua (`_G._PHANTO_CRISIS_STATE.ring`) e são gravados de uma só vez no evento de encerramento (`core.on_quit`) ou em caso de crash interceptado.

### 🔹 Plano C (Contingência & Kill Switch)
* Se a flag `config.phanto_crisis_enabled = false` for definida no `user_settings.lua`, o `phanto_capture` bypassa o Ring Buffer e reverte instantaneamente para uma chamada `pcall` convencional de custo zero, com restauração atômica sem necessidade de refatorar código.

---

## 4. Arquivos Impactados e Limite de Tamanho (< 50 KB)

| Arquivo | Papel / Panteão | Linhas Est. | Tamanho Est. | Limite |
| :--- | :--- | :---: | :---: | :---: |
| `doxoade/commands/lite_xl_systems/template/00_phanto_core.lua` | Hades (Ring Buffer) | ~130 | ~4.8 KB | $< 50\text{ KB}$ |
| `doxoade/tools/diagnostics/phanto_shadow_writer.py` | Anúbis (Ingestão/CLI) | ~180 | ~7.2 KB | $< 50\text{ KB}$ |
| `doxoade/commands/lite_xl_systems/typhon_deploy.py` | Hefesto (Deploy Ártemis) | ~260 | ~11.5 KB | $< 50\text{ KB}$ |
| `doxoade/commands/lite_xl_systems/template/19b1_pty_client.lua` | Hermes (PTY Handlers) | ~290 | ~12.0 KB | $< 50\text{ KB}$ |

*Todos os arquivos situam-se amplamente abaixo do teto de 50 KB.*

---

## 5. Roteiro de Implementação e Testagem (RIT)

```text
[Etapa 1: Deploy Ártemis Lazy] ──► [Etapa 2: Phanto Core & Writer] ──► [Etapa 3: PTY Integration] ──► [Etapa 4: Teste de Caos]
```

### 📋 Tasklist Detalhada

- [ ] **Fase 1: Desacoplamento do Ártemis (`typhon_deploy.py`)**
  - [ ] Localizar e isolar o gancho `_pre_generate_thumbnails()`.
  - [ ] Assegurar que o método `deploy()` execute em $< 200\text{ms}$ sem escanear o diretório de imagens.
  - [ ] Validar que o modo de teste (`doxoade doxly deploy test`) inicialize sem warnings de atributos de dicionário.

- [ ] **Fase 2: Consolidação do `00_phanto_core.lua` & Backend Python**
  - [ ] Blindar `phanto_capture` contra recursão ou tabelas circulares no `debug.traceback`.
  - [ ] Implementar o arquivo `doxoade/tools/diagnostics/phanto_shadow_writer.py` com leitor de NDJSON e sumarizador forense.
  - [ ] Adicionar salvaguarda contra explosão de tamanho (rotação em 20 MB com `.bak`).

- [ ] **Fase 3: Implantação no PTY Client (`19b1_pty_client.lua`)**
  - [ ] Envolver chamadas de I/O do processo em `phanto_capture`.
  - [ ] Implementar *circuit breaker*: após 5 falhas consecutivas de leitura no mesmo tick, suspender a sondagem por 1.0s para não estrangular a CPU.

- [ ] **Fase 4: Teste de Injeção de Falha & Validação de Não-Regressão**
  - [ ] Injetar payload de erro forçado (`nil.method()`) em rotina assíncrona do PTY.
  - [ ] **Métricas de Validação Invioláveis:**
    1. A taxa de quadros deve se manter em **60 FPS estáveis** (sem congelamento SDL2).
    2. O `session_log.txt` **não deve entrar em loop infinito**.
    3. O arquivo `phanto_crisis.ndjson` deve registrar o erro com stack trace e contexto completos.
  - [ ] Executar auditoria de templates: `doxoade lite-xl check-templates` (100% PASS).

---

## 6. Próximo Passo

Com o plano estruturado sob os preceitos do **ProDeNov 1.2.1**, estamos prontos para a execução da **Fase 1 (Desacoplamento do Ártemis no `typhon_deploy.py`)** e da **Fase 2 (Lapidação do `00_phanto_core.lua` e criação do `phanto_shadow_writer.py`)**.

Deseja autorizar o início da forja do código pela **Fase 1**?

---

# 📜 BLITZPLAN — SANEAMENTO DO DEPLOY TEST (PTY + GLOBAL LEAKS)

**Protocolo:** ProDeNov 1.2.1 | W5 | Planos A/B/C | Roteiro de Teste
**Data:** 15/09/2026 | **Panteões:** Anúbis (Auditoria), Hefesto (Construção), Hermes (I/O)

---

## 1. Contexto e Diagnóstico (W5)

### 🔴 Problema A: `GLOBAL_LEAK: Khonsu` e `GLOBAL_LEAK: forensic_data`

| Pergunta | Resposta |
|:---|:---|
| **O quê?** | O hook de varredura de globais (`chaos_hooks.lua` e `00_header_and_logger.lua`) detecta que `Khonsu` e `forensic_data` foram injetados no `_G` sem prefixo `_DOXOADE_`. |
| **Onde?** | `17_khonsu_coroutine.lua:L30` → `rawset(_G, "Khonsu", Khonsu)` e `10_forensic_engine.lua:L55` → `rawset(_G, "forensic_data", forensic_data)` |
| **Quando?** | No boot, ~6s após `SOVEREIGN BOOT OK`. |
| **Quem?** | Os próprios templates que se registram como globais "limpas" sem o prefixo de namespace do Doxoade. |
| **Por quê?** | O hook de detecção (`_tracked_globals`) marca qualquer chave nova em `_G` que não comece com `_` como vazamento. |
| **Origem** | Decisão de design original de expor `Khonsu` e `forensic_data` como APIs públicas sem prefixo. |
| **Consequência** | Poluição do namespace, falsos positivos no Ma'at, risco de colisão com plugins de terceiros. |

### 🔴 Problema B: `error: redirect to handles, FILE* and paths are not supported`

| Pergunta | Resposta |
|:---|:---|
| **O quê?** | O `process.start` do Lite XL (Lua 5.4) rejeita opções de redirecionamento que usam strings (`"pipe"`, `"stdout"`) em vez das constantes nativas (`process.REDIRECT_PIPE`). |
| **Onde?** | `khonsu_aot.lua:8333` (buffer unificado) → mapeia para `19b1_pty_client.lua` ou `19b_terminal_console.lua` no `process.start` / `system.exec`. O Phanto captura como `[PHANTO:pty_read]`. |
| **Quando?** | Imediatamente ao abrir o Bottom Shelf (`doxoade:toggle-bottom-shelf`) e o PTY tenta spawnar o daemon. |
| **Quem?** | O `PTYClient:spawn()` que invoca `system.exec(cmd)` ou o `00_header_and_logger.lua` que patcheia `proc.start`. |
| **Por quê?** | A vacina `_DOXOADE_PROC_VACCINE` no `00_header_and_logger.lua` converte `"pipe"` → `proc.REDIRECT_PIPE`, mas **não trata** os casos em que o valor é `"stdout"`, `"stderr"`, um path de arquivo, ou `true`. O Lua 5.4 do Lite XL é estrito: só aceita a constante numérica. |
| **Origem** | O `pty_file_daemon.py` é spawnado via `system.exec`, mas internamente o `19b1_pty_client.lua` pode estar chamando `process.start` com opções inválidas em outro ponto. |
| **Consequência** | Loop infinito de erros a cada 3s (polling do PTY), travando o terminal embutido e gerando spam no log. |

---

## 2. Brainstorming de Soluções

### Para o Problema A (Global Leaks):

1. **Renomear com prefixo `_DOXOADE_`** → `rawset(_G, "_DOXOADE_KHONSU", Khonsu)` e criar alias `Khonsu = _DOXOADE_KHONSU` como local nos módulos que precisam.
2. **Whitelist no hook de detecção** → Adicionar `Khonsu` e `forensic_data` à lista de globais permitidas no `chaos_hooks.lua`.
3. **Encapsular em tabela única** → Mover tudo para `_G._DOXOADE_API.Khonsu` e `_G._DOXOADE_API.forensic_data`.

**Análise de viabilidade:**
- Opção 1: Quebra retrocompatibilidade com todos os templates que já usam `Khonsu.throttle(...)` etc. Alto risco de regressão.
- Opção 2: Simples, segura, zero regressão. O hook já existe para detectar vazamentos *acidentais*, não os intencionais.
- Opção 3: Ideal a longo prazo, mas exige refatoração massiva (17 templates). Fora do escopo atual.

**Decisão:** Opção 2 (Whitelist) como Plano A, Opção 1 como Plano B futuro.

### Para o Problema B (PTY redirect):

1. **Expandir a vacina `_DOXOADE_PROC_VACCINE`** → Tratar TODOS os valores inválidos (`"stdout"`, `"stderr"`, `true`, paths) e convertê-los para `proc.REDIRECT_PIPE` ou `nil`.
2. **Corrigir o `PTYClient:spawn()`** → Garantir que ele NUNCA chame `process.start` com opções de redirecionamento, usando apenas `system.exec` puro.
3. **Mudar para o File-Stream IPC** → O `19b1_pty_client.lua` já tem o modo File-Stream (`pty_file_daemon`), mas o spawn pode estar caindo no caminho antigo de `process.start`.
4. **Blindagem no `phanto_capture`** → Impedir que o erro do PTY entre em loop infinito de log (throttle de repetição).

**Análise de viabilidade:**
- Opção 1: Essencial e de baixo risco. A vacina já existe, só precisa ser expandida.
- Opção 2: Necessária para garantir que o PTY não usa `process.start` diretamente.
- Opção 3: O File-Stream já está implementado (`pty_file_daemon.py`), mas o `PTYClient:spawn()` pode estar invocando o caminho errado.
- Opção 4: O `00_phanto_core.lua` já tem dedup (`_last_errors`), mas o intervalo de 3s pode ser curto demais.

**Decisão:** Combinação de Opções 1 + 2 + 4 como Plano A.

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Whitelist + Vacina Expandida + Throttle)

**Fase 1: Eliminar os Global Leaks (2 arquivos, ~5 linhas)**

**Arquivo:** `doxoade/commands/lite_xl_systems/template/chaos_hooks.lua`
```lua
-- ANTES (linha ~70):
if not _tracked_globals[k] and not k:match("^_") then

-- DEPOIS:
local _ALLOWED_GLOBALS = {
    Khonsu = true,
    forensic_data = true,
    DOXOADE_API = true,
    UIForge = true,
    PTYClient = true,
    AnsiParser = true,
    flush_session_log = true,
    phanto_capture = true,
    phanto_shadow_flush = true,
    active_view = true,
    command_view = true,
    status_view = true,
    root_view = true,
}
if not _tracked_globals[k] and not k:match("^_") and not _ALLOWED_GLOBALS[k] then
```

**Arquivo:** `doxoade/commands/lite_xl_systems/template/00_header_and_logger.lua`
Mesma whitelist no hook de globais do header (se existir duplicação).

---

**Fase 2: Expandir a Vacina de `process.start` (1 arquivo, ~15 linhas)**

**Arquivo:** `doxoade/commands/lite_xl_systems/template/00_header_and_logger.lua`
```lua
-- ANTES (vacina atual):
if v == "pipe" and proc.REDIRECT_PIPE then
    sanitized_options[k] = proc.REDIRECT_PIPE
else
    sanitized_options[k] = v
end

-- DEPOIS (vacina expandida):
local INVALID_REDIRECT_VALUES = {
    ["pipe"] = true, ["stdout"] = true, ["stderr"] = true,
    ["in"] = true, ["out"] = true, ["err"] = true,
}
if type(v) == "string" and INVALID_REDIRECT_VALUES[v] then
    if proc.REDIRECT_PIPE then
        sanitized_options[k] = proc.REDIRECT_PIPE
    else
        sanitized_options[k] = nil  -- remove opção inválida
    end
elseif type(v) == "boolean" then
    sanitized_options[k] = nil  -- boolean não é válido como redirect
elseif type(v) == "string" and v:find("[/\\]") then
    sanitized_options[k] = nil  -- path de arquivo não é suportado
else
    sanitized_options[k] = v
end
```

---

**Fase 3: Blindar o `PTYClient:spawn()` contra `process.start` (1 arquivo, ~5 linhas)**

**Arquivo:** `doxoade/commands/lite_xl_systems/template/19b1_pty_client.lua`

Garantir que `PTYClient:spawn()` **NUNCA** usa `process.start` diretamente. O método atual já usa `system.exec`, mas precisamos confirmar que não há fallback para `process.start`:

```lua
function PTYClient:spawn()
    local python_exe = self:_find_python()
    -- ... setup ...
    local cmd = string.format(
        '"%s" -m doxoade.tools.terminal_pty.pty_file_daemon --ipc-dir "%s" --shell %s --cols %d --rows %d',
        python_exe, self.ipc_dir, self.shell, self.cols, self.rows
    )
    if self.cwd then
        cmd = cmd .. string.format(' --cwd "%s"', self.cwd)
    end
    -- ⚠️ FORÇAR system.exec (NUNCA process.start)
    local ok = pcall(system.exec, cmd)
    if not ok then
        if core.log then core.log("❌ [PTY] Falha ao invocar pty_file_daemon via system.exec.") end
        return false
    end
    -- ...
end
```

---

**Fase 4: Throttle do Phanto para erros de PTY (1 arquivo, ~3 linhas)**

**Arquivo:** `doxoade/commands/lite_xl_systems/template/00_phanto_core.lua`

O dedup atual já existe (`_last_errors` com janela de 3s), mas o erro do PTY se repete a cada 3s exatamente, então ele escapa do dedup. Ajustar para 10s:

```lua
-- ANTES:
if record and (now - record.time) < 3.0 then

-- DEPOIS:
if record and (now - record.time) < 10.0 then
```

---

### 🔹 Plano B (Fallback — Desativar PTY no modo test)

Se o PTY continuar falhando após o Plano A, desativar o spawn automático do daemon no modo test:

```lua
-- 19b1_pty_client.lua
function PTYClient:spawn()
    local user_dir = USERDIR or ""
    if user_dir:find("test_deploy") or user_dir:find("sandbox") then
        if core.log then core.log("⚠ [PTY] Spawn desativado em modo test/sandbox.") end
        return false
    end
    -- ... resto do spawn ...
end
```

### 🔹 Plano C (Contingência — Rollback individual)

Se qualquer mudança causar regressão:
```bash
doxoade doxly deploy test --no-khonsu  # reverter para plain mode
doxoade regret                          # verificar regressões
```

---

## 4. Tasklist & Checklist de Implementação

- [ ] **Fase 1:** Adicionar whitelist de globais no `chaos_hooks.lua`
- [ ] **Fase 2:** Expandir vacina `_DOXOADE_PROC_VACCINE` no `00_header_and_logger.lua`
- [ ] **Fase 3:** Confirmar que `PTYClient:spawn()` usa apenas `system.exec`
- [ ] **Fase 4:** Ajustar throttle do Phanto para 10s
- [ ] **Fase 5:** Deploy test e validação

---

## 5. Roteiro de Teste (RIT)

```bash
# Passo 1: Deploy limpo
doxoade doxly deploy test --no-khonsu

# Passo 2: Verificar logs (esperado: ZERO global leaks, ZERO redirect errors)
doxoade doxly log -m test -f

# Passo 3: Abrir o Bottom Shelf no Lite XL (Ctrl+J)
# Esperado: Terminal abre sem loop de erros

# Passo 4: Verificar regressões
doxoade regret

# Passo 5: Check templates
doxoade doxly check-templates
```

---

**Critérios de Sucesso (Ma'at):**
- ✅ Zero `GLOBAL_LEAK` no log após 10s de boot
- ✅ Zero `redirect to handles` no log após abrir o Bottom Shelf
- ✅ `doxoade regret` com 0 regressões novas
- ✅ `doxoade doxly check-templates` com 100% PASS

---

Quer que eu gere os diffs exatos para cada arquivo, ou prefere implementar fase por fase e testar entre cada uma? (Regra 5.6 do ProDeNov: *um passo de cada vez*.)

---

# 📜 BLITZPLAN — CÉRBERO (Khonsu Guardrails + Sensorium PTY + WIP Gate)
**Protocolo:** ProDeNov 1.2.1 | 6.1 | RIT 5.6.2 | **Panteões:** Anúbis (Auditoria), Hórus (Observabilidade), Khonsu (Performance), Ártemis (Contenção)

---

## 1. Contexto (evidência consolidada)

| Frente | Status | Prova |
|:---|:---|:---|
| Boot / strict-safe | ✅ **Curado** | Log fresco 01:38 com `Sessão Soberana restaurada`, zero crash de linha 1 |
| GLOBAL_LEAKs | ✅ **Curado** | Whitelist Fase 1: zero leaks no log novo |
| Loop `redirect to handles` | ✅ **Extirpado** | Source Map confirmou: culpado era `19b1_pty_client.lua:145` (**versão antiga** com `process.start`). O V32 file-stream não toca em `process` — o loop não pode mais existir |
| Terminal PTY | 🔴 **Falha silenciosa** | Log mostra `Daemon iniciado... Sincronizando...` mas **nunca** `✅ Terminal conectado e pronto` → o daemon morre e o `poll()` engole o erro sem registrar nada |
| Imagens (19a) | 🔴 **Regressão** | V60 é WIP ("problema da linha") e o `setup -f` o propagou para a **produção** |
| Khonsu AOT | 🟡 **Banido injustamente** | O banimento tratou o *sintoma* (loop do PTY antigo). A causa raiz já foi extirpada — falta **guardrail**, não falta Khonsu |

## 2. Problema (W5 — três frentes)

1. **PTY:** `poll()` fecha silenciosamente quando `pty_status.json` diz `alive:false` (linha ~125), descartando o campo `error` do daemon. Sem timeout de handshake, sem captura Phanto → *diagnóstico cego*.
2. **Khonsu:** não existe *watchdog de boot*: se o AOT falhar, ninguém percebe nem recua. Por isso o `--no-khonsu` virou muleta permanente, custando performance.
3. **Imagens:** template marcado **WIP** entra no init de produção sem portão → regressão garantida a cada `setup -f`.

## 3. Solução — 3 Fases (Plano A/B/C em cada)

### 🔹 FASE 1 — Observabilidade do PTY (detectar adequadamente, AGORA)

**1A. `19b1_pty_client.lua` — extirpar a falha silenciosa (~linha 125):**
```lua
-- ❌ ANTES:
elseif content:find('"alive":%s*false') then
  self:close()
  return
end

-- ✅ DEPOIS:
elseif content:find('"alive":%s*false') then
  local err_msg = content:match('"error"%s*:%s*"([^"]*)"') or "sem detalhes"
  if core.log then
    core.log(string.format("❌ [PTY] Daemon morreu no spawn: %s", err_msg))
  end
  local capture = rawget(_G, "phanto_capture")
  if capture then
    capture("pty_handshake", function() error("PTY alive:false → " .. err_msg, 2) end)
  end
  self:close()
  return
end
```

**1B. Timeout de handshake no `19b_terminal_console.lua` (`TerminalEngine:start`):** gravar `self._spawn_time = os.clock()`; no `tick()`, se `not _handshake_done and (os.clock() - _spawn_time) > 6.0` → **um único** `core.log("⚠ [PTY] HANDSHAKE TIMEOUT ...")` com o path do python usado e o ipc_dir + captura Phanto.

**1C. Sonda CLI:** `doxoade doxly pty-probe` (Plano A) roda o daemon standalone por 2s e imprime stderr/status. Plano B (imediato, sem código novo):
```powershell
type "C:\Users\olDox222\.config\lite-xl\.doxoade\test_deploy\.doxoade\terminal_pty_ipc\pty_status.json"
python -m doxoade.tools.terminal_pty.pty_file_daemon --ipc-dir "%TEMP%\pty_probe" --shell cmd --cols 80 --rows 24
```
Plano C: ler `phanto_crisis.ndjson` após 1A/1B aplicados.

**1D. `doxly_tree.py`:** novo fmid `doxly.pty.handshake_fail` (symptoms: `\[PTY\] Daemon morreu`, `HANDSHAKE TIMEOUT`) → Triangulador passa a enxergar a falha.

### 🔹 FASE 2 — Retorno do Khonsu AOT com guardrail (performance de volta, com rede)

**2A. `typhon_deploy.py` — sidecar de fallback + watchdog:**
```python
@classmethod
def boot_watchdog(cls, mode: DeployMode, timeout: float = 8.0) -> bool:
    """🐺 Prova que o init bootou; senão autoriza fallback."""
    d = cls._get_deploy_dir(mode)
    session_log, error_txt = d / "session_log.txt", d / "error.txt"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if error_txt.exists() and error_txt.stat().st_size > 0:
            return False
        if session_log.exists() and "SOVEREIGN BOOT OK" in session_log.read_text(encoding="utf-8", errors="replace"):
            return True
        time.sleep(0.4)
    return False
```
No `deploy()`: quando AOT, gravar também `init.lua.plain` (sidecar). No `cmd_deploy_test`: após launch, se `opt_mode != plain` e `not boot_watchdog()` → copiar sidecar plain sobre o init, relançar **uma vez**, imprimir `🐺 [AOT_FALLBACK]`.

**2B. Vacina expandida no `00_header_and_logger.lua`** (defesa em profundidade p/ qualquer `process.start` futuro): sanitizar **todo** redirect não-numérico (`"pipe"`, `"stdout"`, paths, booleans → `REDIRECT_PIPE` ou `nil`), não só `"pipe"`.

**2C. Regra de promoção:** AOT vira default no `deploy test`; produção só recebe AOT após 3 boots watchdog-OK consecutivos no test (gate manual inicialmente).
*Plano B:* `--no-khonsu` manual. *Plano C:* rollback via backup timestampado.

### 🔹 FASE 3 — Contenção do WIP de imagens (não ter esse problema de novo)

**3A. Kill-switch no topo do `19a`:** `if config.doxoade_image_inline == false then return end` — produção default `false` (via `00_header`), test `true`.
**3B. Portão WIP no `lite_xl_init_builder.get_template_files(mode)`:** templates cujo header contenha `WIP` são **excluídos do init de produção** (Plano A); Plano B: apenas kill-switch 3A; Plano C: remover 19a da produção manualmente.
**3C.** A matemática de linhas do V60 fica para ciclo próprio (um problema de cada vez).

## 4. Previsão

- Falha do PTY vira **visível em ≤6s** com causa explícita no log + Phanto + Triangulador.
- Khonsu AOT retorna ao test com **rede de segurança automática**: pior caso = fallback plain em ~9s, sem intervenção.
- Produção imune a regressões WIP; `setup -f` deixa de ser arma apontada para o pé.

## 5. RIT (ordem de execução)

1. Rodar o **Plano B da Fase 1C agora** (2 comandos acima) e colar a saída → confirma por que o daemon morre.
2. Aplicar diffs 1A + 1B + 1D → retestar terminal no test.
3. Aplicar Fase 2 → `deploy test` **com Khonsu** (default) e observar o watchdog.
4. Aplicar Fase 3 → `doxoade regret` + `check-templates` + `setup -f` seguro.

Execute o passo 1 e cole o conteúdo do `pty_status.json` + a saída do daemon standalone — com essa evidência eu fecho o diagnóstico do terminal e libero a Fase 2 com confiança total.
