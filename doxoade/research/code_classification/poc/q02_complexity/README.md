# Q02 - Complexity as 3rd dimension (DC2)

**Contrato:** DC2 (Classification) estendido para 3 dimensoes ortogonais.

## O que prova

Tres dimensoes coexistem sem colisao, com valor nao-booleano pela
primeira vez:

| Input | category | has_docstring | complexity |
|---|---|---|---|
| `return x+1` | arithmetic_return | no | 1 |
| `if x>0: return x / return 0` | unknown | no | 2 |
| `for x in xs: print(x)` | unknown | no | 2 |
| `if x>0: for i in range(x): ...` | unknown | no | 3 |
| `if x: if x>0: for i in range(x): ...` | unknown | no | 3 |
| 4+ branches | unknown | no | 4+ |
| `"""Doc."""; if x>0: return x+1` | unknown | yes | 2 |

## Bucketing declarado

`branch_count = N` (contagem exata de If/For/AsyncFor/While/Try/ExceptHandler
no body, recursivo, sem docstring):

| N | complexity | rule |
|---|---|---|
| 0 | 1 | R_c_1 |
| 1 | 2 | R_c_2 |
| 2 | 3 | R_c_3a |
| 3 | 3 | R_c_3b |
| >= 4 | 4+ | R_c_4plus |

**Por que 2 e 3 compartilham "3":** evita proliferacao de buckets sem
agregar valor ao estimador de complexidade. A diferenca entre 2 e 3
branches e menos informativa que entre 0-1, 1-2, 3-4+.

**Por que "4+" e range marker:** extractor emite `branch_count_ge_4=yes`
quando N>=4. Hint estrutural honesto — nao classificacao. Evita enumerar
4, 5, 6, ..., infinitas rules.

## Desafio tecnico declarado

**Primeira dim com valor nao-booleano.** Q00/Q01 tiveram dims com valores
em conjuntos finitos `{yes, no}` e `{arith, ident, const, unknown}`.
Complexity tem valor `{1, 2, 3, 4+}` — o "4+" nao e inteiro.

Extractor lida com isso emitindo DOIS fatos:
- `(F, branch_count, N)` — exato, para rules que precisam do numero
- `(F, branch_count_ge_4, "yes")` — hint, para rule do bucket `4+`

Isso mantem as rules puramente simbólicas (sem OR, sem comparacao
numerica), e o extractor faz a unica aritmetica necessaria.

## Interacao com dims anteriores

`has_docstring` continua filtrado do body (Q01). Em Q02g, a funcao tem
docstring + 1 branch. `branch_count=1` (nao conta docstring), `has_docstring=yes`,
`category=unknown` (body_0 e If, nao Return). Todas as 3 dims coexistem.

## O que NAO prova

- 4+ dims -> Q03 (design pattern) ou Q04 (code smell)
- Complexity em nested functions -> fora do escopo Q02
- Comprehension complexity -> intencionalmente nao conta If/For internos
- Cyclomatic exato (E - N + 2P) -> Q02 e "branch count", nao cyclomatic

## Err table (ProDeNov 5.4)

| Risco | Prob. | Impacto | Mitigacao |
|---|---|---|---|
| `ast.walk` duplo conta nos aninhados | media | alto | walk recursivo unico por stmt top-level |
| Docstring conta como branch | baixa | medio | body filtrado antes de walk |
| Bucket 4+ nao emite hint | baixa | critico | teste Q02f com 4 branches |
| Complexity null em funcao sem body | baixa | medio | body vazio -> branch_count=0 -> "1" |
| Determinismo afetado por walk | baixa | alto | Q02h (100 runs) |

## Planos A / B / C

- **A (implementado):** extractor emite `branch_count` exato + hint
  `branch_count_ge_4=yes`; 5 rules mapeiam buckets.
- **B (se Q03 precisar de granularidade):** extractor emite buckets ja
  agrupados (`complexity_bucket = str(min(N, 4))`), 4 rules. Custo:
  perde informacao do count exato.
- **C (se cyclomatic real for necessario):** trocar contagem por
  formula (E - N + 2P) com extractor computando E, N, P. Custo: muito
  mais complexo, e cyclomatic ja cobre funcoes com 20+ branches —
  fora do escopo Q02.

## Licao

DC2 generaliza para valores **nao-booleanos** porque o engine ja aceita
`str` como valor de fato. Nenhuma mudanca em C1/C3 foi necessaria.

O unico ajuste foi **extractor fazer a unica aritmetica necessaria**
(`>= 4`) e expor como hint estrutural. Rules continuam puras: match
strings exatas, sem comparacao numerica.

Isso valida a separacao C2/C3: numeros e comparacoes ficam em C2
(adaptacao), simbolos e conflito em C3 (expressividade). Se Q03
precisar de "contagem de parametros > 3", mesmo padrao se aplica.
