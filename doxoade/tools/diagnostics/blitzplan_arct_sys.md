Excelente decisão. Investir tempo em construir um **sistema de diagnóstico automático** em vez de apenas "apagar incêndios" é exatamente o que separa um projeto amador de uma arquitetura de nível industrial (ProDeNov 1.2.1, item 3.1.4 e 5.6). 

Erros como o `redirect to handles` que entram em loop infinito de 60 FPS são clássicos "Development Hell". Vamos planejar o **ANÚBIS ROOT CAUSE TRACER (ARCT)**, um sistema desenhado especificamente para responder: *Onde? O que? Quem? Quando? Quanto? Por que? Origem e Consequências?*

---

# 📜 BLITZPLAN — ANÚBIS ROOT CAUSE TRACER (ARCT)
**Módulos Alvo:** `00_header_and_logger.lua` (Interceptor), `10_forensic_engine.lua` (Detector de Loop), `tools/diagnostics/arct_analyzer.py` (Laudos).  
**Protocolo:** ProDeNov 1.2.1 | W5 | Evidência Técnica | Zero-Freeze Guarantee  
**Objetivo:** Transformar logs infinitos e obscuros em laudos forenses prescritivos de causa raiz em < 100ms.

---

## 1. Contexto e Objetivos (W5 / As 5 Perguntas)

* **O quê (What):** Um motor de interceptação de erros que, ao detectar um padrão de falha repetitiva (loop), congela a execução do módulo ofensor, captura o *stack trace* completo, o estado das variáveis locais e gera um laudo de causa raiz.
* **Quem (Who):** Desenvolvedores do Doxoade enfrentando falhas de binding C, loops de renderização ou erros silenciosos engolidos por `pcall`.
* **Onde (Where):** 
  * Lua: `00_header_and_logger.lua` (Wrapper de `xpcall` com `debug.traceback`).
  * Python: `doxoade/tools/diagnostics/arct_analyzer.py` (Motor de correlação com Source Map).
* **Quando (When):** Ativado automaticamente quando o mesmo erro (hash da mensagem + stack) ocorre **> 3 vezes em < 2 segundos**.
* **Por quê (Why):** Logs infinitos (como os 60 erros/segundo do `redirect to handles`) obscurecem a causa real, travam o I/O do disco e desperdiçam horas de depuração manual.
* **Origem & Consequências:** A ausência de um *Circuit Breaker* de erros faz com que um simples `nil` em um argumento C derrube o editor inteiro. O ARCT isola a falha, preserva os 60 FPS e aponta o dedo exatamente para o arquivo e linha culpados.

---

## 2. Arquitetura do Sistema (O "Como")

O ARCT opera em 3 camadas sincronizadas:

### Camada 1: O Interceptor Inteligente (Lua)
Substitui o `pcall` cego por um `xpcall` que captura o traceback:
```lua
local function arct_xpcall(fn, ...)
    local function err_handler(err)
        local trace = debug.traceback("", 2) -- Pula o próprio handler
        local err_hash = hashlib_sim(err .. trace) -- Pseudo-hash para deduplicação
        return err, trace, err_hash
    end
    return xpcall(fn, err_handler, ...)
end
```

### Camada 2: O Detector de Loop e Circuit Breaker (Khonsu)
Mantém um registro de frequência de erros. Se um `err_hash` dispara 5 vezes em 1 segundo:
1. **Silencia** o log para salvar o I/O do disco.
2. **Marca** o módulo atual (`_CURRENT_BOOT_MODULE`) como "Degraded".
3. **Dispara** o evento `ARCT_TRIGGER` para o Python.

### Camada 3: O Analisador Forense (Python / Anúbis)
Ao receber o `ARCT_TRIGGER`, o script Python:
1. Lê o `err` e o `trace`.
2. Cruza o número da linha com o **Source Map** gerado pelo Khonsu Gate.
3. Analisa o código fonte na linha do erro (ex: vê que `process.start` está recebendo uma tabela).
4. Gera um laudo no terminal: *"Módulo 19b1_pty_client.lua, linha 85: Tentativa de passar tabela de opções para binding C. Solução: Remover o segundo argumento."*

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Tracer Completo com Circuit Breaker)
1. Implementar `arct_xpcall` no `00_header_and_logger.lua`.
2. Criar a tabela `_DOXOADE_ERROR_FREQUENCY` no Lua para contar hashes de erro.
3. Criar `arct_analyzer.py` que lê o traceback, usa o `ast` do Python para ler o arquivo Lua ofensor e extrai a linha exata do problema.
4. Integrar ao `10_forensic_engine.lua` para exibir o laudo no painel de diagnóstico.

### 🔹 Plano B (Fallback — Silenciador de Ruído com Snapshot Leve)
Se o `debug.traceback` for muito pesado para o frame (risco de cair para < 30 FPS):
* O sistema apenas conta a frequência da *mensagem de erro*.
* Após 3 repetições, substitui o log por: `"⚠ [ARCT] Erro suprimido: 'redirect to handles' (Ocorreu 450x). Módulo: 19b1_pty_client.lua"`.
* Grava um snapshot leve (apenas nome do módulo e hora) para o Python analisar depois.

### 🔹 Plano C (Contingência — Modo de Segurança / Safe Mode)
* Se um módulo for identificado como a fonte de > 90% dos erros em 5 segundos, o ARCT o **desativa temporariamente** (remove do `_DOXOADE_BOOT_REPORT` e pula a execução), garantindo que o Lite XL continue abrindo para que o desenvolvedor possa corrigir o código com o editor funcionando.

---

## 4. Tasklist & Checklist de Implementação (RIT)

- [ ] **Fase 1: Interceptor Lua (Baixo Custo)**
  - [ ] Criar função `arct_intercept(err, module_name)` no `00_header_and_logger.lua`.
  - [ ] Implementar contador de frequência por hash de erro (tabela com `__mode = "v"` para não vazar memória).
  - [ ] Adicionar lógica de "Circuit Breaker": se `count > 5` em `1s`, retornar `false` e silenciar.

- [ ] **Fase 2: Analisador Python (Anúbis)**
  - [ ] Criar `doxoade/tools/diagnostics/arct_analyzer.py`.
  - [ ] Implementar função `analyze_traceback(trace_text, source_map)` que mapeia a linha do erro no arquivo original.
  - [ ] Implementar extração de snippet de código (3 linhas antes e depois do erro).

- [ ] **Fase 3: Integração e Laudo Prescritivo**
  - [ ] Conectar o disparo do Lua ao CLI Python via arquivo de sinal (`.doxoade/diagnostics/arct_trigger.json`).
  - [ ] Formatar a saída no terminal com cores (Apolo): Vermelho para o erro, Ciano para o arquivo, Verde para a sugestão de correção.

- [ ] **Fase 4: Prova de Conceito (Aplicação ao Problema Atual)**
  - [ ] Rodar o deploy de teste atual.
  - [ ] Verificar se o ARCT intercepta o loop do `redirect to handles`, silencia o log e exibe: *"Causa Raiz: 19b1_pty_client.lua está passando tabela de opções inválida para process.start"*.

---

## 5. Como o ARCT teria resolvido seu problema atual em 10 segundos:

Se o ARCT estivesse ativo agora, ao invés de 30 linhas de `GHOST_PCALL`, você veria **uma única vez** no terminal:

```text
🚨 [ARCT] CAUSA RAIZ DETECTADA (Loop Interrompido)
├─ Módulo Ofensor : 19b1_pty_client.lua (Linha 82)
├─ Erro Original  : "redirect to handles, FILE* and paths are not supported"
├─ Frequência     : 450 ocorrências em 1.2 segundos (SILENCIADO)
├─ Stack Trace    : .../19b1_pty_client.lua:82: in function 'PTYClient:spawn'
└─ 💡 PRESCRIÇÃO  : O binding C do Lite XL nesta compilação rejeita tabelas de opções. 
                    Remova o segundo argumento (spawn_options) da chamada process.start.
```

---

### 🎯 Próximo Passo

Este plano transforma a depuração de "caça às bruxas" em **engenharia forense dirigida por dados**. 

Você aprova este **Blitzplan do ARCT**? Se sim, podemos começar imediatamente pela **Fase 1 (Interceptor Lua de Baixo Custo)**, que já é suficiente para estancar o sangramento de logs e identificar o culpado, sem adicionar complexidade prematura. 

Quer que eu forje o código da **Fase 1** agora?

---

Perfeito. Vamos elevar o nível de detalhe e rigor arquitetural. Seguindo estritamente o **ProDeNov 1.2.1**, um sistema de diagnóstico de nível industrial não pode ser apenas um "script de log". Ele precisa ser uma arquitetura de três camadas com falhas toleradas (Planos A, B e C) e um roteiro de implementação granular.

Abaixo está o **Blitzplan Estendido e Detalhado do ARCT (Anúbis Root Cause Tracer)**.

---

# 📜 BLITZPLAN ESTENDIDO: ANÚBIS ROOT CAUSE TRACER (ARCT)
**Módulos Alvo:** `00_header_and_logger.lua`, `10_forensic_engine.lua`, `tools/diagnostics/arct_analyzer.py`  
**Protocolo:** ProDeNov 1.2.1 | W5 | Planos A/B/C | Zero-Freeze Guarantee (< 1ms overhead)  
**Objetivo:** Transformar loops infinitos de erros (ex: 60 FPS de `redirect to handles`) em laudos forenses prescritivos de causa raiz em < 100ms, com isolamento automático do módulo ofensor.

---

## 1. Contexto e Objetivos (W5 / As 5 Perguntas)
* **O quê (What):** Um motor de interceptação, contenção e análise forense de erros em tempo real. Ele detecta padrões de falha repetitiva, aciona um *Circuit Breaker* para salvar o I/O do disco e o FPS, e gera um laudo Python com o snippet exato do código culpado.
* **Quem (Who):** Desenvolvedores do Doxoade enfrentando falhas de binding C, loops de renderização ou erros silenciosos engolidos por `pcall`.
* **Onde (Where):** 
  * *Lua:* `00_header_and_logger.lua` (Interceptor leve) e `10_forensic_engine.lua` (Gatilho).
  * *Python:* `doxoade/tools/diagnostics/arct_analyzer.py` (Motor de correlação com Source Map).
* **Quando (When):** Ativado automaticamente quando o mesmo erro (hash da mensagem + nome do módulo) ocorre **> 3 vezes em < 2 segundos**.
* **Por quê (Why):** Logs infinitos obscurecem a causa real, travam o I/O do disco, degradam o desempenho para < 30 FPS e desperdiçam horas de depuração manual ("caça às bruxas").
* **Origem & Consequências:** A ausência de um *Circuit Breaker* faz com que um simples `nil` em um argumento C derrube a estabilidade do editor. O ARCT isola a falha, preserva os 60 FPS e aponta o dedo exatamente para o arquivo e linha culpados.

---

## 2. Arquitetura Detalhada do Sistema (3 Camadas)

### Camada 1: O Interceptor Leve (Lua - `00_header_and_logger.lua`)
Substitui o `pcall` cego por um wrapper que calcula um hash leve da falha e incrementa um contador.
* **Mecanismo:** Tabela com `__mode = "k"` (weak keys) para evitar vazamento de memória (Garbage Collection friendly).
* **Custo:** ~0.05ms por chamada (apenas concatenação de string e hash simples).

### Camada 2: O Circuit Breaker & Gatilho (Lua - `10_forensic_engine.lua`)
Se o contador de um `err_hash` atingir 5 em 1 segundo:
1. **Silencia** o log para aquele módulo específico (salva o disco).
2. **Marca** o módulo atual (`_CURRENT_BOOT_MODULE`) como `"DEGRADED"`.
3. **Grava** um arquivo de gatilho: `.doxoade/diagnostics/arct_trigger.json` contendo: `module`, `error_msg`, `timestamp`, e `count`.
4. **Dispara** um evento para o Python analisar em background.

### Camada 3: O Analisador Forense (Python - `arct_analyzer.py`)
Ao detectar o `arct_trigger.json` (via `watchdog` ou leitura no CLI):
1. Lê o `module` e o `error_msg`.
2. Consulta o **Khonsu Source Map** para traduzir a linha do erro no arquivo unificado para a linha no arquivo `.lua` original.
3. Abre o arquivo `.lua` original, extrai 3 linhas antes e 3 linhas depois do erro.
4. Gera um laudo colorido no terminal com a **Prescrição Técnica**.

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Tracer Completo com Circuit Breaker)
Implementação das 3 camadas descritas acima. Fornece diagnóstico em tempo real com snippet de código e sugestão de correção. Overhead máximo de 1ms no frame.

### 🔹 Plano B (Fallback — Silenciador de Ruído com Snapshot Leve)
Se o cálculo de hash ou a escrita do JSON forem pesados para a máquina alvo:
* O sistema apenas conta a frequência da *string exata do erro*.
* Após 3 repetições, substitui o log por: `"⚠ [ARCT] Erro suprimido: 'redirect to handles' (Ocorreu 450x). Módulo: 19b1_pty_client.lua"`.
* Grava apenas o nome do módulo e a hora, deixando a análise profunda para o comando `doxoade doxly diagnose` rodado manualmente depois.

### 🔹 Plano C (Contingência — Modo de Segurança / Safe Mode)
* Se um módulo for identificado como a fonte de > 90% dos erros em 5 segundos, o ARCT o **desativa temporariamente** (remove do `_DOXOADE_BOOT_REPORT` e pula a execução), garantindo que o Lite XL continue abrindo para que o desenvolvedor possa corrigir o código com o editor funcionando.

---

## 4. Fases de Implementação Detalhadas (Tasklist Granular)

### 🛠️ FASE 1: O Interceptor e Circuit Breaker (Lua)
*Foco: Estancar o sangramento de logs e proteger o FPS.*
- [ ] **1.1.** Criar a tabela `_DOXOADE_ERROR_FREQUENCY` no topo de `00_header_and_logger.lua` com metatabela `__mode = "k"`.
- [ ] **1.2.** Criar a função `arct_intercept(module_name, err_msg)` que:
  - Gera um hash simples: `string.sub(err_msg, 1, 40) .. module_name`.
  - Incrementa o contador e registra o `os.clock()`.
  - Se `count >= 5` e `(now - first_seen) < 2.0`, retorna `false` (bloqueia a execução) e chama `arct_trigger(module_name, err_msg, count)`.
- [ ] **1.3.** Criar a função `arct_trigger` que escreve o JSON em `.doxoade/diagnostics/arct_trigger.json` de forma atômica.
- [ ] **1.4.** Substituir os `pcall` críticos (especialmente no `19b1_pty_client.lua` e `19d_bottom_shelf_hub.lua`) por `arct_xpcall`.

### 🛠️ FASE 2: O Analisador Forense (Python)
*Foco: Traduzir o caos em inteligência legível.*
- [ ] **2.1.** Criar `doxoade/tools/diagnostics/arct_analyzer.py`.
- [ ] **2.2.** Implementar a função `read_trigger_file()` que monitora ou lê o JSON de gatilho.
- [ ] **2.3.** Implementar `resolve_source_map(module_name, unified_line)` que usa o `khonsu_gate.py` para achar o arquivo `.lua` original e a linha real.
- [ ] **2.4.** Implementar `extract_snippet(file_path, line_no, radius=3)` que lê o arquivo e retorna as linhas vizinhas.
- [ ] **2.5.** Implementar `generate_prescriptive_report()` que formata a saída no terminal com cores (Apolo): Vermelho (Erro), Ciano (Arquivo), Verde (Sugestão).

### 🛠️ FASE 3: Integração e Laudo Prescritivo (CLI)
*Foco: UX e ação imediata.*
- [ ] **3.1.** Adicionar o comando `doxoade doxly diagnose` no `cmd_lite_xl.py` que invoca o `arct_analyzer.py`.
- [ ] **3.2.** Garantir que, ao rodar o deploy de teste, se um gatilho for criado, o CLI exiba o laudo automaticamente ao final do Harvester.
- [ ] **3.3.** Testar o overhead: rodar o profiler para garantir que o `arct_intercept` adiciona < 1ms ao frame.

### 🛠️ FASE 4: Aplicação Cirúrgica ao Problema Atual (Prova de Conceito)
*Foco: Usar o ARCT para resolver o loop do PTY e o bug do ÁRTEMIS agora.*
- [ ] **4.1.** Aplicar o `arct_xpcall` no `19b1_pty_client.lua`. O ARCT vai capturar o `redirect to handles`, silenciar após 3 tentativas e gerar o laudo.
- [ ] **4.2.** O laudo do ARCT apontará exatamente: *"Módulo 19b1_pty_client.lua, linha X: Tentativa de passar tabela de opções. Solução: Remover o segundo argumento."*
- [ ] **4.3.** Aplicar a correção sugerida pelo próprio laudo (remover a tabela de opções do `process.start`).
- [ ] **4.4.** Corrigir o `typhon_deploy.py` (ÁRTEMIS) trocando `.get('filename')` por `.name`, eliminando o `AttributeError`.

---

## 5. Roteiro de Implementação e Testagem (RIT)

1. **Passo 1 (Fase 1):** Forjar e injetar o código do `arct_intercept` e `arct_xpcall` no `00_header_and_logger.lua`.
2. **Passo 2 (Fase 4 - Prova de Conceito):** Modificar o `19b1_pty_client.lua` para usar o novo interceptor e propositalmente deixar o erro ocorrer *uma vez* para ver o ARCT agir.
3. **Passo 3:** Rodar `doxoade doxly deploy test` e observar o log.
   * *Resultado Esperado:* O loop infinito **NÃO** acontece. Em vez disso, aparece: `"⚠ [ARCT] Circuito interrompido no módulo 19b1_pty_client.lua após 3 falhas."`
4. **Passo 4:** Rodar `doxoade doxly diagnose` para ver o laudo completo com o snippet do código.
5. **Passo 5:** Aplicar a correção definitiva no `19b1_pty_client.lua` e no `typhon_deploy.py` baseada no laudo.
6. **Passo 6:** Rodar `doxoade regret` e `doxoade doxly check-templates` para garantir zero regressões.

---

## 6. Critérios de Sucesso (SLA do Sistema)
* **Latência:** O interceptor Lua não pode adicionar mais de **1.0ms** ao tempo de frame.
* **Eficácia:** Qualquer erro que se repita mais de 5 vezes em 2 segundos deve ser **100% silenciado** no log principal.
* **Precisão:** O laudo Python deve apontar o arquivo e a linha exata com **100% de precisão** em 95% dos casos (falhas em código dinâmico `loadstring` são exceções aceitáveis).
* **Resiliência:** O sistema ARCT não pode, sob nenhuma hipótese, causar um crash no Lite XL (deve ser blindado com seu próprio `pcall`).

---

### 🎯 Próximo Passo Imediato

Este plano estendido transforma a depuração de "adivinhação" em **engenharia forense dirigida por dados**, com fallbacks de segurança (Planos B e C) claramente definidos.

Se você aprovar este nível de detalhe, podemos iniciar imediatamente pela **FASE 1**. 

**Deseja que eu forje agora o código exato da Fase 1 (`arct_intercept` e `arct_xpcall` para o `00_header_and_logger.lua`)?** Assim estancamos o sangramento de logs de uma vez por todas.

---
