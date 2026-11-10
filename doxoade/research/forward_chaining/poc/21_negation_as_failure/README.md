# P21 — Negation as failure (C3, aquecimento)

**Contrato:** C1 (Inferência) + C3 (Expressividade com negação).

## Semântica — DECLARADA

`NOT C` significa "C **não é derivável** do WM atual".
- C é um **único padrão** nesta PoC (composto → P22).
- Avaliado contra o **snapshot do ciclo** (herança de P01/P02/P20).
- Múltiplas negações numa regra = conjunção (todas devem falhar para derivar).
- Wildcard `_` casa com qualquer valor, **não liga** variável.

**Snapshot é essencial.** Sem ele, `IF NOT done THEN done` entra em loop
(a negação continua passando depois de derivar `done`). Com snapshot:
ciclo 1 não tem `done` → deriva; ciclo 2 tem `done` → negação falha.
P21e testa esse caso.

## O que prova

- **P21a:** NAF básico — deriva se não há blocker.
- **P21b:** blocker presente → não deriva.
- **P21c:** NAF avalia por binding de `X`, não por par `(X,Y)`.
  `NOT (X,r,X)` bloqueia se existe `(v,r,v)` para `v`=valor de `X`,
  independente de `Y`. Exemplo: `(a,r,b)` é bloqueado porque existe
  `(a,r,a)`, mesmo `Y≠X`.
- **P21d:** grafo cíclico — negação da recíproca bloqueia ambos lados.
- **P21e:** self-defeating quiesce via snapshot (ciclo 2 bloqueia).
- **P21f:** duas negações conjuntas — 4 sub-casos (none/bad/ugly/both).
- **P21g:** determinismo em 100 runs.

## Diferença de P22 (futuro)

| Aspecto | P21 (NAF) | P22 (negação explícita) |
|---|---|---|
| Significado | "não provável agora" | "provado que é falso" |
| Natureza | procedural | declarativa |
| Fatos negativos | não existem | `(X, ¬r, Y)` explícito |
| Contradição | impossível | possível (X r Y ∧ X ¬r Y) |
| Precedente | Prolog, sistemas especialistas | lógica estendida (Well-Founded, ASP) |
| Custo | baixo | alto (semânticas de contradição) |

NAF cobre ~90% dos casos práticos. P22 fica registrado como direção
no README, com gatilho: **quando P30 (rewrite) precisar expressar
"esta construção é proibida"** — ex: "não use `eval()`".

## O que NÃO prova
- Negação composta (conjunção interna) → P22.
- Fatos negativos explícitos → P22.
- Contradição `(X,r,Y) ∧ (X,¬r,Y)` → P22.
- **Constraint `X != Y`** (desigualdade entre variáveis) — não é NAF.
  É construto separado. Exemplo: "derivar `(X,not_self,Y)` só se X≠Y"
  exige `X != Y` como builtin, não `NOT (X,r,X)`. Direção candidata a P22
  ou a builtin do matcher. Registrado em `research_directions.md`.

## Err table (ProDeNov 5.4)
| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Self-defeating loop | alta (sem snapshot) | crítico | P21e testa snapshot |
| NAF avaliada sobre derivados do mesmo ciclo | média | alto | `facts` list inalterada até merge |
| Wildcard em conclusão | média | alto | `substitute` retorna None |
| Negação silenciosamente bloqueia | baixa | médio | `LOG.debug` de blocker |
| Conjunção interpretada como disjunção | média | alto | P21f 4 sub-casos |

## Planos A / B / C
- **A (implementado):** NAF por padrão singular, contra snapshot.
- **B (se NAF não cobrir P30):** NAF composto (conjunção interna). Custo: `unify` recursivo.
- **C (se B falhar):** migrar para P22 (negação explícita com fatos negativos).

## Lição
NAF + snapshot é a combinação minimalista que evita 90% dos loops de
negação. O ponto sutil: NAF **depende** do estado, e o snapshot é o que
fixa "qual estado" está sendo consultado. Sem snapshot, NAF é não-monotônica
e o engine perde a garantia de terminação de P01. P21e é a sonda que separa
"motor que termina" de "motor que trava em `IF NOT done THEN done`".

NAF e `X != Y` são construtos distintos que costumam ser confundidos:
- `NOT (X,r,X)` → "não há self-loop em X" (procedural, sobre fatos).
- `X != Y` → "X e Y têm valores diferentes" (constraint, sobre bindings).

P21c originalmente assumia o segundo, mas o motor implementa o primeiro.
Teste reformulado para provar o primeiro, e o segundo fica registrado como
gap — honestamente. Sem essa distinção, P22 herdaria ambiguidade.
