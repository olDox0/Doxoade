# doxoade/research/forward_chaining/poc/00_fizzbuzz/README.md
# P00 — FizzBuzz smoke test

**Contrato:** C1 (Inferência). Prova que MATCH → SELECT → FIRE → quiescência
**termina, deriva e rastreia** sobre 100 inputs com regras positivas apenas.

## O que prova
- Terminação em quiescência (`fired_this_cycle = False` → break).
- Derivação correta (`out` == oráculo em 100/100).
- Rastreio (`trace` contém regra, condições, conclusão, ciclo).
- Prioridades respeitadas na varredura (stable sort por `-priority`).

## O que NÃO prova (deixa para as próximas)
- Ciclos reais → **P01** (`max_cycles` aqui é rede de segurança, não teste).
- Conflito entre regras → **P02** (FizzBuzz particiona div3/div5; nunca há disputa).
- Unificação / variáveis → **P20** (`out=X` copiaria `n` para `out`).
- Negação como falha → **P21** (aqui usamos `div5=no`, não `NOT`).

## Err table (ProDeNov 5.4)
| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Loop infinito | baixa | alto | `max_cycles=100` + `CycleLimitError` |
| Regra dispara sem match | baixa | alto | `Rule.match` testada em teste de mesa |
| Trace incompleto | baixa | médio | `trace` comparada a `expected.txt` |
| `except` silencioso | nula | alto | todo ponto crítico loga em `logging.txt` |

## Plano A / B / C (ProDeNov 1.2.1)
- **A (implementado):** varredura `sorted(-priority)` por ciclo, `out` idempotente.
- **B (se não termina em `max_cycles`):** adicionar `_fired_signatures: set[(rule_id, frozenset(fact_pairs_used))]` e pular combinações já disparadas. É o que P01 formaliza.
- **C (se B ainda falha):** bug no matcher → parar a escada, revisar `Rule.match`.

## Ciclo de vida
Passa → anotar lição em `docs/research/poc_notes.md`, **descartar o código**.
Nada migra para `src/`. O que sobrevive é `Fact` / `Rule` / `Engine.run(trace)`
como **contrato C1**.

---

# P01 — Terminação em ciclo e falha loud

**Contrato:** C1 (Inferência) — extensão de P00.

## O que prova

### P01a — ciclo de regras quiesce via idempotência
Seed `x=1`; regras `x→y→z→x`. R3 tenta derivar `x=1` no ciclo 1, mas
o fato já existe. Idempotência + monotonicidade garantem quiescência
em 2 ciclos, sem `CycleLimitError`.

### P01b — cadeia > `max_cycles` falha explicitamente
6 regras em cadeia com `max_cycles=3`. O engine **não** para em silêncio:
levanta `CycleLimitError` com contagem de trace. `logging.txt` registra
o erro.

## O que NÃO prova (deixa para as próximas)
- Conflito real entre regras → **P02** (aqui R1/R2/R3 nunca disputam).
- Unificação → **P20** (`out=X` copiaria `n`).
- Negação como falha → **P21** (não usada aqui).

## Mecanismo de terminação — declarado
Duas condições garantem quiescência:
1. **Monotonicidade:** `facts` só cresce, nunca remove.
2. **Idempotência:** `if any(f.to_pair() == new_fact.to_pair())` skip.

Essas duas juntas implicam: cada regra dispara no máximo `|conclusão|`
vezes. Como o conjunto de conclusões é finito, o motor termina — a menos
que `max_cycles` seja atingido por cadeia longa, caso em que P01b
demonstra falha loud.

## Err table (ProDeNov 5.4)
| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Ciclo silencioso | baixa | alto | P01a + P01b juntos |
| `CycleLimitError` não levantado | baixa | alto | teste em `run_p01b` |
| Trace incompleto | baixa | médio | `trace_len` verificado |
| Loop com regra nova a cada ciclo | baixa | alto | fora do escopo de C1; exigiria unificação (P20) |

## Planos A / B / C
- **A (implementado):** monotonicidade + idempotência.
- **B (se B falha):** `_fired_signatures: set[(rule_id, frozenset(fact_pairs))]`
  — impede re-fire mesmo se P00 for relaxado.
- **C (se A e B falham):** `max_cycles` muito baixo → investigar quantos
  ciclos são realmente necessários, não mascarar.

## Lição
"Ciclo de regras" não causa loop porque o engine é **monotônico**. A falha
loud (`CycleLimitError`) é o que importa: `max_cycles` não é uma rede de
segurança silenciosa, é uma *condição de falha declarada*.

---

# P01 — Terminação em ciclo e falha loud

**Contrato:** C1 (Inferência), extensão de P00.

## Semântica de ciclo — DECLARADA

Um **ciclo** é uma rodada de match sobre um **snapshot congelado** da
memória de trabalho, seguida de fire dos novos fatos.

Consequências:
1. Regras do mesmo ciclo **não veem** fatos derivados por outras regras
   do mesmo ciclo.
2. Ordem de iteração das regras é **irrelevante** para o resultado.
3. Cadeias lineares `a0→a1→...→aN` exigem N ciclos.
4. `max_cycles` conta **rodadas de match**, não disparos.

Isso contrasta com a semântica "varredura contínua" (sem snapshot),
na qual a cadeia propaga em 1 rodada. Essa escolha foi feita porque
ordem de iteração em varredura contínua produz resultado **dependente
de ordem** — o que é não-determinismo acidental.

## O que prova

### P01a — ciclo de regras quiesce via idempotência
Seed `x=1`; R1: x→y, R2: y→z, R3: z→x.
- Ciclo 1 dispara R1 (y=1).
- Ciclo 2 dispara R2 (z=1).
- Ciclo 3 tenta R3 (x=1), mas x=1 já existe → quiesce.
Total: 3 ciclos, 2 entradas em trace.

### P01b — cadeia > `max_cycles` falha explicitamente
Cadeia de 6 regras com `max_cycles=3`. Ciclos 1–3 disparam R_00, R_01, R_02
e o limite corta antes da quiescência. `CycleLimitError` é levantado com
mensagem explícita. Trace tem 3 entradas — o que foi derivado antes do erro.

## O que NÃO prova (deixa para as próximas)
- Conflito real entre regras → **P02**.
- Unificação → **P20**.
- Negação como falha → **P21**.

## Mecanismo de terminação — declarado
1. **Snapshot congelado:** match nunca depende de ordem.
2. **Monotonicidade:** `facts` só cresce.
3. **Idempotência:** `pair in existing or pair in seen_in_cycle` skip.

Isso garante: cada regra dispara no máximo uma vez por fato; a memória
cresce finitamente; a menos que `max_cycles` corte por cadeia longa
(que é justamente o que P01b testa).

## Err table (ProDeNov 5.4)
| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Ciclo silencioso | baixa | alto | P01a + P01b juntos |
| `CycleLimitError` não levantado | baixa | alto | teste em `run_p01b` |
| Ordem de iteração afetar resultado | nula | alto | snapshot elimina por construção |
| Trace incompleto | baixa | médio | `trace_len` verificado |

## Planos A / B / C
- **A (implementado):** snapshot + idempotência + monotonicidade.
- **B (se B falha):** `fired_signatures: set[(rule_id, frozenset(fact_pairs))]`
  como cache extra. Custo: memória O(R × F). Só se A não bastar.
- **C (se A e B falham):** `max_cycles` foi mal calibrado — investigar
  cadeia real, não mascarar.

## Lição (descoberta durante a sonda)
A pergunta "o que é um ciclo?" **não é detalhe de implementação**. É a
primeira decisão de contrato do motor. Sem snapshot, ordem importa; com
snapshot, ordem não importa. P00 e P01a não distinguiam as duas
semânticas porque suas cadeias eram curtas. P01b forçou a escolha.
Foi preciso **reescrever o expected** depois de reconhecer a ambiguidade
— o que é o comportamento correto quando o contrato não estava claro.

---

# P01 - Terminacao em ciclo e falha loud

**Contrato:** C1 (Inferencia) - extensao de P00.

## Semantica de ciclo - DECLARADA

Um ciclo e uma rodada de match sobre SNAPSHOT congelado, seguida de fire.
Regras do mesmo ciclo nao veem fatos derivados por outras regras do
mesmo ciclo. Ordem de iteracao das regras e irrelevante para o resultado.

Cadeias lineares `a0 -> a1 -> ... -> aN` exigem N ciclos.
`max_cycles` conta rodadas de match, nao disparos.

## O que prova

### P01a - ciclo de regras quiesce via idempotencia
Seed `x=1`; R1: x->y, R2: y->z, R3: z->x.
- Ciclo 1 dispara R1 (y=1).
- Ciclo 2 dispara R2 (z=1).
- Ciclo 3 tenta R3 (x=1), mas x=1 ja existe -> quiesce.
Total: 3 ciclos, 2 entradas em trace.

### P01b - cadeia > max_cycles falha explicitamente
Cadeia de 6 regras com `max_cycles=3`. Ciclos 1-3 disparam R_00, R_01,
R_02 e o limite corta antes da quiescencia. `CycleLimitError` levantado
com mensagem explicita. Trace tem 3 entradas - o que foi derivado antes
do erro.

## O que NAO prova
- Conflito entre regras -> P02.
- Unificacao -> P20.
- Negacao como falha -> P21.

## Mecanismo de terminacao - declarado
1. Snapshot congelado: match nunca depende de ordem.
2. Monotonicidade: `facts` so cresce.
3. Idempotencia: `pair in existing or pair in seen_in_cycle` skip.

## Lição
"Ciclo" e decisao de contrato, nao detalhe. Sem snapshot, ordem importa;
com snapshot, ordem nao importa. P00 e P01a nao distinguiam as duas
semanticas. P01b forcou a escolha.

---
