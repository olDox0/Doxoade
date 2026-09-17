Sua observação vai direto na ferida da arquitetura anterior. O modelo antigo do `19b` não era um terminal de fato: ele era um **executor de scripts batch temporários (`run_*.cmd`) com polling de arquivo (`out_*.txt`) no disco**.

Esse mecanismo sofria de 4 limitações graves:
1. **Ausência de `stdin` interativo:** Impossibilitava rodar `python` (REPL), `input()`, confirmações de pacotes (`[y/N]`), `pdb` ou `ssh`.
2. **Sessão descartável (Stateless):** Cada comando rodava em um subshell efêmero que morria logo em seguida — um `cd pasta` ou um `set VAR=1` se perdia no comando seguinte.
3. **I/O desnecessário no disco:** Criação e destruição contínua de arquivos `.cmd`, `.txt` e `.flag` na pasta `.doxoade/terminal_temp/`.
4. **Sem propagação de sinais:** Impossibilidade de enviar `Ctrl+C` real para interromper um script em loop.

Abaixo está o **Blitzplan arquitetural oficial (ProDeNov 1.2.1)** para reconstruir o `19b` como uma **Sessão de Terminal Interativa Persistente e Contínua (True PTY & Interactive Stream Engine)**.

---

# 📜 BLITZPLAN — TERMINAL INTERATIVO SOBERANO (REFORMULAÇÃO DO 19B)
**Módulos Alvo:** `doxoade/commands/lite_xl_systems/template/19b_terminal_console.lua`, `19d_bottom_shelf_hub.lua` e `doxoade/tools/terminal_systems/terminal_stream_daemon.py`  
**Protocolo:** ProDeNov 1.2.1 | PASC-6.1 | W5 | Limite < 50KB por arquivo  
**Panteões:** Hermes (Comunicação/Streams), Hefesto (Processos), Apolo (UX/TrueColor) e Zeus (CLI)

---

## 1. Contexto e Objetivos (W5 / 5 Perguntas)

* **O quê (What):**
  1. **Sessão de Shell Viva e Persistente:** O Doxly mantém um processo de shell ativo em background (`powershell.exe`, `cmd.exe` ou `bash`) com o `venv` já ativado na raiz do projeto. O estado (diretório atual, variáveis de ambiente, histórico) persiste entre comandos.
  2. **Canal Bidirecional de I/O em Tempo Real (`stdin` / `stdout` / `stderr`):** Digitação enviada instantaneamente ao stream de entrada do processo vivo; saída transmitida por stream contínuo via buffer compartilhado / socket local.
  3. **Interatividade Real:** Capacidade de responder a prompts dinâmicos (`input()`, confirmações `y/n`, `python` interativo, `pytest -s`).
  4. **Controle de Sinais (`Ctrl+C` / `Ctrl+D` / `Ctrl+L`):** Interrupção de processos travados via sinal de cancelamento sem matar a IDE.
  5. **Extirpação do Batch-File Polling:** Eliminação total de arquivos `.cmd` e `.txt` temporários em disco.
* **Quem (Who):** Desenvolvedores executando testes, scripts interativos, migrações e comandos do Doxoade diretamente no rodapé da IDE.
* **Onde (Where):**
  * `doxoade/tools/terminal_systems/terminal_stream_daemon.py` (Worker de processo persistente com PTY/pipes).
  * `doxoade/commands/lite_xl_systems/template/19b_terminal_console.lua` (Motor de buffer virtual, parser ANSI TrueColor e despachante).
  * `doxoade/commands/lite_xl_systems/template/19d_bottom_shelf_hub.lua` (Roteamento de teclado, foco e atalhos).
* **Quando (When):** Instantaneamente ao abrir o Bottom Shelf (`Ctrl+J` / `doxoade:toggle-bottom-shelf`).
* **Por quê (Why):** Um desenvolvedor precisa de uma linha de comando real dentro do seu ambiente de trabalho sem atritos de subshell fechado ou falta de interatividade.
* **Origem & Consequências (Origin & Consequences):** O modelo anterior foi prototipado como um *command runner* simplificado que atingiu seu teto. A reformulação estabelece paridade de recursos com terminais integrados modernos.

---

## 2. Nova Arquitetura: Streaming Interativo Bidirecional

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DOXLY BOTTOM SHELF (LUA)                              │
│                                                                                 │
│   [Buffer Virtual de Linhas] ◄── Parser ANSI TrueColor ◄── Leitor de Stream     │
│   [Linha de Entrada / Prompt] ──► Eventos de Tecla ───► Escritor de Stdin       │
└──────────────────────────────┬────────────────────────▲─────────────────────────┘
                               │ (Stdin / Sinais)       │ (Stdout / Stderr Stream)
                               ▼                        │
┌─────────────────────────────────────────────────────────────────────────────────┐
│               HERMES TERMINAL DAEMON (Python / Native Worker)                   │
│                                                                                 │
│   • Mantém a sessão do Shell viva (PowerShell / CMD / Bash + Venv)              │
│   • Comunicação assíncrona não-bloqueante (Threads I/O + Non-blocking Pipes)   │
│   • Trata sinais de cancelamento (SIGINT / GenerateConsoleCtrlEvent)            │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Sessão Persistente com Stream Worker Assíncrono)
1. **Terminal Stream Daemon (`terminal_stream_daemon.py`):**
   * Lança o shell pai com pipes redirecionados (`stdin=PIPE`, `stdout=PIPE`, `stderr=STDOUT`).
   * Roda em thread assíncrona lendo bytes brutos e despejando em um buffer circular de memória mapeada (ou pipe de IPC ultrarrápido).
   * Recebe inputs do Lua e injeta diretamente no `stdin` do processo vivo.
2. **Motor Virtual no Lua (`19b_terminal_console.lua`):**
   * Conecta-se à sessão viva no boot do módulo.
   * `execute_command(cmd)` simplesmente escreve `cmd .. "\n"` no stream de `stdin`.
   * Leitura em cada ciclo de frame (`coroutine.yield(0.01)`) que puxa novos bytes do stream e atualiza o buffer de tela em $O(1)$.
   * `Ctrl+C` no prompt envia sinal de interrupção ao daemon, parando o processo em execução sem fechar o terminal.
3. **Persistência Real:**
   * Comandos como `cd subpasta` alteram o diretório do processo pai; o próximo comando já roda dentro de `subpasta`.
   * Variáveis exportadas continuam ativas.

### 🔹 Plano B (Fallback — Persistent Subprocess via Standard Pipes sem Daemon Externo)
* Caso o daemon de background não esteja disponível, o `19b` utiliza a API nativa `system.exec` em modo pipe contínuo mantido no registry do Lua, com leitura fatiada pelo `Khonsu`.

### 🔹 Plano C (Contingência — Despacho Externo com 1 Clique)
* Se houver falha de descritores de arquivo ou travamento de PTY, o botão `[> Terminal]` dispara o **Windows Terminal (`wt.exe`) / PowerShell elevado** na raiz do projeto com o venv carregado (já blindado contra caminhos com espaços).

---

## 4. Arquivos Impactados e Limites (< 50KB)

```
doxoade/
├── tools/terminal_systems/
│   ├── __init__.py
│   └── terminal_stream_daemon.py    # [NOVO] Processo persistente de shell (~16KB)
└── commands/lite_xl_systems/template/
    ├── 19b_terminal_console.lua     # [REFORMULADO] Virtual Screen & Stdin Stream (~26KB)
    └── 19d_bottom_shelf_hub.lua     # [ATUALIZADO] Foco contínuo e atalhos Ctrl+C/D (~24KB)
```

---

## 5. Tasklist & Checklist de Implementação

- [ ] **Fase 1: O Motor de Sessão Persistente (`terminal_stream_daemon.py`)**
  - [ ] Implementar inicialização de shell contínuo com venv injetado (`PowerShell`/`CMD`/`Bash`).
  - [ ] Implementar leitura assíncrona de `stdout`/`stderr` sem deadlocks.
  - [ ] Implementar canal de escrita de `stdin` e manipulador de `SIGINT`/`Ctrl+C`.
  - [ ] Suporte a auto-recuperação (reinicia o shell se ele for finalizado com `exit`).

- [ ] **Fase 2: Refatoração do `19b_terminal_console.lua`**
  - [ ] Extirpar a geração de arquivos temporários `.cmd`, `.txt` e `.flag`.
  - [ ] Conectar envio de texto diretamente ao `stdin` da sessão ativa.
  - [ ] Implementar leitura de streaming por chunks em regime contínuo.
  - [ ] Mapear comandos especiais: `clear` limpa a tela virtual; `Ctrl+C` cancela a execução atual.
  - [ ] Preservar o parser TrueColor 24-bit e o autocomplete inteligente (`TAB`).

- [ ] **Fase 3: Roteamento de Teclado no `19d_bottom_shelf_hub.lua`**
  - [ ] Garantir captura contínua de teclas quando a aba de Terminal estiver ativa.
  - [ ] Permitir envio de caracteres únicos para comandos interativos (ex: `y` / `n`).

- [ ] **Fase 4: Validação Empírica & Anti-Regressão**
  - [ ] Testar comando interativo: `python -c "nome = input('Nome: '); print('Olá', nome)"`.
  - [ ] Testar persistência de diretório: `cd doxoade` seguido de `cd commands` e `dir` / `ls`.
  - [ ] Testar interrupção de loop infinito com `Ctrl+C`.
  - [ ] Rodar `doxoade doxly check-templates` e `doxoade regret` para garantir integridade absoluta.

---

**Plano delineado e fundamentado no padrão ProDeNov.**  
Podemos iniciar a **Fase 1** (criação do daemon de streaming) e a **Fase 2** (reestruturação do `19b`)?
