# P31 - for-range-len -> iteracao direta (C4 generaliza?)

**Contrato:** C4 (Atuacao). AST + padrao -> AST nova via ast.unparse.

**Diferenca de P30b:** P31 **nao usa engine**. P30a/b provou que C2+C3->C4
compõem. P31 isola se C4 generaliza ou e one-shot.

## Subset declarado

Aceita **apenas**:

```
for IDX in range(len(SEQ)):
    <body onde toda ocorrencia de IDX esta dentro de SEQ[IDX]>
```

Exatamente: `For.target=Name`, `For.iter=range(len(Name))`, body onde
`IDX` aparece **somente** como indice de `SEQ`. Qualquer uso livre de
`IDX` (ex: `print(i)`) -> passthrough.

Nome derivado: `f"{SEQ}_item"` (deterministico, evita colisao com SEQ).

## O que prova

- **P31a:** rewrite basico. `for i in range(len(x)): print(x[i])` vira
  `for x_item in x: print(x_item)`.
- **P31b:** idempotencia. Segunda aplicacao e no-op (pattern nao casa mais).
- **P31c:** passthrough. `for x in y: print(x)` fica inalterado.
- **P31d:** passthrough. `for i in range(len(x)): print(i)` - IDX usado
  como valor, nao como indice. Nao substituivel.
- **P31e:** passthrough. `for i in range(len(x)): print(y[i])` - indice
  de SEQ diferente.
- **P31f:** output compila.
- **P31g:** determinismo (100 runs).

## Por que P31 nao passa pelo engine

Seria possivel derivar `(g, pattern, for_range_len)` via engine e depois
rewrite no padrao de P30a/b. Mas:

1. C2+C3->C4 ja foi provado em P30a/b.
2. Adicionar deteccao via engine aqui dobra o custo sem provar nada novo.
3. A pergunta de P31 e diferente: **C4 generaliza?**

Se no futuro quizermos multi-pattern via engine (ex: `pattern(authority)`
derivado uma vez, N rewrites), P31 ganha deteccao. Por ora, inline.

## Limitacao conhecida

`SEQ_item` pode colidir com variavel ja usada no escopo externo. P31
aceita isso por determinismo. Deteccao de colisao fica para producao.

## O que NAO prova
- Range com multiplos args (`range(a, b)`) -> fora do subset.
- Enumerate patterns (`for i, x in enumerate(...)`) -> futuro.
- Deteccao de padrao via engine -> nao necessario aqui.

## Err table (ProDeNov 5.4)
| Risco | Prob. | Impacto | Mitigacao |
|---|---|---|---|
| Rewrite de caso invalido (IDX livre) | media | alto | P31d, P31e |
| Colisao de nome derivado | baixa | medio | `{SEQ}_item` documentado |
| Nao idempotente | media | critico | P31b |
| Output nao compila | baixa | critico | P31f |
| Mutacao nao-deterministica | baixa | alto | P31g |

## Planos A / B / C
- **A (implementado):** rewrite inline, sem engine.
- **B (se multi-pattern):** padroes viram fatos via engine, rewrite
  consome fatos (arquitetura de P30a/b generalizada).
- **C (se P31 falhar em caso real):** abandonar `range-len` - Python
  moderno prefere `enumerate` ou comprehension direta. P31 pode nao
  valer o custo de producao.

## Licao
P31 responde a pergunta que P30b deixou em aberto: "C4 e rewrite
especifico ou mecanismo parametrico?". Se P30b so passou por hardcode,
P31 expoe. Se P31 passa, a arquitetura suporta N padroes.
