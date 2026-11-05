
# 📜 BLITZPLAN — HÓRUS STATE WATCHDOG & ANÚBIS BLAME TRACKER
**Protocolo:** ProDeNov 1.2.1 | PASC-6.1 | W5
**Panteões Mobilizados:** Hórus (Observabilidade), Ma'at (Invariantes), Anúbis (Forense/Blame) e Chronos (Performance)
**Módulo Alvo:** `doxoade/commands/lite_xl_systems/template/22_plugin_state_watchdog.lua`

---

## 1. Contexto e Objetivos (W5 / As 5 Perguntas)
* **O quê (What):** Um motor forense de interceptação que detecta, isola e aponta a causa raiz de mutações de estado ilegais, *race conditions* e *view orphaning* causadas por plugins nativos do Lite XL. Ele gera um relatório de "Blame" (Culpabilidade) empírico.
* **Quem (Who):** Engenheiros Doxoade investigando crashes intermitentes de `attempt to index a nil value` em `core/docview` ou `Tried to set active view to nil`.
* **Onde (Where):** Hookado nos ciclos de `core.step`, `RootView:draw`, `core.set_active_view` e `core.open_doc`.
* **Quando (When):** Em tempo real, durante a sessão da IDE, com custo $O(1)$ no hotpath para não violar a Regra dos 60 FPS.
* **Por quê (Why):** Plugins como o `autoreload.lua` escutam eventos de I/O de disco e, ao detectarem mudança, destroem e recriam `DocViews` embackground. Se isso ocorrer *durante* um ciclo de renderização (`draw`) ou enquanto o `Node:update_layout` está calculando splits, a árvore de views entra em colapso, gerando telas brancas ou crashes silenciosos do SDL2.
* **Origem & Consequências:** A cegueira forense atual nos obriga a desativar plugins inteiros. Com o Watchdog, ganhamos a capacidade de criar **Vacinas Ma'at** (ex: envelopar apenas `autoreload.check_files` com um `Khonsu.debounce` ou bloquear sua execução se `core.redraw` estiver ativo).

---

## 2. Arquitetura da Solução: Os 4 Cães de Guarda

O sistema opera através de 4 sensores passivos e ativos que alimentam o **Phanto Crisis** e o **Shadow Logger**:

### 🐕 Cão 1: Ma'at View-Tree Invariant Guard (Detector de Mutação Ilegal)
O Lite XL **não permite** que a árvore de views (`node.views`) seja alterada *durante* o `RootView:draw`. O `autoreload` frequentemente viola isso.
* **Mecanismo:** Tira um hash rápido (contador de views + ponteiro do `active_view`) *antes* e *depois* do `RootView:draw`.
* **Ação:** Se a estrutura mudar durante o draw, o Ma'at lança um alerta de `"ILLEGAL_DRAW_MUTATION"` com o stack trace completo, pegando o plugin no flagra.

### 🐕 Cão 2: Hórus Active View Sentinel (Caçador de `nil`)
O crash `Tried to set active view to nil` é a assinatura clássica de um plugin que acabou de fechar uma view e tentou focá-la.
* **Mecanismo:** Hook em `core.set_active_view(view)`. Se `view == nil` ou `view.doc == nil`, o Hórus intercepta, **bloqueia a ação** (evitando o crash) e grava o `debug.traceback` no Phanto Crisis.

### 🐕 Cão 3: Anúbis Stack Blame Resolver (Atribuição de Culpa)
Quando o Lite XL crasha, o traceback geralmente aponta para `data/core/init.lua` ou `tmpXXX.lua` (devido ao AOT Khonsu). O Anúbis sobe a pilha de chamadas procurando por `plugins/` ou `data/plugins/`.
* **Mecanismo:** Extrai o nome do arquivo do plugin (ex: `plugins/autoreload.lua:45`) e o associa ao erro no `phanto_crisis.ndjson`.
* **Resultado:** Um ranking de plugins mais instáveis (`plugin_blame_report.json`).

### 🐕 Cão 4: Chronos Layout Profiler (Detector de Frame Spikes)
Plugins que hookam `Node:update_layout` ou `DocView:update` podem causar engasgos ao redimensionar a janela.
* **Mecanismo:** Mede o tempo de `Node:update_layout`. Se exceder 2ms, grava o evento de spike e varre as corrotinas ativas para identificar o gargalo.

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Interceptação Forense com Blame Tracker)
1. Criar `22_plugin_state_watchdog.lua` com hooks de baixo custo.
2. Implementar o **Blame Tracker** que cruza o `phanto_crisis.ndjson` e gera um resumo no `session_log.txt` ao fechar a IDE:
   ```text
   📊 [HÓRUS BLAME REPORT]
   • plugins/autoreload.lua: 4 mutações ilegais bloqueadas, 2 crashes de nil evitados.
   • plugins/linewrap.lua: 0 incidentes.
   ```
3. Integrar com o **Source Map Resolver** do Khonsu para que o traceback aponte exatamente para a linha do plugin original, e não para o buffer unificado.

### 🔹 Plano B (Fallback — Modo Sentinela Passiva)
Se o ambiente estiver sob estresse extremo de CPU, desativam-se os hashes do Cão 1 e Cão 4, mantendo apenas o **Cão 2 (Hórus Sentinel)** e o **Cão 3 (Anúbis Blame)**, que possuem custo zero de CPU (apenas envelopamento de funções).

### 🔹 Plano C (Contingência — Vacinação Ma'at Imediata)
Com base nos dados coletados pelo Hórus, injetamos vacinas no `00_header_and_logger.lua` para neutralizar plugins tóxicos conhecidos antes mesmo que eles carreguem:
```lua
-- Exemplo de Vacina Ma'at contra o autoreload
local orig_autoreload = package.loaded["plugins.autoreload"]
if orig_autoreload and orig_autoreload.check_files then
    local orig_check = orig_autoreload.check_files
    orig_autoreload.check_files = function(...)
        -- Bloqueia recarregamento se a UI estiver no meio de um draw ou split
        if rawget(_G, "_DOXOADE_DRAW_LOCK") then return end
        return orig_check(...)
    end
end
```

---

## 4. Estrutura de Arquivos e Contratos

```text
doxoade/commands/lite_xl_systems/template/
└── 22_plugin_state_watchdog.lua  # [NOVO] Hórus Watchdog & Anúbis Blame (~12KB)

.doxoade/diagnostics/
├── phanto_crisis.ndjson          # Alimentado com tags de [BLAME: plugin_name]
└── plugin_blame_report.json      # Relatório consolidado de culpabilidade
```

### Contrato de Dados (NDJSON do Phanto com Blame)
```json
{"ts": 1730710000, "cat": "INCIDENT", "act": "nil_view_intercepted", "blame": "plugins/autoreload.lua:82", "ctx": {"msg": "Hórus blocked set_active_view(nil)"}}
{"ts": 1730710005, "cat": "MUTATION", "act": "illegal_draw_mutation", "blame": "plugins/autoreload.lua:114", "ctx": {"msg": "View tree changed during RootView:draw"}}
```

---

## 5. Roteiro de Investigação Profunda (Como usaremos isso)

Com o **Hórus Watchdog** ativo no ambiente de testes (`doxoade doxly deploy test`), poderemos responder empiricamente:

1. **O `autoreload` é o único culpado?**
   * O Blame Tracker vai nos dizer se o `linewrap`, `macmodkeys` ou `scale` também estão corrompendo o `core.active_view`.
2. **Qual é o gatilho exato?**
   * O stack trace do Hórus vai revelar se o crash ocorre quando o usuário salva o arquivo (`Doc:save`), quando o sistema operacional notifica a mudança de arquivo, ou quando o timer de polling do plugin dispara.
3. **Podemos reescrever o `autoreload`?**
   * Se o plugin for estruturalmente inseguro, usaremos os dados para escrever o **Doxoade Auto-Reloader Nativo** (módulo `23_safe_autoreload.lua`), que respeita o ciclo de vida do `Khonsu` e do `RootView:draw`.

---
   
