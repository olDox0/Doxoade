# P10 — AST -> fatos (C2, sem engine)

**Contrato:** C2 (Adaptação). `src: str → frozenset[FactPair]`.

## Subset declarado

P10 aceita **apenas** `x = a + b` (Assign + BinOp + Name × 2). 6 fatos:

| Fato | Origem |
|---|---|
| `stmt=Assign` | tipo do nó raiz |
| `assign.target=x` | `Name.id` do target |
| `assign.value=BinOp` | tipo de `node.value` |
| `binop.op=Add` | `type(node.value.op).__name__` |
| `binop.left=a` | `Name.id` de `left` |
| `binop.right=b` | `Name.id` de `right` |

Outros shapes → erro explícito. P11/P12/P13 expandem o subset.

## O que prova

- **P10a:** `extract("x = a + b") == EXPECTED_P10A` (6 fatos, comparação por conjunto).
- **P10b:** 100 extrações → serialização byte-a-byte idêntica (`|` como separador interno).
- **P10c:** `"x = "` → `SyntaxError` propagado (não silencioso).
- **P10d:** `"pass"` → `UnsupportedNodeError` (parsable, fora do subset).

## O que NÃO prova
- Unificação sobre os fatos → **P20**.
- Múltiplos statements / funções → **P11**.
- Dados externos (CSV/JSON) → **P12 / P13**.

## Err table (ProDeNov 5.4)
| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Shape inesperado cai em silêncio | média | alto | `SUPPORTED_NODES` whitelist |
| Serialização não-determinística | baixa | alto (diff quebra) | `sorted_lines` + P10b |
| Erro engolido (`except: pass`) | baixa | crítico | P10c + P10d exigem type específico |
| Múltiplos statements aceitos | baixa | médio | `parse_single` rejeita > 1 |

## Planos A / B / C
- **A (implementado):** whitelist explícita de `ast.Assign + ast.BinOp + ast.Name`.
- **B (se A falha em expandir para P11):** trocar whitelist por visitor pattern com dispatch por tipo. Custo: mais código, menos contrato.
- **C (se B falha):** abandonar subset declarado, aceitar qualquer AST e serializar genericamente (`type(node).__name__` como tipo). Custo: perde tipagem estrutural que P20 vai precisar.

## Lição (confirmar ao rodar)
Serializer **sem engine** é pré-requisito testável. Se `frozenset` extraído diverge do esperado, nenhuma inferência downstream é confiável. Separar C2 de C1 permite diagnosticar isso antes de P20 — que é onde o custo do erro seria alto.

