# P30a - AST real -> fatos -> inferencia (C2+C3)

**Contrato:** C2 (Adaptacao) + C3 (Expressividade) sobre AST Python **real**.
**Nao faz** rewrite (C4). Isso e P30b.

## Subset declarado

```
def NAME(PARAM):
    if COND:
        return VALUE
    return FALLBACK
