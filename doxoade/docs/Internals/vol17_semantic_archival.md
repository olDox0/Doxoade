# Doxoade Internals - Vol. 17: Arquivologia Semântica e Resgate de Poder

**Data:** 16/01/2026
**Versão:** 1.0 (Lazy-Gold)
**Foco:** Combate à Erosão Funcional (PASC-1.1)

## 1. O Desafio da Evolução
Refatorações agressivas costumam causar a "Erosão Funcional", onde parâmetros importantes são removidos por serem considerados (erroneamente) obsoletos.

## 2. A Solução: `diff --legacy (-l)`
Implementamos um motor de análise que:
1. Extrai o histórico de commits de um arquivo alvo.
2. Recupera o conteúdo histórico via Git-Show (sem checkout).
3. Converte versões passadas em mapas semânticos via AST.
4. Compara argumentos e assinaturas, disparando alertas de `CONTRATO ALTERADO`.

## 3. Visualização de Código Perdido (-lc)
O modo `--legacy-code` permite injetar o corpo das funções removidas diretamente no relatório, permitindo que o desenvolvedor recicle lógica útil (PASC-9) sem precisar navegar manualmente por commits antigos.

## 4. Relação Diagnose vs Diff
- **Diagnose:** Painel de Situação (O que está acontecendo agora?).
- **Diff Standard:** Auditoria de Linhas (Como o texto mudou?).
- **Diff Legacy:** Auditoria de Poder (O que a ferramenta deixou de saber fazer?).

## 5. O Problema da Poda Silenciosa
Em refatorações de larga escala (como a transição para Lazy-Gold), é comum a remoção de argumentos de funções ou deleção de utilitários considerados "mortos". O `git diff` textual falha em alertar sobre a perda de capacidade lógica.
### A Solução: Auditoria Semântica (`diff -l`)
Implementamos um motor de análise que utiliza o Git como banco de dados de conteúdo e a AST como parser de estrutura.
- **Assinaturas Históricas:** O sistema extrai o mapa `função: [argumentos]` de cada commit.
- **Relatório de Regressão:** Dispara alertas de `CONTRATO ALTERADO` quando a interface de uma função perde parâmetros entre versões.
- **Legacy Code Injection (-lc):** Permite injetar o corpo de funções removidas no terminal para reciclagem imediata (PASC-9).