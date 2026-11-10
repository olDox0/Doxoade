// doxoade/tools/rev_eng/src/pe_parser.c
/* pe_parser.c — parser PE32/PE32+ mínimo (Degrau 0)
 *
 * Fluxo:
 *   1. Lê DOS header (MZ), pega e_lfanew (offset do PE header)
 *   2. Lê PE signature ("PE\0\0")
 *   3. Lê COFF header (Machine, NumberOfSections, SizeOfOptionalHeader,
 *      PointerToSymbolTable, NumberOfSymbols)
 *   4. Lê Optional header (Magic → PE32 ou PE32+, AddressOfEntryPoint)
 *   5. Lê Section Table (com resolução de nomes longos via String Table,
 *      localizada após a Symbol Table)
 *   6. Lê Import Directory (RVA → offset via seções)
 *
 * Toda leitura valida bounds via file_reader_at().
 */
#include "pe_parser.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Offsets fixos do DOS header */
#define DOS_E_LFANEW_OFF   0x3C
#define DOS_MAGIC          0x5A4D  /* "MZ" em LE */

/* PE signature */
#define PE_SIG             0x00004550  /* "PE\0\0" em LE */

/* Machine types */
#define MACHINE_I386       0x014C
#define MACHINE_AMD64      0x8664

/* Optional header magic */
#define OPT_MAGIC_PE32     0x010B
#define OPT_MAGIC_PE32P    0x020B

/* Tamanho do COFF header (após a signature) */
#define COFF_HEADER_SIZE   20

/* Offsets dentro do COFF header */
#define COFF_PTR_SYMTAB    8
#define COFF_NUM_SYMS      12
#define COFF_OPT_SIZE      16

/* Tamanho de cada símbolo COFF */
#define COFF_SYMBOL_SIZE   18

/* Índice do Import Directory no DataDirectory */
#define DIR_IMPORT         1

/* Converte RVA para offset de arquivo, consultando as seções.
 * Retorna -1 se RVA não cair em nenhuma seção. */
static int rva_to_offset(const PreIR *ir, uint32_t rva, uint32_t *out_off)
{
    for (uint32_t i = 0; i < ir->section_count; i++) {
        const SectionEntry *s = &ir->sections[i];
        uint32_t vsize = s->virtual_size;
        /* Se VirtualSize == 0, usar raw_size (comportamento de alguns linkers). */
        if (vsize == 0) vsize = s->raw_size;

        if (rva >= s->va && rva < s->va + vsize) {
            uint32_t delta = rva - s->va;
            /* Se o delta excede o que está no arquivo, a região é zerada
             * em memória. Não há offset válido. */
            if (delta >= s->raw_size) {
                return -1;
            }
            *out_off = s->raw_offset + delta;
            return 0;
        }
    }
    return -1;
}

/* Lê string NUL-terminada do arquivo em `off`, copiando para `buf`.
 * Retorna 0 em sucesso, -1 se `off` fora de bounds ou string > buf_size-1. */
static int read_cstr(const FileReader *fr, size_t off,
                     char *buf, size_t buf_size)
{
    if (buf_size == 0) return -1;
    for (size_t i = 0; i < buf_size; i++) {
        uint8_t c;
        if (file_reader_u8(fr, off + i, &c) != 0) return -1;
        buf[i] = (char)c;
        if (c == 0) return 0;
    }
    return -1;
}

static int cmp_symbol_va(const void *a, const void *b)
{
    const SymbolEntry *sa = (const SymbolEntry *)a;
    const SymbolEntry *sb = (const SymbolEntry *)b;
    if (sa->va < sb->va) return -1;
    if (sa->va > sb->va) return 1;
    return 0;
}

/* Copia até `dst_size-1` chars, NUL-terminando. */
static void safe_strcpy(char *dst, const char *src, size_t dst_size)
{
    if (dst == NULL || dst_size == 0) return;
    if (src == NULL) { dst[0] = '\0'; return; }
    size_t n = strlen(src);
    if (n >= dst_size) n = dst_size - 1;
    memcpy(dst, src, n);
    dst[n] = '\0';
}


static int parse_symbols(const FileReader *fr, PreIR *ir,
                         uint32_t ptr_symtab, uint32_t num_syms,
                         size_t strtab_off, uint32_t strtab_size,
                         char *err_buf, size_t err_buf_size)
{
    ir->symbols = NULL;
    ir->symbol_count = 0;
    if (ptr_symtab == 0 || num_syms == 0) return 0;

    uint32_t real_count = 0;
    uint32_t i = 0;
    while (i < num_syms) {
        size_t off = (size_t)ptr_symtab + (size_t)i * 18;
        uint8_t num_aux = 0;
        if (file_reader_u8(fr, off + 17, &num_aux) != 0) break;
        real_count++;
        i += 1 + num_aux;
    }
    if (real_count == 0) return 0;

    SymbolEntry *syms = (SymbolEntry *)calloc(real_count, sizeof(SymbolEntry));
    if (syms == NULL) {
        safe_strcpy(err_buf, "calloc symbols falhou", err_buf_size);
        return -1;
    }

    i = 0;
    uint32_t written = 0;
    while (i < num_syms) {
        size_t off = (size_t)ptr_symtab + (size_t)i * 18;
        uint32_t name1 = 0, name2 = 0;
        if (file_reader_u32(fr, off,     &name1) != 0) break;
        if (file_reader_u32(fr, off + 4, &name2) != 0) break;

        uint32_t value = 0;
        uint16_t section_raw = 0;
        uint8_t  storage_class = 0, num_aux = 0;
        file_reader_u32(fr, off + 8,  &value);
        file_reader_u16(fr, off + 12, &section_raw);
        file_reader_u8 (fr, off + 16, &storage_class);
        file_reader_u8 (fr, off + 17, &num_aux);
        int16_t section = (int16_t)section_raw;

        char namebuf[256] = "";
        if (name1 == 0 && name2 != 0) {
            if (strtab_size > 4 && name2 < strtab_size) {
                read_cstr(fr, strtab_off + name2, namebuf, sizeof(namebuf));
            }
        } else {
            memcpy(namebuf, &name1, 4);
            memcpy(namebuf + 4, &name2, 4);
            namebuf[8] = '\0';
        }

        int is_section_sym = (storage_class == 3 && value == 0 && namebuf[0] == '.');
        if (section >= 1 && section <= (int)ir->section_count &&
            storage_class != 0 &&
            namebuf[0] != '\0' && !is_section_sym) {
            const SectionEntry *s = &ir->sections[section - 1];
            uint64_t va = ir->image_base + s->va + value;
            char *dup = strdup(namebuf);
            if (dup != NULL) {
                syms[written].va = va;
                syms[written].name = dup;
                written++;
            }
        }
        i += 1 + num_aux;
    }

    qsort(syms, written, sizeof(SymbolEntry), cmp_symbol_va);
    ir->symbols = syms;
    ir->symbol_count = written;
    return 0;
}

/* Resolve nome de seção que começa com "/N" via String Table.
 * `strtab_off` é o offset do início da String Table (primeiro uint32 = tamanho).
 * Retorna 0 em sucesso, -1 se não for /N ou se a resolução falhar. */
static int resolve_long_section_name(const FileReader *fr,
                                     const uint8_t *raw8,
                                     size_t strtab_off,
                                     char *out_name, size_t out_size)
{
    if (raw8[0] != '/') return -1;

    char numbuf[9];
    memcpy(numbuf, raw8 + 1, 7);
    numbuf[7] = '\0';
    for (int k = 0; k < 7; k++) {
        if (numbuf[k] == ' ' || numbuf[k] == '\0') { numbuf[k] = '\0'; break; }
    }
    long n = strtol(numbuf, NULL, 10);
    if (n <= 0) return -1;

    /* n é relativo ao início da String Table (inclui os 4 bytes de tamanho). */
    if (read_cstr(fr, strtab_off + (size_t)n, out_name, out_size) != 0) {
        return -1;
    }
    return 0;
}

/* Lê a Import Directory. */
static int parse_imports(const FileReader *fr, PreIR *ir,
                         uint32_t import_rva, uint32_t import_size,
                         char *err_buf, size_t err_buf_size)
{
    if (import_rva == 0 || import_size == 0) {
        ir->imports = NULL;
        ir->import_count = 0;
        return 0;
    }

    uint32_t imp_off;
    if (rva_to_offset(ir, import_rva, &imp_off) != 0) {
        safe_strcpy(err_buf, "import RVA fora de seção", err_buf_size);
        return -1;
    }

    int is_pe32plus = (ir->format != NULL && strcmp(ir->format, "PE32+") == 0);
    uint32_t thunk_size = is_pe32plus ? 8 : 4;

    uint32_t count = 0;
    for (uint32_t i = 0; ; i++) {
        size_t desc_off = (size_t)imp_off + i * 20;
        uint32_t name_rva;
        if (file_reader_u32(fr, desc_off + 12, &name_rva) != 0) break;
        if (name_rva == 0) break;
        count++;
        if (count > 256) {
            safe_strcpy(err_buf, "imports demais (>256), abortando", err_buf_size);
            return -1;
        }
    }

    if (count == 0) {
        ir->imports = NULL;
        ir->import_count = 0;
        return 0;
    }

    ImportEntry *imps = (ImportEntry *)calloc(count, sizeof(ImportEntry));
    if (imps == NULL) {
        safe_strcpy(err_buf, "calloc imports falhou", err_buf_size);
        return -1;
    }

    for (uint32_t i = 0; i < count; i++) {
        size_t desc_off = (size_t)imp_off + i * 20;
        uint32_t oft = 0, name_rva = 0;
        file_reader_u32(fr, desc_off,      &oft);
        file_reader_u32(fr, desc_off + 12, &name_rva);

        ImportEntry *imp = &imps[i];

        uint32_t name_off;
        if (rva_to_offset(ir, name_rva, &name_off) == 0) {
            if (read_cstr(fr, name_off, imp->dll, PRE_IR_DLL_NAME_MAX) != 0) {
                safe_strcpy(imp->dll, "<nome-longa>", PRE_IR_DLL_NAME_MAX);
            }
        } else {
            safe_strcpy(imp->dll, "<rva-invalida>", PRE_IR_DLL_NAME_MAX);
        }

        if (oft == 0) {
            imp->func_count = 0;
            imp->funcs = NULL;
            continue;
        }

        uint32_t oft_off;
        if (rva_to_offset(ir, oft, &oft_off) != 0) {
            imp->func_count = 0;
            imp->funcs = NULL;
            continue;
        }

        uint32_t fcount = 0;
        for (uint32_t j = 0; ; j++) {
            if (is_pe32plus) {
                uint64_t e64;
                if (file_reader_u64(fr, (size_t)oft_off + (size_t)j * 8, &e64) != 0) break;
                if (e64 == 0) break;
            } else {
                uint32_t e32;
                if (file_reader_u32(fr, (size_t)oft_off + (size_t)j * 4, &e32) != 0) break;
                if (e32 == 0) break;
            }
            fcount++;
            if (fcount > 4096) break;
        }

        if (fcount == 0) {
            imp->func_count = 0;
            imp->funcs = NULL;
            continue;
        }

        char **funcs = (char **)calloc(fcount, sizeof(char *));
        if (funcs == NULL) {
            safe_strcpy(err_buf, "calloc funcs falhou", err_buf_size);
            ir->imports = imps;
            ir->import_count = i;
            return -1;
        }

        uint32_t fwritten = 0;
        for (uint32_t j = 0; j < fcount; j++) {
            uint64_t entry64 = 0;
            uint32_t entry32 = 0;

            if (is_pe32plus) {
                file_reader_u64(fr, (size_t)oft_off + (size_t)j * 8, &entry64);
            } else {
                file_reader_u32(fr, (size_t)oft_off + (size_t)j * 4, &entry32);
            }

            uint64_t entry = is_pe32plus ? entry64 : (uint64_t)entry32;
            if (entry == 0) break;

            int is_ordinal;
            uint64_t name_or_ordinal;
            if (is_pe32plus) {
                is_ordinal = (entry & 0x8000000000000000ULL) != 0;
                name_or_ordinal = entry & 0x7FFFFFFFFFFFFFFFULL;
            } else {
                is_ordinal = (entry & 0x80000000u) != 0;
                name_or_ordinal = entry & 0x7FFFFFFFu;
            }

            if (is_ordinal) {
                char tmp[32];
                snprintf(tmp, sizeof(tmp), "<ordinal:%llu>",
                         (unsigned long long)(name_or_ordinal & 0xFFFF));
                funcs[fwritten] = strdup(tmp);
            } else {
                uint32_t hint_off;
                if (rva_to_offset(ir, (uint32_t)name_or_ordinal, &hint_off) == 0) {
                    char name_buf[256];
                    if (read_cstr(fr, hint_off + 2, name_buf, sizeof(name_buf)) == 0) {
                        funcs[fwritten] = strdup(name_buf);
                    } else {
                        funcs[fwritten] = strdup("<nome-invalido>");
                    }
                } else {
                    funcs[fwritten] = strdup("<rva-invalida>");
                }
            }
            if (funcs[fwritten] == NULL) {
                for (uint32_t k = 0; k < fwritten; k++) free(funcs[k]);
                free(funcs);
                safe_strcpy(err_buf, "strdup falhou", err_buf_size);
                ir->imports = imps;
                ir->import_count = i;
                return -1;
            }
            fwritten++;
        }

        imp->funcs = funcs;
        imp->func_count = fwritten;
    }

    ir->imports = imps;
    ir->import_count = count;
    return 0;
}

/* Copia nome de seção (8 bytes, possivelmente sem NUL) para buf[9]. */
static void copy_section_name(const uint8_t *raw8, char *buf9)
{
    int i;
    for (i = 0; i < 8; i++) {
        if (raw8[i] == 0) break;
        buf9[i] = (char)raw8[i];
    }
    buf9[i] = '\0';
}

int pe_parse(const FileReader *fr, PreIR *out,
             char *err_buf, size_t err_buf_size)
{
    if (fr == NULL || out == NULL) return -1;

    memset(out, 0, sizeof(*out));
    out->file_path = fr->path;

    /* 1. DOS header: MZ */
    uint16_t mz;
    if (file_reader_u16(fr, 0, &mz) != 0 || mz != DOS_MAGIC) {
        safe_strcpy(err_buf, "assinatura MZ ausente", err_buf_size);
        return -1;
    }

    uint32_t e_lfanew;
    if (file_reader_u32(fr, DOS_E_LFANEW_OFF, &e_lfanew) != 0) {
        safe_strcpy(err_buf, "e_lfanew inacessível", err_buf_size);
        return -1;
    }
    if (e_lfanew < 0x40 || e_lfanew > fr->size - 24) {
        safe_strcpy(err_buf, "e_lfanew fora de bounds", err_buf_size);
        return -1;
    }

    /* 2. PE signature */
    uint32_t sig;
    if (file_reader_u32(fr, e_lfanew, &sig) != 0 || sig != PE_SIG) {
        safe_strcpy(err_buf, "assinatura PE ausente", err_buf_size);
        return -1;
    }

    /* 3. COFF header */
    size_t coff_off = (size_t)e_lfanew + 4;
    uint16_t machine, num_sections, opt_size;
    uint32_t ptr_symtab, num_syms;
    if (file_reader_u16(fr, coff_off,                &machine)      != 0 ||
        file_reader_u16(fr, coff_off + 2,            &num_sections) != 0 ||
        file_reader_u16(fr, coff_off + COFF_OPT_SIZE,&opt_size)     != 0 ||
        file_reader_u32(fr, coff_off + COFF_PTR_SYMTAB, &ptr_symtab) != 0 ||
        file_reader_u32(fr, coff_off + COFF_NUM_SYMS,   &num_syms)   != 0) {
        safe_strcpy(err_buf, "COFF header inacessível", err_buf_size);
        return -1;
    }
    (void)machine;

    if (num_sections == 0 || num_sections > 96) {
        safe_strcpy(err_buf, "num_sections fora de faixa", err_buf_size);
        return -1;
    }

    /* 4. Optional header */
    size_t opt_off = coff_off + COFF_HEADER_SIZE;
    uint16_t opt_magic;
    if (file_reader_u16(fr, opt_off, &opt_magic) != 0) {
        safe_strcpy(err_buf, "optional header inacessível", err_buf_size);
        return -1;
    }

    uint32_t entry_rva = 0;
    uint32_t import_rva = 0, import_size = 0;

    if (opt_magic == OPT_MAGIC_PE32) {
        out->format = "PE32";
        file_reader_u32(fr, opt_off + 16, &entry_rva);
        file_reader_u32(fr, opt_off + 96 + DIR_IMPORT * 8,     &import_rva);
        file_reader_u32(fr, opt_off + 96 + DIR_IMPORT * 8 + 4, &import_size);
    } else if (opt_magic == OPT_MAGIC_PE32P) {
        out->format = "PE32+";
        file_reader_u32(fr, opt_off + 16, &entry_rva);
        file_reader_u32(fr, opt_off + 112 + DIR_IMPORT * 8,     &import_rva);
        file_reader_u32(fr, opt_off + 112 + DIR_IMPORT * 8 + 4, &import_size);
    } else {
        safe_strcpy(err_buf, "optional header magic desconhecido", err_buf_size);
        return -1;
    }

    out->entry_va = entry_rva;

    if (opt_magic == OPT_MAGIC_PE32) {
        uint32_t ib;
        if (file_reader_u32(fr, opt_off + 28, &ib) == 0) out->image_base = ib;
    } else {
        file_reader_u64(fr, opt_off + 24, &out->image_base);
    }

    /* 5. String Table: começa após a Symbol Table.
     * Symbol Table começa em PointerToSymbolTable e tem
     * NumberOfSymbols entradas de 18 bytes cada. */
    size_t strtab_off = 0;
    uint32_t strtab_size = 0;
    int has_strtab = 0;

    if (ptr_symtab != 0 && num_syms != 0) {
        strtab_off = (size_t)ptr_symtab + (size_t)num_syms * COFF_SYMBOL_SIZE;
        if (file_reader_u32(fr, strtab_off, &strtab_size) == 0 && strtab_size > 4) {
            has_strtab = 1;
        }
    }

#ifdef DOXREVENG_DEBUG_IMPORTS
    fprintf(stderr, "[DEBUG] e_lfanew=0x%x coff_off=0x%zx opt_off=0x%zx opt_size=%u\n",
            e_lfanew, coff_off, opt_off, opt_size);
    fprintf(stderr, "[DEBUG] ptr_symtab=0x%x num_syms=%u strtab_off=0x%zx strtab_size=%u has_strtab=%d\n",
            ptr_symtab, num_syms, strtab_off, strtab_size, has_strtab);
#endif

    /* 6. Section table */
    size_t sec_off = opt_off + opt_size;
    SectionEntry *secs = (SectionEntry *)calloc(num_sections, sizeof(SectionEntry));
    if (secs == NULL) {
        safe_strcpy(err_buf, "calloc sections falhou", err_buf_size);
        return -1;
    }

    for (uint16_t i = 0; i < num_sections; i++) {
        size_t off = sec_off + (size_t)i * 40;
        uint8_t raw_name[8];
        const uint8_t *np = file_reader_at(fr, off, 8);
        if (np == NULL) {
            free(secs);
            safe_strcpy(err_buf, "section table truncada", err_buf_size);
            return -1;
        }
        memcpy(raw_name, np, 8);

        char resolved[256];
        int resolved_ok = 0;
        if (has_strtab &&
            resolve_long_section_name(fr, raw_name, strtab_off,
                                      resolved, sizeof(resolved)) == 0) {
            safe_strcpy(secs[i].name, resolved, PRE_IR_SECTION_NAME_MAX);
            resolved_ok = 1;
        } else {
            copy_section_name(raw_name, secs[i].name);
        }

#ifdef DOXREVENG_DEBUG_IMPORTS
        if (raw_name[0] == '/' || resolved_ok) {
            fprintf(stderr, "[DEBUG] section[%u] raw='%.8s' resolved='%s' ok=%d\n",
                    i, (const char*)raw_name, secs[i].name, resolved_ok);
        }
#endif

        file_reader_u32(fr, off + 8,  &secs[i].virtual_size);   /* VirtualSize */
        file_reader_u32(fr, off + 12, &secs[i].va);             /* VirtualAddress */
        file_reader_u32(fr, off + 16, &secs[i].raw_size);       /* SizeOfRawData */
        file_reader_u32(fr, off + 20, &secs[i].raw_offset);     /* PointerToRawData */
        file_reader_u32(fr, off + 36, &secs[i].characteristics);
    }
    out->sections = secs;
    out->section_count = num_sections;

    parse_symbols(fr, out, ptr_symtab, num_syms,
                  strtab_off, strtab_size, err_buf, err_buf_size);

    /* 7. Imports */
    if (parse_imports(fr, out, import_rva, import_size, err_buf, err_buf_size) != 0) {
        pre_ir_free(out);
        return -1;
    }

    return 0;
}
