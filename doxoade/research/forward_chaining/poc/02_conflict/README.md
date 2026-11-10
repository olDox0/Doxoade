# P02 — Conflito real e determinismo

**Contrato:** C1 (Inferência) estendido com resolução de contradição por prioridade.

## Semântica de conflito — DECLARADA

Duas regras que produzem fatos com a **mesma key** e **valores diferentes**
no mesmo ciclo constituem conflito. Política:

1. Maior prioridade vence.
2. Empate → primeira regra em `rules` vence (tie-break por ordem de definição).
3. Perdedor vai para `shadowed` — nunca re-entra no WM.
4. Cada resolução gera entrada em `conflicts` (rastreável).

Sem essa política, WM ganharia `out=X` **e** `out=Y` — contradição silenciosa.
P02 é o teste de que a política existe e é determinística.

## O que prova

- **P02a:** conflito real, prioridade 10 vs 1 → só `out=Y` no WM, 1 conflito logado.
- **P02b:** chaves distintas, ambas disparam, 0 conflitos.
- **P02c:** 100 runs de P02a → saída byte-a-byte idêntica.
- **P02d:** empate de prioridade → ordem em `rules` decide (`first` na ordem A, `second` na ordem B).

## O que NÃO prova (deixa para as próximas)
- Confiança / decay → **P23** (confidence engine, futuro).
- Remoção de fato / "unshadowing" → fora de escopo.
- Unificação → **P20**.

## Err table (ProDeNov 5.4)
| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Conflito silencioso (ambos entram) | baixa | crítico | P02a com `out_values != ['Y']` |
| Não-determinismo por ordem | baixa | alto | P02c com 100 runs |
| Tie-break implícito | média | alto | P02d com duas ordens |
| Perdedor re-tenta todo ciclo | média | médio | `shadowed` persiste |

## Planos A / B / C
- **A (implementado):** resolução por prioridade + tie-break por ordem.
- **B (se A falha):** `confidence` numérica substitui prioridade
  (rascunho de P23).
- **C (se A e B falham):** replanejar contrato — conflito pode não ser
  detectável por key isolada (ex: `temp=high` vs `temp=low` são opostos
  semânticos, não sintáticos).

## Lição
Conflito **não** é bug do motor. É o motor **funcionando**. O teste correto
é que o resultado é único, rastreável e determinístico — não que "não há
conflito". Engines que nunca logam conflito estão mentindo.
