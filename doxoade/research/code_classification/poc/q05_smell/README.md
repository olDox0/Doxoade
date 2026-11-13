# Q05 - Code smell detection (DC2, domain expansion)

**Contrato:** DC2 (Classification) com 5 dimensoes.
**NAO faz upgrade de engine.** Q04 kernel inlined sem mudanca.

## Por que Q05 nao mexe no engine

Q04 fechou a lacuna tecnica real (retraction cross-cycle). Q05 testa
o engine em cenario real, sem expandir. Isso valida **Plan B** da
ProDeNov 1.2.1: quando feature pode ser expressada com o vocabulario
existente, nao se adiciona feature ao engine.

Q05 explora **retraction em contexto real**: aggregate default
`has_any_smell=none` (prio 1, NAF) e retratado por specific
`has_any_smell=dirty` (prio 20) quando qualquer smell_* aparece.

## Smells declarados

| Smell | Condicao | Regra | Escopo |
|---|---|---|---|
| `magic_number` | Constant int ∉ {0,1,-1} em `Compare.comparators` | R_magic | Apenas Compare |
| `long_method` | `body_len >= 4` (apos docstring) | R_long | Threshold 4 |
| `dead_code` | `Return` no body-level seguido por outro stmt | R_dead | Body-level apenas |

**Nao detecta** (fora do escopo Q05):
- Magic em `Assign`/`If`/`BinOp` (so `Compare`)
- Dead nested (Return dentro de `If`)
- Long method com threshold diferente de 4
- Smells estilo OO (god class, feature envy)

## Estrutura de derivacao

```
seed:      has_magic_number, long_body, dead_after_return
            (extracted, prio 0 = seed)
cycle 1:
  R_magic → smell_magic_number=yes    (prio 15)
  R_long  → smell_long_method=yes      (prio 15)
  R_dead  → smell_dead_code=yes        (prio 15)
  R_clean → has_any_smell=none         (prio 1, NAF all smell_*)
cycle 2:
  R_dirty_magic → has_any_smell=dirty  (prio 20, RETRAI none)
  R_dirty_long  → has_any_smell=dirty  (prio 20, idempotente)
  R_dirty_dead  → has_any_smell=dirty  (prio 20, idempotente)
```

Smells sao **ortogonais** — predicados distintos (`smell_magic_number`
vs `smell_long_method` vs `smell_dead_code`). Coexistem sem colisao.

Aggregate `has_any_smell` e **single-valued** — `none` ou `dirty`.
Retraction de Q04 atua aqui: `none` sai quando `dirty` entra.

## O que Q05 prova

1. **Domain expansion sem engine upgrade.** Q04 kernel inlined,
   nenhuma linha alterada.
2. **Retraction em contexto real.** Nao mais artificial como Q04a
   (que usava rules stub). Retraction acontece na pratica:
   `has_any_smell=none → dirty` quando specifics aparecem.
3. **5 dims coexistem** (category, complexity, has_any_smell,
   smell_* individuais).
4. **Smells ortogonais nao colidem.** Q05e tem 3 smells simultaneos
   sem conflito — predicados distintos.
5. **Clean nao dispara retraction** (Q05a, retr=0).

## Err table (ProDeNov 5.4)

| Risco | Prob. | Impacto | Mitigacao |
|---|---|---|---|
| `has_magic_number` em Assign falso positivo | nula (check so Compare) | critico | funcao `_has_magic_number` restrita |
| Dead nested detectado errado | baixa | medio | `_has_dead_after_return` body-level only |
| 3 smells colidirem | nula | critico | predicados ortogonais |
| `has_any_smell=none` nao retratado | baixa | critico | Q05b/c/d/e verificam retr=1 |
| Clean retrata por engano | baixa | alto | Q05a verifica retr=0 |

## Planos A / B / C

- **A (implementado):** 3 smells com predicados ortogonais, aggregate
  `has_any_smell` single-valued via retraction.
- **B (se Q06 precisar de smells OO):** schema de fato enriquecido
  (`Fact.subject_type`, `Fact.confidence`), smells com agregacao
  ponderada.
- **C (se smells precisarem de multiplas dimensoes de threshold):**
  bucket como Q02 (`smell_long_severity=mild|moderate|severe`).

## Licao

**Domain expansion sem feature de engine.** Q04 fechou o gap tecnico.
Q05 nao precisou adicionar nada — a combinacao de retraction (Q04) +
NAF (P21) + prioridade (P02) + ortogonalidade de predicados resolve
"clean vs dirty" naturalmente.

**Retraction deixa de ser artificial.** Q04 exercitou retraction com
rules stub (Q04a-c-d). Q05 usa retraction em cenario onde ela tem
proposito real: default `none` precisa sair quando specifics aparecem.
Se Q05 falhasse aqui, Q04 nao serviria para aplicacoes reais.
