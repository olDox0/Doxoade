# 📋 BLITZPLAN — Integração do Shadow Profiling & Chrono-Matrix no Ecossistema Doxoade

**Documento:** `doxoade/docs/Protocols/Blitzplan_Shadow_Telemetry_v1.md`  
**Conformidade:** `ProDeNov.md` (Itens 1.0 a 1.4, 2.1, 5.6 e 6.1)  
**Subsistemas:** `Horus` (Observabilidade) / `Apolo` (UI/UX) / `Hades` (Persistência) / `Zeus` (CLI)  
**Data:** 25/09/2026 — 03:57 AM BRT  

---

## 1. Requisição & Diagnóstico Forense (W5H — ProDeNov §1.1)

| Pergunta | Definição do Projeto |
| :--- | :--- |
| **O quê? (What)** | Promover o protótipo de **Shadow Timeline Profiler** validado em `consult` para o núcleo do Doxoade, integrando-o ao pacote recém-estruturado `telemetry_systems` e viabilizando inspeção temporal para qualquer comando do sistema. |
| **Onde? (Where)** | `doxoade/commands/telemetry_systems/` (como motor central `shadow_matrix.py`), com pontes em `doxoade/cli.py` e no comando `telemetry`. |
| **Quem? (Who)** | Subsistemas **Horus** (amostragem multi-thread 200Hz), **Apolo** (densidade visual CP437 `░▒▓█`), e **Hades** (armazenamento NSR em `.doxoade/shadow_profiling/`). |
| **Quando? (When)** | Disparado sob demanda com a flag global `--shadow-prof` / `-P` em qualquer comando, ou inspecionado retroativamente com `doxoade telemetry --matrix`. |
| **Quanto? (Cost/Impact)** | ~5ms de intervalo de tick; <0.8% de overhead de CPU durante o tracking; retenção circular de dumps para não acumular mais de 10MB no disco. |
| **Por quê? (Why)** | O Doxoade cresceu e 87.9% da memória é consumida no boot de subsistemas legados. É indispensável quantificar **onde e quando** ocorre a retenção de memória e a saturação de I/O para orientar o *Lazy Loading* e o particionamento de processos. |
| **Consequências?** | Capacidade de engenharia de ponta: decisões de arquitetura e refatoração passam a ser embasadas em métricas temporais reais (CPU Normalizado, Memória Tripartite e Throughput de I/O de Disco em KB/s). |

---

## 2. Matriz de Contingência (Planos A, B e C — ProDeNov §1.2.1)

* **Plano A (Principal — Adotado):**
  * Centralizar o motor em `doxoade/commands/telemetry_systems/shadow_matrix.py`.
  * Atualizar o `telemetry.py` para ler os arquivos `.json` de `.doxoade/shadow_profiling/` quando invocado com `--matrix` ou `--timeline`.
  * Criar o comando orquestrador `doxoade profile <comando> [args]` (ex: `doxoade profile check`, `doxoade profile consult index`), que executa o comando filho encapsulado no profiler sem poluir a sintaxe dos módulos individuais.
* **Plano B (Intermediário — Fallback):**
  * Caso subprocessos ou comandos que utilizam `sys.exit()` impeçam a coleta final no mesmo processo, o `ShadowProfiler` captura o encerramento via `atexit` / `sys.unraisablehook` e força o flush do dump antes da terminação do interpretador.
* **Plano C (Degradação Graciosa):**
  * Se o ambiente de execução não possuir a biblioteca `psutil` instalada (ex.: em containers mínimos ou Android/Termux puro), o profiler degrada suavemente para medições internas via `tracemalloc`, `os.times()` e `time.perf_counter()`, mantendo o HUD funcional sem quebrar o CLI.

---

## 3. Arquitetura dos Arquivos & Limites (ProDeNov §2.1)

```
doxoade/commands/telemetry_systems/
├── __init__.py               # Manifesto do pacote
├── telemetry.py              # CLI do comando 'telemetry' (suporte a --matrix/--timeline)
├── telemetry_io.py           # Renderizador legado e visualizador do histórico DB
├── telemetry_utils.py        # Agregadores analíticos e cálculo de gargalos
├── shadow_matrix.py          # 🆕 O Motor Central: 200Hz Multi-thread, CP437, RAM Tripartite, I/O KB/s
└── cmd_profile.py            # 🆕 Comando Zeus 'doxoade profile <cmd>'
```

*Todos os arquivos respeitam o limite de 50KB por módulo, utilizam caminhos relativos no cabeçalho e importação segura de bibliotecas.*

---

## 4. Tasklist de Implementação & Checklist de Regressão (ProDeNov §1.2 e §1.3)

### Fase 1: Fundação do Módulo
- [ ] **T1.1:** Criar `doxoade/commands/telemetry_systems/shadow_matrix.py` (migração e aprimoramento do laboratório `consult`).
- [ ] **T1.2:** Implementar política de retenção / expurgo circular (manter no máximo os últimos 20 dumps para proteger o disco).
- [ ] **T1.3:** Criar `doxoade/commands/telemetry_systems/__init__.py` exportando `ShadowProfiler` e `telemetry`.

### Fase 2: Roteamento CLI & Orquestração
- [ ] **T2.1:** Criar `doxoade/commands/telemetry_systems/cmd_profile.py` (`doxoade profile`).
- [ ] **T2.2:** Adicionar opções `--matrix` e `--timeline` ao comando `doxoade telemetry`.
- [ ] **T2.3:** Registrar o comando `profile` no `_lazy_map` do `doxoade/cli.py`.

### Fase 3: Checklist de Teste e Anti-Regressão
- [ ] **C3.1:** Executar `doxoade panel --fast` (Garantir 0 erros de sintaxe ou imports).
- [ ] **C3.2:** Testar comando encapsulado: `doxoade profile consult search --deep asyncio`.
- [ ] **C3.3:** Testar comando nativo pesado: `doxoade profile check`.
- [ ] **C3.4:** Testar visualização retroativa: `doxoade telemetry --matrix`.
- [ ] **C3.5:** Validar exibição e integridade dos blocos CP437 no terminal sem falha de decodificação.

---

Se o plano estiver aprovado, daremos início imediato à **Fase 1**.
