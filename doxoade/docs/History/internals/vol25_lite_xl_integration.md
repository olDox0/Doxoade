```lua
return {
  ["config"] = {
    ["fps"] = 60,
    ["transitions"] = false
  }
}
```

#### B. Binary Doc Guard & Preservação do Highlighter
Em vez de anular `doc.highlighter`, o guard intercepta a abertura no `core.open_doc`:
```lua
if first_line:find("^\x1bLua") or first_line:find("%z") then
  doc.syntax = (syntax_mod and syntax_mod.plain_text_syntax) or { patterns = {}, symbols = {} }
  if doc.highlighter and doc.highlighter.reset then
    doc.highlighter:reset()
  end
end
```

#### C. Tokenizer Active Shield V2.2 com Lexer Semântico O(N)
* **Binary Short-Circuit**: Se a linha contiver `%z` ou `^\x1bLua`, retorna `{ "normal", text }, nil` instantaneamente sem chamar o motor de regex do Lua.
* **Lexer Semântico de Alta Disponibilidade**: Se o motor nativo falhar, processa a linha via `safe_lex_semantic_line`, decompondo identificadores (`symbol`), palavras-chave (`keyword`) e alimentando o dicionário do `autocomplete.lua`.

---

### 3. TYPHON DOXLY: MECANISMO DE TRIANGULAÇÃO DE 3 VIAS

A teoria de diagnóstico do Typhon foi adaptada para o ecossistema Lite XL, cruzando 3 fontes simultâneas de verdade:

```text
                       ╔══════════════════════════════════╗
                       ║   TYPHON DOXLY TRIANGULATION     ║
                       ╚══════════════════════════════════╝
                                      ▲
                                     ╱ ╲
                                    ╱   ╲
     ┌───────────────────────────┐         ┌───────────────────────────┐
     │  VIA 1: SOTÉRIA ENVELOPES │         │   VIA 2: PROBES VIVOS     │
     │  (Varredura de Sintomas)  │◄───────►│  (Inspeção de Invariantes)│
     └───────────────────────────┘         └───────────────────────────┘
                  ▲                                     ▲
                   ╲                                   ╱
                    ▼                                 ▼
                     ┌───────────────────────────────┐
                     │     VIA 3: PROVA DE CAOS      │
                     │  (Injeção & Sensibilidade)    │
                     └───────────────────────────────┘
```

#### Componentes do Typhon Doxly:
1. **`doxly_tree.py`**: Árvore taxonômica declarativa contendo 5 subsistemas e 12 modos de falha reais catalogados com sintomas regex tolerantes a acentuação.
2. **`doxly_probes.py`**: Bateria de 5 detectores ativos (`user_settings.lua`, `runtime_probe.json`, `profiler_telemetry.json`, `session_log.txt`, `error.txt`) executando em $< 5\text{ms}$.
3. **`doxly_chaos.py`**: Suíte de injeção de caos no sandbox que comprovou **100.0% de Cobertura Sensorial (12/12 falhas detectáveis e 0 silenciosas)**.
4. **`doxly_triangulator.py`**: Motor ponderado que calcula o índice de confiança estatístico ($\%$) e executa autorreparos atômicos (`--repair`).
5. **`doxly_stress_pack.py`**: Bateria de bombardeio simultâneo multi-vetor comprovando **100% de Sobrevivência e 100% de Acurácia de Triangulação**.
6. **`cmd_typhon_doxly.py`**: CLI Click integrado (`doxoade doxly typhon [tree|probe|chaos|triangulate|report]`).

---

### 4. KHONSU AOT COMPILER GATE & SOURCE MAP

Para blindar o deploy em Produção e Teste:

* **Template Source Map (`TemplateSourceMap`)**: Durante a fusão dos 25 templates `.lua`, o sistema mapeia linha a linha os intervalos de cada arquivo.
* **Pre-Flight Gatekeeper**: O `DoxlyKhonsuGate` compila o buffer unificado via runtime nativo antes de gravar no disco.
* **Rastreabilidade Instantânea**: Se ocorrer qualquer falha léxica ou de fechamento de blocos (`<eof> expected near 'end'`), o portão intercepta, traduz a linha global para `(arquivo_template.lua, linha_relativa)` e renderiza snippet visual colorido.
* **Artefato Oficial**: O `init.lua` de Produção é gerado em **Bytecode AOT Binário Oficial (`178.074 bytes | Lua 5.4.8`)**, com tempo de boot sub-10ms.

---

### 5. TABELA DE MODOS DE FALHA CATALOGADOS (DOXLY_TREE)

| ID da Falha | Subsistema | Severidade | Descrição / Causa Raiz | Auto-Fix |
| :--- | :---: | :---: | :--- | :---: |
| `doxly.tokenizer.nil_compare` | syntax | CRITICAL | Loop `while i <= text_len` com `text` nulo | ✔ SIM |
| `doxly.tokenizer.invalid_state` | syntax | HIGH | State numérico retornado no Lite XL 2.1+ | ✔ SIM |
| `doxly.syntax.corrupted_pattern` | syntax | MEDIUM | Pattern nulo ou range quebrado em syntax | ✔ SIM |
| `doxly.syntax.binary_raw_highlight`| syntax | HIGH | Highlighting de código sobre bytecode \x1bLua | ✔ SIM |
| `doxly.docview.nil_highlighter` | render | CRITICAL | DocView tentando indexar `doc.highlighter` nulo | ✔ SIM |
| `doxly.node.orphan_view` | render | HIGH | View injetada sem herdar métodos de contrato | ✔ SIM |
| `doxly.settings.nil_table_index` | config | HIGH | `settings.lua:843` indexando retorno nulo | ✔ SIM |
| `doxly.config.missing_user_settings`| config | MEDIUM | `user_settings.lua` ausente no USERDIR | ✔ SIM |
| `doxly.khonsu.coroutine_budget_spike`| runtime| MEDIUM | Corrotina ultrapassando limite de 1.5ms | ❌ NÃO |
| `doxly.process.ghost_zombie` | runtime| HIGH | Processo Lite XL zumbi travando lock IPC | ✔ SIM |
| `doxly.api.missing_critical_symbol`| api_guard| CRITICAL | Símbolo essencial ausente em runtime_probe | ❌ NÃO |
| `doxly.api.patch_nil_target` | api_guard| HIGH | `API.patch` em método ou classe inexistente | ✔ SIM |

---

### 6. COMANDOS OPERACIONAIS HOMOLOGADOS

```bash
# Diagnóstico & Probes Vivos
doxoade doxly typhon probe -m production

# Triangulação de 3 Vias com Auto-Repair
doxoade doxly typhon triangulate -m production --repair

# Prova de Sensibilidade contra o Caos (100% Cobertura)
doxoade doxly typhon chaos

# Prova de Fogo sob Estresse Composto
doxoade doxly typhon chaos --stress

# Deploy Supervisionado com Khonsu Gate AOT
doxoade doxly deploy test
doxoade doxly deploy production
```

---
*Fim do Volume 25. Registrado e selado para a posteridade do ecossistema Doxoade.*
```
