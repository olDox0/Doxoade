# Doxoade Internals - Vol. 14: Ajuste de Performance e Gargalos

## 1. Identificando Lentidão em Treinos de IA
Se o tempo por época aumenta progressivamente (como visto no Alfagold v19), o problema raramente é CPU.
- **Causa provável:** Você está guardando o histórico de perdas (Loss) em uma lista sem converter para `.item()` ou float puro, mantendo o grafo de computação do NumPy/AI na memória.
- **Como confirmar:** `doxoade telemetry -v`. Se o "Memory Peak" cresce a cada medição, é um vazamento.

## 2. Padrão de Profiling de Alvo
O Doxoade v69.5 agora filtra o "Efeito Observador". O `CodeSampler` ignora a própria infraestrutura para garantir que 100% da atenção do profiler esteja no `script_alvo.py`.