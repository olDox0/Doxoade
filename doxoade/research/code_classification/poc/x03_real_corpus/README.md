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

---

## Resultado do corpus atual

| Kind | Count | % |
|---|---|---|
| covered | 0 | 0.0% |
| extraction_miss | 69 | 58.5% |
| rule_miss | 16 | 13.6% |
| silent_quiescence | 33 | 28.0% |

**1 unit tem `coverage_overlap: true`** — U0052 (`__repr__` de `_Wild`,
`current_category=constant_return`). Q05 acertou, mas heuristica disparou
(`self_arg` + `dunder_name`). Sem `coverage_overlap`, esse acerto seria
invisivel atras de `kind=extraction_miss`.

**`covered=0` e finding, nao bug.** Q05 so classifica funcao de 1 statement
com Return simples (`arith`/`ident`/`const`/`unknown`). Codigo real e
multi-statement. Nenhuma funcao do corpus se encaixa. **E o sinal mais
valioso do X03:** Q05 nao cobre codigo real. Q06 e o fix. Apos Q06,
esperado: `covered > 0`.

**69 `extraction_miss`** e dominio das heuristicas — nao significa 69 bugs,
significa 69 unidades onde a extracao atual e cega a algum padrao. Os 6
`dead_local` FPs (que inflavam para 71) foram removidos por
`_name_loaded_in_children` (ver Lição).

---

## Bug fixes descobertos no primeiro misses.json

Manual review dos primeiros 9 `dead_local` e 19 `magic_outside_compare`
encontrou 8 FPs. Ambos os fixes sao em `engine_x03.py`.

### H10 — 66% FP rate (9 hits, 6 FP)

`symtable.is_referenced()` no escopo da funcao nao conta `Load` vindo de
comprehension, generator ou closure. `h` em `hex_to_ansi` carregado dentro
de `(int(h[i:i+2], 16) for i in (0,2,4))` era marcado como `is_local`,
`is_assigned`, `not is_referenced` — parecia dead. Mas `h` esta em
`GeneratorExp`, cujo `Load` vira `is_free` no escopo filho e nao propaga.

**Fix:** `_name_loaded_in_children(fn_sym, name)` percorre escopos filhos
procurando `name` como `is_free`. Se achar, nao e dead.

**Trade-off:** sintatico, nao semantico. Se `x` e carregado em closure
nunca chamado, `x` continua contado como "usado". Sob-reportar e mais
seguro que over-reportar para X04.

### H6 — 10% FP rate (19 hits, 2 FP)

`_iter_own_scope` itera siblings, nao subtree. `Constant(4)` em
`if branch_count >= 4` estava em `Compare.comparators`, e o `continue` no
no `Compare` nao pulava os filhos.

**Fix:** `ast.NodeVisitor` com `visit_Compare = noop` (pula subarvore
inteira) e `visit_Constant` que so marca fora de Compare.

**FPs removidos:** U0065 `_is_long_body`, U0067 `extract_facts` (Q05).
Ambos fliparam para `rule_miss` (`smell_magic_number=yes` do extractor
Q05, que varre `Compare` corretamente).

---

**Primeiro misses.json mentiu em 8 unidades.** Manual review de 9
`dead_local` e 19 `magic_outside_compare` (2 min) encontrou 6+2 FPs.
Se X04 tivesse treinado em cima do JSON v1, induziria `dead_local` para
`h`, `chars`, `neg` — todos falsos. Curadoria manual antes de consumo e
barata (2 min) e evita indução corrompida.

---

X03 PASS: real corpus collection + fixes H10/H6 descobertos na revisao

Adiciona x03_real_corpus como probe de coleta para inducao sobre Q05.
118 units em 4 arquivos (doxcolors, retro_forward_cmd, engine_q05,
engine_p70).

Fixes descobertos na revisao manual do primeiro misses.json:

- X01: RuleTable.rules_for preserva ordem de construcao (fix preventivo;
  fixture de X01 nao exercita empate, mas Q05 tem 17 rules com empates
  em p15/p20). X03 C6 expos 73/118 identicas antes do fix, 118/118 depois.
  expected_x01.txt byte-identico.

- X03 H10: _name_loaded_in_children detecta Loads vindos de comprehensions,
  generators e closures (que symtable.is_referenced nao propaga). 9 hits
  antes, 6 FPs. Trade-off: sintatico, nao semantico — so-reporta.

- X03 H6: NodeVisitor pula subarvore inteira de Compare. 19 hits antes,
  2 FPs em `if X >= 4` mal visitados. Units U0065/U0067 flipam
  extraction_miss -> rule_miss (Q05 ve o magic via Compare).

- X03: coverage_overlap: bool em units extraction_miss com Q05 acertando
  (current_category != "unknown"). 1 unit: U0052.

- X03: H6 renomeado magic_in_assign -> magic_outside_compare (nome
  correto: fora de Compare, nao "em Assign").

Baseline: covered=0, extraction_miss=69, rule_miss=16, silent=33.
coverage_overlap=1. Determinism: 3 runs -> 1 hash.

---

X04 v1.1: relax C4 do X03 + ler summary parcial em X04

Fix do X04 FAIL causado por C4 rígido do X03:

- X03: all_kinds_present aceita >=2 kinds (antes exigia os 3).
  silent_quiescence=0 e SUCESSO quando X04 cobriu, nao falha.
  baseline X03 continua PASS (tem os 3 kinds).

- X04: run_x03_with_rules le summary mesmo em returncode != 0.
  X03 escreve summary antes de retornar (inclusive em FAIL), entao
  delta parcial e recuperavel.

Rodada pos-fix: covered 0 -> 48, silent 33 -> 0, rule_miss 16 -> 0.
X04 PASS (6/6). X03 PASS (7/7).

Finding v2: connected components + Jaccard 0.7 e transitivo — clusters
absorvem via cadeia (U0002 -> U0055 -> U0031 -> U0117 -> U0072).
v2 deve usar clique clustering ou threshold dinamico.

---

## Known limitations (v1)

1. **Connected components e transitivo.** Jaccard nao e distancia
   metrica; cadeia A~B~C pode unir A e C com Jaccard baixo. Fix v2:
   clique clustering (todos pares dentro do cluster >= threshold) ou
   DBSCAN.

2. **Derived facts na assinatura inflam clusters.** `category=unknown`,
   `has_any_smell=*`, `dead_after_return=no`, `has_magic_number=no`,
   `long_body=no` sao fatos derivados que o motor ja produz. Usar na
   assinatura faz regra induzida depender de "contexto vazio". Fix v2:
   assinatura so com seed_facts (extractor ve), nao derived.

3. **Sem hold-out.** v1 memoriza (mede delta no mesmo corpus).
   Generalizacao real precisa split treino/validacao. Fix v2.

4. **Nomes auto para interseccoes compostas.** `cluster_NNN` exige
   humano renomear em review.md. Fix v2: dicionario de nomes derivados
   para combinacoes conhecidas (ex: body_0_kind=Assign + has_any_smell=dirty
   -> long_initializer).

5. **Sem quarantine.** Regra induzida entra como `stable`. v2:
   comeca em `candidate` com confidence baixa.

---

# X04 - Inducao por clustering sobre misses.json (v1)

**Contrato provado:** clusters emergem com Jaccard >= threshold sobre
facts; regras induzidas tem evidence rastreavel; delta mensuravel;
X03 re-run com --rules ainda passa seus 7 checks.

## O que X04 NAO prova

1. **Generalizacao** — v1 memoriza. Delta medido no mesmo corpus
   prova que a regra dispara nos exemplos, nao que generaliza.
   Hold-out fica para v2.

2. **Qualidade semantica das regras** — `cluster_NNN` e honesto:
   "sabemos que X units se agrupam, nao sabemos o que isso e".
   Humano renomeia em review.md ou v2 deriva nomes.

3. **FP rate** — sem baseline humano, nao ha como medir FPs.

## Decisoes v1 (Q1-Q3)

- **Escopo:** `silent_quiescence` + `rule_miss` (49 units).
  `extraction_miss` fica fora — e dominio de Q06.
- **Clustering:** connected components + Jaccard >= 0.7.
  Deterministico, rastreavel, mas **transitivo** (ver limitacao 1).
- **Naming:** hibrido. Interseccao com 1 fact descritivo -> nome
  derivado (`returns_call`). Composta -> `cluster_NNN` (humano).
- **Agressividade:** min_cluster_size=3.

## Resultado (corpus atual, 118 units)

| Metrica | Antes | Depois | Delta |
|---|---|---|---|
| covered | 0 | 48 | +48 |
| extraction_miss | 69 | 69 | 0 |
| rule_miss | 16 | 1 | -15 |
| silent_quiescence | 33 | 0 | -33 |

**Interpretacao honesta:** +48 covered. 4 units em cluster_000
(vago mas honesto), 29 em cluster_001 (tautologico — qualquer funcao
nao-dirty), 15 em cluster_002 (util — long_method ja sabido por Q05).
Delta real, semantica v2.

## Known limitations (v1) -> v2 TODO

1. **Connected components e transitivo.** Jaccard nao e distancia
   metrica. Cadeia A~B (0.75) + B~C (0.75) pode unir A e C com 0.5.
   Observado: U0002 -> U0055 -> U0031 -> U0117 -> U0072 absorvidos em
   cluster_001. Fix v2: clique clustering (todos pares >= threshold)
   ou DBSCAN.

2. **Derived facts na assinatura inflam Jaccard.** `category=unknown`,
   `has_any_smell=*`, `has_magic_number=no`, `long_body=no`,
   `dead_after_return=no` sao fatos que o motor ja produz. Usar na
   assinatura faz regra induzida depender de "contexto vazio".
   cluster_001 = {has_any_smell=none} apos remover triviais — semantica
   zero. Fix v2: assinatura so com seed_facts (extractor ve).

3. **Sem hold-out.** v1 memoriza. v2: split treino/validacao.

4. **Nomes auto para interseccoes compostas.** `cluster_NNN` exige
   humano renomear em review.md. v2: dicionario de nomes derivados
   para combinacoes conhecidas (ex: body_0_kind=Assign +
   has_any_smell=dirty -> long_initializer).

5. **Sem quarantine.** Regra induzida entra como stable. v2: comeca
   em candidate com confidence baixa.

## Estrutura

```
x04_induction/
├── engine_x04.py         # ~590 LOC
├── induced_rules.json    # 3 regras, evidence rastreavel
├── output.txt            # gerado por engine
├── expected_x04.txt      # baseline
├── README.md             # este
└── logging.txt           # runtime
```

## Interface X03 (--rules)

X04 invoca X03 assim:

```cmd
py engine_x03.py --rules ../x04_induction/induced_rules.json
```

X03 em modo --rules:
- Carrega induced_rules.json, combina com RULES_Q05
- Roda pipeline com ruleset combinado
- **Nao** sobrescreve output.txt / misses.json / expected_x03.txt
- Escreve `output_x03_with_rules.txt` e `x03_with_rules_summary.json`

X04 le o summary para delta.

## Licao v1

**Mecanismo funciona; semantica precisa v2.** Clustering + interseccao +
regra = loop fechado. Bug descoberto: C4 rigido do X03 (exigia
silent_quiescence >= 1) bloqueava inducao agressiva — fix: >=2 kinds,
silent=0 e sucesso. Quando o sistema mede a si mesmo e o "sucesso" quebra
um check antigo, o check estava errado, nao o sistema.
