# Doxoade Internals - Vol. 18: Fortaleza Aegis e Hacking Ético

**Versão:** 1.0 (Aegis v2)
**Foco:** Auto-Proteção e Prova de Vulnerabilidade

## 1. O Protocolo Aegis (Regra 8)
O Doxoade v75.40 deixou de ser vulnerável por design ao migrar o `exec()` nativo para o `restricted_safe_exec`.
- **Sandbox Wrapper:** O código do usuário/terceiro roda em uma "caixa de vidro" sem `__builtins__`.
- **AST Shield:** O sistema bloqueia instruções de `import` e acessos a atributos privados (`__class__`, `__base__`) antes mesmo da compilação.

## 2. Suite de Hacking Ativo (`doxoade hack`)
- **Baseline/Verify:** Detecção de Tamper (adulteração) via hashes SHA-256 determinísticos do Core.
- **Technical Pentest (-r):** Motor de **Taint Analysis** que rastreia a linhagem do dado. Ele prova se um `input()` chega a um "Sink" perigoso e gera um relatório de **Attack Path**.

## 3. Diagnóstico de Segurança
O arquivo `diagnostic/hacking_diagnose.py` serve como teste de estresse contínuo, tentando "quebrar" o sandbox para garantir que as travas de segurança nunca sejam removidas.