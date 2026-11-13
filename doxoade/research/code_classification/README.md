# Code Classification — linha de pesquisa

**Status:** iniciando. Q00 verde = primeiro marco.
**Base:** forward chaining kernel (research/forward_chaining, 12 PoCs, C1-C7).

## Motivação

O kernel de forward chaining esta provado (C1-C7). A pergunta natural
agora e: e possivel usa-lo para **descrever e diagnosticar codigo** de
forma simbolica, sem ML?

Codigo tem propriedades formais que classificacao simbolica captura bem:
- Categoria funcional (pura, recursiva, effectful)
- Complexidade ciclomatica (O(1), O(n), O(n^2))
- Design pattern (factory, visitor, singleton)
- Code smell (long method, magic number, dead code)
- Origem de erro (test falha X, classificacao Y -> discrepancia)

Cada uma dessas e uma **regra sobre fatos estruturais**. Nao precisa de
embedding, nao precisa de corpus gigante.

## Contratos-alvo

- **DC1 (Extraction)**: `src: str -> set[StructuralFact]`
  Fatos estruturais derivados de AST. "O que o codigo CONTEM."

- **DC2 (Classification)**: `StructuralFact + rules -> CategoryFact`
  Categoria derivada. "O que o codigo E."

- **DC3 (Aggregation)**: `CategoryFacts -> DescriptionFact`
  Composicao. "O que dizer sobre o codigo." (futuro)

- **DC4 (Triangulation)**: `Classification x Observation -> Discrepancy`
  Diagnostico. "O que esta errado." (futuro, depende de DC2)

## O que cabe (agora)

- Classificacao simbolica por regra
- Vocabulario controlado (categoria = string fixa)
- Multiplas dimensoes (categoria + complexidade + smell, sem colisao)
- Fatos derivados de AST via `ast.parse` (nao comentario, nao string)
- Determinismo obrigatorio (100 runs = mesmo output)

## O que NAO cabe (agora)

- ML, embeddings, corpus
- NLP de comentarios ou nomes de variavel
- Geracao de codigo (isso e `forward_chaining`, P30b/P31)
- Analise semantica de runtime (precisa de trace)
- Backward chaining (deferido em `forward_chaining/research_directions.md`,
  trigger: >100 regras ou explain_negative precisar)

## Escada de PoCs (proposta inicial, ajustavel)

| PoC | Prova | Contrato |
|---|---|---|
| Q00 | 1 funcao -> 1 categoria, 4 regras, default unknown | DC2 |
| Q01 | multi-dimensao (categoria + has_docstring) | DC2 |
| Q02 | complexidade (count branches -> bucket) | DC2 |
| Q03 | design pattern (factory) | DC2 |
| Q04 | code smell (long method) | DC2 |
| Q05 | triangulacao: teste falha x classificacao | DC4 |

Cada PoC prove UM contrato. Q01+ expandem vocabulario; DC4 so entra
quando DC2 estiver com 3+ dimensoes testadas.

## Direções deferidas (com gatilho)

- **Backward chaining** — trigger: >100 regras de classificacao, ou
  explain_negative de Q03+ falhar por falta de goal-driven.
- **Error triangulation (DC4)** — trigger: Q03/Q04 verdes. Antes disso,
  nao ha o que triangular.
- **Word tree / combinatory** — fora do escopo deste linha.

## Quando promove

Todos DC1-DC4 com >=1 PoC verde cada. Ai promove para
`doxoade/code_classification/` (mesma logica de promocao de FC:
contratos, nao codigo).

## Nomenclatura

PoCs dessa linha usam prefixo `q` (q00, q01...). Linha de FC usa
numeros (00, 01...). Sem colisao de nome.
