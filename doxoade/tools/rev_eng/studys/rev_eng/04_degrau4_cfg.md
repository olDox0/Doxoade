# Experimento 04 — Fase 4 (blocos básicos / CFG)

## Hipótese
Consigo identificar blocos básicos e arestas de sucessão a partir
da lista linear de instruções, e reconstruir a estrutura de `if/else`
a partir dos diamantes no CFG.

## Método
1. `disasm_collect` produz `InsnList` (lista linear de `DecodedInsn`).
2. `cfg_build` identifica líderes (primeira instrução, alvos de
   jcc/jmp, instrução após jcc/jmp/ret/call), agrupa em blocos,
   calcula sucessores por tipo de fluxo de controle.
3. `cfg_print_text` e `cfg_print_dot` emitem o grafo.

## Resultado — `degrau0_O0_g.exe`
✅ Confirmado:
- 6239 instruções, 1648 blocos básicos (~3.78 insns/bloco).
- Bloco 0 (ret) → 0 sucessores.
- Bloco 1 (jne) → 2 sucessores (fallthrough 0x14000103c, alvo 0x140001083).
- Bloco 5 (jmp) → 1 sucessor (alvo 0x140001083).
- Diamante clássico de `if/else` nos blocos 1–7, convergindo em 0x140001083.

## O que o CFG revela
- `0x140001083` é o ponto de merge dos testes `if (is_pe32/pe32plus)`.
- Estrutura: `if (is_pe32) { if (magic == 0x10b) ... else ... } else if (is_pe32plus) ... else goto fail;`
- Padrão típico de if/else aninhado, que um decompilador reconheceria.

## Limites remanescentes (aceitos)
- Sem predecessores (só sucessores) — suficiente para Fase 4,
  útil na Fase 5 para dominadores.
- Saltos indiretos (`jmp *reg`, `call *reg`) não têm alvo
  resolvível — o bloco fica com 0 sucessores.
- Código morto (após `ret`/`jmp` sem alvo) é incluído como bloco
  — na Fase 5, seria marcado como inalcançável.

## Próximo passo
Fase 5 — descompilador inicial: reconhecer `if`, `if/else`, `while`
a partir do CFG e emitir pseudo-C.
