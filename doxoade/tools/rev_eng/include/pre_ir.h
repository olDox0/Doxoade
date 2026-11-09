/* pre_ir.h — IR arcaica, descartável, para estudo (Degrau 0) */
#ifndef PRE_IR_H
#define PRE_IR_H

#include <stdint.h>
#include <stdio.h>

#define PRE_IR_SECTION_NAME_MAX 256
#define PRE_IR_DLL_NAME_MAX     64

typedef struct {
    char     name[PRE_IR_SECTION_NAME_MAX];
    uint32_t va;
    uint32_t virtual_size;    /* VirtualSize (novo) */
    uint32_t raw_offset;
    uint32_t raw_size;        /* SizeOfRawData */
    uint32_t characteristics;
} SectionEntry;

typedef struct {
    char     dll[PRE_IR_DLL_NAME_MAX];
    uint32_t func_count;
    char   **funcs;
} ImportEntry;

typedef struct {
    const char   *file_path;
    const char   *format;
    uint32_t      entry_va;
    uint32_t      section_count;
    SectionEntry *sections;
    uint32_t      import_count;
    ImportEntry  *imports;
} PreIR;

int pre_ir_print_json(const PreIR *ir, FILE *out);
void pre_ir_free(PreIR *ir);

#endif
