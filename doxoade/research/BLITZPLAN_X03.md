# X03 — Real corpus collection for induction

**PoC:** X03 (linha code_classification / RuleTable research)
**Depende de:** Q05 (extractor), X01 (RuleTable)
**Contrato provado (se PASS):** motor roda em código real sem crash;
cada `FunctionDef` do corpus é catalogada em `misses.json`; flat ≡
table em 17 rules reais.

---

## Objetivo

X03 **não** é probe de feature. É **coleta de dados para indução** (X04).
Produz corpus rotulado de negativos-de-cobertura.

Cada `FunctionDef` recebe uma das 4 categorias:

| Categoria | Significado | Alvo |
|---|---|---|
| `covered` | Motor classificou (category ≠ unknown) | negativo |
| `extraction_miss` | Heurística flagou; extractor não vê | Q06 |
| `rule_miss` | unknown + pattern/smell disparou | X04 |
| `silent_quiescence` | unknown + sem pattern + sem smell | X06 (backward) |

`silent_quiescence` é o sinal mais forte: motor viu os fatos, nenhuma
regra específica casou.

---

## Corpus (fechado, ~2.000 LOC)

| # | Arquivo | LOC | Arquitetura |
|---|---|---|---|
| 1 | `doxoade/tools/doxcolors.py` | ~500 | classes + threading + builtins.print patch |
| 2 | `doxoade/commands/retro_forward_cmd.py` | ~650 | click, subprocess, IO |
| 3 | `doxoade/research/code_classification/poc/q05_smell/engine_q05.py` | ~700 | kernel denso, dataclasses |
| 4 | `doxoade/research/forward_chaining/poc/70_substitutable_matcher/engine_p70.py` | ~600 | classes + matchers |

Flexibilidade: expandir corpus é possível, mas cada arquivo novo
adiciona ruído. Preferir expandir depois de ver o primeiro misses.json.

---

## Fluxo

```
para cada arquivo:
  try: tree = ast.parse(open(file).read())
  except SyntaxError: marca arquivo como parse_error, segue para o próximo

  para cada FunctionDef ou AsyncFunctionDef em tree (walk):
    (1) seed = extract_facts_adapted(node)
        - Duplica Q05 (`_count_branches`, `_name_prefix`,
          `_has_magic_number`, `_is_long_body`, `_has_dead_after_return`)
        - Aceita AsyncFunctionDef (extrai igual + marca H1)
        - Filtra docstring (Q01 padrão)
    (2) result_flat = Engine.run(seed, RULES_Q05)
    (3) result_table = Engine.run(seed,
                          RuleTable(rules=RULES_Q05,
                                    domain_index={"programming": [...all...]})
                          .rules_for(domain="programming"))
    (4) assert result_flat.trace == result_table.trace   # identidade X01→Q05
    (5) heuristics = [H1..H8](node) → lista de nomes que dispararam
    (6) kind = classify(result_flat, heuristics)
    (7) append ao catálogo

100 runs sobre (1)-(7) → assert mesmo sha256 do json sem `generated_at`
dump misses.json versionado
self-check em main() → PASS/FAIL
```

---

## Heurísticas H1–H8

| # | Nome | Detecta | Alvo |
|---|---|---|---|
| H1 | `async_def` | `AsyncFunctionDef` | Q06 |
| H2 | `self_arg` | 1º arg == "self" | Q06 |
| H3 | `decorator` | `node.decorator_list != []` | Q06 |
| H4 | `yield_expr` | `ast.Yield` / `YieldFrom` no body | Q06 |
| H5 | `recursive_call` | `ast.Call` cujo `func.id == node.name` | Q06 |
| H6 | `magic_in_assign` | int ∉ {0,1,-1} em `Assign`/`BinOp`/`If` (**fora** `Compare`) | Q06 |
| H7 | `dead_nested` | `Return` em `If`/`For`/`While` + stmt irmão | Q06 |
| H8 | `dunder_name` | `node.name.startswith('__')` | Q06 |

Nenhuma heurística toca o motor. AST-walk local. FPs vão para X04
revisar (Q3: só coleta, curadoria depois).

---

## misses.json — schema

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-11-13T...",
  "corpus_hash": "sha256(concat dos 4 sha256 de arquivo)",
  "engine_config": {
    "extractor": "q05_adapted",
    "rules_id": "q05_flat_17",
    "rules_count": 17,
    "max_cycles": 100
  },
  "units_analyzed": 220,
  "units_by_kind": {
    "covered": 45,
    "extraction_miss": 18,
    "rule_miss": 12,
    "silent_quiescence": 145
  },
  "units": [
    {
      "id": "U0001",
      "file": "doxoade/tools/doxcolors.py",
      "unit_name": "safe_print",
      "lineno": 87,
      "end_lineno": 95,
      "class_context": null,
      "kind": "extraction_miss",
      "detected_by": ["heuristic:recursive_call"],
      "seed_facts": [
        ["safe_print", "kind", "function"],
        ["safe_print", "has_docstring", "yes"],
        ["safe_print", "body_len", "4"],
        ["safe_print", "branch_count", "3"]
      ],
      "derived_facts": [
        ["safe_print", "category", "unknown"],
        ["safe_print", "complexity", "3"],
        ["safe_print", "smell_long_method", "yes"],
        ["safe_print", "has_any_smell", "dirty"]
      ],
      "current_category": "unknown",
      "current_pattern": null,
      "suggested_target": "Q06"
    }
  ]
}
```

**Completo (Q7):** `units` inclui `covered`. ~900 entradas no corpus
atual. Benefício: X04 usa `covered` como negative examples.

---

## classificação (kind)

```
if heuristics != []:              kind = "extraction_miss"
elif category != "unknown":        kind = "covered"
elif pattern or any smell_*:       kind = "rule_miss"
else:                              kind = "silent_quiescence"
```

Único caso ambíguo: heurística dispara **E** category != unknown
(ex: método com `self` **e** `smell_long_method`). Decisão: vence
`extraction_miss`. Justificativa: a heurística aponta uma lacuna que
importa mais que o acerto do smell.

---

## Self-check (Q8) — dentro do engine

`main()` de `engine_x03.py` roda:

1. Corpus processado (4 arquivos, sem `parse_error` inesperado)
2. `>= 5 misses` (excluindo `covered`)
3. `>= 1 miss em >= 2 arquivos` (não pode ser "tudo de um")
4. `>= 1 extraction_miss` **e** `>= 1 rule_miss` **e** `>= 1 silent_quiescence`
5. `>= 1 heurística dispara por arquivo` (senão corpus não exercita aquela arquitetura)
6. `flat.trace == table.trace` em todas as 220 unidades
7. 100 runs → mesmo sha256 do json sem `generated_at`

PASS → `output.txt` com sumário; `misses.json` gerado.
FAIL → `output.txt` com falhas, `misses.json` **não** é produzido.

---

## Versionamento (Q6)

`misses.json` versionado em git. `corpus_hash` embutido. Se qualquer
dos 4 arquivos mudar, regenerar e commitar com nota no formato:
`X03: regenerate (corpus_hash <novo> from <antigo>)`. Drift detectável
por diff do hash.

---

## Fora de escopo (registrar no README para evitar drift)

- Que misses são "verdadeiras" (X04 decide)
- Curadoria de heurísticas (X04 revisa FPs)
- Bug do `#` no intelligence (escopo do intelligence)
- Indução automática (X04+)
- Generalização cross-domain (Q09)
- Performance (>5s em 4 arquivos)
- Análise semântica de runtime
- Detecção de bug de código (X03 é cobertura, não linter)

---

## Err table

| ID | Risco | Prob | Impacto | Mitigação |
|---|---|---|---|---|
| E1 | `ast.parse` falha | baixa | médio | try/except por arquivo; kind=`parse_error`, segue |
| E2 | `extract_facts_adapted` diverge de Q05 | baixa | crítico | rodar contra Q05a-e no self-check (mesmo output nas 5) |
| E3 | FP de heurística sistemático | média | médio | X03 cataloga, X04 filtra |
| E4 | Corpus tem <5 misses | baixa | alto | corpus atual tem `doxcolors.py` duplicado + `apply_tags` NameError; deve gerar 20+ |
| E5 | RuleTable diverge de flat | baixa | crítico | self-check (6) |
| E6 | `units` grande (>20k entradas) | baixa | médio | se passar de 20k, split por arquivo (`misses_<basename>.json` + `_summary.json`) |
| E7 | Determinismo quebra por `id()` hash | baixa | alto | `id` é `U0001..` ordinal, não `hash()` |

---

## RIT

1. Discussão (este doc)
2. Implementar `engine_x03.py` (~250 LOC)
3. Rodar sem versionar `misses.json` (ver saída crua)
4. Inspecionar 5-10 misses manualmente (2 min)
5. `accept` do `misses.json` + `output.txt` versionados
6. Rodar 100× → mesmo hash
7. Revisão final

---

## Próximo passo

Se aprovado, escrever `engine_x03.py`. Depois rodar. Depois X04 consome o json.
