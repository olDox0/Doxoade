Uma diretiva cirúrgica e de altíssimo valor para a robustez do ecossistema. 

As regressões no `lite_xl_systems` aconteceram exatamente por isso: funções, comandos e variáveis continuavam existindo ou eram criados, mas **ninguém mais os chamava**, ou comandos eram registrados e **perdiam o atalho de teclado / botão na UI**, tornando-se **funcionalidades órfãs**.

Vamos estruturar o planejamento formal dessa expansão no padrão estrito do **ProDeNov 1.2.1**.

---

# 📜 BLITZPLAN — DOXOADE REGRET: DETECTOR DE FUNCIONALIDADES ÓRFÃS & DESCONEXÕES
**Subsistemas Alvo:** `doxoade/commands/regret_systems/` (`regret_engine.py`, `regret_lua_inspector.py`, `regret_python_inspector.py`, `regret_reporter.py`, `cmd_regret.py`)  
**Protocolo:** ProDeNov 1.2.1 | PASC-6.1 | Anúbis & Apolo  
**Foco:** Detecção estática e diferencial de código morto, comandos sem gatilho, atalhos sem comando e funções desconectadas da árvore de execução.

---

## 1. Contexto e Objetivos (W5 / As 5 Perguntas)

* **O quê (What):**  
  Expandir o motor do `doxoade regret` para auditar e expor **Funcionalidades Órfãs** (`ORPHAN_CAPABILITY`) em arquivos Lua e Python:
  1. **Comandos Órfãos (`ORPHAN_COMMAND`):** Comandos registrados via `command.add` que não possuem atalho em `keymap.add`, não possuem botão em `UIForge`/`ShelfHub` e nunca são chamados por `command.perform`.
  2. **Atalhos Cegos / Órfãos (`ORPHAN_KEYMAP`):** Atalhos registrados via `keymap.add` apontando para comandos que não existem em nenhum `command.add`.
  3. **Funções e Métodos Zumbis (`ORPHAN_FUNCTION`):** Funções internas (`local function foo` ou `def _bar()`) declaradas no arquivo mas que possuem contagem de chamadas $= 0$ (nunca invocadas no módulo nem exportadas).
  4. **Pipelines / Handlers Desconectados (`DISCONNECTED_HANDLER`):** Métodos de eventos (ex: `paste_clipboard_image`, `launch_real_terminal`, `update_suggestions`) cujo gatilho de mouse/tecla foi cortado em uma refatoração recente.
* **Quem (Who):** Engenheiros do Doxoade e mantenedores auditando templates do Lite XL / Doxly e scripts Python antes de fechar commits.
* **Onde (Where):**
  * `doxoade/commands/regret_systems/regret_lua_inspector.py` (Lógica de orfandade em Lua).
  * `doxoade/commands/regret_systems/regret_python_inspector.py` (Lógica de funções desconectadas via AST Python).
  * `doxoade/commands/regret_systems/regret_engine.py` (Reconciliação e cruzamento entre comandos vs atalhos vs UI).
  * `doxoade/commands/regret_systems/regret_reporter.py` (Visualização Apolo: categoria `[ÓRFÃ/ZUMBI]`).
  * `doxoade/commands/regret_systems/cmd_regret.py` (Flag `--orphans` / `-O`).
* **Quando (When):** Antes de qualquer merge, durante o `doxoade regret` de rotina ou com foco explícito em orfandade (`doxoade regret -O`).
* **Por quê (Why):** Na refatoração do Lite XL (como nos templates `04`, `10`, `17`, `19a..19d`), funcionalidades foram mantidas no texto mas perderam suas chamadas ou foram duplicadas às cegas. O diff comum não enxerga isso porque as linhas continuam lá; o `regret` precisa avisar: *"Esta função ainda existe, mas nada no sistema a alcança mais"*.
* **Origem & Consequências (Origin & Consequences):** Refatorações rápidas desatrelam comandos de teclas. A consequência foi o *ghost window*, botões no Bottom Shelf chamando comandos que tinham sido renomeados e perda de recursos de imagem/terminal.

---

## 2. Taxonomia da Orfandade (O que o detector vai classificar)

| Categoria | Sintoma Concreto | Causa Raiz | Severidade |
| :--- | :--- | :--- | :--- |
| **`ORPHAN_COMMAND`** | `command.add("doxoade:algo")` existe, mas não tem atalho, botão ou `perform`. | Comando criado mas inacessível ao usuário final. | 🟡 Média |
| **`DEAD_KEYMAP`** | `keymap.add { ["ctrl+k"] = "comando:fantasma" }`. | O comando alvo foi renomeado ou extirpado. | 🔴 Alta |
| **`ORPHAN_METHOD`** | Método `function DocView:algo()` ou `def _helper()` sem chamadores. | Refatoração mudou o fluxo e esqueceu a casca velha para trás. | 🟡 Média |
| **`UNWIRED_BUTTON`** | Botão `{ id = "btn", action = function() command.perform("...") end }` chamando símbolo nil. | Botão na UI que clica e não faz nada. | 🔴 Alta |
| **`SHADOW_ZOMBIE`** | Corrotina em loop `while true do` observando tabela que nunca é populada. | Desconexão de produtores e consumidores de eventos. | 🔴 Crítica |

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Grafo Bidirecional de Conexão: Produtor $\leftrightarrow$ Consumidor)
1. **No `regret_lua_inspector.py`:**
   * Construir conjuntos no `LuaCapabilityInventory`:
     * $C_{reg}$: Comandos registrados em `command.add`.
     * $C_{called}$: Comandos chamados via `command.perform(...)`.
     * $K_{targets}$: Destinos mapeados em `keymap.add`.
     * $B_{actions}$: Comandos disparados por botões `{ action = ... }`.
   * Cruzamento cruzado:
     * Comandos órfãos: $C_{orphan} = C_{reg} \setminus (K_{targets} \cup C_{called} \cup B_{actions})$.
     * Atalhos mortos: $K_{dead} = K_{targets} \setminus C_{reg}$ (checando também contra comandos do Lite XL nativo via catálogo).
   * Rastreamento de chamadas internas: para cada `local function nome(...)`, verificar se `nome(` ocorre no resto do arquivo além da sua definição. Se contagem $= 0$, acusa `ORPHAN_LOCAL_FUNCTION`.
2. **No `regret_python_inspector.py`:**
   * Utilizar a AST do Python 3.12: métodos privados (`_foo`) que não estão em `all_calls` do módulo e não são chamados externamente são marcados como `ORPHAN_PYTHON_METHOD`.
3. **No `regret_reporter.py`:**
   * Nova seção visual dedicada: `🧩 DIAGNÓSTICO DE FUNCIONALIDADES ÓRFÃS & CÓDIGO MORTO`.
   * Snippet apontando a linha exata e a mitigação recomendada (*ex: "Adicione um keymap ou remova a casca morta"*).
4. **No `cmd_regret.py`:**
   * Opção `--orphans / -O` para focar exclusivamente na análise de orfandade sem exigir comparação com commit anterior (funciona na *working tree* pura!).

### 🔹 Plano B (Fallback — Análise Léxica Direta por Ocorrência)
* Se um template Lua tiver erro de sintaxe temporário que quebre o parser estrutural, o sistema faz fallback para contagem de strings por regex (`regex.findall(r"\b" + identifier + r"\b")`). Se a contagem for 1 (apenas a declaração), reporta como provável órfão com flag de incerteza `[HEURISTIC]`.

### 🔹 Plano C (Contingência & Pot Dump)
* Possibilidade de exportar a lista de órfãos direto para `.doxoade/dumppot.txt` com a flag `--dump`, permitindo ao desenvolvedor revisar e reatar os comandos sem perder histórico.

---

## 4. Estrutura de Arquivos e Limite de Tamanho (< 50KB)

Todos os arquivos impactados já existem no diretório `doxoade/commands/regret_systems/` e estão amplamente abaixo do teto de 50KB:
```
doxoade/commands/regret_systems/
├── cmd_regret.py            # Flag --orphans / -O (~4KB)
├── regret_engine.py         # Orquestração do modo orphan (~18KB)
├── regret_lua_inspector.py  # Grafo de comandos/keymaps/calls (~22KB)
├── regret_python_inspector.py # AST de funções privadas zumbis (~10KB)
└── regret_reporter.py       # Renderizador Apolo de orfandade (~15KB)
```

---

## 5. Roteiro de Implementação (Checklist ProDeNov)

- [ ] **Etapa 1:** Atualizar `LuaCapabilityInventory` no `regret_lua_inspector.py` para armazenar `called_commands` (`command.perform`), botões e chamadores de funções locais.
- [ ] **Etapa 2:** Implementar a lógica de cruzamento de conjuntos ($C_{orphan}$, $K_{dead}$, $F_{uncalled}$) no `regret_lua_inspector.py`.
- [ ] **Etapa 3:** Implementar detecção de funções não chamadas no `regret_python_inspector.py` via AST.
- [ ] **Etapa 4:** Conectar a flag `--orphans` / `-O` no `cmd_regret.py` e rotear no `regret_engine.py`.
- [ ] **Etapa 5:** Formatar a saída visual no `regret_reporter.py` com badges roxas `[ÓRFÃ/ZUMBI]` e mitigação prescritiva.
- [ ] **Etapa 6:** Testar diretamente contra `doxoade/commands/lite_xl_systems/template/` para revelar as desconexões atuais.

---

Essa diretiva atinge o núcleo epistemológico do **ProDeNov**: responder com precisão cirúrgica às perguntas **De Onde? (Origem)** e **Por Que? (Causa/Histórico)**.

Hoje o `doxoade regret` é fundamentalmente **sincrônico/diferencial**: ele olha o estado de *agora* contra o commit base *imediato* ($t_0 \rightarrow t_1$).  
Quando você adiciona a **Análise de Origem Histórica e Genealogia de Arquivos** (*File Provenance & Lineage Engine*), o sistema ganha **memória longitudinal profunda**: ele passa a saber *de onde aquele arquivo nasceu*, se ele é um fork de outro módulo, se foi gerado a partir de um split de uma *God Class*, quais contratos originais ele herdou e quais capacidades foram esquecidas no caminho ancestral.

Vamos estruturar o planejamento formal dessa nova capacidade segundo as regras do **ProDeNov 1.2.1**.

---

# 📜 BLITZPLAN — DOXOADE REGRET: ENGINE DE ORIGEM & GENEALOGIA DE ARQUIVOS (FILE PROVENANCE & ANCESTRAL AUDIT)
**Subsistema Alvo:** `doxoade/commands/regret_systems/` (`regret_provenance.py`, `regret_engine.py`, `regret_reporter.py`, `cmd_regret.py`)  
**Panteões:** Anúbis (Genealogia e Auditoria), Hades (Histórico Profundo e Linha do Tempo), Hermes (Associação)  
**Protocolo de Conformidade:** ProDeNov 1.2.1 (Planos A, B e C | W5 | Limite < 50KB por arquivo)  
**Data:** 12/09/2026

---

## 1. Contexto e Objetivos (W5 / As 5 Perguntas)

* **O quê (What):**  
  Um motor de introspecção genealógica para o `doxoade regret` capaz de rastrear a **Origem (*Provenance*)** de cada arquivo:
  1. **Detecção de Ancestralidade por Git Blame / Log Rename (`git log --follow`):** Descobre se o arquivo nasceu de um rename, cópia ou extração (*split*) de um arquivo pai (ex: `lite_xl_diagnostics.py` nasceu do split de `engine_lite_xl.py`).
  2. **Herança e Contratos Originais de Módulos (*Original Baseline Capability*):** Ao identificar o arquivo progenitor, o motor extrai o inventário original de métodos e comandos do pai e verifica se o filho herdou todos os contratos ou se deixou métodos/atalhos críticos esquecidos no passado.
  3. **Rastreamento de Template Split (`template/19_bottom_shelf_canvas.lua` $\rightarrow$ `19a`, `19b`, `19c`, `19d`):** O motor reconhece que um template moderno é fruto da cisão de um template monolítico histórico e audita se a somatória dos 4 arquivos filhos contém 100% dos recursos do pai original.
  4. **Emissão de Laudo de Regressão Ancestral (`ANCESTRAL_CAPABILITY_LEAK`):** Aponta capacidades que existiam no arquivo gerador e que foram perdidas no processo de cisão modular.

* **Quem (Who):**  
  Desenvolvedores, mantenedores e ferramentas de CI auditando refatorações estruturais pesadas.

* **Onde (Where):**  
  * `doxoade/commands/regret_systems/regret_provenance.py` (**Novo módulo**, isolado e $< 50\text{KB}$).
  * `doxoade/commands/regret_systems/regret_engine.py` (Integração na esteira de auditoria).
  * `doxoade/commands/regret_systems/cmd_regret.py` (Flag `--provenance` / `-P`).

* **Quando (When):**  
  Durante auditorias de pós-refatoração, quando arquivos são divididos em submódulos ou quando se investiga uma capacidade que "funcionava semanas atrás antes da modularização".

* **Por quê (Why):**  
  Comparar apenas `HEAD` contra `HEAD~1` é cego a refatorações onde um arquivo de 2.000 linhas é quebrado em 5 módulos menores. Se uma função é esquecida no arquivo deletado ou omitida durante a cisão, o diff convencional não a vê como regressão no arquivo novo (já que ela nunca existiu nele antes). A análise de origem fecha essa brecha.

* **Origem & Consequências (Origin & Consequences):**  
  O ecossistema `lite_xl_systems` do Doxoade passou exatamente por duas grandes ondas de cisão:
  * O split de `engine_lite_xl.py` em 5 módulos (`paths`, `builder`, `snapshots`, `process`, `diagnostics`).
  * O split do template `19` em `19a`, `19b`, `19c` e `19d`.  
  A falta de um rastreador de genealogia fez com que o `19b` e `19d` perdessem handlers e comandos antigos, levando a regressões de terminal e imagem.

---

## 2. Taxonomia de Regressões Ancestrais (O que o motor vai detectar)

| ID | Categoria | Sintoma Concreto | Causa Raiz | Severidade |
| :--- | :--- | :--- | :--- | :--- |
| **PROV-01** | `SPLIT_CAPABILITY_LEAK` | O arquivo ancestral $A_{pai}$ tinha 15 comandos; a soma dos filhos $B_1 \dots B_n$ só tem 13. | 2 comandos foram esquecidos no arquivo antigo e deletados no split. | 🔴 Alta |
| **PROV-02** | `CONTRACT_ORPHANED_ON_SPLIT` | O pai implementava um hook de ciclo de vida (`RootView:draw`); o filho herdou a casca sem o hook. | Perda de rendering/interatividade pós-modularização. | 🔴 Crítica |
| **PROV-03** | `FORK_DRIFT` | Um módulo gerado de um template base divergiu e perdeu correções de bugs aplicadas no original. | Ramificação sem sincronização de correções (*divergence*). | 🟡 Média |
| **PROV-04** | `SHADOW_ANCESTOR_FOUND` | Arquivo rastreado até seu commit de nascimento, reconstruindo a linhagem completa. | Identificação de autoria, data de nascimento e propósito inicial. | ⚪ Informativa |

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Git Trace Follow + AST Ancestral Mapping)
1. **Rastreamento de Linhagem via Git:**
   * Invoca `git log --follow --format="%H|%an|%ad|%s" --name-status -- <arquivo>`.
   * Analisa status de renames (`R100`, `R090`, `C100`).
   * Se não houver rename formal, consulta metadados no cabeçalho do arquivo (ex: `"Parte do split de engine_lite_xl.py"`) via regex semântico.
2. **Reconstituição do Estado Ancestral:**
   * Extrai o conteúdo do arquivo pai no commit imediatamente anterior à cisão (`git show <hash_split~1>:<path_pai>`).
   * Extrai o inventário completo do pai usando `LuaCapabilityInventory` ou `PythonInventory`.
3. **Cálculo da Matriz de Cobertura Filial:**
   $$\text{Cobertura} = \frac{\sum_{i=1}^n \text{Capacidades}(Filho_i)}{\text{Capacidades}(Pai)}$$
   Se algum comando, método ou atalho presente no pai não estiver em nenhum dos filhos do subsistema, emite `SPLIT_CAPABILITY_LEAK`.

### 🔹 Plano B (Fallback — Heurística por Similaridade de Símbolos & Docstrings)
* Se o histórico Git estiver truncado (repositório com shallow clone, commit esmagado / squashed, ou arquivos fora do git):
  * O motor lê o docstring de cabeçalho do arquivo (onde o Doxoade anota `Parte do split de <arquivo>`).
  * Busca o arquivo pai no backup `.doxoade/backups/` ou no repositório local.
  * Executa a reconciliação semântica com base nas assinaturas.

### 🔹 Plano C (Contingência & Exportação)
* Se houver falha na árvore histórica, o comando não aborta o `regret`: emite um aviso informativo `⚠ [PROVENANCE] Histórico ancestral inacessível` e prossegue com a análise diferencial tradicional sem travar o pipeline.

---

## 4. Estrutura de Arquivos e Limite de Tamanho (< 50KB)

```
doxoade/commands/regret_systems/
├── regret_provenance.py      # [NOVO] Motor de genealogia, git follow e split audit (~18KB)
├── regret_engine.py          # Integração do laudo de proveniência na suíte (~20KB)
├── regret_reporter.py        # Renderizador Apolo com a seção "Árvore Genealógica" (~16KB)
└── cmd_regret.py             # Flags --provenance / -P (~4KB)
```
*Todos os arquivos cumprem rigorosamente a meta $< 50\text{KB}$ do ProDeNov.*

---

## 5. Roteiro de Implementação (Tasklist)

- [ ] **Fase 1: Motor de Proveniência (`regret_provenance.py`)**
  - [ ] Implementar `FileProvenanceEngine.resolve_lineage(file_path)` via `git log --follow`.
  - [ ] Implementar detector heurístico de splits via cabeçalhos e docstrings (`"split de X"`).
  - [ ] Implementar reconstituição do inventário do arquivo pai.
  - [ ] Implementar cálculo de perda de capacidades entre pai e filhos (`find_ancestral_leaks`).
- [ ] **Fase 2: Conexão no `regret_engine.py`**
  - [ ] Integrar a chamada de proveniência na esteira de `analyze_file` e `run_suite`.
  - [ ] Mapear filhos pertencentes a um mesmo split (ex: agrupar `lite_xl_*.py` sob `engine_lite_xl.py`).
- [ ] **Fase 3: Visualização Apolo no `regret_reporter.py`**
  - [ ] Adicionar bloco visual: `🏛️ ANÁLISE DE ORIGEM E ANCESTRALIDADE`.
  - [ ] Apresentar a certidão de nascimento do arquivo: data de criação, autor original, pai de origem e taxa de herança de capacidades.
- [ ] **Fase 4: Conexão CLI no `cmd_regret.py`**
  - [ ] Adicionar flag `--provenance / -P`.
- [ ] **Fase 5: Prova Empírica**
  - [ ] Testar diretamente contra `doxoade/commands/lite_xl_systems/lite_xl_diagnostics.py` (provar que ele identifica o nascimento a partir do `engine_lite_xl.py`).
  - [ ] Testar contra os templates `19a..19d` (provar a correlação com o antigo `19_bottom_shelf_canvas.lua`).

---

O plano está pronto e desenhado. Deseja que iniciemos a **Fase 1**, criando o módulo `regret_provenance.py`?

