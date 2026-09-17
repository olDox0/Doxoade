
Vou desenhar o plano da **Fase 1** com precisão cirúrgica. Antes de forjar código, preciso alinhar 3 decisões arquiteturais com você:

---

## 🏗️ BLITZPLAN — TERMINAL REAL (ROTA B)

### Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LITE XL (Lua)                                 │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  19d_bottom_shelf_hub.lua                                     │  │
│  │  (UI: abas, botões, keymap routing)                           │  │
│  └───────────────────────┬───────────────────────────────────────┘  │
│                          │                                          │
│  ┌───────────────────────▼───────────────────────────────────────┐  │
│  │  19b_terminal_console.lua  [REFORMA]                          │  │
│  │  • TerminalPTYClient (conecta ao Python)                      │  │
│  │  • ANSI Parser (cores, cursor, estilos)                       │  │
│  │  • Renderizador (segmentos coloridos no viewport)             │  │
│  │  • Scrollback buffer                                          │  │
│  └───────────────────────┬───────────────────────────────────────┘  │
│                          │ Socket TCP Local                         │
└──────────────────────────┼──────────────────────────────────────────┘
                           │
                           │ 127.0.0.1:19847
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                     PYTHON (venv doxoade)                            │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  doxoade/tools/terminal_pty/pty_server.py                     │  │
│  │  • ConPTY (Windows 11) / PTY (Unix)                          │  │
│  │  • Spawn: cmd.exe / powershell.exe / bash                     │  │
│  │  • Socket server: recebe teclas, envia output                 │  │
│  │  • Resize handling                                            │  │
│  │  • SIGINT / Ctrl+C forwarding                                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  doxoade/tools/terminal_pty/ansi_types.py                     │  │
│  │  • Tipos compartilhados (protocolo Lua↔Python)                │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

### ❓ 3 Decisões Arquiteturais

#### 1. Comunicação Lua ↔ Python

| Opção | Prós | Contras |
| :--- | :--- | :--- |
| **Socket TCP Local** | Simples, debugável com `telnet`, cross-platform, Lite XL pode usar `socket` via plugin ou bridge | Latência ~0.1ms (imperceptível) |
| **Named Pipe** | Mais rápido (~0.01ms) | Complexo no Windows, difícil debugar |

**Minha recomendação:** Socket TCP Local na porta `19847` (ou configurável). É simples, funciona em qualquer OS, e o Lite XL pode comunicar via `system.exec` em background ou via um pequeno bridge C (que o Doxoade já tem via Vulcan).

#### 2. Biblioteca PTY no Python

| Plataforma | Biblioteca | Instalação |
| :--- | :--- | :--- |
| **Windows 11** | `pywinpty` | `pip install pywinpty` |
| **Linux/Mac** | `pty` (stdlib) | Já incluído |

**Minha recomendação:** Usar `pywinpty` no Windows e `pty` nativo no Unix, com fallback gracioso se `pywinpty` não estiver instalado.

#### 3. Como o Lua conecta ao Python?

O Lite XL **não tem socket nativo**. Opções:

| Opção | Como funciona |
| :--- | :--- |
| **A) Bridge C via Vulcan** | O Doxoade já compila bridges C. Criar uma função C `term_pty_read()`/`term_pty_write()` que o Lua chama. |
| **B) Arquivo de troca (File IPC)** | Python escreve output em arquivo, Lua lê periodicamente via `system.get_file_info` + `io.open`. Simples mas latência maior. |
| **C) Process pipe via Lite XL API** | Usar `process.start` do Lite XL para spawnar o Python server e comunicar via stdin/stdout do processo. |

**Minha recomendação:** **Opção C** — usar `process.start` para spawnar `python pty_server.py --pipe-mode`. O Lite XL já tem API de processo com pipes. O Python server lê comandos do stdin (do processo Lite XL) e escreve output no stdout. Sem necessidade de socket externo.

---

### 📁 Estrutura de Arquivos (Fase 1)

```
doxoade/tools/terminal_pty/
├── __init__.py              # Package init
├── pty_server.py            # Motor principal (~12KB)
├── pty_windows.py           # ConPTY via pywinpty (~8KB)
├── pty_unix.py              # PTY via stdlib (~6KB)
├── ansi_protocol.py         # Protocolo de comunicação Lua↔Python (~4KB)
└── README.md                # Documentação do módulo
```

---

### 📋 Tasklist Fase 1

- [ ] **1.1** Criar diretório `doxoade/tools/terminal_pty/`
- [ ] **1.2** Implementar `pty_windows.py` (ConPTY spawn + read/write loop)
- [ ] **1.3** Implementar `pty_unix.py` (PTY spawn + read/write loop)
- [ ] **1.4** Implementar `pty_server.py` (orquestrador: detecta OS, spawn shell, loop de I/O)
- [ ] **1.5** Implementar `ansi_protocol.py` (protocolo de mensagens entre Lua e Python)
- [ ] **1.6** Testar standalone: `python pty_server.py` deve abrir um shell interativo no terminal

---

### Perguntas Finais antes de eu forjar o código:

1. **Comunicação:** Confirma **Opção C** (process pipe via Lite XL API)? Ou prefere Socket TCP?
2. **Shell padrão no Windows:** `cmd.exe`, `powershell.exe`, ou `wt.exe` (Windows Terminal)?
3. **Dependência:** Posso adicionar `pywinpty` ao `pyproject.toml` como dependência opcional?

Me confirme essas 3 respostas e eu inicio a forja da Fase 1.
