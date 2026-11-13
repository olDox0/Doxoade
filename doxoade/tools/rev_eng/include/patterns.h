/* patterns.h — catálogo de padrões de arquitetura x86-64 (Fase 5b)
 *
 * Detecta, por função:
 *   - prólogo com frame pointer (push rbp; mov rbp, rsp)
 *   - canary (gs:0x28 no prólogo e epílogo)
 *   - tail call (termina com jmp func, sem ret)
 *   - switch table (jmp qword ptr [reg*8 + table])
 *   - leaf (nenhum call interno)
 */
#ifndef PATTERNS_H
#define PATTERNS_H

#include "functions.h"
#include "disasm.h"
#include "cfg.h"
#include "pre_ir.h"

/* Preenche fe->flags para cada função em fl.
 * Requer insns e cfg válidos (saída de disasm_collect/cfg_build).
 * ir é reservado para uso futuro (ex: resolver endereços de switch table). */
int patterns_analyze(const InsnList *insns, const CFG *cfg,
                     const PreIR *ir, FunctionList *fl,
                     char *err_buf, size_t err_buf_size);

#endif
