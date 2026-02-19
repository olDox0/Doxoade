# Doxoade Internals - Vol. 21: O Tribunal de Ma'at e a Sentença de Anúbis

**Data:** 14/02/2026
**Status:** Consolidado em Produção
**Foco:** Anti-Regressão e Higiene de Repositório

## 1. O Problema da Entropia
Ao atingir 17k LOC, o projeto começou a sofrer com "Vazamentos de Infraestrutura": caches de análise e binários de build estavam sendo enterrados no Git, sujando a linhagem do tempo.

## 2. A Solução Ma'at (Atena + Invariantes)
Implementamos um motor de auditoria que não avalia apenas "erros de código", mas "pecados arquiteturais":
- **PASC 1.3 (Peso):** Bloqueio de arquivos > 20KB.
- **PASC 8.6 (Direcionalidade):** Bloqueio de acesso direto ao DB via comandos.

## 3. A Sentença de Anúbis
O Sistema Anúbis age no "Limbo" (Git Stage). Ele compara os arquivos preparados com as leis do `DNM` (Directory Navigation Module). Se você tentar comitar um `__pycache__`, o Anúbis intervém antes que o erro se torne permanente.

## 4. O Ciclo Lazarus-Save
A maior inovação deste ciclo foi a integração do **Protocolo Lázaro** dentro do fluxo de salvamento. Se o Ma'at ou o Anúbis detectarem uma regressão, o sistema oferece a **Forense Instantânea**, permitindo que o Engenheiro visualize o erro e o corrija sem sair do terminal.