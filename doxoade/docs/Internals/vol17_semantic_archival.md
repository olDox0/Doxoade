# Doxoade Internals - Vol. 16: Arquivologia Forense e Resgate Temporal

**Versão:** 1.0 (Lazy-Gold)
**Foco:** Combate à Entropia Funcional

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