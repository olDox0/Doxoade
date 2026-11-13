# Q01 - Multi-dimensional classifier (DC2)

**Contrato:** DC2 (Classification) estendido para 2 dimensoes.

## O que prova

Duas dimensoes coexistem sem colisao:

| Input | category | has_docstring |
|---|---|---|
| `"""Doc."""; return x+1` (dentro da func) | arithmetic_return | yes |
| `return x+1` | arithmetic_return | no |
| `"""Doc."""; print(x)` | unknown | yes |
| `print(x)` | unknown | no |

Por construcao: `category` e `has_docstring` sao predicados distintos.
Engine faz conflito por `(subject, predicate)`, entao nunca colidem.

## Desafio tecnico declarado

Docstring muda `body[0]` de `Return` para `Expr(Constant(str))`. Se
extracao fosse ingenua:

- `body_0_kind=Expr` (por causa do docstring)
- `R_arith` exige `body_0_kind=Return` -> falharia
- Funcao com docstring viraria `unknown` incorretamente

**Solucao:** `ast.get_docstring` detecta; `body_stmts = body[1:]` filtra.
`has_docstring` vira **fato separado**. R_arith continua igual.

Docstring e metadata, nao logica. Extracao respeita isso.

## O que NAO prova

- 3+ dimensoes simultaneas -> Q02 (complexidade, 3a dim)
- Dimensoes com valores nao-booleanos -> Q03 (pattern, string)
- Dimensoes derivadas (nao seed) -> Q03+ quando 2 regras por dim
- Cross-cycle conflict -> ainda nao exercitado (Q00/Q01 sao single-cycle)

## Err table (ProDeNov 5.4)

| Risco | Prob. | Impacto | Mitigacao |
|---|---|---|---|
| Docstring detectado errado | baixa | critico | `ast.get_docstring` (stdlib) |
| Filtragem remove stmt errado | baixa | critico | has_doc garante body[0]=docstring |
| Filtragem deixa body vazio | baixa | medio | body_stmts vazio -> R_unknown |
| Conflito entre dims | nula | critico | predicados distintos |
| Categoria nao-deterministica | baixa | alto | Q01e (100 runs) |

## Planos A / B / C

- **A (implementado):** `ast.get_docstring` + filtragem explicita. Rules
  inalteradas de Q00. has_docstring e seed.
- **B (se Q02 exigir):** Dimensoes como tuplas `(dim_name, dim_value)`
  em vez de predicados flat. Permite N dims sem crescimnto de schema.
- **C (se cross-cycle conflict):** extension do engine para detectar
  `(s, p, X)` vs `(s, p, Y)` em ciclos diferentes. Vira sonda propria.

## Licao

DC2 **generaliza** para multi-dim. Duas dimensoes ortogonais coexistem
sem conflito **porque o engine ja tem a primitiva certa** (chave =
`(subject, predicate)`). Nao precisa de regra especial.

O que precisa de atencao e **extracao**: docstring e ruido estrutural
para classificacao, nao sinal. Filtragem no `extract_facts` mantem as
regras simples e o contrato honesto.

**Promocao:** Q01 nao promove isolado. DC2 esta consolidado com 2 dims
testadas. Q02 (complexidade) e Q03 (pattern) sao candidatas naturais
para 3a e 4a dims. DC2 promove so quando 4+ dims provam generalizacao
sem mudanca de contrato no engine.
