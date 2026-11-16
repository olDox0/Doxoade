/* xref.c — banco de referências cruzadas (Fase 5c) */
#include "xref.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Procura símbolo com va == target (binary search). */
static const char *lookup_symbol(const PreIR *ir, uint64_t va)
{
    if (ir == NULL || ir->symbols == NULL || ir->symbol_count == 0) return NULL;
    uint32_t lo = 0, hi = ir->symbol_count;
    while (lo < hi) {
        uint32_t mid = (lo + hi) / 2;
        if (ir->symbols[mid].va < va) lo = mid + 1;
        else hi = mid;
    }
    if (lo < ir->symbol_count && ir->symbols[lo].va == va)
        return ir->symbols[lo].name;
    return NULL;
}

static void resolve_target(const PreIR *ir, uint64_t va, XrefEntry *x)
{
    x->target_name = lookup_symbol(ir, va);
    x->owned_name = NULL;
}

int xref_build(const InsnList *insns, const PreIR *ir,
               const FunctionList *fl,
               XrefList *out, char *err_buf, size_t err_buf_size)
{
    (void)fl;
    if (out == NULL) return -1;
    memset(out, 0, sizeof(*out));
    if (insns == NULL || insns->count == 0) return 0;

    uint32_t cap = insns->count / 4 + 16;
    XrefEntry *arr = (XrefEntry *)calloc(cap, sizeof(XrefEntry));
    if (arr == NULL) {
        snprintf(err_buf, err_buf_size, "calloc xrefs falhou");
        return -1;
    }
    uint32_t n = 0;

    for (uint32_t i = 0; i < insns->count; i++) {
        const DecodedInsn *insn = &insns->insns[i];
        uint64_t target = 0;
        ControlFlowType cf = insn_control_flow(insn, &target);

        XrefType type;
        int has = 0;

        if (cf == CF_CALL && target != 0) { type = XREF_CODE_CALL; has = 1; }
        else if (cf == CF_JMP && target != 0) { type = XREF_CODE_JMP; has = 1; }
        else if (cf == CF_JCC && target != 0) { type = XREF_CODE_JCC; has = 1; }

        if (has) {
            if (n >= cap) {
                cap *= 2;
                XrefEntry *tmp = (XrefEntry *)realloc(arr, cap * sizeof(XrefEntry));
                if (tmp == NULL) { free(arr); return -1; }
                arr = tmp;
            }
            arr[n].target_va = target;
            arr[n].source_va = insn->va;
            arr[n].type = type;
            resolve_target(ir, target, &arr[n]);
            n++;
        }

        if (insn->has_rip_target) {
            if (n >= cap) {
                cap *= 2;
                XrefEntry *tmp = (XrefEntry *)realloc(arr, cap * sizeof(XrefEntry));
                if (tmp == NULL) { free(arr); return -1; }
                arr = tmp;
            }
            arr[n].target_va = insn->rip_target;
            arr[n].source_va = insn->va;
            arr[n].type = XREF_DATA_RIP;
            resolve_target(ir, insn->rip_target, &arr[n]);
            n++;
        }
    }

    out->count = n;
    out->entries = arr;
    return 0;
}

void xref_free(XrefList *xl)
{
    if (xl == NULL || xl->entries == NULL) return;
    for (uint32_t i = 0; i < xl->count; i++)
        free(xl->entries[i].owned_name);
    free(xl->entries);
    xl->entries = NULL;
    xl->count = 0;
}

static const char *type_name(XrefType t)
{
    switch (t) {
        case XREF_CODE_CALL: return "CALL";
        case XREF_CODE_JMP:  return "JMP";
        case XREF_CODE_JCC:  return "JCC";
        case XREF_DATA_RIP:  return "RIP";
        case XREF_DATA_ABS:  return "ABS";
    }
    return "?";
}

void xref_print_text(const XrefList *xl, FILE *out)
{
    if (xl == NULL || out == NULL) return;
    fprintf(out, "[XREF] %u referências\n\n", xl->count);
    for (uint32_t i = 0; i < xl->count; i++) {
        const XrefEntry *x = &xl->entries[i];
        fprintf(out, "  %-4s 0x%016llx -> 0x%016llx",
                type_name(x->type),
                (unsigned long long)x->source_va,
                (unsigned long long)x->target_va);
        if (x->target_name != NULL)
            fprintf(out, "  <%s>", x->target_name);
        fprintf(out, "\n");
    }
}

int xref_print_target(const XrefList *xl, uint64_t target_va, FILE *out)
{
    if (xl == NULL || out == NULL) return -1;
    int found = 0;
    for (uint32_t i = 0; i < xl->count; i++) {
        const XrefEntry *x = &xl->entries[i];
        if (x->target_va == target_va) {
            if (!found)
                fprintf(out, "[XREF] quem referencia 0x%llx:\n",
                        (unsigned long long)target_va);
            fprintf(out, "  %-4s 0x%016llx",
                    type_name(x->type),
                    (unsigned long long)x->source_va);
            if (x->target_name)
                fprintf(out, "  <%s>", x->target_name);
            fprintf(out, "\n");
            found++;
        }
    }
    return found;
}

void xref_stats(const XrefList *xl,
                uint32_t *calls, uint32_t *jmps, uint32_t *jccs,
                uint32_t *rips, uint32_t *abs)
{
    *calls = *jmps = *jccs = *rips = *abs = 0;
    for (uint32_t i = 0; i < xl->count; i++) {
        switch (xl->entries[i].type) {
            case XREF_CODE_CALL: (*calls)++; break;
            case XREF_CODE_JMP:  (*jmps)++; break;
            case XREF_CODE_JCC:  (*jccs)++; break;
            case XREF_DATA_RIP:  (*rips)++; break;
            case XREF_DATA_ABS:  (*abs)++; break;
        }
    }
}
