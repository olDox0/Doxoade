# P70 - Substitutibilidade de matcher (C7) + mensuracao (C6)

**Contrato:** C7 (Substitutibilidade) com C6 (Mensuracao) embutido.

## Pergunta

Se eu troco o matcher ingenuo por um indexado, o comportamento observavel
(trace + fatos finais) muda? Se muda, "modular" e teatro.

## Interface dos matchers

```python
match(conditions, negations, facts) -> list[(bindings, witnesses)]
```

Dois matchers, mesmo contrato:
- **NaiveMatcher**: backtracking forcabruto sobre todos os fatos.
- **IndexedMatcher**: `facts_by_predicate` bucket.

`IndexedMatcher` cai para `facts` inteiro quando predicado e `Var` (nao
da para indexar sem saber o predicado).

## O que prova

- **P70a-d:** trace hash identico em 4 cenarios (FizzBuzz-like, transitive,
  NAF, mixed). Nenhum dos dois matchers produz resultado divergente.
- **P70e:** indexed reduz lookups em cenario com muitos fatos irrelevantes
  (100 labels + 2 seeds). Speedup medido.
- **P70f:** 100 runs determinam hash estavel nos dois matchers.

## C6 embutido (mensuracao)

Toda sub-sonda reporta:
- `cycles`: quantos ciclos ate quiescencia
- `derived`: quantos fatos derivados
- `rules_fired`: quantas aplicacoes de regra
- `lookups`: quantos fatos o matcher examinou (proxy de custo)

C6 nao e sonda separada porque a **metrica e o argumento** de que C7
importa. Separar seria fragmentar a prova.

## O que C7 prova

C7 **nao** prova que o indexed e correto em todos os casos possiveis.
Prova que:
1. Em cenarios representativos de C1-C6, os matchers sao **observacionalmente
   equivalentes**.
2. O indexed e **mensuravelmente mais barato** quando ha muitos fatos.

Se um novo PoC introduzir padrao onde os matchers divergem, P70 falha. A
implementacao do novo matcher precisa respeitar o contrato C7 para entrar.

## O que NAO prova
- Correcao do indexed em predicado `Var` (cai para `facts` inteiro, mas
  nao ha teste especifico - `mixed` nao exercita).
- Substituicao de *outros* componentes (fact store, trace, explain).
  P70 e sobre o matcher.

## Err table (ProDeNov 5.4)
| Risco | Prob. | Impacto | Mitigacao |
|---|---|---|---|
| Matchers divergem em caso nao coberto | media | critico | 4 cenarios, cobrindo 4 contratos |
| Indexed fica MAIS lento em caso Var | media | medio | P70e mede; se inverter, falha |
| Trace signature colide (hash) | baixa | alto | SHA-256 de 16 hex chars |
| Cenario trivial demais | media | alto | mixed_many_facts forca indexacao |

## Planos A / B / C
- **A (implementado):** dois matchers, interface comum, 4 cenarios.
- **B (se cenario novo divergir):** adicionar cenario a lista. C7 falha ate
  matcher ser ajustado.
- **C (se matchers nao puderem ser equivalentes):** contrato C7 abandona
  "substituibilidade total"; cada PoC declara qual matcher usa.

## Licao
C7 e o ultimo contrato porque **e o unico que depende dos outros**.
Substitutibilidade sem C1-C6 testado nao tem contra o que comparar.
Apos P70, o kernel esta pronto para promocao.

**Promocao**: o que sobrevive para `src/` nao e nenhum engine de PoC -
e o **contrato** `Matcher.match(conditions, negations, facts) -> results`.
A escolha naive vs indexed vira configuracao de producao, nao decisao
de PoC.
