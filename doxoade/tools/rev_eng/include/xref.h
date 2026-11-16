/* xref.h — banco de referências cruzadas (Fase 5c) */
#ifndef XREF_H
#define XREF_H

#include "disasm.h"
#include "pre_ir.h"
#include "functions.h"
#include <stdio.h>

typedef enum {
    XREF_CODE_CALL = 0,
    XREF_CODE_JMP,
    XREF_CODE_JCC,
    XREF_DATA_RIP,
    XREF_DATA_ABS,
} XrefType;

typedef struct {
    uint64_t    target_va;
    uint64_t    source_va;
    XrefType    type;
    const char *target_name;
    char       *owned_name;
} XrefEntry;

typedef struct {
    uint32_t   count;
    XrefEntry *entries;
} XrefList;

int xref_build(const InsnList *insns, const PreIR *ir,
               const FunctionList *fl,
               XrefList *out, char *err_buf, size_t err_buf_size);

void xref_free(XrefList *xl);

void xref_print_text(const XrefList *xl, FILE *out);

int xref_print_target(const XrefList *xl, uint64_t target_va, FILE *out);

void xref_stats(const XrefList *xl,
                uint32_t *calls, uint32_t *jmps, uint32_t *jccs,
                uint32_t *rips, uint32_t *abs);

#endif /* XREF_H */
