# Q00 - Baseline classifier (DC2)

**Contrato:** DC2 (Classification).
`StructuralFact + rules -> CategoryFact`.

## O que prova

Toda funcao recebe exatamente UMA categoria:

| Input | Categoria | Regra |
|---|---|---|
| `def f(x): return x + 1` | `arithmetic_return` | R_arith |
| `def g(x): return x` | `identity_return` | R_ident |
| `def h(): return 42` | `constant_return` | R_const |
| `def k(x): print(x)` | `unknown` | R_unknown (NAF) |

## Mecanismo do default

Reusa NAF (P21) + prioridade (P02):
- R_arith/R_ident/R_const tem prio=10
- R_unknown tem prio=1 e NAF `NOT (f, category, _)`
- Ciclo 1: concretas + R_unknown disparam. Conflito resolvido por
  prioridade. Se concreta dispara, R_unknown vai para shadowed.
- Ciclo 2: concreta idempotente; R_unknown nao dispara (NAF falha
  porque categoria existe).
- Quiesce em 2-3 ciclos.

## INVARIANTE — depende de:

Todas as 4 regras dependem APENAS de fatos seed (extraidos do AST no
ciclo 0). Nao ha regra que dependa de fato derivado por outra regra.

Isso elimina **conflito cross-ciclo** (P02 so testa conflito
within-ciclo). Se uma regra futura depender de fato derivado, pode
haver `(f, category, X)` em ciclo N e `(f, category, Y)` em ciclo M>N,
sem deteccao. Q00 evita esse caso por design.

## O que NAO prova

- Multi-categoria (`(f, category, X)` E `(f, has_docstring, yes)`) —
  Q01.
- Complexidade — Q02.
- Design pattern — Q03.
- Code smell — Q04.
- Cross-cycle conflict resolution — deixa para Q0X quando regras
  encadeadas emergirem.

## Err table (ProDeNov 5.4)

| Risco | Prob. | Impacto | Mitigacao |
|---|---|---|---|
| Duas categorias ao mesmo tempo | baixa | critico | winners dict + priority |
| Categoria perdida (nem concreta nem unknown) | baixa | critico | R_unknown como fallback |
| Cross-cycle conflict | n/a (invariante) | alto | documentado |
| Categoria nao-deterministica | baixa | alto | Q00e (100 runs) |

## Planos A / B / C

- **A (implementado):** 4 regras, prioridade + NAF, within-cycle conflict.
- **B (se multi-categoria):** usar predicates distintos por dimensao
  (`category`, `has_docstring`, `complexity`). Sem conflito por
  construcao.
- **C (se cross-cycle conflitar):** extension para cross-cycle conflict
  resolution (matching por subject+predicate no merge, nao so por
  idempotencia exata).

## Licao

DC2 e o primeiro contrato com **fallback** (unknown). O fallback nao e
regra especial no engine — e apenas uma regra normal com NAF + prioridade
baixa. Isso mostra que a arquitetura de C1-C3 ja suporta classification
sem extensao. Prova de que o kernel promovido e suficiente.

## Quando Q00 promove

Nao promove isolado. DC2 completo so quando Q01-Q04 existirem e
provam que classificacao **generaliza** (diferente de rewrite, que foi
P30b+P31). Por ora, Q00 fica em research.
