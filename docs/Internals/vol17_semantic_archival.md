# Doxoade Internals - Vol. 16: Arquivologia Forense e Resgate Temporal

**Data:** 14/01/2026
**Versão:** 1.0 (Alpha 75.0 - Legacy Audit)
**Status:** Vigente
**Foco:** Combate à Entropia Funcional e Erosão de Contratos

## 1. O Problema da Erosão Funcional
Identificamos que refatorações sucessivas tendem a "podar" funcionalidades úteis por simplificação excessiva. O `git diff` tradicional, focado em linhas de texto, falha em alertar o engenheiro sobre a perda de parâmetros ou funções inteiras.

## 2. A Solução: Auditoria Legada (`diff -l`)
Implementamos uma camada de análise semântica sobre o histórico do Git.

### Mecanismo Técnico:
- **Git log integration:** O sistema recupera metadados e conteúdo de versões passadas sem necessidade de `checkout`.
- **AST Signature Extraction:** Utilizamos o módulo `ast` para converter o código histórico em um mapa de assinaturas (`função: [argumentos]`).
- **Comparação de Contratos:** O motor compara o mapa atual com o mapa histórico, disparando alertas de:
    - `✘ FUNÇÃO REMOVIDA`: Funcionalidade que deixou de existir.
    - `⚠ CONTRATO ALTERADO`: Função que perdeu ou alterou parâmetros.

## 3. Padrão de Visualização Chief-Gold
A renderização foi projetada para simetria absoluta:
- **Destaque de Mudança:** Uso de `+` (Verde) e `-` (Vermelho) alinhados para comparação imediata de argumentos.
- **Sincronia Temporal:** Cada commit é tratado como um "Snapshot" de integridade funcional.

## 4. Relação com o Diagnose
- **Diagnose:** Auditoria do **Estado Presente** (O que estou fazendo agora?).
- **Diff Legacy:** Auditoria do **Estado Evolutivo** (O que eu perdi no caminho?).