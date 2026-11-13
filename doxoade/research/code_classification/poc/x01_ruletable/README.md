# X01 — Rule Table por domain (probe)

**Pergunta:** tabling por `domain` preserva resultado?

**Resposta (se PASS):** sim. `RuleTable` filtra rules por domain sem
perder, mangle ou reordenar semanticamente. Engine continua o mesmo.

## Contexto

Probe mínimo da arquitetura de tabelamento discutida em
`BLITZPLAN_X00_RULETABLE.md`. **Não é X00.** X00 é o Source Auditor
completo (que vem depois). X01 é pré-requisito: prova que a abstracao
`RuleTable` não mente.

## Decisoes R1/R2/R3 (aplicadas)

- **R1 Classificador separado** — `RuleTable` é módulo próprio.
  Classifica por `domain` (estático, explícito). Classificador dinâmico
  de contexto fica para X03+.
- **R2 Tabela estática** — `domain_index` é literal Python no protótipo,
  vira YAML/JSON em X02+. Sem aprendizado automático ainda.
- **R3 Fallback + log** — X01 não exercita fallback ainda (todo cenario
  tem rules aplicáveis). Fallback e chaos log ficam para X03.

## O que prova

### X01a — rules expostas == rules esperadas
`table.domain_rules("programming")` retorna exatamente as 4 rules de
`RULES_PROGRAMMING`. Prova que indexação não perde.

### X01b — run(raw) == run(tab)
Mesmo seed, mesma engine, rules passadas por caminhos diferentes
(lista direta vs. via `RuleTable`). Compara:
- `live_tuples` (fatos vivos finais)
- `cycles` (ciclos usados)
- `retractions` (quantas retrações ocorreram)
- `trace_len` (tamanho do trace)
- `rules_attempted` (esforço total)

Todos 5 idênticos. Prova que `RuleTable` é transparente.

### X01c — boundary enforced
Programing run: `status=b_active`, sem `diagnostic`.
Diagnosis run: `diagnostic=yes`, sem `status`, sem `b_flag`.

Prova que domain filtration funciona: rules de outro domain **não** vazam.

### X01d — determinism
100 runs de X01b. Mesmo `(identical, live_tuples, cycles, retractions)`
todas as vezes.

## O que NAO prova

- **Fallback** (o que acontece se domain não cobre cena). X03.
- **Chaos log** (detecção de miss silenciosa). X03.
- **Symptom index** (ativação por sintoma). X02.
- **Multi-domain simultâneo** (domain="programming" + symptom="crash").
  X02.
- **Refino de rule** (prune, split, merge). X04.
- **Performance** (tabela vale o custo?). X05.

## Err table (ProDeNov 5.4)

| Risco | Prob. | Impacto | Mitigacao |
|---|---|---|---|
| Rule em duas tabelas diverge | baixa | critico | fonte unica (`_rules: dict`), indices so guardam ids |
| Tabela perde rule por typo de id | media | alto | X01a detecta (compara ids) |
| Boundary viola (domain vaza) | media | alto | X01c detecta |
| Ordem de rules afeta resultado | baixa | alto | engine usa priority (stable sort) |
| Determinismo quebra com retracao | baixa | critico | X01d (100 runs) |

## Tamanho

- **Hoje:** ~480 L (kernel inline + RuleTable + sub-sondas).
- **Pós-Q10 (consolidação):** ~80 L (kernel compartilhado via `lib/`).

Tamanho alto é dívida conhecida do padrão "PoC independente". Não é bug.

## Licao (se PASS)

`RuleTable` é uma **abstração fina** sobre `dict` — nada mágico. Sua
viabilidade depende de:
1. **Fonte única** (`_rules`) — sem duplicação.
2. **Índices só de ids** — sem estado duplicado.
3. **Sem reordenação** — engine já ordena por priority.

Próximo teste real: **X02 (symptom index + multi-domain)** — mais
desafiador porque duas chaves combinam.
