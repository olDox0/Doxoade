# P30b - Rewrite de AST (C4, puro)

**Contrato:** C4 (Atuacao). AST + fato -> AST nova via `ast.unparse`.
**Nao faz:** re-parse do output, re-inferencia, multi-pattern.

## O que prova

- **P30b-1:** `def f(x): if x > 0: return x\n    return None` vira
  `def f(x): return x if x > 0 else None` (via ast.unparse).
- **P30b-2:** idempotencia - `rewrite(rewrite(x)) == rewrite(x)` porque
  o pattern deixa de casar naturalmente (If sumiu).
- **P30b-3:** passthrough - input sem pattern retorna unparse do original
  (nao levanta erro - nao-match e comportamento valido).
- **P30b-4:** output compila com `compile()` - codigo emitido e Python valido.
- **P30b-5:** 100 runs byte-a-byte identicos.

## Por que idempotencia via nao-match e suficiente

Existem 2 estrategias de idempotencia:
- **Anotacao**: marcar node com `_rewritten = True` antes de emitir.
- **Nao-match natural**: apos rewrite, o pattern deixa de casar.

Nao-match e mais simples e prova-se correta: se a transformacao remove
a condicao de match, reaplicar nao pode disparar. Testado em P30b-2.

Anotacao seria necessaria se o output ainda casasse com o pattern (loop
de rewrite). Aqui nao acontece - a AST nova nao tem `If` como body[0].

## O que NAO prova
- Multi-pattern (for-range-len -> iteracao direta) -> P31.
- Rewrite sobre AST invalida -> cada `ast.parse` levanta `SyntaxError`,
  testado em P10c.
- Optimizacao de rewrite (aplicar N regras num passo) -> depois de P31.

## Err table (ProDeNov 5.4)
| Risco | Prob. | Impacto | Mitigacao |
|---|---|---|---|
| Output nao compila | baixa | critico | P30b-4 compila |
| Nao idempotente | media | critico | P30b-2 rewrite-duplo |
| Perde informacao no passthrough | media | alto | P30b-3 baseline |
| Diferenca de unparse entre versoes 3.12.x | media | medio | comentario em expected |

## Planos A / B / C
- **A (implementado):** rewrite + unparse + idempotencia via nao-match.
- **B (se idempotencia falhar em P31):** adicionar `_rewritten` marker.
- **C (se unparse reformatar demais):** usar `astor` ou `lib2to3` para
  preservar comentarios e formatacao original.

## Lição
C4 e o primeiro contrato que produz **artefato externo** (codigo, nao so
fatos). O teste chave nao e "produziu algo", e "produziu algo que compila
e que pode ser reprocessado sem mudar". P30b-2 e P30b-4 juntos provam isso.
