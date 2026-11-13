/* functions.c — identificação de funções e call graph (Fase 5a) */
#include "functions.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Procura símbolo com va == target (binary search em ir->symbols). */
static const char *lookup_symbol(const PreIR *ir, uint64_t va)
{
    if (ir == NULL || ir->symbols == NULL || ir->symbol_count == 0) return NULL;
    uint32_t lo = 0, hi = ir->symbol_count;
    while (lo < hi) {
        uint32_t mid = (lo + hi) / 2;
        if (ir->symbols[mid].va < va) lo = mid + 1;
        else hi = mid;
    }
    if (lo < ir->symbol_count && ir->symbols[lo].va == va) {
        return ir->symbols[lo].name;
    }
    return NULL;
}

/* Encontra o índice da função cujo [start_va, end_va) contém va.
 * Entradas estão ordenadas por start_va. */
static int find_function_by_va(const FunctionList *fl, uint64_t va)
{
    if (fl->count == 0) return -1;
    uint32_t lo = 0, hi = fl->count;
    while (lo < hi) {
        uint32_t mid = (lo + hi) / 2;
        if (fl->entries[mid].start_va <= va) lo = mid + 1;
        else hi = mid;
    }
    if (lo == 0) return -1;
    const FunctionEntry *fe = &fl->entries[lo - 1];
    if (va < fe->end_va) return (int)(lo - 1);
    return -1;
}

/* Adiciona callee ao vetor (com dedupe). */
static void add_callee(FunctionEntry *fe, uint32_t idx)
{
    for (uint32_t k = 0; k < fe->callee_count; k++)
        if (fe->callee_idx[k] == idx) return;
    fe->callee_idx = (uint32_t *)realloc(
        fe->callee_idx, (fe->callee_count + 1) * sizeof(uint32_t));
    if (fe->callee_idx == NULL) return;  /* OOM: ignora aresta */
    fe->callee_idx[fe->callee_count++] = idx;
}

/* Contexto para qsort de candidatos. */
typedef struct { uint64_t va; const char *name; } Candidate;

static int cmp_candidate(const void *a, const void *b)
{
    const Candidate *ca = (const Candidate *)a;
    const Candidate *cb = (const Candidate *)b;
    if (ca->va < cb->va) return -1;
    if (ca->va > cb->va) return 1;
    return 0;
}

int functions_build(const InsnList *insns, const CFG *cfg, const PreIR *ir,
                    FunctionList *out, char *err_buf, size_t err_buf_size)
{
    if (out == NULL) return -1;
    memset(out, 0, sizeof(*out));
    if (insns == NULL || insns->count == 0) return 0;

    const uint64_t text_start = insns->insns[0].va;
    const DecodedInsn *last = &insns->insns[insns->count - 1];
    const uint64_t text_end = last->va + last->length;

    /* --- 1. Coletar candidatos --- */

    /* 1a. Símbolos dentro do .text */
    uint32_t cand_cap = (ir ? ir->symbol_count : 0) + insns->count / 4 + 16;
    Candidate *cands = (Candidate *)calloc(cand_cap, sizeof(Candidate));
    if (cands == NULL) {
        snprintf(err_buf, err_buf_size, "calloc candidates falhou");
        return -1;
    }
    uint32_t cand_count = 0;

    /* entrada do .text sempre é uma função */
    cands[cand_count].va = text_start;
    cands[cand_count].name = NULL;
    cand_count++;

    if (ir != NULL) {
        for (uint32_t i = 0; i < ir->symbol_count; i++) {
            uint64_t va = ir->symbols[i].va;
            if (va >= text_start && va < text_end) {
                /* Pular símbolos com nome de seção (.text, .data, etc.). */
                int is_section_name = 0;
                for (uint32_t s = 0; s < ir->section_count; s++) {
                    if (strcmp(ir->symbols[i].name, ir->sections[s].name) == 0) {
                        is_section_name = 1;
                        break;
                    }
                }
                if (is_section_name) continue;

                if (cand_count >= cand_cap) {
                    cand_cap *= 2;
                    cands = (Candidate *)realloc(cands, cand_cap * sizeof(Candidate));
                    if (cands == NULL) {
                        snprintf(err_buf, err_buf_size, "realloc candidates falhou");
                        return -1;
                    }
                }
                cands[cand_count].va = va;
                cands[cand_count].name = ir->symbols[i].name;
                cand_count++;
            }
        }
    }

    /* 1b. Alvos de CALL direta */
    for (uint32_t i = 0; i < insns->count; i++) {
        uint64_t target = 0;
        if (insn_control_flow(&insns->insns[i], &target) == CF_CALL && target != 0) {
            if (target >= text_start && target < text_end) {
                if (cand_count >= cand_cap) {
                    cand_cap *= 2;
                    cands = (Candidate *)realloc(cands, cand_cap * sizeof(Candidate));
                    if (cands == NULL) {
                        snprintf(err_buf, err_buf_size, "realloc candidates falhou");
                        return -1;
                    }
                }
                cands[cand_count].va = target;
                cands[cand_count].name = NULL;
                cand_count++;
            }
        }
    }

    /* --- 2. Ordenar e deduplicar (prefere nome) --- */
    qsort(cands, cand_count, sizeof(Candidate), cmp_candidate);

    uint32_t unique = 0;
    for (uint32_t i = 0; i < cand_count; i++) {
        if (unique > 0 && cands[i].va == cands[unique - 1].va) {
            if (cands[unique - 1].name == NULL && cands[i].name != NULL)
                cands[unique - 1].name = cands[i].name;
            continue;
        }
        cands[unique++] = cands[i];
    }

    if (unique == 0) {
        free(cands);
        return 0;
    }

    /* --- 3. Alocar FunctionList --- */
    out->entries = (FunctionEntry *)calloc(unique, sizeof(FunctionEntry));
    if (out->entries == NULL) {
        free(cands);
        snprintf(err_buf, err_buf_size, "calloc entries falhou");
        return -1;
    }
    out->count = unique;

    for (uint32_t i = 0; i < unique; i++) {
        FunctionEntry *fe = &out->entries[i];
        fe->start_va = cands[i].va;
        fe->end_va = (i + 1 < unique) ? cands[i + 1].va : text_end;
        fe->block_first = UINT32_MAX;
        fe->block_count = 0;
        fe->call_count = 0;
        fe->callee_count = 0;
        fe->callee_idx = NULL;

        if (cands[i].name != NULL) {
            fe->name = cands[i].name;   /* aponta para o símbolo em ir */
            fe->synth_name = NULL;
        } else {
            /* gera sub_XXXXXXXXXXXXXXXX */
            char *synth = (char *)malloc(24);
            if (synth != NULL) {
                snprintf(synth, 24, "sub_%llx", (unsigned long long)fe->start_va);
                fe->synth_name = synth;
                fe->name = synth;
            } else {
                fe->name = "<unnamed>";
            }
        }
    }
    free(cands);

    /* --- 4. Atribuir blocos e coletar CALLs --- */
    if (cfg != NULL) {
        for (uint32_t b = 0; b < cfg->block_count; b++) {
            int fi = find_function_by_va(out, cfg->blocks[b].start_va);
            if (fi < 0) continue;
            FunctionEntry *fe = &out->entries[fi];
            if (fe->block_first == UINT32_MAX) fe->block_first = b;
            fe->block_count++;

            uint32_t last_i = cfg->blocks[b].insn_first + cfg->blocks[b].insn_count - 1;
            const DecodedInsn *li = &insns->insns[last_i];
            uint64_t target = 0;
            if (insn_control_flow(li, &target) == CF_CALL) {
                fe->call_count++;
                if (target != 0) {
                    int ci = find_function_by_va(out, target);
                    if (ci >= 0) add_callee(fe, (uint32_t)ci);
                    else out->external_calls++;
                } else {
                    out->external_calls++;
                }
            }
        }
    }

    return 0;
}

void functions_free(FunctionList *fl)
{
    if (fl == NULL || fl->entries == NULL) return;
    for (uint32_t i = 0; i < fl->count; i++) {
        free(fl->entries[i].synth_name);
        free(fl->entries[i].callee_idx);
    }
    free(fl->entries);
    fl->entries = NULL;
    fl->count = 0;
}

void functions_print_text(const FunctionList *fl, FILE *out)
{
    if (fl == NULL || out == NULL) return;
    uint64_t total = 0;
    for (uint32_t i = 0; i < fl->count; i++)
        total += fl->entries[i].end_va - fl->entries[i].start_va;

    fprintf(out, "[FUNCTIONS] %u funções (%llu bytes de .text, %u chamadas externas)\n\n",
            fl->count, (unsigned long long)total, fl->external_calls);

    for (uint32_t i = 0; i < fl->count; i++) {
        const FunctionEntry *fe = &fl->entries[i];
        uint64_t size = fe->end_va - fe->start_va;

        char flags[64] = "-";
        patterns_format_flags(fe->flags, flags, sizeof(flags));

        fprintf(out, "  0x%016llx %-32s %5llu B  %3u blocos  %3u calls  [%-20s]",
                (unsigned long long)fe->start_va, fe->name,
                (unsigned long long)size, fe->block_count, fe->call_count, flags);

        if (fe->callee_count > 0) {
            fprintf(out, "  -> ");
            for (uint32_t k = 0; k < fe->callee_count; k++) {
                if (k > 0) fprintf(out, ", ");
                uint32_t ci = fe->callee_idx[k];
                fprintf(out, "%s", fl->entries[ci].name);
            }
        }
        fprintf(out, "\n");
    }
}

void functions_print_dot(const FunctionList *fl, FILE *out)
{
    if (fl == NULL || out == NULL) return;
    fprintf(out, "digraph CALLS {\n");
    fprintf(out, "  rankdir=LR;\n");
    fprintf(out, "  node [shape=box, fontname=\"monospace\", fontsize=9];\n");

    for (uint32_t i = 0; i < fl->count; i++) {
        const FunctionEntry *fe = &fl->entries[i];
        fprintf(out, "  f%u [label=\"%s\\n0x%llx\"];\n",
                i, fe->name, (unsigned long long)fe->start_va);
    }
    for (uint32_t i = 0; i < fl->count; i++) {
        const FunctionEntry *fe = &fl->entries[i];
        for (uint32_t k = 0; k < fe->callee_count; k++) {
            fprintf(out, "  f%u -> f%u;\n", i, fe->callee_idx[k]);
        }
    }
    fprintf(out, "}\n");
}
