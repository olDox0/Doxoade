# Experimento 08 — Fase 5d (dominadores e loops)

## Hipótese
Consigo calcular o dominador imediato (idom) e detectar loops
naturais (back-edges) a partir do CFG, em binários PE32/PE32+.

## Método
- Cooper-Harvey-Kennedy (2001): DFS post-order → RPO → idom.
- dom_compute: itera até convergir.
- dom_count_loops: back-edge (p → h) onde h domina p.

## Resultado — where32.exe
- [DOM] 71/2583 blocos alcançáveis, 12 loops
- 71 = blocos de sub_401000 (59) + fall-through (12)
- 2583 = total do .text (3 inalcançáveis)

## Limitação
O CFG do doxreveng NÃO conecta funções via CALL. O DFS do entry
visita apenas a função de entrada. Para o Defaultier, precisamos
de dominadores POR FUNÇÃO (sub-CFG).

## Fix
dom_extract_function: extrai sub-CFG [first, first+count) com
sucessores/predecessores filtrados. O Defaultier processa cada
função individualmente.

## Próximo passo
Fase 6 — Defaultier (pseudo-C pedagógico):
  1. Por função, extrair sub-CFG + dominadores.
  2. Reconhecer if/else via idom do merge.
  3. Reconhecer while via back-edges.
  4. Emitir pseudo-C.

