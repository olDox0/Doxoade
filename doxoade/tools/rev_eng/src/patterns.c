/* patterns.c — detecção de padrões de arquitetura x86-64 (Fase 5b) */
#include "patterns.h"
#include <string.h>
#include <stdio.h>

/* Retorna a primeira instrução da função. */
static const DecodedInsn *first_insn(const InsnList *insns, const CFG *cfg,
                                     const FunctionEntry *fe) {
    if (cfg == NULL || fe->block_first == UINT32_MAX) return NULL;
    uint32_t idx = cfg->blocks[fe->block_first].insn_first;
    if (idx >= insns->count) return NULL;
    return &insns->insns[idx];
}

/* Retorna a última instrução da função. */
static const DecodedInsn *last_insn(const InsnList *insns, const CFG *cfg,
                                    const FunctionEntry *fe) {
    if (cfg == NULL || fe->block_first == UINT32_MAX || fe->block_count == 0) return NULL;
    uint32_t last_b = fe->block_first + fe->block_count - 1;
    uint32_t last_i = cfg->blocks[last_b].insn_first
                    + cfg->blocks[last_b].insn_count - 1;
    if (last_i >= insns->count) return NULL;
    return &insns->insns[last_i];
}

/* Itera por todas as instruções da função, chamando cb. */
static int scan_function(const InsnList *insns, const CFG *cfg,
                         const FunctionEntry *fe,
                         int (*cb)(const DecodedInsn *)) {
    if (cfg == NULL || fe->block_first == UINT32_MAX) return 0;
    uint32_t b0 = fe->block_first;
    uint32_t bN = b0 + fe->block_count;
    for (uint32_t b = b0; b < bN && b < cfg->block_count; b++) {
        uint32_t i0 = cfg->blocks[b].insn_first;
        uint32_t iN = i0 + cfg->blocks[b].insn_count;
        for (uint32_t i = i0; i < iN && i < insns->count; i++) {
            if (cb(&insns->insns[i])) return 1;
        }
    }
    return 0;
}

/* --- Detecção de frame pointer --- */

static int detect_fp_cb(const DecodedInsn *insn) {
    (void)insn;
    return 0;
}

/* Olha as 3 primeiras instruções: push rbp + mov rbp, rsp. */
static int detect_fp(const InsnList *insns, const CFG *cfg, const FunctionEntry *fe) {
    if (cfg == NULL || fe->block_first == UINT32_MAX) return 0;
    uint32_t idx = cfg->blocks[fe->block_first].insn_first;
    uint32_t end = idx + 3;
    if (end > insns->count) end = insns->count;

    for (uint32_t i = idx; i < end; i++) {
        const DecodedInsn *insn = &insns->insns[i];
        /* Capstone: mnemonic "push", op_str "rbp" */
        if (insn->mnemonic[0] != '\0') {
            if (strcmp(insn->mnemonic, "push") == 0 &&
                strcmp(insn->op_str, "rbp") == 0) {
                if (i + 1 < end) {
                    const DecodedInsn *n = &insns->insns[i + 1];
                    if (strcmp(n->mnemonic, "mov") == 0 &&
                        (strcmp(n->op_str, "rbp, rsp") == 0 ||
                         strcmp(n->op_str, "ebp, esp") == 0)) {
                        return 1;
                    }
                }
            }
        } else {
            /* Nativo: 0x55 = push rbp; 0x89 0xE5 = mov rbp, rsp */
            if (insn->opcode_len == 1 && insn->opcode == 0x55) {
                if (i + 1 < end) {
                    const DecodedInsn *n = &insns->insns[i + 1];
                    if (n->opcode_len == 1 && n->opcode == 0x89 &&
                        n->has_modrm && n->modrm == 0xE5) {
                        return 1;
                    }
                }
            }
        }
    }
    return 0;
}

/* --- Detecção de canary --- */

static int canary_cb(const DecodedInsn *insn) {
    if (insn->op_str[0] && strstr(insn->op_str, "gs:0x28")) return 1;
    return 0;
}

static int detect_canary(const InsnList *insns, const CFG *cfg, const FunctionEntry *fe) {
    return scan_function(insns, cfg, fe, canary_cb);
}

/* --- Detecção de tail call --- */

static int is_jmp_mnemo(const char *m) {
    return strncmp(m, "jmp", 3) == 0 && m[3] == '\0';
}

static int is_ret_mnemo(const char *m) {
    return strncmp(m, "ret", 3) == 0;
}

static int detect_tailcall(const InsnList *insns, const CFG *cfg, const FunctionEntry *fe) {
    /* Thunks (1 bloco, 1 instrução) não são tail calls — são stubs de IAT. */
    if (fe->block_count <= 1) return 0;
    const DecodedInsn *last = last_insn(insns, cfg, fe);
    if (last == NULL) return 0;
    if (last->mnemonic[0] && is_jmp_mnemo(last->mnemonic)) {
        /* jmp para fora do .text (thunk de import) — não é tail call. */
        if (last->imm_size > 0) {
            uint64_t target = (uint64_t)last->imm;
            /* Se o alvo está fora da função, é tail call real. */
            if (target < fe->start_va || target >= fe->end_va) return 1;
        }
    }
    return 0;
}

/* --- Detecção de switch table --- */

static int switch_cb(const DecodedInsn *insn) {
    if (insn->mnemonic[0] && is_jmp_mnemo(insn->mnemonic) &&
        insn->op_str[0]) {
        /* Capstone: "jmp qword ptr [rax*8 + 0x140006000]" */
        if (strstr(insn->op_str, "*8") || strstr(insn->op_str, "*4")) {
            return 1;
        }
    }
    return 0;
}

static int detect_switch(const InsnList *insns, const CFG *cfg, const FunctionEntry *fe) {
    return scan_function(insns, cfg, fe, switch_cb);
}

/* --- Main --- */

int patterns_analyze(const InsnList *insns, const CFG *cfg,
                     const PreIR *ir, FunctionList *fl,
                     char *err_buf, size_t err_buf_size) {
    (void)ir; (void)err_buf; (void)err_buf_size;
    for (uint32_t i = 0; i < fl->count; i++) {
        FunctionEntry *fe = &fl->entries[i];
        fe->flags = 0;
        if (detect_fp(insns, cfg, fe))       fe->flags |= FUNC_FLAG_FP;
        if (detect_canary(insns, cfg, fe))   fe->flags |= FUNC_FLAG_CANARY;
        if (detect_tailcall(insns, cfg, fe)) fe->flags |= FUNC_FLAG_TAILCALL;
        if (detect_switch(insns, cfg, fe))   fe->flags |= FUNC_FLAG_SWITCH;
        if (fe->call_count == 0)             fe->flags |= FUNC_FLAG_LEAF;
    }
    return 0;
}

void patterns_format_flags(uint32_t flags, char *out, size_t out_size) {
    out[0] = '\0';
    if (flags == 0) { snprintf(out, out_size, "-"); return; }
    size_t w = 0;
    if (flags & FUNC_FLAG_FP)        w += snprintf(out + w, out_size - w, "fp ");
    if (flags & FUNC_FLAG_CANARY)    w += snprintf(out + w, out_size - w, "canary ");
    if (flags & FUNC_FLAG_TAILCALL)  w += snprintf(out + w, out_size - w, "tail ");
    if (flags & FUNC_FLAG_SWITCH)    w += snprintf(out + w, out_size - w, "switch ");
    if (flags & FUNC_FLAG_LEAF)      w += snprintf(out + w, out_size - w, "leaf ");
    if (w > 0 && out[w-1] == ' ') out[w-1] = '\0';
}
