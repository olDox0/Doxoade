# Experimento 07 — Fase 5c (Xref database)

## Hipótese
Consigo construir um banco de referências cruzadas (código → dados)
que responda "quem referencia 0xX?" e "o que 0xY referencia?".

## Método
- xref_build percorre a InsnList e extrai:
  - CALL/JMP/JCC com target resolvido (direto)
  - RIP-relative memory (Capstone)
- resolve_target: símbolo COFF (se houver) ou NULL (stripped)

## Resultado — where32.exe
- 1842 referências (8610 instruções)
- JCC dominam (~60%), CALL diretos (~30%), RIP (~10%)
- `--target 0x4015e0` → 11 chamadores de sub_4015e0

## Limites
- Strings não extraídas (owned_name sempre NULL)
- CALLs indiretos via IAT não geram xref (target=0)
- XREF_DATA_ABS não implementado (32-bit `[0x...]`)

## Próximo passo
Predecessores no CFG (preparação para dominadores e Defaultier).

