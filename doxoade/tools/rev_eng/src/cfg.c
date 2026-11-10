/* cfg.c — construção de blocos básicos (Fase 4) */
#include "cfg.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Encontra o índice de instrução cujo VA == va.
 * Retorna -1 se não houver (alvo externo ou inválido).
 * As instruções estão em ordem crescente de VA. */
static int find_insn_by_va(const InsnList *insns, uint64_t va)
{
    uint32_t lo = 0, hi = insns->count;
    while (lo < hi) {
        uint32_t mid = (lo + hi) / 2;
        if (insns->insns[mid].va < va) lo = mid + 1;
        else hi = mid;
    }
    if (lo < insns->count && insns->insns[lo].va == va) return (int)lo;
    return -1;
}

/* Encontra o índice de bloco cujo start_va == va. Retorna -1 se não houver. */
static int find_block_by_start(const CFG *cfg, uint64_t va)
{
    for (uint32_t i = 0; i < cfg->block_count; i++) {
        if (cfg->blocks[i].start_va == va) return (int)i;
    }
    return -1;
}

int cfg_build(const InsnList *insns, CFG *out,
              char *err_buf, size_t err_buf_size)
{
    if (insns == NULL || out == NULL) return -1;
    memset(out, 0, sizeof(*out));
    out->insns = insns;
    if (insns->count == 0) return 0;

    /* 1. Coletar líderes.
     * Líderes: primeira instrução, alvos de jcc/jmp, instrução após jcc/jmp/ret. */
    uint8_t *is_leader = (uint8_t *)calloc(insns->count, 1);
    if (is_leader == NULL) {
        snprintf(err_buf, err_buf_size, "calloc leaders falhou");
        return -1;
    }
    is_leader[0] = 1;

    for (uint32_t i = 0; i < insns->count; i++) {
        uint64_t target = 0;
        ControlFlowType cf = insn_control_flow(&insns->insns[i], &target);

        /* Alvo de salto é líder (se cair em uma instrução conhecida). */
        if ((cf == CF_JCC || cf == CF_JMP) && target != 0) {
            int ti = find_insn_by_va(insns, target);
            if (ti >= 0) is_leader[ti] = 1;
        }

        /* Instrução após jcc/jmp/ret é líder (fallthrough). */
        if (cf == CF_JCC || cf == CF_JMP || cf == CF_RET) {
            if (i + 1 < insns->count) is_leader[i + 1] = 1;
        }
        /* call também gera fallthrough líder (a chamada retorna). */
        if (cf == CF_CALL && i + 1 < insns->count) {
            is_leader[i + 1] = 1;
        }
    }

    /* 2. Contar blocos. */
    uint32_t nblocks = 0;
    for (uint32_t i = 0; i < insns->count; i++) if (is_leader[i]) nblocks++;

    if (nblocks == 0) {
        free(is_leader);
        return 0;
    }

    BasicBlock *blocks = (BasicBlock *)calloc(nblocks, sizeof(BasicBlock));
    if (blocks == NULL) {
        free(is_leader);
        snprintf(err_buf, err_buf_size, "calloc blocks falhou");
        return -1;
    }

    /* 3. Agrupar instruções em blocos. */
    uint32_t bi = 0;
    uint32_t i = 0;
    while (i < insns->count) {
        if (!is_leader[i]) { i++; continue; }
        BasicBlock *b = &blocks[bi];
        b->start_va = insns->insns[i].va;
        b->insn_first = i;
        uint32_t j = i;
        while (j < insns->count) {
            j++;
            if (j >= insns->count) break;
            if (is_leader[j]) break;
        }
        b->insn_count = j - i;
        b->end_va = insns->insns[j - 1].va + insns->insns[j - 1].length;
        bi++;
        i = j;
    }
    out->block_count = nblocks;
    out->blocks = blocks;

    /* 4. Calcular sucessores. */
    for (uint32_t b = 0; b < nblocks; b++) {
        BasicBlock *blk = &blocks[b];
        uint32_t last_idx = blk->insn_first + blk->insn_count - 1;
        const DecodedInsn *last = &insns->insns[last_idx];
        uint64_t target = 0;
        ControlFlowType cf = insn_control_flow(last, &target);

        uint32_t succ[2] = {0, 0};
        uint32_t nsucc = 0;

        switch (cf) {
            case CF_JCC: {
                /* fallthrough: bloco seguinte (se existir e for contíguo) */
                if (b + 1 < nblocks && blocks[b + 1].start_va == blk->end_va) {
                    succ[nsucc++] = b + 1;
                }
                /* alvo: bloco cujo start_va == target */
                if (target != 0) {
                    int ti = find_block_by_start(out, target);
                    if (ti >= 0) succ[nsucc++] = (uint32_t)ti;
                }
                break;
            }
            case CF_JMP: {
                if (target != 0) {
                    int ti = find_block_by_start(out, target);
                    if (ti >= 0) succ[nsucc++] = (uint32_t)ti;
                }
                break;
            }
            case CF_CALL:
            case CF_NONE: {
                /* fallthrough */
                if (b + 1 < nblocks && blocks[b + 1].start_va == blk->end_va) {
                    succ[nsucc++] = b + 1;
                }
                break;
            }
            case CF_RET:
                /* sem sucessores */
                break;
        }

        if (nsucc == 0) {
            blk->succ_count = 0;
            blk->succ_idx = NULL;
        } else {
            blk->succ_idx = (uint32_t *)malloc(nsucc * sizeof(uint32_t));
            if (blk->succ_idx == NULL) {
                snprintf(err_buf, err_buf_size, "malloc succ falhou");
                /* libera o que já foi */
                for (uint32_t k = 0; k < b; k++) free(blocks[k].succ_idx);
                free(blocks);
                out->blocks = NULL;
                out->block_count = 0;
                free(is_leader);
                return -1;
            }
            memcpy(blk->succ_idx, succ, nsucc * sizeof(uint32_t));
            blk->succ_count = nsucc;
        }
    }

    free(is_leader);
    return 0;
}

void cfg_free(CFG *cfg)
{
    if (cfg == NULL) return;
    if (cfg->blocks != NULL) {
        for (uint32_t i = 0; i < cfg->block_count; i++) {
            free(cfg->blocks[i].succ_idx);
        }
        free(cfg->blocks);
        cfg->blocks = NULL;
    }
    cfg->block_count = 0;
    cfg->insns = NULL;
}

void cfg_print_text(const CFG *cfg, const InsnList *insns, FILE *out)
{
    fprintf(out, "[CFG] %u instruções, %u blocos básicos\n\n",
            insns->count, cfg->block_count);
    for (uint32_t b = 0; b < cfg->block_count; b++) {
        const BasicBlock *blk = &cfg->blocks[b];
        fprintf(out, "Bloco %u: 0x%llx - 0x%llx (%u instruções)\n",
                b, (unsigned long long)blk->start_va,
                (unsigned long long)blk->end_va, blk->insn_count);

        /* Primeira e última instrução do bloco (para leitura rápida). */
        const DecodedInsn *first = &insns->insns[blk->insn_first];
        const DecodedInsn *last  = &insns->insns[blk->insn_first + blk->insn_count - 1];
        fprintf(out, "  primeira: 0x%llx (%u bytes)\n",
                (unsigned long long)first->va, first->length);
        fprintf(out, "  última:   0x%llx (%u bytes)\n",
                (unsigned long long)last->va, last->length);

        if (blk->succ_count == 0) {
            fprintf(out, "  sucessores: (nenhum — ret ou fim de região)\n\n");
        } else {
            fprintf(out, "  sucessores:");
            for (uint32_t s = 0; s < blk->succ_count; s++) {
                uint32_t sidx = blk->succ_idx[s];
                fprintf(out, " [%u] 0x%llx", sidx,
                        (unsigned long long)cfg->blocks[sidx].start_va);
            }
            fprintf(out, "\n\n");
        }
    }
}

void cfg_print_dot(const CFG *cfg, const InsnList *insns, FILE *out)
{
    (void)insns;
    fprintf(out, "digraph CFG {\n");
    fprintf(out, "  rankdir=TB;\n");
    fprintf(out, "  node [shape=box, fontname=\"monospace\", fontsize=9];\n");
    for (uint32_t b = 0; b < cfg->block_count; b++) {
        const BasicBlock *blk = &cfg->blocks[b];
        fprintf(out, "  b%u [label=\"B%u\\n0x%llx\\n%u insns\"];\n",
                b, b, (unsigned long long)blk->start_va, blk->insn_count);
    }
    for (uint32_t b = 0; b < cfg->block_count; b++) {
        const BasicBlock *blk = &cfg->blocks[b];
        for (uint32_t s = 0; s < blk->succ_count; s++) {
            fprintf(out, "  b%u -> b%u;\n", b, blk->succ_idx[s]);
        }
    }
    fprintf(out, "}\n");
}
