
---

# ⚡ BLITZPLAN: OTIMIZAÇÃO, ZERO-DELAY E TELEMETRIA LAN-GIT

## 1. Necropsia dos Gargalos Atuais (Por que há delay?)

Analisando o log e a telemetria, encontramos os 3 fatores que geram latência e overhead:

1. **O Modelo de Polling Cego (Delay de ~2500ms):**
   * A cada 2,5 segundos, cada máquina faz um `GET /api/notepad`. Se o usuário digita algo, a outra máquina leva até 2,5s para ver o texto.
2. **I/O de Disco Redundante (Disco vs RAM):**
   * A cada requisição `GET`, o Python executa `open("shared_notes.md", "r")`. Com dois dispositivos ativos, são dezenas de leituras em disco por minuto de um arquivo que muitas vezes nem mudou.
3. **Busy-Wait no CLI (5.219 hits de `time.sleep(1)`):**
   * O loop principal do servidor em `cli_lan_git.py:224` gasta ciclos de clock acordando a cada 1 segundo em vez de aguardar um `threading.Event()`.

---

## 2. Solução de Baixa Latência (Reduzindo o Delay de 2500ms para < 5ms)

### Plano A: Server-Sent Events (SSE / Push em Tempo Real) — Recomendado
* **Como funciona:** O navegador abre uma conexão contínua `GET /api/notepad/stream` com cabeçalho `text/event-stream`.
* **Zero bibliotecas externas:** 100% suportado nativamente pelo Python (`http.server`) e pelo JavaScript do navegador (`new EventSource('/api/notepad/stream')`).
* **Resultado:** Quando Amaranth der `POST`, o servidor imediatamente avisa o Bluebaby via stream. O texto aparece no outro computador em **menos de 5 milissegundos**, sem polling e sem consumir CPU.

### Plano B: Cache em Memória com Revisão Numérica (Fallback)
* Se usarmos polling, o servidor mantém em memória:
  * `_notepad_revision: int`
  * `_notepad_cache: str`
* O cliente pede: `GET /api/notepad?rev=42`. Se a versão ainda for 42, o servidor responde `304 Not Modified` em 0.2ms **sem tocar no disco**.

---

## 3. Arquitetura do Sistema de Telemetria LAN-Git (Web & Rede)

O novo subsistema de medição deve responder às perguntas fundamentais do ProDeNov:
* **O quê?** Métricas de pacotes, requisições HTTP, latência e transferências Git.
* **Quem?** Dispositivos identificados (`192.168.18.52 [Amaranth]`, `192.168.18.91 [Bluebaby]`).
* **Quanto?** 
  * RTT (Round Trip Time / Latência por rota em milissegundos).
  * Throughput (KB/s de streaming Git, downloads de ZIP/FastPack).
  * Cache Hit Ratio (% de requisições atendidas em RAM vs Disco).
* **Segurança:** Mapa de tentativas incorretas e IPs bloqueados em tempo real.

### Estrutura do Novo Módulo: `doxoade/commands/lan_git/telemetry_lan_git/`

```text
doxoade/commands/lan_git/
├── telemetry_lan_git/
│   ├── __init__.py
│   ├── network_metrics.py     # Coletor em anel circular (RTT, latências P50/P99, bytes in/out)
│   ├── peer_radar.py          # Rastreador de peers ativos e dispositivos na LAN
│   └── terminal_dashboard.py  # Mini-dashboard CLI em tempo real (estilo 'top' / 'htop' de rede)
```

---

## 4. Roteiro de Execução (Ritual ProDeNov)

| Etapa | Foco | Ação Técnica |
| :---: | :--- | :--- |
| **Capítulo 1** | **Eliminar o Delay** | Implementar Push em Tempo Real (SSE) no `portal_server_lan_git.py` e cache em RAM com persistência assíncrona. |
| **Capítulo 2** | **Coletor de Métricas de Rede** | Criar o `network_metrics.py` para medir RTT (ms), requisições/segundo e vazão sem impactar o processamento. |
| **Capítulo 3** | **Painel de Telemetria LAN** | Criar o comando `doxoade lan-git telemetry` (ou `doxoade lan-git top`) para visualização forense em tempo real. |

Podemos iniciar pelo **Capítulo 1** (trocar o polling pelo SSE para transformar a sincronização em tempo real instantâneo) ou prefere começar concebendo o **coletor de métricas (Capítulo 2)** para já medirmos o ganho antes e depois?

---

Em rigorosa conformidade com o **Protocolo ProDeNov** (seções **1.0 a 1.4**, **2.0 a 2.1**, **3.1** e **5.6**), estruturamos o **Plano de Preparação do Capítulo 1**.

Antes de tocar em qualquer linha de código, definimos a arquitetura, os limites de complexidade, as salvaguardas (Planos A, B e C) e a matriz W5 para validação prévia.

---

# 📜 PRODENOV :: CAPÍTULO 1 — ESPECIFICAÇÃO & PREPARAÇÃO
**Meta:** Latência Quase-Zero (< 20ms) e Eliminação de I/O Redundante no Bloco de Notas LAN.

---

## 1. Avaliação de Complexidade (Item 0 do ProDeNov)
* **0.0 Thirdparty:** Zero dependências externas (stdlib pura: `http.server`, `threading`, `queue`, `EventSource` nativo do navegador).
* **0.1 Devflow:** Sem interrupções de fluxo; transição suave e retrocompatível com a API existente (`/api/notepad`).
* **0.2 Rabbit Hole:** Baixo risco. SSE (*Server-Sent Events*) é uma especificação simples sobre HTTP 1.1 em texto plano (`text/event-stream`).
* **0.3 Sensibilidade:** Alta sensibilidade a concorrência (múltiplas abas conectadas no stream SSE exigem `threading.Lock` ou filas desacopladas para não travar o socket principal).
* **0.4 Revisitar:** Desenhar a persistência desacoplada para não precisarmos refazer o modelo de I/O no futuro.

---

## 2. Matriz de Diagnóstico e Engenharia W5 (Item 3.1.4)

| Eixo | Especificação Forense |
| :--- | :--- |
| **O quê?** | Substituir o polling periódico de 2500ms por um barramento reativo de eventos SSE (`/api/notepad/events`) + Cache em RAM com persistência assíncrona. |
| **Onde?** | `portal_server_lan_git.py`, `ui_templates_lan_git.py` e loop principal de `cli_lan_git.py`. |
| **Quem?** | Host Amaranth (`192.168.18.52`) transmitindo eventos de escrita para Bluebaby (`192.168.18.91`) e demais clientes. |
| **Quando?** | Disparado imediatamente quando um cliente finaliza um debounce de digitação (emissão imediata em < 5ms). |
| **Quanto?** | **Latência:** queda de ~2500ms para < 20ms.<br>**I/O em disco:** redução de 98% das leituras (leitura única no boot; leituras subsequentes 100% em RAM).<br>**Ciclos de CPU no Host:** eliminação de 5.200+ voltas de loop desnecessárias. |
| **Por quê?** | O modelo de polling cego (`setInterval 2500ms`) força leituras constantes no disco e introduz um atraso perceptível que prejudica a experiência de colaboração. |
| **Origem?** | Implementação preliminar síncrona com I/O direto em disco. |
| **Consequências?** | Sincronização em tempo real de nível industrial (estilo editor moderno), com consumo de rede e CPU praticamente nulo em repouso. |

---

## 3. Matriz de Contingência e Segurança (Planos A, B e C)

### 🟢 Plano A (Principal — Push Server-Sent Events)
* O cliente abre uma conexão persistente via `new EventSource('/api/notepad/events')`.
* O servidor mantém uma lista de ouvintes (`listeners`) em memória protegida por um `threading.Lock`.
* Quando ocorre um `POST /api/notepad`:
  1. O texto é atualizado na RAM (`_cached_content`).
  2. O servidor itera pelos ouvintes e envia um pacote leve: `data: {"text": "...", "rev": 42}\n\n`.
  3. O texto é persistido em segundo plano no arquivo `shared_notes.md`.
* **Vantagem:** Latência quase nula (~3ms em Wi-Fi), zero polling.

### 🟡 Plano B (Fallback Automático — Polling Baseado em ETag/Revisão)
* Caso o navegador do cliente não suporte SSE ou haja proxies/firewalls que cortem streams HTTP persistentes:
* O JavaScript detecta o evento `onerror` do `EventSource` e faz fallback transparente para polling inteligente:
  * `GET /api/notepad?rev=42`
* Se a revisão na memória for igual, o servidor responde `304 Not Modified` em 0.3ms (sem ler disco e sem trafegar o corpo do texto).

### 🔴 Plano C (Resiliência Extrema — LocalStorage & Buffer Offline)
* Se a conexão Wi-Fi cair por completo durante a digitação:
* O navegador armazena o rascunho no `localStorage` do navegador com badge amarelo: `⚠ Modo Offline (Rascunho salvo no navegador)`.
* Assim que a conexão for restabelecida, o cliente faz o reenvio automático sem perda de dados.

---

## 4. Estrutura dos Módulos e Limite de 50KB (Item 2.1)

Vamos manter tudo modular e bem abaixo do limite de 50KB por arquivo:

1. **`portal_server_lan_git.py`** (~18KB):
   * Introdução da classe desacoplada `NotepadBroadcaster`:
     * Gerencia a lista de conexões ativas.
     * Mantém `_content` e `_revision` em RAM.
     * Grava assincronamente no `shared_notes.md`.
   * Adição da rota `GET /api/notepad/events` (SSE streaming).

2. **`ui_templates_lan_git.py`** (~14KB):
   * Conexão nativa `EventSource` com reconexão resiliente.
   * Interceptação da tecla `Tab` e suporte ao `localStorage` (Plano C).
   * Indicador dinâmico de latência: `⚡ Sincronizado em tempo real (SSE Ativo)`.

3. **`cli_lan_git.py`** (~16KB):
   * Substituição do `while True: time.sleep(1)` por um `threading.Event().wait()` cancelável por `Ctrl+C`.

---

## 5. Checklist de Verificação (DoD - Definition of Done)

- [ ] O `shared_notes.md` é carregado na RAM no início e atualizado sem travar requisições de leitura.
- [ ] O SSE conecta e mantém o socket aberto sem causar vazamento de conexões (*connection leak*).
- [ ] Ao digitar no Amaranth, o texto reflete no Bluebaby em menos de 50 milissegundos comprovados.
- [ ] Se o SSE for desligado forçadamente, o Plano B (Revisão 304) assume sem quebrar a UI.
- [ ] O arquivo `shared_notes.md` no disco permanece idêntico ao estado da RAM.
- [ ] Execução de `doxoade telemetry` para atestar a redução drástica de *Hot Lines*.

---

Esta é a estrutura de preparação do **Capítulo 1**. 
Aprovando este escopo do ProDeNov, iniciamos imediatamente a implementação passo a passo!
