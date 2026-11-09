
# 📋 Plano — Sistema de Diagnóstico V2

## 🎯 Contexto: o que nos desacelerou

5 problemas distintos convergiram nesta crise. Cada um **mascarava o outro**:

| # | Problema | Custou |
|---|---|---|
| **P1** | Crash em `node.lua:321` (não hookado) escapou por 4 iterações | ~6h |
| **P2** | `resolve-line` retorna mapeamento **stale** (buffer regenerado ≠ init.lua do crash) | ~2h |
| **P3** | 6 arquivos NDJSON independentes sem correlação cruzada | ~1h |
| **P4** | `"horizontal"` em vez de `"hsplit"` nunca detectado estaticamente | ~3h |
| **P5** | `--audit` dizia "íntegra" enquanto o editor crashava | ~2h |

Total: ~14h de tentativa-erro que poderiam ser ~3h com ferramental correto.

---

## 🏗️ Plano em 5 Fases

### 🔷 FASE 1 — Consolidar Telemetria (2h)

**Objetivo**: 1 arquivo NDJSON com correlação cruzada, ao invés de 6 fragmentados.

**Entregáveis**:
- `27_unified_telemetry.lua` — absorve `22_plugin_state_watchdog`, `24_trigger_tracker`, `25_keymap_forensic`
- `sensorium.ndjson` único substitui `flow_trace.ndjson`, `trigger_tracker.ndjson`, `keymap_forensic.json`, `plugin_state_audit.ndjson`
- Cada evento tem `correlation_id` (mesmo ID propagado em toda a cadeia `KEY → DISPATCH → EXEC → EFFECT → EXIT`)
- `10_forensic_engine` e `23_traceback_translator` escrevem no mesmo arquivo com prefixo de categoria (`PERF:`, `TRACE:`)
- CLI: `flow --correlate <id>` mostra timeline completa de 1 comando

**Critério de aceite**:
- `ls .doxoade/diagnostics/*.ndjson` → **1 arquivo** (era 6)
- `flow --correlate a1b2c3` retorna sequência cronológica completa
- Zero regressão: `--audit` continua funcionando

**Por quê primeiro**: reduz ruído em 80%. Todas as fases seguintes consomem do mesmo arquivo.

---

### 🔷 FASE 2 — Prevenção Estática de Contratos (3h)

**Objetivo**: `"horizontal"` nunca mais chega em produção.

**Entregáveis**:
- `lite_xl_contracts.yaml` — catálogo de invariantes:
  ```yaml
  node_types:
    valid: [leaf, hsplit, vsplit]
    forbidden: [horizontal, vertical, split, tree]
  node_fields:
    position: {type: table, required: true, sub: {x: number, y: number}}
    size:     {type: table, required: true, sub: {x: number, y: number}}
    views:    {type: table, required: true}
  functions:
    - name: Node:update_layout
      precondition: "self.position and self.size"
    - name: Node:get_child_overlapping_point
      precondition: "for each c in {self.a, self.b}: c ~= nil"
  ```
- `lite_xl_contract_validator.py` — analisa AST dos templates + detecta:
  - Atribuições de tipo inválido (`node.type = "horizontal"`)
  - `position = nil` ou `size = nil` em nós
  - Padrões como `node.size.x` sem guard
- `check-templates --check-contracts` — flag nova
- `preflight` bloqueia se `contract_violations > 0`

**Critério de aceite**:
- Detecta **exatamente** o bug que acabamos de corrigir (retro-análise)
- Detecta `npp_layout` acessando `node.size.x` sem guard
- Zero falso-positivo nos 48 templates atuais

**Por quê segundo**: previne regressão. Sem isso, próximos fixes podem reintroduzir o problema.

---

### 🔷 FASE 3 — Diagnóstico de AOT vs Source Confiável (1h)

**Objetivo**: `resolve-line` nunca mais dá resposta stale.

**Entregáveis**:
- `deploy` avisa claramente: *"Modo AOT ativo. Para debug com source map, use `--no-khonsu` ou `--debug-mode`"*
- `resolve-line --from-init <path>` — lê o `init.lua` **real** ao invés de regenerar
- `resolve-line` falha rápido se `init.lua` é bytecode: *"Bytecode não tem source map mapeável"*
- Buffer unificado ganha **fingerprint** (`sha256`) armazenado em `last_build.json`
- `resolve-line` compara fingerprint e avisa se buffer mudou desde o crash
- `flow --diagnose` roda `resolve-line` automaticamente para cada `ERROR` do trace

**Critério de aceite**:
- `resolve-line 3448` (após deploy) retorna a linha **exata** do crash
- Se buffer foi regenerado, emite `⚠ Buffer mudou após crash. Mapeamento não confiável.`

**Por quê terceiro**: sem isso, `resolve-line` é pior que nada (dá falsa confiança).

---

### 🔷 FASE 4 — Cobertura de Hooks Completa (2h)

**Objetivo**: nenhum crash interno escapa do `flow --audit`.

**Entregáveis**:
- Hook defensivo em `npp_layout` (`03b_tab_compact_staircase`):
  ```lua
  local _orig_npp_layout = npp_layout
  npp_layout = function(node)
    if not node.size or not node.position then
      record({phase="LAYOUT_ERROR", cmd="npp_layout",
              info='{"reason":"missing size/position"}'})
      return {n=0, rects={}, ids={}, row_h=20, total_h=20}  -- fallback
    end
    return _orig_npp_layout(node)
  end
  ```
- `--audit` ganha seção **"Funções críticas não hookadas"** via análise estática:
  - Scan dos templates: quem acessa `node.position`/`node.size` sem guard?
  - Scan dos core: `node.lua`, `rootview.lua` — funções não cobertas por guard
- `flow --coverage` — reporta % de funções críticas hookadas (meta: 100%)
- Auto-detecta `unhooked_crash_path` no trace

**Critério de aceite**:
- `flow --coverage` mostra ≥ 95% das funções críticas cobertas
- Testes de estresse (`Ctrl+L` + `Ctrl+Alt+D` + `Ctrl+Shift+L` + `F6`) **não** geram `ERROR` silencioso

---

### 🔷 FASE 5 — Recuperação Automática Pós-Crash (3h)

**Objetivo**: nunca mais debugar por tentativa.

**Entregáveis**:
- `deploy --safe-mode` — se crash em < 30s após launch, **rollback automático** para `.stable`
- `regret` roda **automaticamente** no final do deploy (bloqueia se regressão crítica)
- `flow --diagnose` — agrega:
  - Timeline do crash (`--last N` antes do `ERROR`)
  - `resolve-line` correto (Fase 3)
  - Hooks ausentes (Fase 4)
  - Sugestão de fix baseada em `lite_xl_contracts.yaml`
  ```
  🔴 DIAGNÓSTICO
  Crash: node.lua:321 (get_child_overlapping_point)
  Causa provável: 26_doxly_flow_tracer não hooka esta função
  Fix sugerido: adicionar guard em get_child_overlapping_point
  Contrato violado: node.a=nil sem pre-check
  ```
- `deploy --require-regret` — falha se `regret` detectar regressão nova

**Critério de aceite**:
- Crash simulado (`chaos-deep`) → rollback em < 35s sem intervenção
- `flow --diagnose` fornece **fix aplicável** (snippet pronto para colar)

---

## 📊 Priorização Recomendada

| Fase | Tempo | Valor | Ordem |
|---|---|---|---|
| **1. Consolidar** | 2h | ⭐⭐⭐⭐⭐ | **1º** — reduz ruído em 80% |
| **3. AOT/Source** | 1h | ⭐⭐⭐⭐⭐ | **2º** — habilita debug confiável |
| **2. Contratos** | 3h | ⭐⭐⭐⭐ | **3º** — previne regressão |
| **4. Hooks** | 2h | ⭐⭐⭐ | 4º — cobertura total |
| **5. Recovery** | 3h | ⭐⭐⭐ | 5º — nice to have |

**Total: ~11h** fatiável em entregas de 30-60 min.

**Recomendação de execução**:
```
Semana 1:  Fase 1 (2h) + Fase 3 (1h)         → base confiável
Semana 2:  Fase 2 (3h)                        → prevenção de regressão
Semana 3:  Fase 4 (2h) + limpeza              → cobertura
Semana 4:  Fase 5 (3h)                        → automação completa
```
