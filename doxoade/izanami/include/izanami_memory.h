//laurix/izanami/include/izanami_memory.h
/* ==========================================================================
 * [IZANAMI MEMORY] Descritores e Sonda de Memória Física / MMIO (UEFI 2.10).
 * Permite mapear memória RAM convencional, ACPI e periféricos de eletrônica.
 * Em estrita conformidade com o protocolo ProDeNov v2.0.
 * ========================================================================== */

#ifndef IZANAMI_MEMORY_H
#define IZANAMI_MEMORY_H

#include "izanami_types.h"

/* --------------------------------------------------------------------------
 * 1. Tipos de Memória Canônicos da Especificação UEFI
 * -------------------------------------------------------------------------- */
typedef enum {
    EfiReservedMemoryType,          /* 0  - Reservada pelo firmware */
    EfiLoaderCode,                  /* 1  - Código do Bootloader */
    EfiLoaderData,                  /* 2  - Dados do Bootloader */
    EfiBootServicesCode,            /* 3  - Código UEFI (liberável pós-boot) */
    EfiBootServicesData,            /* 4  - Dados UEFI (liberável pós-boot) */
    EfiRuntimeServicesCode,         /* 5  - Código de Runtime (permanente) */
    EfiRuntimeServicesData,         /* 6  - Dados de Runtime (permanente) */
    EfiConventionalMemory,          /* 7  - RAM LIVRE UTILIZÁVEL (Usada pelo Kernel) */
    EfiUnusableMemory,              /* 8  - RAM com defeito físico */
    EfiACPIReclaimMemory,           /* 9  - Tabelas ACPI (liberáveis após parse) */
    EfiACPIMemoryNVS,               /* 10 - NVS ACPI (Preservada para hardware) */
    EfiMemoryMappedIO,              /* 11 - REGISTRADORES DE ELETRÔNICA / HARDWARE (MMIO) */
    EfiMemoryMappedIOPortSpace,     /* 12 - Portas de E/S mapeadas */
    EfiPalCode,                     /* 13 - Processadores com PAL */
    EfiPersistentMemory,            /* 14 - NVDIMM / Memória não-volátil */
    EfiMaxMemoryType
} EFI_MEMORY_TYPE;

/* --------------------------------------------------------------------------
 * 2. Descritor Físico de Memória UEFI (Tamanho variável no firmware)
 * -------------------------------------------------------------------------- */
typedef struct {
    UINT32 Type;
    UINT32 Pad;
    UINT64 PhysicalStart;
    UINT64 VirtualStart;
    UINT64 NumberOfPages;          /* 1 Página = 4096 bytes (4 KB) */
    UINT64 Attribute;
} EFI_MEMORY_DESCRIPTOR;

/* Protótipo da função GetMemoryMap da Boot Services */
typedef EFI_STATUS (EFIAPI *EFI_GET_MEMORY_MAP)(
    UINTN                 *MemoryMapSize,
    EFI_MEMORY_DESCRIPTOR *MemoryMap,
    UINTN                 *MapKey,
    UINTN                 *DescriptorSize,
    UINT32                *DescriptorVersion
);

/* --------------------------------------------------------------------------
 * 3. Estrutura Consolidada de Telemetria Física do Izanami
 * -------------------------------------------------------------------------- */
typedef struct {
    UINT32 ConventionalMB;          /* RAM livre utilizável */
    UINT32 BootServicesMB;          /* Memória recuperável após ExitBootServices */
    UINT32 ReservedMB;              /* Firmware permanente */
    UINT32 MmioMB;                  /* Espaço de registradores de hardware */
    UINT32 AcpiMB;                  /* Tabelas ACPI da placa-mãe */
    UINTN  DescriptorCount;         /* Quantidade de blocos mapeados */
    UINTN  MapKey;                  /* Chave transacional do firmware */
    UINTN  DescriptorSize;          /* Tamanho do descritor na BIOS */
} IZANAMI_MEMORY_SUMMARY;

/* Interface pública da sonda */
EFI_STATUS izanami_probe_memory(EFI_SYSTEM_TABLE *ST, IZANAMI_MEMORY_SUMMARY *Summary);
void izanami_display_memory_inspector(EFI_SYSTEM_TABLE *ST);

#endif /* IZANAMI_MEMORY_H */
