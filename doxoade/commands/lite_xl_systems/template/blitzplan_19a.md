# 📜 BLITZPLAN — TERMINAL HÍBRIDO SOBERANO (DOXLY IDE)
**Módulos Alvo:** `19b_terminal_console.lua` e `19d_bottom_shelf_hub.lua`  
**Protocolo de Conformidade:** ProDeNov 1.2.1 (Planos A, B e C | W5 | Limite < 50KB)  
**Data:** 09/09/2026 | **Autor:** Nexus Core / Apolo, Hermes & Zeus

---

## 1. Contexto e Objetivos (W5 / 5 Perguntas)

* **O quê:** 
  1. **Motor de Autocomplete Visual no Input da IDE:** Transformar a linha de comando interna do Bottom Shelf em um input moderno com **Ghost Text** (texto fantasma inline) e **Dropdown Flutuante de Sugestões** (comandos do Doxoade, submódulos Doxly, Git e arquivos do projeto via `TAB`).
  2. **Lançador de Terminal Nativo Real (Windows Terminal / PowerShell com Venv):** Adicionar a capacidade de disparar com 1 clique (ou atalho) um **terminal de verdade do sistema operacional** (`wt.exe` / `powershell` / `cmd`), já contextualizado na raiz do projeto e com o ambiente virtual (`venv`) ativado.
  3. **Higienização do Buffer de Exibição:** Eliminar a exibição bugada corrigindo o parser ANSI para suportar **TrueColor 24-bit** (`Fore.PRIMARY`, etc.), tratar o `\r` (evitando linhas duplicadas em spinners/progress bars) e expurgar sequências de controle cruas (`\x1b[2K`, `\x1b[?25l`).
* **Quem:** Desenvolvedores executando comandos rápidos dentro da IDE ou sessões interativas no terminal nativo.
* **Onde:** `doxoade/commands/lite_xl_systems/template/` (`19b_terminal_console.lua` e `19d_bottom_shelf_hub.lua`).
* **Quando:** Durante qualquer digitação no Bottom Shelf ou quando uma tarefa exigir interatividade real (`REPL`, `input()`, `pytest`, `Sotéria`).
* **Por quê:** O terminal interno em Lua/SDL2 é excelente como *Command Runner* com autocomplete ágil para tarefas rápidas, mas um terminal de verdade no SO é insubstituível para sessões interativas pesadas.
* **Origem & Consequências:** O `19b` tentava ser um terminal VT100 completo desenhado em retângulos SDL2, mas não possuía PTY de stdin nem suporte a TrueColor 24-bit, gerando caracteres corrompidos na tela.

---

## 2. A Nova Arquitetura de UX (Como vai funcionar)

### A. O Input Bar com Autocomplete Inteligente (Dentro da IDE)
Ao digitar no Bottom Shelf, duas camadas visuais guiam o desenvolvedor:

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│ ⚡ Sugestões (TAB para autocompletar | ↑↓ para navegar):                        │
│   ► doxoade check           [AUDITORIA]  Auditoria de qualidade modular         │
│     doxoade check-templates [DOXLY]      Validação dos templates Lua           │
│     doxoade chaos           [TESTE]      Injeção de caos no Sandbox             │
│     doxoade regret          [REGRESSÃO]  Auditoria de contratos e histórico     │
└─────────────────────────────────────────────────────────────────────────────────┘
> doxoade ch[eck]                     <-- [eck] em cinza escuro (Ghost Text)
```

* **Vocabulário Dinâmico:**
  * **Comandos Doxoade:** `check`, `mk`, `regret`, `run`, `backup`, `diff`, `doctor`, `init`, `debug`.
  * **Comandos Doxly:** `doxly deploy test`, `doxly deploy production`, `doxly check-templates`, `doxly log`.
  * **Comandos Git:** `git status`, `git diff`, `git log`, `git add`, `git commit`.
  * **Arquivos do Projeto:** autocompleta nomes de arquivos `.py`, `.lua`, `.md` existentes na raiz.
  * **Atalhos Rápidos:** `cls` (limpar), `term` / `wt` (abrir terminal nativo).

---

### B. Abertura do "Terminal Mesmo" (Nativo com Venv)
Três portas de entrada rápidas para abrir o terminal real sem sair do fluxo:
1. **Botão no Topo do Hub:** Botão destacado `[⚡ Abrir Terminal Real (Venv)]`.
2. **Atalho de Teclado Global:** `Ctrl+Shift+T` ou `F12` abre o terminal nativo instantaneamente.
3. **Comando no Próprio Prompt:** Digitar `term`, `terminal`, `wt` ou `cmd` e teclar Enter.

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Autocomplete Híbrido + Windows Terminal / Conhost)
1. **Detecção e Lançamento do Terminal do SO:**
   * Ordem de precedência:
     1. `wt.exe` (**Windows Terminal** moderno): abre com aba no diretório do projeto e dispara o script de ativação do venv.
     2. `powershell.exe`: abre janela independente com `-ExecutionPolicy Bypass -NoExit` ativando o venv.
     3. `cmd.exe`: abre com `/k "venv\Scripts\activate.bat"`.
     4. Linux/Termux: `$TERMINAL` ou `x-terminal-emulator` / `bash`.
2. **Motor de Autocomplete em `19b_terminal_console.lua`:**
   * População dinâmica do catálogo de comandos e arquivos do projeto.
   * Seleção por `Tab`, `Shift+Tab` ou setas `↑` e `↓`.
   * Geração de **Ghost Text** inline na linha do cursor.
   * Renderização de caixa suspensa flutuante (*Dropdown Box*) de sugestões acima do input bar.
3. **Higienização do Buffer ANSI:**
   * Parser completo de **TrueColor 24-bit** (`\x1b[38;2;R;G;Bm`), permitindo que as cores do `doxcolors` apareçam perfeitas.
   * Tratamento de `\r` (Carriage Return) para sobrescrever a linha em vez de duplicá-la.
   * Expurgador de códigos de escape de cursor (`\x1b[2K`, etc.).

### 🔹 Plano B (Fallback — PowerShell Puro / CMD)
* Se o `wt.exe` não estiver instalado no Windows (ex.: versões anteriores do Windows 10), o motor faz fallback silencioso para `powershell.exe` ou `cmd.exe` com o venv ativado, sem quebrar o fluxo.

### 🔹 Plano C (Contingência — Fuga para o CLI Doxoade)
* Caso haja restrição de permissão ou falha de `subprocess`, a IDE invoca o comando nativo `doxoade terminal` ou `doxoade venv`, delegando o provisionamento para o Zeus CLI já homologado.

---

## 4. Arquivos Impactados e Limites (< 50KB)

```
doxoade/commands/lite_xl_systems/template/
├── 19b_terminal_console.lua    # Parser TrueColor + Lançador de Terminal Real (~18KB)
└── 19d_bottom_shelf_hub.lua    # Renderizador da Caixa de Autocomplete + Botão Real (~22KB)
```
*Ambos os arquivos respeitam rigorosamente a meta de tamanho do ProDeNov.*

---

## 5. Especificação Técnica da Engenharia

### 5.1. Lançador do Terminal Nativo Real (`19b_terminal_console.lua`)

```lua
function TerminalEngine:launch_real_terminal()
  local proj = get_active_project_dir()
  local scripts_dir, venv_dir = detect_project_venv(proj)
  local sep = PATHSEP or "/"

  if PLATFORM == "Windows" then
    -- 1. Tenta Windows Terminal (wt.exe)
    local wt_cmd = string.format('wt.exe -d "%s"', proj)
    if venv_dir then
      local act_bat = venv_dir .. sep .. "Scripts" .. sep .. "activate.bat"
      wt_cmd = string.format('wt.exe -d "%s" cmd.exe /k "%s"', proj, act_bat)
    end

    local ok = pcall(system.exec, wt_cmd)
    if not ok or not system.get_file_info(os.getenv("LOCALAPPDATA") .. "\\Microsoft\\WindowsApps\\wt.exe") then
      -- 2. Fallback para PowerShell com Venv
      local ps_cmd = string.format('start "Doxoade Terminal" powershell.exe -NoExit -Command "Set-Location \'%s\'', proj)
      if venv_dir then
        local act_ps1 = venv_dir .. sep .. "Scripts" .. sep .. "Activate.ps1"
        ps_cmd = ps_cmd .. string.format('; if (Test-Path \'%s\') { & \'%s\' }', act_ps1, act_ps1)
      end
      ps_cmd = ps_cmd .. '"'
      pcall(system.exec, ps_cmd)
    end
  else
    -- Linux / POSIX
    local term_cmd = string.format('x-terminal-emulator -e "bash -c \'cd %s && exec bash\'" &', proj)
    pcall(system.exec, term_cmd)
  end

  if core.log then
    core.log("⚡ [TERMINAL REAL] Janela de terminal nativa aberta no projeto.")
  end
end
```

### 5.2. Parser TrueColor 24-bit (`19b_terminal_console.lua`)

```lua
-- Suporte a: \x1b[38;2;R;G;Bm (TrueColor FG) e \x1b[48;2;R;G;Bm (TrueColor BG)
local r, g, b = code_str:match("^38;2;(%d+);(%d+);(%d+)$")
if r and g and b then
  current_fg = { tonumber(r), tonumber(g), tonumber(b), 255 }
end
```

### 5.3. Dropdown Flutuante de Autocomplete (`19d_bottom_shelf_hub.lua`)

```lua
-- Renderiza a caixa de sugestões suspensa acima do input bar se houver candidatos
if #term.suggestions > 0 and term.input_text ~= "" then
  local box_h = math.min(6, #term.suggestions) * item_h + 8
  local box_y = input_y - box_h - 4
  draw_rect_safe(x + 10, box_y, 450, box_h, { 15, 15, 18, 250 })
  draw_rect_safe(x + 10, box_y, 450, 1, style.accent)
  -- desenha sugestões com badge [DOXOADE], [FILE], etc.
end
```

---

## 6. Tasklist & Checklist de Execução

- [ ] **Fase 1: Motor do Terminal Real & Parser ANSI/TrueColor (`19b_terminal_console.lua`)**
  - [ ] Implementar `TerminalEngine:launch_real_terminal()` (WT ➔ PowerShell ➔ CMD com venv).
  - [ ] Atualizar `parse_ansi_segments` para suportar TrueColor 24-bit (`38;2;r;g;b`) e filtrar artefatos de cursor.
  - [ ] Adicionar suporte a comandos de prompt: `term`, `wt`, `cmd` abrirem o terminal nativo.

- [ ] **Fase 2: Autocomplete Visual e UI do Bottom Shelf (`19d_bottom_shelf_hub.lua`)**
  - [ ] Adicionar botão de ação no header: `[⚡ Terminal Real]`.
  - [ ] Implementar renderização do **Ghost Text** inline na caixa de input.
  - [ ] Implementar renderização do **Dropdown Box** com as sugestões ativas.
  - [ ] Mapear navegação por `TAB` / `Shift+TAB` e `Enter`.

- [ ] **Fase 3: Validação de Estabilidade e Regressão**
  - [ ] Rodar `doxoade doxly check-templates` (assegurar 30/30 PASS e 82/82 comandos).
  - [ ] Fazer deploy no ambiente de teste (`doxoade doxly deploy test`).
  - [ ] Testar no Lite XL:
    1. Clicar no botão `[⚡ Terminal Real]` e verificar se o terminal do Windows abre no projeto com o venv ativado.
    2. Digitar `dox` no prompt interno e verificar o autocompletion visual e a navegação por TAB.
  - [ ] Rodar `doxoade regret` para garantir conformidade contínua.

---

**Plano delineado no padrão ProDeNov.**  
Podemos iniciar a **Fase 1** (Lançador do Terminal Real e Parser TrueColor no `19b`)?

---

### 🩺 Diagnóstico da Abertura de Terminal Externo no Windows

O motivo do terminal real (especialmente como Administrador) não ter aberto decorre de como o Windows e o Lite XL gerenciam processos:

---

### 🔍 1. Por que o terminal externo / Admin falhou?

1. **O Comportamento do `system.exec` no Lite XL:**
   * No Windows, o `system.exec` do Lite XL invoca a API `CreateProcessW` em modo desacoplado (`DETACHED_PROCESS` ou sem console associado).
   * Se você tentar executar `wt.exe` ou `cmd.exe` diretamente pelo `system.exec`, o processo é criado em segundo plano sem janela interativa ou é finalizado imediatamente.
2. **A Elevação de Privilégios (Admin / UAC no Windows):**
   * Nenhum processo comum pode abrir outro processo com privilégios de Administrador usando apenas `CreateProcess`.
   * Para disparar a janela de confirmação de Administrador do Windows (UAC), é obrigatório usar a API `ShellExecuteEx` com o verbo **`runas`**, ou disparar via PowerShell:
     ```powershell
     Start-Process wt.exe -Verb RunAs -WorkingDirectory "C:\projeto"
     ```
3. **Ativação Automática do Virtualenv:**
   * Ao abrir um terminal externo (seja `wt.exe`, `powershell.exe` ou `cmd.exe`), o ideal é que ele já inicie **com o `venv` ativado** e na pasta raiz do seu projeto, sem exigir que você navegue ou rode `activate` manualmente.

---

### 🏛️ 2. Proposta de Arquitetura para o Terminal Real (ProDeNov 1.2.1)

Vamos criar um **Despachante Soberano de Terminais Externos** integrado ao `19b_terminal_console.lua` e `19d_bottom_shelf_hub.lua`:

```
                                    ┌─► [1. Windows Terminal (wt.exe)]  (Prioridade 1 - Abas & TrueColor)
[Invocação no Doxly] ──► Roteador ──┼─► [2. PowerShell 7 / Windows PS]  (Prioridade 2)
  (Normal ou Admin)      Soberano   └─► [3. CMD Clássico (cmd.exe)]     (Fallback Seguro)
                                                    │
                                                    ▼
                                       Injeta Script de Ativação
                                          do Venv do Projeto!
```

---

### 🎛️ 3. Modos de Terminal Disponíveis

| Modo | Comando no Console | Ação Realizada |
| :--- | :--- | :--- |
| **Terminal Normal** | `term` ou `wt` ou botão `[Terminal]` | Abre o **Windows Terminal** (ou PowerShell/CMD) na raiz do projeto com o `venv` ativo. |
| **Terminal Administrador** | `admin` ou `sudo` ou botão `[🛡️ Admin]` | Dispara o prompt do UAC e abre o terminal elevado como **Administrador** com o `venv` ativo. |
| **CMD Puro** | `cmd` | Abre o Prompt de Comando clássico (`cmd.exe /k`) com o `activate.bat` executado. |
| **PowerShell Puro** | `ps` ou `pwsh` | Abre o PowerShell com a política de execução liberada e `Activate.ps1` carregado. |

---

### 🛠️ 4. Como será implementado nos Templates

1. **No `19b_terminal_console.lua`:**
   * Adicionar o despachante `TerminalEngine:launch_external_terminal(as_admin, shell_type)`.
   * Se `as_admin == true`, monta o comando via PowerShell `Start-Process ... -Verb RunAs`.
   * Se for `cmd.exe`: executa `cmd.exe /k "cd /d <projeto> && venv\Scripts\activate.bat"`.
   * Se for `wt.exe`: executa `wt.exe -d "<projeto>" cmd.exe /k "venv\Scripts\activate.bat"`.
2. **Comandos Interativos do Console Studio:**
   * Digitar `wt`, `term`, `cmd`, `admin` ou `sudo` no prompt do Console Studio abrirá a janela externa instantaneamente.
3. **Na Barra Superior do Bottom Shelf (`19d_bottom_shelf_hub.lua`):**
   * Botões dedicados:
     * **`[> Terminal]`** (Abre terminal externo normal)
     * **`[🛡️ Admin]`** (Abre terminal externo como Administrador)

---

Podemos avançar com o **Blitzplan e implementação** desse despachante de terminais reais?
