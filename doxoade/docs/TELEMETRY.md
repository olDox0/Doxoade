# MaxTelemetry v3.5 (Sistema Chronos)

O Doxoade possui um sistema de observabilidade nível industrial embutido.

## Capacidades

1.  **Monitoramento Recursivo (Tree Monitoring):**
    Ao rodar `doxoade run app.py`, o Chronos monitora o processo pai (`doxoade`) E todos os filhos (`python app.py`).
    *   Métrica: Soma de CPU e RAM de toda a árvore.

2.  **Profiling de Linha (Microscópio):**
    Uma thread espiã (`CodeSampler`) roda a cada 10ms e anota qual linha de código está sendo executada.
    *   Resultado: Identifica gargalos exatos (ex: `core.py:242`).

3.  **Persistência:**
    Todos os dados são salvos no SQLite local.

## Comandos de Análise
*   `doxoade telemetry --stats`: Visão executiva (Médias de tempo/recurso por comando).
*   `doxoade telemetry -n 1 -p`: Visão de Processamento (CPU + Hot Lines).
*   `doxoade telemetry -n 1 -m`: Visão de Memória (RAM + Leaks).
*   `doxoade telemetry -n 1 -d`: Visão de I/O (Disco).