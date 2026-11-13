# P50 - Explainability (C5): positive + negative

**Contrato:** C5 (Explicacao).
`Fatos + Regras + Trace -> Cadeia legivel`.

## Extensao sobre P20/P21

`TraceEntry` ganha `derived_from: list[tuple]` — os fatos exatos usados
em cada derivacao. Sem isso, explain() nao pode reconstruir a cadeia.

## O que prova

- **P50a:** explain(avo(joao,pedro)) -> {rule: R_trans, cycle: 1,
  parents: [pai(joao,maria), pai(maria,pedro)]}.
- **P50b:** explain_chain(bisavo(joao,ana)) — arvore de 2 niveis:
  bisavo <- {avo, pai}; avo <- {pai, pai}; tudo ate seed.
- **P50c:** why_not(avo(joao,ana)) -> R_trans falha em cond[1] com
  bindings {X=joao, Y=maria, Z=ana} (implica pai(maria,ana) ausente).
- **P50d:** explain(seed) -> {source: seed}.
- **P50e:** explain(unknown) -> {source: unknown}.
- **P50f:** completeness: 3 derived, 3 trace; todos parents sao seed
  ou derived (grafo fechado).
- **P50g:** determinismo (100 runs).

## Limitacao conhecida

`explain_chain` mostra **uma** derivacao (a primeira cronologica). Se um
fato tem duas derivacoes, so a primeira e exibida. Extensao para "todas
as derivacoes" fica para producao.

## why_not e aproximado

`match_with_diagnostic` reporta o **ponto mais profundo** onde todas as
extensoes morrem. Isso e util para debug mas nao e prova completa: uma
condicao pode falhar em um caminho mas ter match em outro. Como o
backtracking explora todos os caminhos, "deepest fail" e o limite
inferior (garantido insatisfativel quando reportado).

## O que NAO prova
- Explicacao de fato com multiplas derivacoes (so a primeira).
- Explicacao de falha em regra com negacao (P21 nao usado aqui).
- Explicacao em linguagem natural (fora do escopo C5).

## Err table (ProDeNov 5.4)
| Risco | Prob. | Impacto | Mitigacao |
|---|---|---|---|
| Trace sem derived_from | alta (sem mudar engine) | critico | trace extendido em P50 |
| explain() em fato nao derivado | media | medio | source=unknown |
| why_not com deepest_fail impreciso | media | alto | documentado como aproximacao |
| Grafo quebrado (orfao) | baixa | critico | P50f completeness |

## Planos A / B / C
- **A (implementado):** trace com derived_from + explain / explain_chain
  / why_not.
- **B (se multiplas derivacoes):** trace guarda lista de derivacoes por
  fato; explain_chain ganha flag `all_paths=True`.
- **C (se why_not mais preciso):** backward chaining completo (goal-driven)
  em vez de diagnostic forward. Alinha com `research_directions.md`.

## Licao
C5 separa "motor que deriva" de "motor que explica". A diferenca mora no
trace: saber *que* um fato foi derivado e trivial (basta olhar `facts`);
saber *como* exige `derived_from`. E explicar *por que nao* exige um
caminho distinto — backtracking com diagnostico.

Depois de P50, C1-C5 estao cobertos. Falta C6 (mensuracao) e C7
(substitutibilidade).
