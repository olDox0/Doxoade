/* pre_ir.h — IR arcaica, descartável, para estudo */
#ifndef PRE_IR_H
#define PRE_IR_H

#include <stdint.h>
#include <stdio.h>

#define PRE_IR_SECTION_NAME_MAX 256
#define PRE_IR_DLL_NAME_MAX     64

typedef struct {
    char     name[PRE_IR_SECTION_NAME_MAX];
    uint32_t va;
    uint32_t virtual_size;
    uint32_t raw_offset;
    uint32_t raw_size;
    uint32_t characteristics;
} SectionEntry;

typedef struct {
    char     dll[PRE_IR_DLL_NAME_MAX];
    uint32_t func_count;
    char   **funcs;
} ImportEntry;

typedef struct {
    uint64_t va;
    char    *name;
} SymbolEntry;

typedef struct {
    const char   *file_path;
    const char   *format;
    uint64_t      image_base;
    uint32_t      entry_va;
    uint32_t      section_count;
    SectionEntry *sections;
    uint32_t      import_count;
    ImportEntry  *imports;
    uint32_t      symbol_count;
    SymbolEntry  *symbols;
} PreIR;

int pre_ir_print_json(const PreIR *ir, FILE *out);
void pre_ir_free(PreIR *ir);

#endif /* PRE_IR_H */
