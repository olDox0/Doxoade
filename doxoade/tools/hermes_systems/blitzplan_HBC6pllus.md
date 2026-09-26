# doxoade/tools/hermes_systems/blitzplan_HBC6plus.md
# ☤ BLITZPLAN: HERMES HBC6+ — ENGINE DAEMON & ALLOY OPTIMIZATION
**Versão do Documento:** 1.0.0-PRODENOV  
**Responsabilidade:** Hermes Systems & Vulcan Forge  
**Classificação:** Arquitetura Estrutural de Runtime  

---

## 1. Justificativa & Diagnóstico Forense (W5H — ProDeNov §3.1.4)

| Pergunta | Diagnóstico da Arquitetura Atual | Diretriz da Nova Arquitetura |
| :--- | :--- | :--- |
| **O quê? (What)** | Cold-start pesado (~40MB RAM, 160ms a 800ms de boot), overhead de terminal (`WriteConsoleW`) e compilação Cython impura (Metal 0% com excesso de chamadas C-API). | Criação do `engine_daemon` (runtime residente), canal assíncrono universal de terminal (`print`/`click.echo`) e o compilador de ligas híbridas `alloy_opt`. |
| **Onde? (Where)** | `doxoade/boot.py`, `doxoade/tools/hermes_systems/`, `doxoade/tools/vulcan/` e canais de I/O em `doxoade/tools/doxcolors.py`. | Centralizado em `doxoade/tools/engine_daemon/` e no pipeline de forja `alloy_opt` em `tools/vulcan/`. |
| **Quem? (Who)** | Hermes (Comunicação/IPC), Vulcan (Alloy Engine) e Apolo (Terminal flicker-free). | Um daemon leve de fundo gerenciando o ciclo de vida e servindo o CLI do Doxoade. |
| **Quando? (When)** | O daemon sobe de forma transparente no primeiro comando ou via boot de sistema, mantendo estado quente; o CLI conecta via IPC ultrarrápido. | Planejado como sprint de refatoração para a próxima janela de evolução do Doxoade. |
| **Quanto? (Cost/Impact)** | Eliminação de 90% da latência de boot (queda de ~200ms para <15ms em comandos CLI frequentes) e redução de 80% do tempo de terminal no Windows. | Manter a pegada do daemon em disco e memória restrita (<35MB RSS em repouso). |
| **Por quê? (Why)** | Micro-benchmarks de C enganam: em produção, o custo de carregar DLLs, checar hashes e cruzar o GIL anula ganhos de arquivos pequenos se tudo for inicializado a cada disparo. | Módulos de orquestração Python nunca serão 100% C puro; tratá-los como **Liga Metálica** (`alloy_opt`) resolve o problema sem impor anotações C manuais impossíveis. |

---

## 2. Os Três Pilares da Arquitetura HBC6+

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DOXOADE HBC6+ RUNTIME                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌──────────────────┐      ┌──────────────────┐       ┌──────────────────┐
│   PILAR 1        │      │   PILAR 2        │       │   PILAR 3        │
│  engine_daemon   │      │  Async Echo Hook │       │    alloy_opt     │
│ (IPC Residente)  │      │ (print/click.echo│       │ (Liga Python + C)│
└──────────────────┘      └──────────────────┘       └──────────────────┘
```

---

### PILAR 1: O `engine_daemon` (Runtime Residente & Cold-Start Zero)
* **Conceito:** O Doxoade CLI não precisa reinicializar bancos SQLite, compilar bridges C e reconstruir o `sys.meta_path` a cada invocação isolada.
* **Mecanismo:**
  1. Um processo daemon em segundo plano (`engine_daemon`) inicializa o ambiente uma única vez e mantém na memória:
     - Mapeamentos de memória virtual (`mmap`) de dicionários globais (`master.bin`).
     - Pool de conexões abertas com `doxoade.db` (modo WAL).
     - Árvore de módulos pré-carregados na memória C.
  2. A CLI comum torna-se um despachante leve (Thin Dispatcher) que conversa com o daemon via **Named Pipe no Windows** (`\\.\pipe\doxoade_engine`) ou **Domain Socket no Linux/Termux** (`/tmp/doxoade.sock`).
  3. Se o daemon não estiver ativo, a CLI faz fallback gracioso para o boot tradicional in-process.

---

### PILAR 2: I/O Desacoplado — Async Terminal Engine
* **Diagnóstico Comprovado:** A telemetria acusou que chamadas repetidas a `click/_winconsole.py:WriteConsoleW` e `colorama/win32.py:SetConsoleTextAttribute` chegam a consumir **centenas de hits por comando**, pausando a execução a cada print formatado.
* **Solução:**
  1. Interceptação transparente de `builtins.print` e `click.echo`.
  2. As mensagens são despejadas em um **Ring Buffer SPSC atômico em C** (`hermes_async_log.c`) sem aquisição de GIL.
  3. Uma thread dedicada em C descarrega as mensagens em lote diretamente no buffer de console do Windows, evitando milhares de trocas de contexto (*syscalls*).
  4. Um método `drain()` síncrono garante que relatórios finais e prompts do usuário nunca sejam truncados.

---

### PILAR 3: `alloy_opt` — A Filosofia da Liga Metálica
* **O Paradoxo do Metal Puro:** O Vulcan acusa `Pureza de Metal: 0% - LIXO` quando um arquivo faz chamadas idiomáticas de Python (`Path`, `dict`, `len`, `field`), porque o Cython gera código C amarrado ao GIL.
* **A Visão da Liga Metálica (`Alloy`):** O ouro puro é maleável demais; ferramentas de corte exigem **ligas**. Um módulo do Doxoade não precisa ser 100% C puro para ser extremamente veloz.
* **Pipeline do `alloy_opt`:**
  1. **Refino de Base (Fase Python):**  
     Antes de passar pelo compilador, um transformador AST analisa os nós comuns:
     - Resolve inline de constantes conhecidas.
     - Transforma chamadas repetidas de atributos em acessos locais em cache (`_local_len = len`).
     - Converte dataclasses críticas para slots de acesso fixo (`__slots__`).
  2. **Fusão em Liga (Fase Cython/C):**  
     O código refinado é compilado com diretivas de baixa fricção:
     - `cdivision=True`, `infer_types=True`.
     - Flags de compilação GCC balanceadas (`-O2 -fno-strict-aliasing`).
  3. **Resultado:** O módulo atinge o estado de **Alloy** (Liga): não requer tipagem manual exaustiva em C, elimina os atritos de overhead do Python puro e roda com proteção de memória e integridade garantidas.

---

## 3. Matriz de Contingência (Planos A a C — ProDeNov §1.2.1)

| Plano | Estratégia | Condição de Disparo |
| :--- | :--- | :--- |
| **Plano A (Principal)** | `engine_daemon` ativo via Named Pipe / Socket local + Ring Buffer C para todo o I/O do terminal + pipeline `alloy_opt` nos comandos principais. | Ambiente padrão com permissão de IPC local e compilador detectado. |
| **Plano B (Fallback Sem Daemon)** | Invocação in-process tradicional acelerada pelo cache de disco (`.hcache` / `.pyd`), com Ring Buffer assíncrono interno da mesma thread. | Falha de permissão no Named Pipe, porta ocupada ou execução em container restrito. |
| **Plano C (Degradação Graciosa)** | Modo `--pure`: Bypass completo do daemon, compilação e bridges nativas. Execução 100% Python puro com tratamento de exceções padrão. | Falha catastrófica de binários, arquitetura heterogênea sem suporte C ou flag de emergência. |

---

## 4. Roteiro de Implementação em Sprints (Tasklist Futura)

### Fase 1: Fundação do `engine_daemon`
- [ ] Especificar o protocolo de comunicação binária via Named Pipe (`doxoade_ipc.c`).
- [ ] Criar o comando `doxoade engine daemon start|stop|restart|ping`.
- [ ] Implementar o handshake de cold-start com autenticação local.

### Fase 2: Unificação de I/O de Terminal (Async Output)
- [ ] Generalizar o `hermes_async_log.c` para aceitar buffers Rich e ANSI TrueColor.
- [ ] Substituir o driver de console no `doxcolors.py` para utilizar o Ring Buffer C.
- [ ] Conectar o `click.echo` ao pipeline assíncrono com guardas de auto-flush.

### Fase 3: Forja de Ligas (`alloy_opt`)
- [ ] Implementar o analisador AST `AlloyRefiner` em `doxoade/tools/vulcan/alloy_opt.py`.
- [ ] Criar métrica de "Classificação de Liga" (Bronze, Prata, Ouro) em vez de binarismo "Metal vs Lixo".
- [ ] Validar integração da forja de ligas com os comandos do `intelligence_systems` e `check_systems`.

---

## 5. Critérios de Sucesso (DoD — Definition of Done)

1. **Boot Percebido:** `doxoade --help` e comandos de consulta rápida devem responder em **< 20 ms** quando o daemon estiver residente.
2. **Impacto de Terminal:** O tempo gasto em `WriteConsoleW` na telemetria deve cair em **pelo menos 70%** em saídas densas de terminal.
3. **Classificação Alloy:** Módulos que antes marcavam `0% Pureza` devem atingir ganho mensurável de **1.8× a 3.5×** sem quebrar contratos de dinamismo do Python.

