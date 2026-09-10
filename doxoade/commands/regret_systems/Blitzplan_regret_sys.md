# doxoade/commands/regret_systems/Blitzplan_regret_sys.md
# 📜 BLITZPLAN — SISTEMA DOXOADE REGRET (ANÁLISE DE REGRESSÕES E PERDA DE CAPACIDADES)

## 1. Contexto e Objetivos (W5 / 5 Perguntas)
* **O quê:** Sistema de detecção estática e diferencial de regressões funcionais, podas acidentais de comandos, quebra de contratos de UX e remoção de salvaguardas nos templates e motores do Lite XL / Doxoade.
* **Quem:** Módulo de Auditoria Anúbis / Apolo para desenvolvedores e pipelines de CI/CD.
* **Onde:** `doxoade/commands/regret_systems/`
* **Quando:** Durante reconciliações de git (`rebase`), pré-commits (`git status`), ou na investigação pontual de arquivos (`doxoade regret <arquivo>`).
* **Por quê:** Refatorações no ecossistema Doxly/Lite XL frequentemente causam "regressões silenciosas" (como a remoção de atalhos de PrintScreen/imagem, podas de handlers de mouse, perda de time-slicing do Khonsu ou anulação de polyfills seguros).
* **Origem & Consequências:** Modificações rápidas sem verificação semântica de diff que levam à quebra de UX no editor em tempo de execução.

## 2. Taxonomia de Regressão Monitorada
1. **`COMMAND_LOST`:** Comandos registrados via `command.add` que existiam no commit anterior/base e foram removidos.
2. **`KEYMAP_LOST`:** Atalhos registrados via `keymap.add` extirpados.
3. **`HANDLER_MUTILATED`:** Métodos essenciais de ciclo de vida (`on_mouse_pressed`, `on_text_input`, `paste_clipboard_image`) deletados ou esvaziados.
4. **`SHIELD_DROPPED`:** Remoção de blocos `pcall`, `xpcall` ou substituição de `draw_rect_safe` por chamadas C puras instáveis.
5. **`PERF_THROTTLE_REMOVED`:** Eliminação de rotinas `Khonsu.debounce`, `Khonsu.throttle` ou yield em loops de I/O.
6. **`INTEGRATION_BROKEN`:** Perda de referências a submódulos (`.doxoade/assets/images`, `image_systems`).

## 3. Planos de Contingência e Execução
* **Plano A (Semântico via AST/Regex + Git Show):** Compara o inventário estrutural de símbolos da versão base contra a versão de trabalho atual.
* **Plano B (Léxico Heurístico):** Análise direta de hunks de diff unificado (`git diff -U0`) caso o arquivo esteja com sintaxe incompleta.
* **Plano C (Dump de Resgate):** Exportação dos blocos extirpados para `.doxoade/dumppot.txt` para recuperação rápida sem reverter a branch inteira.

---

Vamos estruturar o planejamento formal do **`doxoade regret`** seguindo à risca as diretrizes do **ProDeNov (Protocolo de Desenvolvimento Novíssimo)**.

---

# 📜 BLITZPLAN: `doxoade regret` (Motor de Detecção de Regressões)

## 1. Contextualização e Requisição (W5 / 5 Perguntas)

* **O quê:** Um comando CLI inteligente (`doxoade regret [ARQUIVO] [--commits N] [--staged] [--working-tree]`) que inspeciona o histórico recente do Git (últimos $N$ commits) e a área de trabalho atual (*uncommitted/working tree*) para identificar **perdas de capacidades, quebra de contratos de UX, remoção acidental de proteções e podas de funcionalidades**.
* **Quem:** Desenvolvedores do ecossistema Doxoade trabalhando em módulos críticos do Lite XL (Lua) e Python.
* **Onde:** `doxoade/commands/regret_systems/` (com ponto de entrada no CLI Zeus).
* **Quando:** Antes de fechar commits (`pre-commit`), durante reconciliações (`git rebase`), após refatorações agressivas ou ao investigar "por que tal recurso parou de funcionar".
* **Por quê:** Refatorações e limpezas em templates Lua do Lite XL costumam podar silenciosamente handlers de eventos, atalhos de teclado (`keymap`), comandos registrados (`command.add`), hooks de clipboard/PrintScreen e polyfills de compatibilidade, gerando regressões de UX difíceis de rastrear apenas com diffs brutos de texto.
* **Origem & Consequências:** Mudanças em arquivos como `19_bottom_shelf_canvas.lua` e `17_khonsu_coroutine.lua` que simplificam código podem remover o tratamento de imagens coladas (PrintScreen/CAS) ou corromper a temporização do time-slicing, quebrando a experiência do usuário final no editor.

---

## 2. Taxonomia de Regressão no Doxly (O que o `regret` procura)

O `doxoade regret` não deve ser apenas um `git diff` colorido. Ele deve ser um **analisador semântico de perdas estruturais**. Ele classificará as perdas em categorias de gravidade:

| Categoria | Tipo de Perda Detectada | Exemplo Prático | Severidade |
| :--- | :--- | :--- | :--- |
| **UX & Atalhos** | Comando ou Tecla Removida | Removido `keymap.add { ["ctrl+v"] = ... }` ou `command.add("doxoade:paste-image")` | 🔴 Alta |
| **Handlers / Eventos** | Evento do Ciclo de Vida Podado | `RootView:on_mouse_pressed`, captura de clipboard ou drop de arquivos removidos | 🔴 Alta |
| **Shields & Polyfills** | Proteção contra Crash Removida | Removido `pcall`, fallback de `nil` no Tokenizer ou `draw_rect_safe` | 🔴 Crítica |
| **Integração Externa** | Chamada de Sistema ou I/O Podada | Removido acesso a `.doxoade/assets/images`, perda de leitura de metadados | 🟡 Média |
| **Performance** | Throttle/Debounce Afrouxado | Remoção de `Khonsu.debounce` ou time-slicing retornando a loops bloqueantes | 🟡 Média |
| **Código Morto / Órfão** | Variável/Função Desconectada | Função mantida mas nunca mais chamada após refatoração | ⚪ Informativa |

---

## 3. Planos de Execução (Planos A, B e C — Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Análise Semântica Estrutural + Git Diff)
* O motor utiliza o `LuaStructuralParser` (já prototipado no `doxly_structural_fuzzer.py`) e o Git via `subprocess`.
* Compara a AST/símbolos da versão `HEAD~N` (ou commit base) contra a versão da árvore de trabalho (*working tree*).
* Extrai listas de:
  1. Comandos registrados (`command.add`).
  2. Atalhos mapeados (`keymap.add`).
  3. Métodos sobrescritos (`RootView:*`, `DocView:*`, `Node:*`).
  4. Proteções `pcall` e chamadas a módulos seguros.
* Realiza a diferença de conjuntos: **$Símbolos_{antigos} \setminus Símbolos_{novos} = Regressões$**.

### 🔹 Plano B (Fallback — Análise Léxica Heurística por Diffs)
* Caso o arquivo esteja corrompido ou com erro de sintaxe que impeça o parsing completo, o sistema chaveia para análise de diff unificado (`git diff -U0`).
* Filtra todas as linhas removidas (`-`) que contenham padrões críticos (`command.add`, `keymap.add`, `pcall`, `paste`, `clipboard`, `image`, `on_mouse`, `draw_`).
* Confirma se essas linhas reapareceram de outra forma como adição (`+`). Se não reapareceram, acusa regressão heurística.

### 🔹 Plano C (Quarentena & Recuperação de Emergência)
* O comando gera um patch reverso com `--restore-lost-features` (em modo `--dry-run` por padrão).
* Permite extrair o bloco de código extirpado para um arquivo de scratchpad (`.doxoade/dumppot.txt`) para reinserção manual sem desfazer o refactor atual.

---

## 4. Estrutura de Arquivos Planejada (Limite < 50KB por arquivo)

```
doxoade/commands/regret_systems/
├── __init__.py
├── cmd_regret.py            # CLI Zeus (click): doxoade regret [FILE] [--commits N] [--dry-run]
├── regret_engine.py         # Orquestrador do fluxo de análise de regressão
├── regret_git_reader.py     # Leitor de estados e diffs do Git (working tree / commits)
├── regret_lua_inspector.py  # Inspetor de símbolos perdidos em arquivos Lua
└── regret_reporter.py       # Renderizador Apolo (UX clara, snippets do que foi extirpado)
```

---

## 5. Estudo de Caso Imediato: O Incidente do Template 19 (`19_bottom_shelf_canvas.lua`)

Com base no seu `git status` e histórico:
1. **O Problema:** O `19_bottom_shelf_canvas.lua` gerenciava a captura e colagem de imagens (`PrintScreen` / Clipboard / tags `[DOX-IMG]`).
2. **O Risco de Regressão Atual:** Houve alterações pendentes em:
   * `doxoade/commands/lite_xl_systems/template/19_bottom_shelf_canvas.lua`
   * `doxoade/commands/lite_xl_systems/template/17_khonsu_coroutine.lua`
   * `doxoade/tools/image_systems/` (criado como untracked)
3. **Aplicação do `doxoade regret`:**
   * O comando vai ler o diff de `19_bottom_shelf_canvas.lua` comparando o estado do commit anterior contra o estado atual modificado.
   * Ele apontará exatamente se:
     * Métodos como `FloatingPanel:paste_clipboard_image` ou handlers de tecla foram removidos ou desacoplados.
     * A integração com o Khonsu (`coroutine.yield` durante a decodificação da imagem) foi truncada.
     * As chamadas para `image_systems` perderam compatibilidade de contrato.

---

## 6. Tasklist & Checklist de Implementação

- [ ] **Fase 1: Preparação dos Placeholders (ProDeNov 2.1)**
  - [ ] Criar diretório `doxoade/commands/regret_systems/`.
  - [ ] Adicionar headers com caminho relativo, docstrings de objetivo e imports em cada módulo.
- [ ] **Fase 2: Motor de Extração Git (`regret_git_reader.py`)**
  - [ ] Leitura de working tree (uncommitted/staged).
  - [ ] Extração de snapshots dos últimos $N$ commits (`git show <commit>:<path>`).
- [ ] **Fase 3: Inspetor Semântico Lua (`regret_lua_inspector.py`)**
  - [ ] Comparação de inventário de Comandos, Keymaps e Handlers.
  - [ ] Detecção de blocos de proteção eliminados (`pcall`, polyfills).
- [ ] **Fase 4: Formatação Forense Apolo (`regret_reporter.py`)**
  - [ ] Exibição das 5 Perguntas (*O que foi removido? Onde estava? Qual o impacto no UX?*).
  - [ ] Snippet visual do código eliminado.
- [ ] **Fase 5: Integração CLI & Validação**
  - [ ] Integrar no grupo Zeus principal (`doxoade regret`).
  - [ ] Testar diretamente contra `template/19_bottom_shelf_canvas.lua` e `template/17_khonsu_coroutine.lua`.

---

**Aprovado o plano de desenvolvimento?** Se estiver de acordo, posso iniciar a forja dos placeholders e do motor de inspeção do `doxoade regret`.

---
