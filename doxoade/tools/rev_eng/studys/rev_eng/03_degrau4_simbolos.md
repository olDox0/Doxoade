# Experimento 03 — Degrau 4 (resolução de símbolos)

## Hipótese
Consigo ler a COFF Symbol Table do binário e anotar alvos de
RIP-relative, jcc e call com o nome do símbolo, igual ao objdump.

## Método
1. `parse_symbols` lê 18 bytes por símbolo, pula auxiliares,
   filtra section symbols (Static + Value 0 + nome '.'), constrói
   mapa VA → nome, ordena por VA.
2. `symbol_lookup` faz binary search com `max_offset`:
   - RIP-relative: max_offset = 0 (exato)
   - jcc/call: max_offset = 0x1000 (até 4KB, para `<simbolo+offset>`)
3. `disasm.c` anota o alvo com `<nome>` ou `<nome+offset>`.

## Resultado
✅ Confirmado para `degrau0_O0_g.exe`:

| Endereço | Antes | Depois |
|---|---|---|
| 0x140001005 | `[rip+0x6784 (0x140007790)]` | `[rip+0x6784 (0x140007790) <.refptr.__mingw_initltsdrot_force>]` |
| 0x14000103a | `jne 0x140001083` | `jne 0x140001083 <pre_c_init+0x82>` |
| 0x14000109f | `call 0x140005bc0` | `call 0x140005bc0 <__set_app_type>` |
| 0x14000108a | `[rip+0x8f7c (0x14000a00c)]` | `[rip+0x8f7c (0x14000a00c) <managedapp>]` |

## Limites encontrados e corrigidos
1. **Section symbols poluíam** — `.text`, `.data`, etc. têm símbolo
   na COFF Symbol Table. Filtro: `storage_class == 3 && value == 0 && name[0] == '.'`.
2. **Offset grande enganoso** — `__bigtens_D2A+0xf0` aparecia porque
   o `symbol_lookup` aceitava qualquer offset. Corrigido com `max_offset`:
   RIP-relative exige match exato; jcc/call aceita até 4KB.

## Limites remanescentes (aceitos)
- Símbolos sem SectionNumber (absolutos/externos) não aparecem.
- Binários stripped (hostname.exe, where32.exe) não têm Symbol Table,
  então não há anotação — o disasm funciona, mas sem símbolos.
- Símbolo `<pre_c_init+0x82>` é o alvo (offset dentro da função);
  o `objdump` mostra `140001083 <pre_c_init+0x82>`, igual.

## Próximo passo
Fase 4 — blocos básicos. Identificar limites (após ret/jmp,
antes de alvos de jcc) e construir o CFG.
