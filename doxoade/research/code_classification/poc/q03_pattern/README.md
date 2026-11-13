# Q03 - Pattern detection + cross-cycle chaining (DC2)

**Contrato:** DC2 (Classification) com 4 dimensoes ortogonais.

## Diferenca qualitativa de Q00-Q02

Ate Q02, **todas as rules matchavam apenas fatos seed** (extraidos do AST).
Q03 forca uma rule a matchar em **fatos derivados por outras rules** — o
motor compoe em camadas.

Cadeia (Q03a):
```
cycle 1 (seed):   name_prefix=create       (extraido)
                  return_expr_kind=Call    (extraido)
cycle 1 (rules):  R_create_prefix  -> has_naming=create
                  R_returns_call   -> has_behavior=returns_call
cycle 2 (rules):  R_factory        -> pattern=factory
                  (le has_naming + has_behavior derivados no cycle 1)
cycle 3:          quiescencia
```

Se Q03 passa, C1+C3 compoem — base para deteccao de padroes reais.

## Targets

| Pattern | Condicoes | Exemplo |
|---|---|---|
| `factory` | `name_prefix=create` AND `return_kind=Call` | `def create_user(n): return User(n)` |
| `accessor` | `name_prefix=get` AND `return_kind=Name` | `def get_x(x): return x` |
| `predicate` | `name_prefix=is` AND `return_kind=Compare` | `def is_valid(x): return x > 0` |
| (nenhum) | qualquer outro | `def foo(x): return bar(x)` |

`name_prefix` ∈ `{create, get, is, other}` — extraido do nome via `startswith`.

## SEM default "utility" — decisao de design

Q00 usou NAF para default `unknown`. Q03 **nao pode** aplicar o mesmo padrao:

```
cycle 1: R_utility        -> pattern=utility  (NAF passa, nada ainda)
cycle 2: R_factory        -> pattern=factory  (hints presentes)
         CONFLITO: (F, pattern, utility) vs (F, pattern, factory)
```

Ambos ficariam em `facts` — WM e monotonico, sem retracao cross-cycle.
Engine atual resolve conflito **within-cycle** (via priorities), mas nao
**cross-cycle**.

**Decisao:** sem default. Ausencia de `pattern` fact = `pattern=None`.
Honesto sobre limitacao. Deixa retracao cross-cycle para Q04+.

## O que Q03 prova

1. **Cross-cycle chaining funciona.** Rules leem fatos derivados no cycle anterior.
2. **4 dims coexistem** sem colisao (Q03a-e tem 4 dims; Q03d/e tem 3, `pattern=None`).
3. **Partial matches nao disparam pattern.**
   - Q03e: naming=create mas behavior=Constant (nao Call) -> None
   - Q03f: naming=is mas behavior=Call (nao Compare) -> None
4. **Determinismo** com 4 dims (Q03g, 100 runs).

## O que NAO prova

- Retracao cross-cycle (utility default) -> Q04+
- Multi-entity patterns (factory que chama outra funcao) -> fora do escopo Q03
- Padroes estruturais complexos (visitor, strategy) -> requerem multi-funcao

## Err table (ProDeNov 5.4)

| Risco | Prob. | Impacto | Mitigacao |
|---|---|---|---|
| R_factory dispara em cycle 1 (sem hints) | baixa | critico | snapshot semantics (B) impede |
| `pattern=utility` prende WM | n/a (removido) | critico | sem default |
| Prefix `other` dispara algo | baixa | medio | R_create/get/is prefix so com `startswith` explicito |
| Cross-cycle conflict | baixa | alto | ausencia de default elimina fonte |
| Determinismo em 4 dims | baixa | alto | Q03g (100 runs) |

## Planos A / B / C

- **A (implementado):** cross-cycle via facts derivados; sem default; prefixo
  estruturado.
- **B (se Q04 precisar de default):** adicionar retracao cross-cycle no engine
  — ao adicionar `(s, p, new_o)`, remover `(s, p, old_o)` com prioridade menor.
  Custo: engine mais complexo (remocao de facts em facts).
- **C (se multi-funcao for necessario):** Q05 introduz fatos com shape
  `(func_a, calls, func_b)`. Engine atual ja suporta (sujeito = funcao).

## Licao

C1+C3 **compoem em camadas**. Rules no cycle N+1 leem o que cycle N
derivou. Isso ja estava no motor (P02/P20 desde o inicio) mas nunca
exercitado em `code_classification`.

O ponto critico e **nao usar default via NAF quando hints intermediarias
sao derivadas em camadas** — o NAF dispara cedo demais e o resultado se
prende. Documentar essa armadilha evita que Q04 repita o erro.
