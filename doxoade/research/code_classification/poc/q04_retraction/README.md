# Q04 - Cross-cycle retraction (engine upgrade)

**Contrato:** C1 (Inferencia) estendido com retracao.

## Mecanismo declarado

`Fact` ganha campo `priority` (herdado da rule que derivou). Engine
ganha `retracted: set[(s,p,o)]` e `retracted_history: list[dict]`.

Na fase de merge (apos winners within-cycle):

```
para cada winner (s, p, o_new, P_new):
  para cada fato vivo (s, p, o_old, P_old):
    se o_old == o_new: idempotente, skip
    ef_prio = P_old se derived, 999999 se seed
    se P_new > ef_prio: retrata o_old, adiciona o_new
    se P_new < ef_prio: shadow o_new
    se P_new == ef_prio: shadow o_new (tie-break first-wins)
```

**Seeds protegidos.** `source="seed"` tem prio efetiva infinito, nunca
retratados.

**Retracao monotona.** Fato retratado nao ressuscita. Filtro em
`snapshot`/`existing`. NAF sobre vivo.

**Cross-cycle only.** Conflito within-cycle continua como P02 (prioridade
+ tie-break within).

## O que Q04 prova

### Q04a — retração happy path
R_utility (prio 1, NAF default) dispara cycle 1 → pattern=utility.
R_factory (prio 20) dispara cycle 2 → pattern=factory. Retração:
utility sai, factory entra. Final: pattern=factory, retracted=1.

**Sem Q04, WM teria `(create_user, pattern, utility)` E
`(create_user, pattern, factory)`** — contradição em `pattern`.
Resolvido por retração.

### Q04b — sem conflito
R_utility sozinha (nao ha R_factory aplicavel). pattern=utility
permanece. retracted=0.

### Q04c — tie prio cross-cycle
R_a_low (prio 10) dispara cycle 1 → pattern=first_fired.
R_b_low (prio 10) dispara cycle 2 → pattern=second_fired. Tie 10=10
cross-cycle. Shadow novo (first wins). retracted=0.

### Q04d — higher fires first, lower cross
R_a_high (prio 20) dispara cycle 1 → pattern=high.
R_b_low (prio 10) + R_b_verylow (prio 1) disparam cycle 2. Existing
high prio 20. Novos prio 10 e 1 < 20. Shadow ambos. retracted=0,
pattern=high preservado.

### Q04e — determinismo
100 runs de Q04a → mesmo resultado (pattern=factory, retracted=1).

## O que NAO prova

- Retração em cascata (A retrai B, C retrai A) -> Q05+
- Seeds em conflito com derivados -> protegido por design, nao testado
- Retração com multi-valued predicates -> assumido single-valued
- Performance com >1000 facts -> Q04 tem ~10 facts, O(n) scan e trivial

## Err table (ProDeNov 5.4)

| Risco | Prob. | Impacto | Mitigacao |
|---|---|---|---|
| Seed retratado por engano | nula | critico | check `source == "seed"` -> prio 999999 |
| Fato retratado ressuscita | baixa | alto | `retracted` e set permanente |
| Retracao dispara em ciclo errado | baixa | alto | trace + Q04e |
| Cross-cycle loop (A retrai B, B refire) | baixa | critico | NAF sobre vivo previne (utility nao refire com factory presente) |
| Tie-break nao deterministico | baixa | alto | Q04c + rule order |

## Planos A / B / C

- **A (implementado):** prioridade por fato, retracao monotona, seed
  protegido, NAF sobre vivo.
- **B (se cascata for necessaria):** `retracted_by: dict[(s,p,o),
  (s,p,o_new)]` — permite rastrear e desfazer retracao quando o retrator
  e retratado. Custo: ciclo de retracao/des-retracao, mais complexo.
- **C (se multi-valued for necessaria):** `Fact.multi_valued: bool` +
  retracao so para single-valued. Custo: schema de fato mais rico,
  rules declaram cardinalidade.

## Licao

**Prioridade nao resolve cross-cycle conflict sozinha.** Sem retracao,
R_utility (cycle 1) + R_factory (cycle 2) coexistem — engine
within-cycle nao atua em fatos de ciclos distintos.

**Retracao monotona e minimalista.** Nao tenta des-retracoes em
cascata, nao tem rollback, nao reativa fatos. Isso mantem o engine
previsivel. Se Q05 precisar de cascata, e upgrade B explicito.

**NAF sobre vivo previne refire.** Apos retracao de pattern=utility,
NAF de R_utility falha (factory esta em WM). Sem esse detalhe, utility
refiraria cycle 3, factory retrataria cycle 4, loop infinito.
