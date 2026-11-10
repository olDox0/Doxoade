# P20 — Unificação sobre triplas (C1 + C3)

**Contrato:** C1 (Inferência) + C3 (Expressividade com variáveis).
**Mudança de contrato:** fatos passam de `(key, value)` para `(s, p, o)`.

## Modelo

| Termo | Casa com | Liga |
|---|---|---|
| `str` | igualdade estrita | não |
| `Var(name)` | qualquer string | sim (consistente entre condições) |

`match_conditions` faz backtracking exaustivo: para cada condição, tenta
todos os fatos, acumula bindings, propaga. Retorna **todas** as soluções.

## O que prova

- **P20a:** transitividade `pai(X,Y) ∧ pai(Y,Z) → avo(X,Z)`.
- **P20b:** var repetida `r(X,X)` casa só com self-loops — `(a,r,b)` não
  produz `(a,self,b)`.
- **P20c:** duas regras sobre mesmo fato produzem fatos distintos sem
  conflito (`r_inv` + `r_sym`).
- **P20d:** falha de unificação não gera erro nem fato — silêncio correto.
- **P20e:** determinismo em 100 runs (set de derivações idêntico).
- **P20f:** transitividade em grafo cíclico quiesce — `(a,r,b),(b,r,a)`
  produz só `(a,trans,a)` e `(b,trans,b)`, sem explosão.

## Por que triplas (mudança de contrato)

P10/P11 usaram `(key, value)` — unário. Relações binárias em unário exigem
encoding comprimido (`key="pai.a", value="b"`), que viola o princípio C-verb.
Triplas são o formato natural para unificação. P10/P11 continuam válidos
como sondas de extração; o engine de P20 é independente. Reconciliar em P70.

## O que NÃO prova
- Negação como falha → **P21** (falta mecanismo de "não casa").
- Indexação → **P70** (aqui é força bruta `O(|facts|^|conds|)`).
- Conflito entre regras com vars → herda P02, mas não testado aqui.
- Extração de AST → já em P10/P11.

## Err table (ProDeNov 5.4)
| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Var não ligada em conclusão | média | alto | `conclusion_fact` retorna None + warning |
| Bindings inconsistentes (var = 2 valores) | baixa | alto | `unify_term` retorna None |
| Backtracking explodir em |facts| grande | alta (fora de PoC) | aceito em PoC; indexação em P70 |
| Ciclo transitivo explodir | média | alto | idempotência + monotonicidade (P01) |
| Determinismo afetado por ordem | baixa | alto | `new_facts` coletados, sorted depois |

## Planos A / B / C
- **A (implementado):** backtracking exaustivo, sem índice.
- **B (se A não escalar em P30):** índice `facts_by_predicate: dict[p, list[fact]]`.
- **C (se B ainda lento):** RETE parcial — alpha network por condição. Custo alto.

## Lição
Unificação separa brinquedo de engine útil. P00–P02 provam que o motor
**termina**; P20 prova que ele **compõe** — fatos derivados alimentam
regras seguintes via bindings, não via reescrita. A tripla é o formato
que torna isso natural. Manter `(key, value)` para relações binárias
seria compressão prematura — exatamente o que C-verb proíbe.
