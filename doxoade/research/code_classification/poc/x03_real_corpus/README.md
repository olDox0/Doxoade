# doxoade/research/code_classification/poc/x03_real_corpus/README.md
# X03 - Real corpus collection for induction

**Contrato provado:** motor roda em codigo real sem crash; cada
`FunctionDef` do corpus e catalogada em `misses.json`; flat == table
em 17 rules Q05 reais.

## Diferenca de X01

X01 provou que `RuleTable` filtra por domain **sem perder** resultado em
fixture sintetica. X03 prova duas coisas novas:

1. `RuleTable` **preserva ordem** em cenario real (17 regras, empates em
   prioridade). X01 nao exercitou — fixture tem 4 prioridades distintas.
2. Motor roda em codigo real (doxoade, 4 arquivos, ~2.000 LOC) sem crash.

## O que X03 NAO e

- **Nao e auditor.** Nao decide se codigo esta bom ou ruim.
- **Nao e linter.** Nao detecta bugs. `apply_tags` em `doxcolors.py` tem
  `NameError` real (`rendered_text`); H9 ve o bug, mas `H9` nao ve se
  o `NameError` ocorre — so ve que o nome nunca foi ligado em lugar algum.
- **Nao e curadoria.** FPs de heuristica sao aceitos; X04 filtra.
- **Nao e generalizacao.** Um dominio (Python), quatro arquiteturas.

## O que X03 e

- **Coleta.** Cada `FunctionDef` vira um registro em `misses.json`, com
  categoria, fatos seed, fatos derivados, heuristica detectada.
- **Baseline.** `expected_x03.txt` e golden reference; `misses.json` e
  versionado — drift detectavel via diff do `corpus_hash`.
- **Sensor.** As 4 categorias map para 3 alvos:

| Kind | Alvo | Significado |
|---|---|---|
| `extraction_miss` | Q06 | Extractor nao ve o que o humano ve |
| `rule_miss` | X04 | Motor viu (pattern/smell), mas nao classificou |
| `silent_quiescence` | X06 | Motor nao viu nada de util |
| `covered` | (negative) | Motor classificou |

## Corpus (fechado, ~2.000 LOC, 4 arquiteturas)

| # | Arquivo | LOC | Units | Arch |
|---|---|---|---|---|
| 1 | `doxoade/tools/doxcolors.py` | ~500 | 29 | classes + threading + builtins.print patch |
| 2 | `doxoade/commands/retro_forward_cmd.py` | ~650 | 15 | click, subprocess, IO |
| 3 | `doxoade/.../q05_smell/engine_q05.py` | ~700 | 34 | kernel denso, dataclasses |
| 4 | `doxoade/.../70_substitutable_matcher/engine_p70.py` | ~600 | 40 | classes + matchers |

**Total: 118 units catalogadas.** Fechado por enquanto; expansao aceita
depois que X04 produzir sinal sobre o corpus atual.

## Heuristicas H1-H10

| # | Nome | Detecta | Alvo |
|---|---|---|---|
| H1 | `async_def` | `AsyncFunctionDef` | Q06 |
| H2 | `self_arg` | 1o arg == "self" | Q06 |
| H3 | `decorator` | `decorator_list != []` | Q06 |
| H4 | `yield_expr` | `ast.Yield` / `YieldFrom` no body | Q06 |
| H5 | `recursive_call` | `ast.Call` cujo `func.id == node.name` | Q06 |
| H6 | `magic_outside_compare` | int nao-trivial fora de `Compare` | Q06 |
| H7 | `dead_nested` | `Return` em `If`/`For`/`While` + stmt irmao | Q06 |
| H8 | `dunder_name` | `node.name.startswith("__")` | Q06 |
| H9 | `undefined_name` | `Name(Load)` sem binding em scope | Q06 |
| H10 | `dead_local` | binding local sem `Load` | Q06 |

**Todas mapeiam para Q06.** Nenhuma toca o motor. Curadoria (remover FPs)
fica em X04.

H9 e H10 usam `symtable` (stdlib) — full scope-aware: closure, `global`,
`nonlocal`, comprehension, lambda, class body. Nao usam AST-walk ingênuo
que geraria FPs em codigo valido.

## Resultado do corpus atual

| Kind | Count | % |
|---|---|---|
| covered | 0 | 0.0% |
| extraction_miss | 71 | 60.2% |
| rule_miss | 14 | 11.9% |
| silent_quiescence | 33 | 28.0% |

**`covered=0` e finding, nao bug.** Q05 so classifica funcao de 1 statement
com Return simples (`arith`/`ident`/`const`/`unknown`). Codigo real e
multi-statement. Nenhuma funcao do corpus se encaixa. **E o sinal mais
valioso do X03:** Q05 nao cobre codigo real. Q06 e o fix. Apos Q06,
esperado: `covered > 0`.

**71 `extraction_miss`** e dominio das heuristicas — nao significa 71 bugs,
significa 71 unidades onde a extracao atual e cega a algum padrao.

## Self-check (7 checks, todos em `main`)

| # | Check | O que valida | Limite |
|---|---|---|---|
| C1 | `corpus_processed` | 4/4 arquivos parseados | >=1 unit por arquivo |
| C2 | `min_misses` | corpus tem sinal | >=5 non-covered |
| C3 | `miss_diversity` | nao e "tudo de 1 arquivo" | >=2 arquivos com miss |
| C4 | `all_kinds_present` | corpus cobre as 3 categorias de miss | extraction+rule+silent |
| C5 | `heuristics_per_file` | cada arquivo exercita extracao | >=1 heuristica por arquivo |
| C6 | `identity` | flat.trace == table.trace em 100% | todas as units |
| C7 | `determinism` | 3 runs -> mesmo hash (sem `generated_at`) | 1 hash unico |

**Se qualquer check falha, `misses.json` NAO e escrito.** Evita commit de
artefato ruim. `output.txt` sempre e escrito (diagnostico).

## C6 — o teste que X01 nao fez

X01 tem fixture com 4 prioridades distintas (10, 15, 1, 20). Nenhum empate
-> `sorted(-priority)` totalmente determinado -> bug de ordem em `RuleTable`
nao dispara.

X03 tem 17 regras com **empates em p15 e p20** -> ordem importa -> 73/118
identicas antes do fix.

**Bug descoberto pelo X03:** `RuleTable.rules_for` usava `set` internamente,
perdendo ordem de construcao. `sorted` stable preserva ordem de entrada em
empate. Sem fix: `flat.trace != table.trace` em qualquer ciclo com multiplas
regras `dirty_*` disparando (mesmo predicado `has_any_smell`, mesma prio 20).

**Fix:** iterar `self._rules.values()` (dict, insertion order garantido
Py3.7+) em vez de `for i in ids` (set, ordem arbitraria).

**Propagacao:** `engine_x01.py` recebeu o mesmo fix preventivamente.
X01 continua PASS porque fixture nao exercita o bug. `expected_x01.txt`
byte-identico.

## Err table

| ID | Risco | Prob | Impacto | Mitigacao |
|---|---|---|---|---|
| E1 | `ast.parse` falha | baixa | medio | try/except por arquivo; kind=`parse_error`, segue |
| E2 | `extract_facts_adapted` diverge de Q05 | baixa | critico | verbatim de Q05 + async; C6 detecta |
| E3 | FP de heuristica sistematico | media | medio | X03 cataloga, X04 filtra |
| E4 | Corpus tem <5 misses | baixa | alto | corpus atual gera 118 units |
| E5 | RuleTable diverge de flat | baixa | critico | C6; achou bug real e foi fixado |
| E6 | `units` grande (>20k) | baixa | medio | split por arquivo + `_summary.json` |
| E7 | Nao-determinismo por `id()` hash | baixa | alto | `id` ordinal `U0001..`, nao hash |
| E8 | H9/H10 geram FPs em massa | baixa | medio | symtable full scope-aware; se virar problema, X04 |

## Planos A / B / C

- **A (implementado):** Q05 extractor adapted, H1-H10, flat+table em paralelo,
  `misses.json` completo com `covered` + misses.
- **B (se `misses.json` fica grande):** `covered` truncado para
  `(id, file, unit_name, kind, current_category)`; misses completos.
  Aplicar so quando passar de ~5.000 units.
- **C (se corpus diverge muito):** split por arquivo; `_summary.json`
  agregado por script separado.

## Licao

**X01 mente no fixture, X03 corrige.** Probes sinteticos provam o que o
fixture exercita. O fixture de X01 era bom para testar "filtra por domain
sem perder", ruim para testar "preserva ordem" — que o README prometia mas
o codigo nao fazia. X03 expos.

**`covered=0` nao e bug, e finding.** Q05 foi calibrado para PoCs curtos
(Q00-Q05 tem 1 statement). Codigo real nao e assim. X03 e o sensor que
diz isso com numero.

**Heuristicas nao sao bugs, sao cegueiras.** 71 `extraction_miss` nao
significa "71 bugs". Significa "71 lugares onde a extracao atual nao ve
o que o humano ve". Q06 as transforma em `covered` ou as refuta
(`extraction_miss` virando `covered` = extraiu e classificou).
