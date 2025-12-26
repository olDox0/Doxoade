# Protocolo Aegis (Segurança)

Diretrizes de segurança inegociáveis para desenvolvimento no Doxoade.

## 1. Proibição de Execução Arbitrária
*   ❌ **Proibido:** `eval()`, `exec()`.
*   ❌ **Proibido:** `pickle` para dados não confiáveis (Use `json`).

## 2. Sanitização de Subprocessos
*   ❌ **Proibido:** `subprocess.run("cmd arg", shell=True)`
*   ✅ **Obrigatório:** `subprocess.run(["cmd", "arg"], shell=False)`
    *   *Exceção:* Comandos internos do Windows (`dir`, `echo`) exigem shell, mas devem ser auditados.

## 3. Filtragem Dupla (Double Filtering)
O comando `doxoade security` aplica filtros em duas camadas:
1.  Passa exclusões para a ferramenta (Bandit/Safety).
2.  Filtra o JSON de saída novamente no Python para garantir que pastas como `venv/` e `tests/` nunca gerem alertas falsos.

## 4. Tratamento de Erros
*   ❌ **Proibido:** `except:` (Bare except). Captura `SystemExit` e impede shutdown.
*   ✅ **Obrigatório:** `except Exception:` ou exceções específicas.