# 📑 Doxoade Internals - Vol. 20: Inteligência de Recursos e ALB

## 1. Visão Geral (A Singularidade de Performance)
A versão v41.0 "Chief-Gold" marca a transição de um executor estático para um sistema autoconsciente. O objetivo é a **Simbiose com o Hospedeiro**: o Doxoade agora monitora a carga do computador e ajusta sua própria intensidade para não degradar a experiência do usuário.

## 2. Componentes da Tríade de Recursos

### A. ALB (Adaptive Load Balancing) - `governor.py`
O Governador de Recursos atua como o sistema nervoso autônomo do Doxoade.
*   **Modos de Operação:**
    *   **Turbo:** CPU < 110%, RAM < 80%. Execução em potência máxima.
    *   **Eco:** CPU > 110%. Introduz micro-pausas (30ms) para reduzir aquecimento.
    *   **Sobrevivência:** CPU > 180% ou RAM > 85%. Desativa análises AST pesadas (Modo Degradado).
*   **Targeted Bypass:** Scans direcionados (alvo único) ignoram limites ECO para garantir produtividade instantânea.

### B. UFS (Unified File Streamer) - `streamer.py`
O UFS resolve o "Imposto de Chamada de Sistema".
*   **Mecanismo:** Buffer efêmero em RAM.
*   **Regra de Ouro:** "Leia uma vez, use para sempre".
*   **Impacto:** Redução de até 90% no tempo de I/O em projetos massivos, unificando a leitura para Check, Analysis e Filters.

### C. Memory Arena - `memory_pool.py`
Implementação da regra **MPoT-3** (Alocação Controlada).
*   **Conceito:** Pré-alocação de slots para objetos de "finding".
*   **Benefício:** Zera o custo de criação de objetos em loops de scan. O Garbage Collector do Python não é acionado durante a auditoria.

## 3. Persistência Elástica
O `DoxoLogWorker` agora utiliza **Batch Commits** adaptativos. Se o `governor` detecta pressão de disco, os logs são retidos na fila (RAM) e gravados em blocos de 50 itens apenas quando o I/O silencia.