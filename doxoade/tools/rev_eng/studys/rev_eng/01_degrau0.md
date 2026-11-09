# doxoade/tools/rev_eng/studys/rev_eng/01_degrau0.md

/* degrau0.c — alvo de teste para o doxreveng (Degrau 0)
 *
 * Elementos deliberados para exercitar o parser e, depois, o desmontador:
 *   - 4 funções: main, parse_args, process, report
 *   - switch em process (gera tabela de saltos ou cadeia de comparações)
 *   - loops em parse_args e report (geram blocos básicos com back-edge)
 *   - if/else em main e parse_args (geram saltos condicionais)
 *   - chamadas de libc: strlen, strcmp, printf
 *   - chamada via ponteiro de função (força salto indireto, mesmo com -O2)
 *   - alocação dinâmica (malloc/free) para exercitar o heap e imports
 *
 * Compilar em duas variantes:
 *   -O0 -g   (com símbolos, gabarito absoluto)
 *   -O2 -s   (otimizado, sem símbolos, contraste)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Modos de operação */
enum {
    MODE_NORMAL  = 0,
    MODE_VERBOSE = 1,
    MODE_QUIET   = 2
};

/* parse_args: loop + if/else + strcmp
 * Retorna 0 em sucesso, -1 em argumento inválido. */
static int parse_args(int argc, char **argv, int *mode)
{
    *mode = MODE_NORMAL;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-v") == 0) {
            *mode = MODE_VERBOSE;
        } else if (strcmp(argv[i], "-q") == 0) {
            *mode = MODE_QUIET;
        } else {
            return -1;
        }
    }
    return 0;
}

/* process: switch com 4 casos (gera tabela de saltos no -O2)
 * Aloca um buffer, mede o tamanho e libera. */
static int process(int mode, const char *input)
{
    size_t len = strlen(input);
    char *buf = (char *)malloc(len + 1);
    if (buf == NULL) {
        return -1;
    }
    memcpy(buf, input, len + 1);

    int result;
    switch (mode) {
        case MODE_NORMAL:
            result = (int)len;
            break;
        case MODE_VERBOSE:
            result = (int)len * 2;
            break;
        case MODE_QUIET:
            result = 0;
            break;
        default:
            result = -1;
            break;
    }

    free(buf);
    return result;
}

/* report: loop com printf, usa operador ternário aninhado */
static void report(int mode, int result)
{
    const char *label = (mode == MODE_VERBOSE) ? "verbose"
                      : (mode == MODE_QUIET)   ? "quiet"
                      :                          "normal";

    for (int i = 0; i < 3; i++) {
        printf("[%s] result=%d (iter %d)\n", label, result, i);
    }
}

int main(int argc, char **argv)
{
    int mode = MODE_NORMAL;

    if (parse_args(argc, argv, &mode) != 0) {
        printf("usage: degrau0 [-v|-q]\n");
        return 1;
    }

    /* Chamada via ponteiro: impede inline mesmo em -O2,
     * forçando um salto indireto observável. */
    int (*fn)(int, const char *) = process;
    int result = fn(mode, "hello");

    report(mode, result);
    return 0;
}

---

# Experimento 01 — Degrau 0 (binário próprio)

## Hipótese
Consigo, com um parser PE em C sem dependências externas, ler header,
seções e imports de um binário compilado por mim com gcc 13, e o JSON
pré-IR bate com o `objdump` em ≥90% dos campos.

## Método
1. Compilar `degrau0.c` com `-O0 -g` e `-O2 -s` (Metalcraft)
2. `objdump -h` e `objdump -p` como gabarito
3. `doxreveng <exe>` → JSON
4. Comparar campo a campo

## Resultado
✅ Confirmado para `degrau0_O0_g.exe`:
- format: PE32+ (bate)
- entry_va: 0x131a (bate com AddressOfEntryPoint)
- 17 seções, todas com VA, virtual_size, raw_offset, raw_size corretos
- 2 DLLs: KERNEL32.dll (14 funções), msvcrt.dll (33 funções) — bate com objdump
- Nomes de seção longos resolvidos via String Table

## Limites encontrados e eliminados
1. **Thunks de 8 bytes em PE32+** — o parser lia uint32; PE32+ usa uint64
   para OriginalFirstThunk. Corrigido com `file_reader_u64` + `thunk_size`.
2. **String Table após a Symbol Table** — não após a Section Table.
   Corrigido com `ptr_symtab + num_syms * 18`.
3. **rva_to_offset sem VirtualSize** — falhava para .bss. Corrigido com
   `virtual_size` separado e checagem de `delta >= raw_size`.
4. **Nomes truncados em 8 chars** — PRE_IR_SECTION_NAME_MAX era 9.
   Corrigido para 256.

## Limites remanescentes (aceitos para Degrau 0)
- Ordinal imports viram `<ordinal:NNN>` (precisa de tabela da DLL)
- FirstThunk não usado (só OriginalFirstThunk)
- Sem validação de Machine
- Sem fuzz testing

## Próximo passo
Degrau 1: `hostname.exe` do Windows 10 (PE32+, ~15KB).
Hipótese: o parser lida sem modificação? Onde quebra?

---

 Experimento 01 — Degrau 0 e Degrau 1

## Hipótese
Consigo, com um parser PE em C sem dependências externas, ler header,
seções e imports de binários reais, e o JSON pré-IR bate com o `objdump`
em ≥90% dos campos.

## Método
1. Compilar `degrau0.c` com `-O0 -g` e `-O2 -s` (Metalcraft)
2. `objdump -h` e `objdump -p` como gabarito
3. `doxreveng <exe>` → JSON
4. Comparar campo a campo

---

## Degrau 0 — binário próprio

### `degrau0_O0_g.exe` (com símbolos)
- format: PE32+ ✅
- entry_va: 0x131a ✅ (bate com AddressOfEntryPoint)
- 17 seções, todas com VA, virtual_size, raw_offset, raw_size corretos ✅
- KERNEL32.dll (14 funções) + msvcrt.dll (33 funções) ✅
- Nomes longos resolvidos via String Table (ptr_symtab=0xa600) ✅

### `degrau0_O2_s.exe` (stripped)
- format: PE32+ ✅
- entry_va: 0x131a (mesmo do O0)
- 10 seções (sem .debug_*, porque -s strip)
- KERNEL32.dll (14) + msvcrt.dll (31 — malloc e memcpy inlinados)
- has_strtab=0 (stripped), copy_section_name lidou ✅

### Contraste O0 vs O2
| Campo | O0 | O2 |
|---|---|---|
| Seções | 17 | 10 |
| .debug_* | presente | ausente |
| msvcrt.dll | 33 funções | 31 funções |
| has_strtab | 1 | 0 |

---

## Degrau 1 — `hostname.exe` (Windows 10, PE32+)

### Resultado
✅ Parser funcionou sem modificação.

- format: PE32+ ✅
- entry_va: 0x1c10 (plausível, cai na .text)
- 6 seções: .text, .rdata, .data, .pdata, .rsrc, .reloc ✅
- 17 DLLs (incluindo API Sets api-ms-win-*) ✅
- 1 import por ordinal (WS2_32.dll ordinal 115) → `<ordinal:115>` ✅
- 1 símbolo C++ mangled (`?terminate@@YAXXZ`) ✅
- `.data` com VirtualSize (2072) > SizeOfRawData (512) — `rva_to_offset` lidou ✅
- ptr_symtab=0 (stripped), has_strtab=0 ✅

### Limites encontrados (e como o parser lidou)
| Limite | Comportamento |
|---|---|
| API Sets (`api-ms-win-*`) | Parseou normalmente |
| Import por ordinal | `<ordinal:NNN>` (não resolve nome real) |
| Símbolo C++ mangled | Parseou como string |
| `ptr_symtab = 0` (stripped) | `has_strtab = 0`, usou `copy_section_name` |
| `.data` com VirtualSize > SizeOfRawData | `rva_to_offset` lidou (range = virtual_size, offset até raw_size) |
| `.rsrc` (resources) | Parseou como seção normal |

---

## Limites eliminados no Degrau 0
1. Thunks de 8 bytes em PE32+ (uint64 vs uint32)
2. String Table após Symbol Table (ptr_symtab + num_syms * 18)
3. `rva_to_offset` sem VirtualSize (corrigido com virtual_size separado)
4. Nomes truncados em 8 chars (PRE_IR_SECTION_NAME_MAX = 256)

## Limites remanescentes (aceitos)
- Ordinal imports viram `<ordinal:NNN>`
- `FirstThunk` não usado (só `OriginalFirstThunk`)
- Sem validação de `Machine`
- Sem fuzz testing

## Próximo passo — Degrau 2
Testar o path **PE32** (não PE32+). O parser tem o código, mas nunca foi
exercitado. Candidato: um `.exe` de 32 bits do `SysWOW64`.

---

## Degrau 2 — `where32.exe` (Windows 10, PE32)

### Resultado
✅ Parser funcionou sem modificação no path PE32.

- format: PE32 ✅
- entry_va: 0x6980 (plausível, cai na .text)
- 5 seções: .text, .data, .idata, .rsrc, .reloc ✅
- 7 DLLs: KERNEL32, msvcrt, ntdll, USER32, WS2_32, SHLWAPI, VERSION ✅
- 1 import por ordinal (WS2_32 ordinal 116) → `<ordinal:116>` ✅
- 1 símbolo C++ mangled (`?terminate@@YAXXZ`) ✅
- 1 função SEH do PE32 (`_except_handler4_common`) ✅
- ptr_symtab=0 (stripped), has_strtab=0 ✅

### O que o Degrau 2 confirma
- O path PE32 (thunks de 4 bytes, DataDirectory em opt+96) está correto.
- O parser lida com PE32 e PE32+ sem modificação.
- DLLs de sistema (ntdll) e funções SEH são parseadas normalmente.

---

# Experimento 01 — Degraus 0, 1 e 2 (parser PE)

## Hipótese
Consigo, com um parser PE em C sem dependências externas, ler header,
seções e imports de binários reais (PE32 e PE32+), e o JSON pré-IR bate
com o `objdump` em ≥90% dos campos.

## Método
1. Compilar `degrau0.c` com `-O0 -g` e `-O2 -s` (Metalcraft)
2. `objdump -h` e `objdump -p` como gabarito
3. `doxreveng <exe>` → JSON
4. Comparar campo a campo

---

## Degrau 0 — binário próprio

### `degrau0_O0_g.exe` (com símbolos)
- format: PE32+ ✅
- entry_va: 0x131a ✅ (bate com AddressOfEntryPoint)
- 17 seções, todas com VA, virtual_size, raw_offset, raw_size corretos ✅
- KERNEL32.dll (14 funções) + msvcrt.dll (33 funções) ✅
- Nomes longos resolvidos via String Table (ptr_symtab=0xa600) ✅

### `degrau0_O2_s.exe` (stripped)
- format: PE32+ ✅
- entry_va: 0x131a (mesmo do O0)
- 10 seções (sem .debug_*, porque -s strip)
- KERNEL32.dll (14) + msvcrt.dll (31 — malloc e memcpy inlinados)
- has_strtab=0 (stripped), copy_section_name lidou ✅

### Contraste O0 vs O2
| Campo | O0 | O2 |
|---|---|---|
| Seções | 17 | 10 |
| .debug_* | presente | ausente |
| msvcrt.dll | 33 funções | 31 funções |
| has_strtab | 1 | 0 |

---

## Degrau 1 — `hostname.exe` (Windows 10, PE32+)

### Resultado
✅ Parser funcionou sem modificação.

- format: PE32+ ✅
- entry_va: 0x1c10 (plausível, cai na .text)
- 6 seções: .text, .rdata, .data, .pdata, .rsrc, .reloc ✅
- 17 DLLs (incluindo API Sets api-ms-win-*) ✅
- 1 import por ordinal (WS2_32.dll ordinal 115) → `<ordinal:115>` ✅
- 1 símbolo C++ mangled (`?terminate@@YAXXZ`) ✅
- `.data` com VirtualSize (2072) > SizeOfRawData (512) — `rva_to_offset` lidou ✅
- ptr_symtab=0 (stripped), has_strtab=0 ✅

### Limites encontrados (e como o parser lidou)
| Limite | Comportamento |
|---|---|
| API Sets (`api-ms-win-*`) | Parseou normalmente |
| Import por ordinal | `<ordinal:NNN>` (não resolve nome real) |
| Símbolo C++ mangled | Parseou como string |
| `ptr_symtab = 0` (stripped) | `has_strtab = 0`, usou `copy_section_name` |
| `.data` com VirtualSize > SizeOfRawData | `rva_to_offset` lidou (range = virtual_size, offset até raw_size) |
| `.rsrc` (resources) | Parseou como seção normal |

---

## Degrau 2 — `where32.exe` (Windows 10, PE32)

### Resultado
✅ Parser funcionou sem modificação no path PE32.

- format: PE32 ✅
- entry_va: 0x6980 (plausível, cai na .text)
- 5 seções: .text, .data, .idata, .rsrc, .reloc ✅
- 7 DLLs: KERNEL32, msvcrt, ntdll, USER32, WS2_32, SHLWAPI, VERSION ✅
- 1 import por ordinal (WS2_32 ordinal 116) → `<ordinal:116>` ✅
- 1 símbolo C++ mangled (`?terminate@@YAXXZ`) ✅
- 1 função SEH do PE32 (`_except_handler4_common`) ✅
- ptr_symtab=0 (stripped), has_strtab=0 ✅

### O que o Degrau 2 confirma
- O path PE32 (thunks de 4 bytes, DataDirectory em opt+96) está correto.
- O parser lida com PE32 e PE32+ sem modificação.
- DLLs de sistema (ntdll) e funções SEH são parseadas normalmente.

---

## Limites eliminados no Degrau 0
1. Thunks de 8 bytes em PE32+ (uint64 vs uint32)
2. String Table após Symbol Table (ptr_symtab + num_syms * 18)
3. `rva_to_offset` sem VirtualSize (corrigido com virtual_size separado)
4. Nomes truncados em 8 chars (PRE_IR_SECTION_NAME_MAX = 256)

## Limites remanescentes (aceitos)
- Ordinal imports viram `<ordinal:NNN>`
- `FirstThunk` não usado (só `OriginalFirstThunk`)
- Sem validação de `Machine`
- Sem fuzz testing
- Sem validação de PE truncado/malicioso

## Próximo passo — Degrau 3
Fuzz testing do parser: truncar binários em vários pontos e verificar
onde o parser crasha (ou se crasha). Objetivo: validar a robustez
antes de avançar para o desmontador (Fase 3).
