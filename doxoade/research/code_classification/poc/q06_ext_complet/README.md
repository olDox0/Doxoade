# doxoade/research/code_classification/poc/q06_ext_complet/README.md
# Q06 - Extraction completeness

Problema (dado de X03): 69 `extraction_miss` no corpus. Diagnostico
mostrou que o gap nao e multi-function (0 units) — e extracao
incompleta. 4 heurísticas dominam:

| Heuristica | Cegueira real | Q05 ja viu |
|---|---|---|
| self_arg | 37 | 1 |
| dunder_name | 17 | 1 |
| magic_outside_compare | 17 | 0 |
| decorator | 14 | 0 |

## Estrutura

`q06_ext_complet/` mantem 4 sub-probes flat + 1 orquestrador.
`q06a..d` rodam individualmente (`py q06a_self_arg.py`); `engine_q06.py`
agrega (`retro-forward run q06`).

Razao: 4 sub-probes sao uma **familia** sobre o mesmo problema
(extraction completeness). 4 PoCs numerados separados inflariam o
`retro-forward list` com sondas que nao sao independentes.

## Sub-probes

| ID | Resolve | Cegueira | Status |
|---|---|---|---|
| Q06a | self_arg (has_self_arg + method_role) | 37 | implementado |
| Q06b | dunder_name (is_dunder) | 17 (marginal ~3) | PENDING |
| Q06c | magic_outside_compare (corrige `_has_magic_number`) | 17 | PENDING |
| Q06d | decorator (has_decorator + decorator_names) | 14 | PENDING |

## Ordem de implementacao

Por **cegueira marginal** (nao hits brutos):

1. Q06a (37) — resolve self_arg, derruba dunder_name para ~3 e
   dead_local para parcialmente.
2. Q06c (17) — independe de self_arg.
3. Q06d (14) — independe de self_arg.
4. Q06b (~3) — quase tudo era dunder+self, Q06a ja resolveu.

## Contrato Q06 (agregado)

`engine_q06.py` e o entrypoint. Exit codes:
- 0 = todos 4 PASS
- 2 = algum PENDING (parcial)
- 1 = algum FAIL

`retro-forward run q06` aceita `PARTIAL PASS` (exit 2) sem falhar — o
sistema entende que Q06 esta sendo construido incrementalmente.

Depois que os 4 sub-probes passarem, X03 re-roda com extractors Q06a-d
combinados (futuro `--extractor q06` ou `lib/` consolidado em Q10).

## Independencia dos sub-probes

Cada Q06x duplica o kernel Q05 + extractor + rules. ~500 LOC por
sub-probe. Duplicacao conhecida, aceita por padrao Q00-Q05 (PoC nao
importa de PoC).

Quando Q10 consolidar, os 4 extractors fundem em `lib/`. Por ora,
4 copias coexistem.

## Nota sobre self_arg como `method_role` (nao `category`)

Q06a **nao substitui** `category`. Adiciona **nova dimensao**
ortogonal: `method_role` (initializer, getter, repr, method). Ambas
coexistem. Q05 da `category=constant_return`, Q06a da
`method_role=initializer` — o motor ganha informacao, nao perde.

Razao: categorizar `category` como "method_init" **perderia** a
informacao funcional (constant_return, arithmetic_return). Duas
dimensoes e mais honesto que uma categotegoria combinada.

## Estatuto incremental

Q06a primeiro, permite `retro-forward run q06` funcionar (PARTIAL
PASS) e `accept q06`. Q06b/c/d adicionados um a um, cada um regenera
`expected_q06.txt` via accept. Sem big-bang.

---

Q06a PASS: self_arg extraction + method_role (Q06 partial)

Primeiro sub-probe de Q06 (extraction completeness). Resolve cegueira
real de self_arg: 37 de 38 units com self_arg=yes ficavam category=unknown
em X03 v2 — Q05 nao ve `self`.

Q06a adiciona:
- has_self_arg, is_dunder como seed facts
- method_role (dimensao ortogonal a category): initializer, getter,
  repr, method
- Q06a1..Q06a5 sub-sondas (method init, getter, passthrough function,
  method dunder repr, determinism 100 runs)

engine_q06 (orquestrador) roda 4 sub-probes via subprocess. q06b/c/d
sao stubs PENDING. Retorna 0 em PARTIAL PASS (falha so' quando um
sub-probe quebra — pending e' estado honesto, nao falha).

Baseline: expected_q06.txt contem "Q06 PARTIAL PASS" (q06a PASS,
q06b/c/d PENDING). retro-forward all: 22/22.

Proximo: Q06c (magic_outside_compare, cegueira 17, independe de self_arg).

---

Q06a PASS: self-arg extraction em corpus real (X03 v3)

Q06a em q06_ext_complet resolve 35 de 37 units com self_arg=yes no
corpus X03 (94% success rate). Adiciona:
- has_self_arg, is_dunder como seed facts
- Q06A_RULES: method_role (initializer, getter, repr, method)
- method_role e' dimensao ortogonal a category; Q05 continua
  classificando (const/arith/ident/unknown), Q06a adiciona papel
  funcional do metodo

X03 v3:
- extractor emite has_self_arg, is_dunder
- _heuristic_resolved() + classify_kind() com heuristics resolvidas
- resolved_heuristics / unresolved_heuristics por unit (rastreabilidade)
- method_role incluido em _extract_result

Cleanup:
- Q06A_RULES + RULES_Q05 movidos para posicao canonica (antes de
  _build_table, nao apos _run_pipeline — patch anterior colocou em
  local errado por colagem)
- main() deduplicado (bloco morto apos return)
- _render_output: bloco morto removido

Delta v2 -> v3:
- covered:       0  -> 35  (+35)
- extraction_miss: 69 -> 31 (-38, todos self_arg)
- rule_miss:     16 -> 16  (0)
- silent_quiescence: 33 -> 36 (+3, dunder sem self)

31 extraction_miss restantes: 17 magic_outside_compare (Q06c) +
14 decorator (Q06d). Q06c/Q06d zerariam extraction_miss.

q06_ext_complet: PARTIAL PASS (1 PASS, 3 PENDING).
retro-forward all: 22/22 (apos accept cascata x03 + x04).

Proximo: Q06c (magic_outside_compare, 17 units).
