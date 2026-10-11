/* ==========================================================================
 * # laurix/izanami/include/izanami_kernel.h
 * ==========================================================================
 * [IZANAMI KERNEL] Definições da GDT de 64 bits e Rotina de Handoff Soberana.
 * Em estrita conformidade com o protocolo ProDeNov v2.0.
 * ========================================================================== */

#ifndef IZANAMI_KERNEL_H
#define IZANAMI_KERNEL_H

#include "izanami_types.h"

/* --------------------------------------------------------------------------
 * 1. Estrutura da GDT de 64 bits (x86_64 Long Mode)
 * -------------------------------------------------------------------------- */
typedef struct __attribute__((packed)) {
    UINT16 LimitLow;
    UINT16 BaseLow;
    UINT8  BaseMid;
    UINT8  Access;
    UINT8  Granularity;
    UINT8  BaseHigh;
} GDT_ENTRY;

/* Ponteiro de 10 bytes para a instrução LGDT em 64-bit */
typedef struct __attribute__((packed)) {
    UINT16 Limit;
    UINT64 Base;
} GDT_POINTER;

/* --------------------------------------------------------------------------
 * 2. Protótipos de Funções do Núcleo
 * -------------------------------------------------------------------------- */
EFI_STATUS izanami_kernel_handoff(EFI_HANDLE ImageHandle, EFI_SYSTEM_TABLE *ST);
void izanami_kernel_entry(void);

#endif /* IZANAMI_KERNEL_H */
