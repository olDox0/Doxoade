# Nexus Diagnostic Standard (NDS-01)

## 1. Integridade de Dados
- **SQLite:** Deve ser verificado via `PRAGMA integrity_check`.
- **Vocab Binary:** Deve ser múltiplo de 40 bytes. Se não for, o índice é considerado inválido e deve ser re-indexado.

## 2. Logs de Crash (Lazarus)
- Todos os crashes devem ser persistidos em `.doxoade/crash_logs/`.
- O log deve conter o `argv` para permitir a reprodução do erro.

## 3. Monitoramento WellPro
- Se o processo consumir mais de 1GB de RAM, o pipeline deve pausar por 2 segundos (`throttle`).