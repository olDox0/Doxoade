# Discussão — Forward Chaining (Protótipo) · ProDeNov

## 1. Requisição (contexto formal)

| Campo | Definição |
|---|---|
| **O que** | Módulo Python 3.12 de *forward chaining* com adição dinâmica de instruções (fatos + regras) em runtime. |
| **Onde** | Protótipo em `doxoade/research/forward_chaining/` (não em produção ainda). |
| **Quem** | Dev doxoade; consumo futuro por TYPHON/DOXLY e orquestração NEOVULCAN. |
| **Quando** | Protótipo agora; integração posterior. |
| **Quanto** | Pequeno porte: ~500–800 linhas, ≤ 5 arquivos core, cada < 50 kb (ProDeNov 2.1). |
| **Por quê** | Base para sistemas de tomada de decisão data-driven no ecossistema. |
| **Origem** | Necessidade de raciocínio automático sobre fatos observados (sensores, logs, estado de build, etc.). |
| **Consequências** | Se bem projetado → componente reutilizável de decisão. Se mal projetado → *rabbit hole* de DSL/performance/conflitos (ProDeNov 0.2 e 0.4). |

---

## 2. Brainstorming

### 2.1 O que é forward chaining
Motor **data-driven**: parte de fatos conhecidos, aplica regras `SE condições ENTÃO conclusões`, adiciona novos fatos, repete até **quiescência** (nenhuma regra nova dispara) ou limite de ciclos.

Contraste: *backward chaining* é goal-driven (parte da conclusão e volta). Para decisão reativa a fatos observados, forward é o encaixe natural.

### 2.2 Componentes mínimos

1. **WM (Working Memory)** — conjunto de fatos.
2. **RB (Rule Base)** — conjunto de regras.
3. **Inference Engine** — `match → resolve → fire → repeat`.
4. **Conflict Resolution** — prioridade, especificidade, recência, ordem de inserção.
5. **Trace** — grafo de derivação (quem gerou o quê, a partir do quê).
6. **Dynamic Loading** — `add_rule`, `add_fact`, `remove_rule`, `remove_fact` em runtime.

### 2.3 Formas de "instrução dinâmica"
- **(A) API programática** — `engine.add_rule(Rule(...))` com dataclasses e callables.
- **(B) DSL textual** — `"IF temp == 'high' AND hum == 'low' THEN risk = 'high'"`.
- **(C) Mista** — API como núcleo; DSL como fachada fina (parser mínimo).

> Recomendação: **A no protótipo**, C só depois que a semântica estabilizar. DSL cedo demais é rabbit hole clássico (0.2).

### 2.4 Representação de fatos
- Tupla `(predicado, args...)` — Prolog-like, simples, mas pobre para diagnóstico.
- Dicionário `{key, value, source}` — flexível, mas sem tipagem.
- **Dataclass** `Fact(key, value, source, timestamp, derived_from, rule_id)` — melhor para trace e W5.

### 2.5 Representação de regras
```
Rule(
  id, conditions[list[Condition]], conclusions[list[Fact]],
  priority:int, description:str, tags:list[str]
)
Condition(predicate, matcher: Callable[[value], bool])
```
Regras **puras** (só produzem fatos) — sem efeitos colaterais. Isso preserva determinismo, testabilidade e reversibilidade (ProDeNov "Segurança").

### 2.6 Prevenção de loops
- Assinatura de disparo: `(rule_id, frozenset(fact_ids_usados))` → não repete.
- `max_cycles` (padrão 1000) → `CycleLimitError`.
- Fatos imutáveis por identidade; remoção explícita se necessário.

### 2.7 Trace / explicação
Cada fato derivado guarda `derived_from: list[fact_id]` + `rule_id`. Habilita:
- `explain(fact)` → árvore de derivação.
- `why_not(fact)` → regras quase-elegíveis e condição faltante.
- `impact(fact)` → o que depende dele (para simulação/`--dry-run`).

---

## 3. Viabilidade, manutenção, escalabilidade

**Viabilidade** — Alta. `dataclasses`, `typing`, `functools`, `collections` (stdlib). Zero dependência externa no protótipo (ProDeNov 3.1.1).

**Manutenção**
- Boundaries estritos: `facts.py` ↔ `rules.py` ↔ `engine.py` sem acoplamento cruzado (2.1.6.1).
- `trace.py` e `diagnostics.py` em domínio separado (2.1.6.2 — DDD por contexto).
- Testes por componente; RIT por capítulo.
- Blitzplan em `docs/Research/forward_chaining/blitzplan_fc.md` (7.3 e 7.4).

**Escalabilidade**
- Protótipo: match ingênuo **O(R × F)** por ciclo — ok até milhares de regras/fatos.
- Evolução: índice `facts_by_predicate` → depois RETE se necessário.
- Concorrência: STRAP (Correia) pode ser aplicado depois com workers de *match* e *fire* assíncronos + *pitstop*. **Não** no protótipo.

**Riscos (err table preliminar)**

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Rabbit hole de DSL | Média | Alto | Plano B congela API pura (item 5.6.3) |
| Conflito não determinístico | Média | Alto | Prioridade + ordem de inserção como default |
| Loop infinito | Baixa | Alto | Assinatura + `max_cycles` |
| Regras com efeito colateral | Baixa | Alto | Regras puras por contrato |
| Regressão silenciosa | Média | Médio | RIT + `--dry-run` + diff review (5.5/5.6) |

---

## 4. Arquitetura proposta (Placeholders — ProDeNov 2.1)

```
doxoade/research/forward_chaining/
  fc_core/
    __init__.py          # API pública: Fact, Condition, Rule, Engine
    facts.py             # Fact + FactStore (WM)
    rules.py             # Condition + Rule + RuleStore (RB)
    engine.py            # ForwardChainingEngine (match/resolve/fire)
    trace.py             # DerivationGraph, explain(), why_not()
    diagnostics.py       # W5 + métricas + stub TYPHON
    dsl.py               # (opcional, Plan B) parser mínimo
  tests/
    test_facts.py
    test_rules.py
    test_engine.py
    test_trace.py
    test_diagnostics.py
  docs/
    blitzplan_fc.md
    research_notes.md
```

Cada arquivo segue o modelo 2.1:
```python
# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/fc_core/engine.py
"""
Motor de inferência forward chaining.
Responsabilidades: match → resolve → fire → quiescência.
Não conhece UI, não altera WM diretamente (delega a FactStore).
"""
from dataclasses import dataclass
from typing import Iterable
from .facts import Fact, FactStore
from .rules import Rule, RuleStore

class ForwardChainingEngine:
    def __init__(self, fact_store: FactStore, rule_store: RuleStore, max_cycles: int = 1000): ...
    def run(self, dry_run: bool = False) -> "RunResult": ...
    def explain(self, key: str) -> "DerivationTree": ...
    def diagnose(self) -> dict: ...
```

### 4.1 Boundaries (2.1.6)
- **Source Level** — cada módulo um domínio.
- **SoC** — engine orquestra; nunca renderiza; nunca persiste.
- **Outline dominante** — *Inteligência Artificial / Tomada de decisão automática* + *Estrutura de dados* + *Algoritmos*.
- **Contexto** — orquestração faz normalização/priorização (2.1.6 final).

### 4.2 API mínima (Plan A)
```python
f1 = Fact("temperature", "high", source="sensor")
f2 = Fact("humidity", "low",  source="sensor")

r = Rule(
    id="fire_risk_high",
    conditions=[
        Condition("temperature", lambda v: v == "high"),
        Condition("humidity",    lambda v: v == "low"),
    ],
    conclusions=[Fact("fire_risk", "high", source="derived")],
    priority=10,
    description="Risco alto quando temp alta e umidade baixa.",
)

engine = ForwardChainingEngine(FactStore([f1, f2]), RuleStore([r]))
result = engine.run()
engine.explain("fire_risk")
engine.diagnose()
```

### 4.3 Planos A / B / C

| Plano | Descrição | Quando usar |
|---|---|---|
| **A** | API programática pura (dataclasses + callables). | **Default do protótipo.** |
| **B** | DSL textual mínima (regex/AST) como fachada sobre A. | Se a semântica estabilizar e houver demanda UX. |
| **C** | Lib externa (`experta`, `durable_rules`, `pyke`). | Só se RETE/perf for requisito duro. |

---

## 5. Questões técnicas (ProDeNov 3)

- **3.1.1** — stdlib primeiro; sem deps no protótipo.
- **3.1.4** — `diagnostics.py` responde: onde (rule_id), o que (fatos), quando (ts), quem (source), quanto (ciclos/regras), por quê (condições), origem (fatos base), consequência (derivados).
- **3.1.6 (Anti Long Shot)** — instrumentar antes de otimizar: `RunResult` com `cycles`, `rules_evaluated`, `rules_fired`, `dead_rules`, `elapsed`.
- **3.1.7** — `trace.py` mantém tabela de dependência fatos↔regras (rastreio).
- **5.2** — exceções: `FactError`, `RuleError`, `CycleLimitError`, `ConflictError`.
- **5.3** — `run(dry_run=True)` retorna plano de disparos sem mutar WM.
- **5.4** — err table acima + stubs em docstrings.
- **5.6** — RIT por capítulo; loop `discussão → implementação → teste → discussão/fix`.

---

## 6. Roteiro (RIT) — capítulos

| Cap. | Entrega | Critério de saída |
|---|---|---|
| 1 | `Fact` + `FactStore` | testes de inserção/consulta/duplicata |
| 2 | `Condition` + `Rule` + `RuleStore` | testes de match unitário |
| 3 | `Engine` (match/resolve/fire) | teste de encadeamento + loop protection |
| 4 | `Trace` + `explain`/`why_not` | teste de árvore de derivação |
| 5 | `Diagnostics` (W5) + stub TYPHON | `diagnose()` retorna todos os campos |
| 6 | DSL mínima (Plan B) | parser cobre IF/AND/THEN; senão congela |
| 7 | Revisão | diff review, regressão, blitzplan atualizado |

Cada capítulo com **Plano A + B** (1.2.1) e checklist de revisão de regressão (1.3).

---

## 7. Glossário interno (5.6.5)

- **WM** — Working Memory (fatos).
- **RB** — Rule Base.
- **Match** — encontrar regras elegíveis.
- **Fire** — aplicar conclusões.
- **Quiescência** — nenhuma regra nova dispara.
- **Derivação** — cadeia regra→fato.
- **Assinatura de disparo** — `(rule_id, frozenset(fact_ids))`.
- **Conflito** — múltiplas regras elegíveis simultaneamente.
- **Dead rule** — regra nunca disparada em um run.

---

## 8. Decisões pendentes (para a discussão)

1. **Fato**: dataclass rica (`key/value/source/timestamp/derived_from`) vs. tupla simples? *Recomendo dataclass.*
2. **Instrução dinâmica**: só API (Plan A) ou já prever DSL (Plan B) no protótipo? *Recomendo só A.*
3. **Conflito default**: prioridade + ordem de inserção? *Recomendo sim; documentar como contrato.*
4. **Trace já no Cap. 1** ou só no Cap. 4? *Recomendo trace mínimo desde `Fact` (campo `derived_from`), grafo completo no Cap. 4.*
5. **Local**: `research/` (protótipo) vs. `commands/` (produção)? *Recomendo `research/` até estabilizar.*
6. **Incerteza**: o protótipo é determinístico. Vamos considerar pesos/certeza (CF) agora ou depois? *Recomendo depois — primeiro o núcleo determinístico.*

Se concordar com esse esqueleto, o próximo passo é abrir `docs/Research/forward_chaining/blitzplan_fc.md` com o Cap. 1 detalhado (placeholders + RIT + err table) e começar a implementar `facts.py`. Quer seguir por aí ou ajustar alguma decisão antes?

---

# Plano de sondas — lista modular, controlada, com promoção à produção

## 1. Princípio organizador

A unidade de PoC **não é o domínio** (FizzBuzz, AST, delta, tree). É o **contrato entre dois módulos adjacentes**. Um PoC prova *um contrato*, não um domínio inteiro.

Isso é o que torna a coisa modular e escalável depois:

- Se cada PoC prova **um contrato**, o contrato é o que sobrevive. A implementação da PoC é descartável.
- Se os contratos compõem, você monta a produção no futuro **substituindo implementações, não reescrevendo contratos**.
- Se um módulo da produção quebrar, você sabe exatamente qual contrato re-provar — não precisa re-testar o sistema todo.

Regra dura que decorre disso: **uma PoC nunca importa de outra PoC**. Se P10 precisa do output de P00, ela recebe esse output como arquivo literal. Isso força o contrato a ser explícito e serializável desde o início.

---

## 2. Os contratos do sistema

Mapeando para o MVP do paper (facts / rules / matcher / engine / explain) e para as 6 camadas do Sarasvati:

| # | Contrato | Entrada → Saída | Componente MVP | Camada do paper |
|---|---|---|---|---|
| **C1** | Inferência | `Fatos + Regras → Fatos derivados` | engine + matcher | Reasoning |
| **C2** | Adaptação | `Fonte → Fatos válidos` | (parser adapter) | Acquisition/Semantic |
| **C3** | Expressividade | `Regras → Regras capazes de disparar` | rules vocabulary | Reasoning |
| **C4** | Atuação | `Fatos derivados → Efeito externo` | (actuator) | Representation |
| **C5** | Explicação | `Fatos + Regras + Trace → Cadeia legível` | explain | Representation |
| **C6** | Mensuração | `Trace de execução → Métrica` | (evaluator) | Governance |
| **C7** | Substituibilidade | `Contrato + 2 implementações → Mesmo comportamento` | (todos) | — |

**C7 é o contrato que prova que a modularidade existe.** Sem ele, "modular" é apenas uma palavra. Com ele, cada contrato tem uma garantia explícita de que pode ser trocado depois.

---

## 3. Lista de sondas

### C1 — Inferência (kernel, sem domínio externo)

| ID | Prova | Tamanho | Critério |
|---|---|---|---|
| **P00** | Engine termina, deriva e emite (FizzBuzz 1..100) | ~80 L | saída == referência |
| **P01** | Engine não faz loop em regras cíclicas | ~40 L | termina em ≤ N ciclos |
| **P02** | Duas regras disputam; prioridade resolve determinístico | ~60 L | 100 runs = mesma saída |

### C2 — Adaptação (fonte → fatos)

| ID | Prova | Tamanho | Critério |
|---|---|---|---|
| **P10** | Python AST de 1 statement → conjunto exato de fatos | ~60 L | conjunto == esperado |
| **P11** | Python AST de 1 função simples → fatos | ~80 L | conjunto == esperado |
| **P12** | CSV de 1 linha → fatos tipados | ~40 L | conjunto == esperado |
| **P13** | JSON de 1 objeto aninhado → fatos com hierarquia | ~60 L | conjunto == esperado |

*(P13 substitui a tentação de "texto livre" — JSON dá árvore real sem abrir a porta da linguagem natural.)*

### C3 — Expressividade de regras

| ID | Prova | Tamanho | Critério |
|---|---|---|---|
| **P20** | Unificação com variáveis (`IF Pai(X,Y) AND Pai(Y,Z) THEN Avô(X,Z)`) | ~70 L | deriva fechamento |
| **P21** | Negação como falha (`IF NOT P THEN ...`) | ~50 L | não dispara sem fato |
| **P22** | Recursão transitiva termina e deriva cadeia completa | ~60 L | profundidade N |

### C4 — Atuação (fatos → efeito)

| ID | Prova | Tamanho | Critério |
|---|---|---|---|
| **P30** | Fatos derivados → reescrita de AST (`x[i]` em loop → `for item in x`) | ~100 L | AST refeita == esperada |
| **P31** | Fatos derivados → rótulo (`spam`/`ham` sobre 10 e-mails) | ~80 L | 10/10 |

*(P30 e P31 usam o output literal de P10/P12 como entrada — não importam das PoCs; copiam o arquivo.)*

### C5 — Explicação

| ID | Prova | Tamanho | Critério |
|---|---|---|---|
| **P50** | Trace do P02 reconstrói cadeia de derivação | ~60 L | árvore legível reconstrói todos os fatos |
| **P51** | Explain responde "por que NÃO derivou" | ~50 L | aponta fato/regra faltante |

### C6 — Mensuração

| ID | Prova | Tamanho | Critério |
|---|---|---|---|
| **P60** | Conta ciclos, regras disparadas, fatos derivados por run | ~40 L | contagens batem com trace |

### C7 — Substituibilidade (o teste de modularidade)

| ID | Prova | Tamanho | Critério |
|---|---|---|---|
| **P70** | Trocar matcher ingênuo por matcher indexado, **sem mudar comportamento** | ~150 L | toda a escada (P00–P60) continua verde |

**P70 é o gate de promoção.** Uma PoC só vira "candidata a produção" depois que a troca de implementação foi provada equivalente. Sem P70, nada promove.

---

## 4. Regras de execução

1. **Uma PoC por vez.** Nunca duas em paralelo.
2. **Ordem estrita:** C1 → (C2 ∥ C3 ∥ C4) → C5 → C6 → C7. Não sobe camada com camada anterior vermelha.
3. **Não importa entre PoCs.** Input copiado como arquivo literal.
4. **3 vermelhos seguidos na mesma PoC → para e investiga.** Algo no contrato está errado, não na implementação.
5. **Um contrato está estável** quando *dois PoCs independentes* (ex: P30 e P31 para C4) o exercitam sem tocar no núcleo.

## 5. Ciclo de vida de uma PoC

- Vive em `poc/NN_nome/` com `run.py`, `expected.txt`, `run.sh`.
- Passa → anota **lição** em `docs/research/poc_notes.md` e **descarta** o código.
- Falha → anota **lição** e **descarta** o código.
- **Nada migra para `src/`.** O que migra é a lição; o código é reescrito quando a produção começar.

## 6. Planos A / B / C de ordenação

| Plano | Ordem | Custo | Risco |
|---|---|---|---|
| **A** (recomendado) | C1 → C2/C3/C4 → C5 → C6 → C7 | médio | baixo — kernel validado antes de qualquer domínio |
| **B** | C4 primeiro (uma demo de efeito visível), depois C1 | rápido a demo | alto — pula C1, descobertas do kernel aparecem tarde |
| **C** | C1 ∥ C2 em paralelo | médio | médio — força C2 a inventar fatos que C1 ainda não sabe se aceita |

## 7. O que NÃO provar ainda

- **DSL textual** (é Plan B do paper; nenhum contrato C1–C7 exige).
- **Governance / rule_refiner / evaluator** (C6 é uma sonda mínima; refino automático sem regras em produção não tem o que refinar).
- **Confidence engine** (não é contrato de nenhum MVP; se aparecer necessidade real em P31, aí vira PoC).
- **Surface generation** (linguagem natural é o último passo da escada histórica; vem só depois de C7).
- **Ontologia / tipos formais** (aparece em P20 se unificação exigir; senão, espera).

## 8. Próximo passo concreto

Começar com **P00** — é a única sonda que valida C1 inteiro antes de qualquer domínio. Escrever o `blitzplan` de C1 em `docs/research/forward_chaining/blitzplan_C1.md` com:

- **Cap. 1:** P00 (FizzBuzz) — Plan A: engine ingênuo O(R×F); Plan B: índice `facts_by_predicate`.
- **Cap. 2:** P01 (ciclo) — Plan A: assinatura `(rule_id, frozenset(fact_ids))`; Plan B: contador de ativação por regra.
- **Cap. 3:** P02 (conflito) — Plan A: prioridade + ordem de inserção; Plan B: especificidade de condições.

Cada capítulo com checklist de revisão e err table (ProDeNov 1.2, 1.3, 5.4).

Uma pergunta antes de detalhar: você quer que cada PoC já nasça com `engine.py` como **arquivo único** (~200 L) e só quebre em 5 arquivos no P70 (o gate de substituibilidade), ou prefere 5 arquivos desde P00 mesmo que cada um tenha ~40 L? Minha recomendação é **arquivo único até P70** — 5 arquivos de 40 L escondem acoplamento, e a modularidade real só é *provada* quando P70 consegue trocar uma peça. Antes disso, "5 arquivos" é teatro.
