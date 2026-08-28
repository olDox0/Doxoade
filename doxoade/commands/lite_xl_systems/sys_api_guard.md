:: seguinte, preciso fazer um sistema, chamado litexl_api_guard. ele é responsavel por verificar se aquela função existe e funciona. opcionalmente, como funciona, especificamente o contrato. o lite_xl é open source então teoricamente é facil projetar e planejar o que vamos fazer. isso porque recentemente enfrentei um problema como o 7° templante tive que dar rewind para voltar a funcionar, o problema era uma função de deprecada. tem um backup do 7° template que você pode dar uma olhada. basicamente estou planejando um sistema para impedir que este tipo de problema volte novamente. assim vamos fazer alguns comandos e integrar no doxoade lite-xl diagnose para verificar se esta tudo certo. tinha feito um plano que vou enviar.



permite implementar com segurança, sem quebrar o que já funciona.

Só vou fazer um ajuste arquitetural importante antes de consolidar o plano:

> Os arquivos Lua do Lite XL precisam ser carregados pelo init soberano.  
> Hoje o sistema provavelmente trabalha com templates dentro de:
>
> ```text
> doxoade/commands/lite_xl_systems/template/
> ```
>
> Se criarmos:
>
> ```text
> templates/lite_xl_probes/
> ```
>
> precisaremos garantir que a `LiteXLEngine` saiba injetar esses probes no `init.lua`, preferencialmente **antes** dos templates normais.

Então o Capítulo 1 deve decidir isso:

```text
Opção A — simples e imediata:
  template/00_api_probe.lua
  template/00_api_guard.lua

Opção B — organizada e escalável:
  templates/lite_xl_probes/api_probe.lua
  templates/lite_xl_probes/api_guard.lua
  + modificação na engine para incluir probes antes dos templates
```

Minha recomendação: usar **Opção B conceitualmente**, mas implementar de forma compatível com o mecanismo atual, talvez criando um diretório especial reconhecido pela engine.

---

# Plano geral em 6 capítulos

## Visão macro

```text
Capítulo 1 — Placeholders e Arquitetura
Capítulo 2 — Catálogo Básico / api_catalog.py
Capítulo 3 — Probe Runtime / api_probe.lua + api_guard.lua
Capítulo 4 — Guard Ativo / API Guard
Capítulo 5 — API Scan / Scanner de uso nos templates
Capítulo 6 — Revisão, Integridade e Diagnóstico Aprimorado
```

Fluxo de dados:

```text
api_catalog.py
   ↓
catalog.json
   ↓
api_probe.lua dentro do Lite XL
   ↓
runtime_probe.json
   ↓
api_guard.lua compara catálogo vs runtime
   ↓
guard_state.json
   ↓
engine/CLI mostram diagnóstico
   ↓
api_scan.py cruza uso dos templates com catálogo/runtime
   ↓
relatório final de integridade
```

---

# Tabela resumo dos capítulos

| Capítulo | Objetivo | Dependência | Complexidade | Entrega principal |
|---|---|---:|---:|---|
| 1 | Criar placeholders, diretórios e contrato arquitetural | Nenhum | Baixa | Estrutura base |
| 2 | Criar catálogo básico da API do Lite XL | 1 | Média | `api_catalog.py` + `catalog.json` |
| 3 | Criar probe runtime dentro do Lite XL | 1 | Média | `api_probe.lua` + `runtime_probe.json` |
| 4 | Criar API Guard ativo e proteção de features | 2 e 3 | Alta | `api_guard.lua` + safe patch |
| 5 | Escanear templates para descobrir uso de API | 2 | Média/Alta | `api_scan.py` + `template_usage.json` |
| 6 | Revisão, integridade, diagnóstico e recuperação | Todos | Alta | Relatório final, quarentena, rollback |

---

# Capítulo 1 — Placeholders e Arquitetura

## Objetivo

Criar a base do sistema sem alterar comportamento existente.

Esse capítulo precisa ser extremamente conservador. Nada deve quebrar o Lite XL atual.

---

## Fases

### Fase 1.1 — Definir estrutura de diretórios

Proposta:

```text
doxoade/
    tools/
        lua_systems/
            api_guard/
                __init__.py
                api_catalog.py
                api_scan.py
                api_report.py
    commands/
        lite_xl_systems/
            templates/
                lite_xl_probes/
                    api_probe.lua
                    api_guard.lua
```

Ou, se quisermos compatibilidade imediata com o template loader atual:

```text
doxoade/commands/lite_xl_systems/template/
  00_api_probe.lua
  00_api_guard.lua
```

---

### Fase 1.2 — Criar placeholders Python

Arquivos:

```text
doxoade/tools/lua_systems/api_guard/__init__.py
doxoade/tools/lua_systems/api_guard/api_catalog.py
doxoade/tools/lua_systems/api_guard/api_scan.py
doxoade/tools/lua_systems/api_guard/api_report.py
```

Inicialmente apenas com:

```python
"""Placeholder — API Guard / Catálogo."""
```

ou funções mínimas vazias.

---

### Fase 1.3 — Criar placeholders Lua

Arquivos:

```text
api_probe.lua
api_guard.lua
```

Inicialmente apenas com cabeçalho:

```lua
-- =============================================================================
-- DOXOADE API GUARD — PLACEHOLDER
-- =============================================================================
```

Sem lógica agressiva.

---

### Fase 1.4 — Definir contrato de integração

Precisamos decidir:

1. Onde os probes ficam.
2. Como a engine injeta os probes no init.
3. Em qual ordem eles carregam.
4. Onde os relatórios são gravados.
5. Como o CLI lê esses relatórios.
6. Como o sistema se comporta quando o API Guard estiver ausente.

---

### Fase 1.5 — Definir artefatos

Proposta de diretório de artefatos:

```text
USERDIR/.doxoade/api_guard/
  catalog.json
  runtime_probe.json
  template_usage.json
  guard_state.json
  reports/
    api_guard_report.md
    api_guard_violations.md
```

---

## Entrega do Capítulo 1

```text
✔ Diretórios criados
✔ Placeholders criados
✔ Nenhum comportamento alterado
✔ Contrato de caminhos definido
✔ Base pronta para catálogo e probe
```

---

# Capítulo 2 — Catálogo Básico

## Arquivo principal

```text
doxoade/tools/lua_systems/api_guard/api_catalog.py
```

## Objetivo

Criar o catálogo inicial das APIs do Lite XL que o Doxoade conhece e/ou utiliza.

Esse catálogo nasce do que já existe em:

```python
KNOWN_LITEXL_MODULES
```

dentro de `engine_lite_xl.py`.

---

## Fases

### Fase 2.1 — Definir schema do catálogo

Exemplo:

```python
API_CATALOG_SCHEMA = {
    "id": "RootView.on_text_input",
    "kind": "event_handler",
    "module": "core.rootview",
    "class": "RootView",
    "name": "on_text_input",
    "type": "method",
    "status": "unknown",
    "severity_if_missing": "critical",
    "safe_to_patch": False,
    "fallback": None,
    "notes": "",
}
```

---

### Fase 2.2 — Criar catálogo semente

Começar com módulos já conhecidos:

```text
core
core.common
core.config
core.style
core.command
core.keymap
core.node
core.docview
core.doc
core.view
core.rootview
core.rencache
core.logview
renderer
system
regex
```

Depois adicionar APIs críticas usadas pelos templates:

```text
RootView.draw
RootView.on_key_pressed
RootView.on_text_input
RootView.on_mouse_moved
RootView.on_mouse_pressed
Node.draw_tab_title
Node.split
Node.add_view
Node.get_view_idx
Doc.insert
Doc.remove
Doc.save
Doc.text_input
Doc.get_selection
Doc.set_selection
DocView.draw_line_body
DocView.draw_line_gutter
DocView.get_gutter_width
DocView.scroll_to_line
StatusView.add_item
core.command_view.enter
system.absolute_path
system.mkdir
system.get_file_info
system.list_dir
system.set_clipboard
system.show_in_file_manager
```

---

### Fase 2.3 — Criar loader/salvador do catálogo

Funções iniciais:

```python
get_default_catalog()
load_catalog(path)
save_catalog(path)
get_api_entry(catalog, api_id)
list_critical_apis(catalog)
```

---

### Fase 2.4 — Integrar com a engine

A `LiteXLEngine` pode ganhar:

```python
get_api_catalog()
load_api_catalog()
save_api_catalog()
```

Ou usar:

```python
from doxoade.tools.lua_systems.api_guard.api_catalog import get_default_catalog
```

---

### Fase 2.5 — Comando inicial de visualização

Possível CLI:

```bash
doxoade lite-xl api-catalog show
```

Saída:

```text
🧭 API CATALOG — DOXOADE

✔ core.command
✔ core.keymap
✔ RootView.draw
? RootView.on_text_input
? RootView.on_key_pressed
```

---

## Entrega do Capítulo 2

```text
✔ api_catalog.py funcional
✔ Catálogo mínimo criado
✔ APIs críticas inventariadas
✔ Catálogo pode ser salvo/carregado
✔ Engine consegue consultar catálogo
```

---

# Capítulo 3 — Probe Runtime

## Arquivos principais

```text
templates/lite_xl_probes/api_probe.lua
templates/lite_xl_probes/api_guard.lua
```

ou:

```text
template/00_api_probe.lua
template/00_api_guard.lua
```

---

## Objetivo

Verificar, dentro do Lite XL real, se as APIs do catálogo realmente existem.

Esse capítulo ainda deve ser **passivo**: ele observa, coleta e registra, mas não bloqueia nada.

---

## Fases

### Fase 3.1 — Criar `api_probe.lua`

Responsável por coletar:

```lua
type(core)
type(core.command)
type(core.keymap)
type(core.root_view)
type(core.command_view)
type(RootView.draw)
type(RootView.on_key_pressed)
type(RootView.on_text_input)
type(Doc.insert)
type(Doc.remove)
type(Doc.text_input)
```

Exemplo conceitual:

```lua
local capabilities = {}

capabilities["core"] = type(core)
capabilities["core.command"] = type(command)
capabilities["RootView.on_text_input"] = type(RootView.on_text_input)
```

---

### Fase 3.2 — Gravar relatório runtime

Artefato:

```text
USERDIR/.doxoade/api_guard/runtime_probe.json
```

ou, para facilitar consumo pelo Lua:

```text
USERDIR/.doxoade/api_guard/runtime_probe.lua
```

Exemplo:

```lua
return {
  generated_at = "2026-08-27T23:40:00",
  litexl_version = VERSION,
  platform = PLATFORM,
  capabilities = {
    ["core.command"] = "table",
    ["RootView.on_text_input"] = "nil",
    ["Doc.text_input"] = "function",
  }
}
```

---

### Fase 3.3 — Criar estado global

```lua
rawset(_G, "_DOXOADE_API_PROBE", capabilities)
```

ou:

```lua
rawset(_G, "_DOXOADE_API_STATE", {
  capabilities = capabilities,
  violations = {},
  disabled_features = {},
})
```

---

### Fase 3.4 — Criar `api_guard.lua` passivo

Neste capítulo, o `api_guard.lua` ainda não precisa bloquear recursos.

Ele pode apenas:

1. ler o catálogo embutido;
2. ler o probe;
3. comparar;
4. registrar violações;
5. expor estado global.

Exemplo:

```lua
API_GUARD.state = {
  missing = {},
  type_changed = {},
  unknown = {},
}
```

---

### Fase 3.5 — Mostrar status simples

Pode ser apenas log:

```lua
core.log("[API GUARD] Probe concluído: 2 APIs ausentes.")
```

Mais adiante, integrar com o status bar do `13_toolbar_doxoade.lua`.

---

## Entrega do Capítulo 3

```text
✔ api_probe.lua coleta capacidades reais
✔ runtime_probe gerado
✔ api_guard.lua passivo criado
✔ Estado global disponível
✔ Nenhum recurso existente é quebrado
```

---

# Capítulo 4 — Guard Ativo

## Objetivo

Transformar o API Guard em uma camada de proteção real.

Aqui ele deixa de ser apenas observacional e passa a:

```text
impedir patch em API inexistente
impedir chamada de original nil
desativar feature incompatível
registrar violação
sugerir fallback
```

---

## Fases

### Fase 4.1 — Definir API pública do Guard

Funções principais:

```lua
API.has(path)
API.type_of(path)
API.check(spec)
API.can_patch(target)
API.patch(target, wrapper, options)
API.disable_feature(feature, reason)
API.register_violation(data)
API.get_report()
```

---

### Fase 4.2 — Implementar `API.has`

Exemplo conceitual:

```lua
function API.has(path)
  local value = API.resolve(path)
  return value ~= nil
end
```

Onde:

```lua
API.resolve("RootView.on_text_input")
```

retorna:

```lua
RootView.on_text_input
```

---

### Fase 4.3 — Implementar `API.patch`

Este é o coração do Guard.

Em vez de:

```lua
local original = RootView.on_text_input
function RootView:on_text_input(...)
  ...
end
```

Usar:

```lua
API.patch({
  id = "RootView.on_text_input",
  class = RootView,
  method = "on_text_input",
  template = "07_keymaps_and_help.lua",
  feature = "replace_bar_input_capture",
  severity = "critical",
  wrapper = function(original, self, text, ...)
    if ReplaceBar.visible then
      return true
    end
    if original then
      return original(self, text, ...)
    end
  end
})
```

Se a API não existir:

```text
feature desativada
violação registrada
nenhum patch aplicado
```

---

### Fase 4.4 — Implementar fallback

Exemplo:

```lua
API.patch({
  id = "RootView.on_text_input",
  fallback = function()
    API.disable_feature("replace_bar_input_capture")
    core.error("[API GUARD] RootView.on_text_input indisponível.")
  end
})
```

---

### Fase 4.5 — Piloto no template `07`

O `07_keymaps_and_help.lua` deve ser o primeiro template protegido.

Prioridades nele:

```text
RootView.on_key_pressed
RootView.on_text_input
RootView.on_mouse_pressed
RootView.on_mouse_moved
Doc.text_input
core.command_view.enter
keymap.add
command.add
```

---

### Fase 4.6 — Modo de operação

Recomendo três modos:

```lua
API_GUARD_MODE = "observe"
API_GUARD_MODE = "warn"
API_GUARD_MODE = "enforce"
```

Padrão inicial:

```text
observe/warn
```

Depois:

```text
enforce para features críticas
```

---

## Entrega do Capítulo 4

```text
✔ API Guard ativo
✔ API.patch seguro
✔ Nenhum patch cego
✔ Features podem ser desativadas com segurança
✔ Template 07 protegido como piloto
✔ Falhas deixam de ser silenciosas
```

---

# Capítulo 5 — API Scan

## Arquivo principal

```text
doxoade/tools/lua_systems/api_guard/api_scan.py
```

## Objetivo

Analisar os templates Doxoade para descobrir quais APIs eles usam.

Esse capítulo é importante porque o catálogo diz o que existe, mas o scanner diz **o que os templates consomem**.

---

## Fases

### Fase 5.1 — Scanner simples de `require`

Detectar:

```lua
require "core"
require "core.command"
require "core.rootview"
require "core.docview"
```

---

### Fase 5.2 — Scanner de chamadas e acessos

Detectar padrões como:

```lua
RootView.on_text_input
RootView.draw
Doc.insert
Doc.remove
core.command_view:enter
system.set_clipboard
```

---

### Fase 5.3 — Scanner de patches

Detectar:

```lua
local original_rootview_text_input = RootView.on_text_input
function RootView:on_text_input(...)
```

E gerar:

```json
{
  "template": "07_keymaps_and_help.lua",
  "patch_target": "RootView.on_text_input",
  "original_var": "original_rootview_text_input",
  "risk": "original_may_be_nil"
}
```

---

### Fase 5.4 — Detectar uso antes de declaração

Isso é essencial por causa do backup do `07`.

Exemplo:

```lua
function RootView:on_key_pressed(key, ...)
  if ReplaceBar.visible then
```

mas:

```lua
local ReplaceBar = {}
```

vem depois.

O scanner deve marcar:

```text
USE_BEFORE_LOCAL
```

---

### Fase 5.5 — Scanner de comandos e keymaps

Detectar:

```lua
command.add(nil, {
  ["doxoade:open-replace-bar"] = handler
})
```

e:

```lua
keymap.add {
  ["ctrl+h"] = "doxoade:open-replace-bar"
}
```

Depois verificar:

```text
keymap aponta para comando registrado?
comando existe?
predicado é função válida?
```

---

### Fase 5.6 — Integra com `check-templates`

O comando existente:

```bash
doxoade lite-xl check-templates
```

pode ganhar:

```bash
doxoade lite-xl check-templates --api
```

ou simplesmente integrar por padrão.

Saída esperada:

```text
[FAIL] 07_keymaps_and_help.lua
    ✖ API missing: RootView.on_text_input
    ✖ Use-before-local: ReplaceBar
    ⚠ Optional module missing: core.commands.findreplace
```

---

## Entrega do Capítulo 5

```text
✔ api_scan.py funcional
✔ Uso de APIs mapeado
✔ Patches identificados
✔ Keymaps/comandos validados
✔ Problemas de ordem de locals detectados
✔ check-templates aprimorado
```

---

# Capítulo 6 — Revisão, Integridade e Diagnóstico Aprimorado

## Objetivo

Fechar o ciclo com:

- revisão;
- testes;
- integridade;
- diagnóstico rico;
- recuperação;
- catálogo versionado;
- possível mapper open source do Lite XL.

---

## Fases

### Fase 6.1 — Integridade dos artefatos

Criar hashes para:

```text
catalog.json
runtime_probe.json
template_usage.json
guard_state.json
```

Exemplo:

```json
{
  "catalog_sha256": "...",
  "probe_sha256": "...",
  "usage_sha256": "..."
}
```

---

### Fase 6.2 — Relatório unificado

Gerar:

```text
.doxoade/api_guard/reports/api_guard_report.md
```

Contendo:

```text
Versão do Lite XL
APIs ausentes
APIs deprecadas
Templates afetados
Features desativadas
Patches aplicados
Fallbacks usados
Recomendações
```

---

### Fase 6.3 — Integração com toolbar/status

Aproveitar o `13_toolbar_doxoade.lua` para mostrar:

```text
🧭 API: OK
```

ou:

```text
🧭 API: 1C / 2W
```

---

### Fase 6.4 — Quarentena de templates

Se um template causar violação crítica recorrente:

```text
.doxoade/api_guard/quarantine/
  07_keymaps_and_help.lua.disabled
  reason.txt
```

E o init soberano pode ignorar esse template temporariamente.

---

### Fase 6.5 — Rollback integrado

Aproveitar mecanismos existentes da engine:

```python
backup_workspace_state
restore_workspace_state
promote_to_stable_snapshot
restore_stable_snapshot
```

Fluxo:

```text
API Guard detectou falha crítica no boot
→ snapshot anterior é sugerido
→ usuário pode restaurar
→ sistema permanece observável
```

---

### Fase 6.6 — Catálogo versionado por Lite XL

Criar catálogos como:

```text
catalog/litexl_2.1.0.json
catalog/litexl_2.1.1.json
catalog/litexl_2.2.0.json
```

Ou:

```text
catalog/litexl_api_catalog.json
```

com campo:

```json
"versions": {
  "2.1.0": true,
  "2.2.0": false
}
```

---

### Fase 6.7 — Mapper open source

Esse pode ser o passo mais avançado.

Arquivo possível:

```text
doxoade/tools/lua_systems/api_guard/litexl_source_mapper.py
```

Função:

- ler código-fonte do Lite XL;
- extrair classes;
- extrair métodos;
- extrair comandos;
- extrair keymaps;
- atualizar catálogo automaticamente.

---

## Entrega do Capítulo 6

```text
✔ Sistema revisado
✔ Artefatos íntegros
✔ Relatório completo
✔ Status no HUD
✔ Quarentena opcional
✔ Rollback sugerido
✔ Catálogo versionado
✔ Base para mapper open source
```

---

# Dependências entre capítulos

A ordem recomendada é:

```text
Capítulo 1
   ↓
Capítulo 2
   ↓
Capítulo 3
   ↓
Capítulo 4
   ↓
Capítulo 5
   ↓
Capítulo 6
```

Mas existe uma possibilidade de paralelização:

```text
Capítulo 2 e Capítulo 3 podem avançar juntos
Capítulo 5 pode começar logo após Capítulo 2
Capítulo 6 depende de todos
```

---

# MVP recomendado

Se quisermos o mínimo que já resolve o problema principal, o MVP é:

```text
Capítulo 1 — Placeholders
Capítulo 2 — Catálogo básico
Capítulo 3 — Probe runtime
Capítulo 4 — Guard ativo no template 07
```

Com isso já conseguimos impedir o tipo de falha silenciosa que ocorreu com:

```text
RootView.on_text_input
```

Depois adicionamos:

```text
Capítulo 5 — Scanner completo
Capítulo 6 — Integridade e diagnóstico avançado
```

---

# Estrutura final sugerida

## Python

```text
doxoade/tools/lua_systems/api_guard/
  __init__.py
  api_catalog.py
  api_scan.py
  api_report.py
  litexl_source_mapper.py   # Capítulo 6 ou futuro
```

## Lua

Se usarmos diretório especial:

```text
doxoade/commands/lite_xl_systems/templates/lite_xl_probes/
  api_probe.lua
  api_guard.lua
```

Se usarmos compatibilidade imediata:

```text
doxoade/commands/lite_xl_systems/template/
  00_api_probe.lua
  00_api_guard.lua
```

## Artefatos

```text
USERDIR/.doxoade/api_guard/
  catalog.json
  runtime_probe.json
  template_usage.json
  guard_state.json
  reports/
    api_guard_report.md
    api_guard_violations.md
  quarantine/
```

---

# Recomendação de comportamento padrão

Para não introduzir risco imediato, eu sugiro:

```text
Capítulo 1: inerte
Capítulo 2: apenas catálogo
Capítulo 3: observe/warn
Capítulo 4: enforce apenas para patches críticos
Capítulo 5: auditoria estática
Capítulo 6: diagnóstico completo e recuperação
```

---

# Próximo passo

Se você aprovar essa estrutura, o próximo passo natural é começar pelo:

```text
Capítulo 1 — Placeholders e Arquitetura
```

Eu prepararia:

```text
doxoade/tools/lua_systems/api_guard/__init__.py
doxoade/tools/lua_systems/api_guard/api_catalog.py
doxoade/tools/lua_systems/api_guard/api_scan.py
doxoade/tools/lua_systems/api_guard/api_report.py
```

e os placeholders Lua:

```text
api_probe.lua
api_guard.lua
```

junto com uma proposta concreta de integração com a `LiteXLEngine` para garantir que os probes sejam carregados antes dos templates funcionais.
