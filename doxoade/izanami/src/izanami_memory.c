// laurix/izanami/src/izanami_memory.c
/* ==========================================================================
 * [IZANAMI MEMORY] Motor de Varredura de Memória Física & Registradores MMIO.
 * Operação com buffer estático e aritmética otimizada sem libgcc (__udivdi3).
 * Em estrita conformidade com o protocolo ProDeNov v2.0.
 * ========================================================================== */

#include "../include/izanami_memory.h"

/* Buffer estático de 16 KB: Alocado no .bss, elimina chamadas dinâmicas */
static UINT8 g_mmap_buffer[16384];

/* --------------------------------------------------------------------------
 * Utilitários de Formatação Visual e Números
 * -------------------------------------------------------------------------- */
static void m_print(EFI_SYSTEM_TABLE *ST, const CHAR16 *str) {
    if (ST && ST->ConOut && ST->ConOut->OutputString) {
        ST->ConOut->OutputString(ST->ConOut, str);
    }
}

static void m_set_color(EFI_SYSTEM_TABLE *ST, UINTN attr) {
    if (ST && ST->ConOut && ST->ConOut->SetAttribute) {
        ST->ConOut->SetAttribute(ST->ConOut, attr);
    }
}

static void m_print_uint(EFI_SYSTEM_TABLE *ST, UINT32 val) {
    CHAR16 buf[16];
    INTN i = 14;
    buf[15] = 0;
    if (val == 0) {
        m_print(ST, u"0");
        return;
    }
    while (val > 0 && i >= 0) {
        buf[i--] = (CHAR16)(u'0' + (val % 10));
        val /= 10;
    }
    m_print(ST, &buf[i + 1]);
}

static void m_print_hex32(EFI_SYSTEM_TABLE *ST, UINT32 val) {
    CHAR16 buf[11];
    const CHAR16 hex[] = u"0123456789ABCDEF";
    buf[0] = u'0';
    buf[1] = u'x';
    for (INTN i = 9; i >= 2; i--) {
        buf[i] = hex[val & 0xF];
        val >>= 4;
    }
    buf[10] = 0;
    m_print(ST, buf);
}

static const CHAR16* m_type_to_str(UINT32 type) {
    switch (type) {
        case EfiConventionalMemory:      return u"RAM Livre (Kernel)  ";
        case EfiMemoryMappedIO:          return u"MMIO (Eletronica)   ";
        case EfiBootServicesCode:
        case EfiBootServicesData:        return u"BootServices (Temp) ";
        case EfiACPIReclaimMemory:
        case EfiACPIMemoryNVS:           return u"Tabelas ACPI        ";
        case EfiRuntimeServicesCode:
        case EfiRuntimeServicesData:     return u"Runtime (Permanente)";
        default:                         return u"Reservado Firmware  ";
    }
}

/* --------------------------------------------------------------------------
 * Sonda Primária de Memória Física (GetMemoryMap)
 * -------------------------------------------------------------------------- */
EFI_STATUS izanami_probe_memory(EFI_SYSTEM_TABLE *ST, IZANAMI_MEMORY_SUMMARY *Summary) {
    if (!ST || !ST->BootServices || !Summary) {
        return EFI_INVALID_PARAMETER;
    }

    /* Limpa a estrutura de resumo */
    Summary->ConventionalMB = 0;
    Summary->BootServicesMB = 0;
    Summary->ReservedMB = 0;
    Summary->MmioMB = 0;
    Summary->AcpiMB = 0;
    Summary->DescriptorCount = 0;

    UINTN mmap_size = sizeof(g_mmap_buffer);
    UINTN map_key = 0;
    UINTN desc_size = 0;
    UINT32 desc_version = 0;

    EFI_GET_MEMORY_MAP GetMemMap = (EFI_GET_MEMORY_MAP)ST->BootServices->GetMemoryMap;
    EFI_STATUS status = GetMemMap(&mmap_size, (EFI_MEMORY_DESCRIPTOR*)g_mmap_buffer, &map_key, &desc_size, &desc_version);
    if (status != EFI_SUCCESS) {
        return status;
    }

    Summary->MapKey = map_key;
    Summary->DescriptorSize = desc_size;
    Summary->DescriptorCount = mmap_size / desc_size;

    /* Itera cada descritor usando estritamente o DescriptorSize do firmware */
    for (UINTN i = 0; i < Summary->DescriptorCount; i++) {
        EFI_MEMORY_DESCRIPTOR *desc = (EFI_MEMORY_DESCRIPTOR*)(g_mmap_buffer + (i * desc_size));
        
        /* Conversão rápida: (Páginas de 4 KB * 4096) / (1024 * 1024) = Páginas / 256 = Páginas >> 8 */
        UINT32 mb = (UINT32)(desc->NumberOfPages >> 8);

        switch (desc->Type) {
            case EfiConventionalMemory:
                Summary->ConventionalMB += mb;
                break;
            case EfiBootServicesCode:
            case EfiBootServicesData:
                Summary->BootServicesMB += mb;
                break;
            case EfiMemoryMappedIO:
            case EfiMemoryMappedIOPortSpace:
                Summary->MmioMB += mb;
                break;
            case EfiACPIReclaimMemory:
            case EfiACPIMemoryNVS:
                Summary->AcpiMB += mb;
                break;
            default:
                Summary->ReservedMB += mb;
                break;
        }
    }

    return EFI_SUCCESS;
}

/* --------------------------------------------------------------------------
 * Interface do Painel de Inspeção Física
 * -------------------------------------------------------------------------- */
void izanami_display_memory_inspector(EFI_SYSTEM_TABLE *ST) {
    ST->ConOut->ClearScreen(ST->ConOut);

    m_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTCYAN, EFI_BACKGROUND_BLACK));
    m_print(ST, u"================================================================\r\n");
    m_print(ST, u"  [IZANAMI SYSTEMS] - Inspetor Forense de Memoria Fisica & MMIO \r\n");
    m_print(ST, u"================================================================\r\n\r\n");

    IZANAMI_MEMORY_SUMMARY sum;
    EFI_STATUS st = izanami_probe_memory(ST, &sum);
    if (st != EFI_SUCCESS) {
        m_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTRED, EFI_BACKGROUND_BLACK));
        m_print(ST, u"  ERRO: Nao foi possivel consultar o mapa de memoria da BIOS.\r\n");
        return;
    }

    /* Resumo Consolidado */
    m_set_color(ST, EFI_TEXT_ATTR(EFI_YELLOW, EFI_BACKGROUND_BLACK));
    m_print(ST, u"TOPOLOGIA CONSOLIDADA DE HARDWARE:\r\n");

    m_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTGREEN, EFI_BACKGROUND_BLACK));
    m_print(ST, u"  • RAM Livre (Kernel)       : ");
    m_print_uint(ST, sum.ConventionalMB);
    m_print(ST, u" MB\r\n");

    m_set_color(ST, EFI_TEXT_ATTR(EFI_CYAN, EFI_BACKGROUND_BLACK));
    m_print(ST, u"  • Recuperavel pos-boot     : ");
    m_print_uint(ST, sum.BootServicesMB);
    m_print(ST, u" MB (BootServices)\r\n");

    m_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTMAGENTA, EFI_BACKGROUND_BLACK));
    m_print(ST, u"  • Registradores MMIO       : ");
    m_print_uint(ST, sum.MmioMB);
    m_print(ST, u" MB (Perifericos / Eletronica)\r\n");

    m_set_color(ST, EFI_TEXT_ATTR(EFI_BROWN, EFI_BACKGROUND_BLACK));
    m_print(ST, u"  • Tabelas ACPI             : ");
    m_print_uint(ST, sum.AcpiMB);
    m_print(ST, u" MB (Sensores e Topologia)\r\n");

    m_set_color(ST, EFI_TEXT_ATTR(EFI_DARKGRAY, EFI_BACKGROUND_BLACK));
    m_print(ST, u"  • Firmware Permanente      : ");
    m_print_uint(ST, sum.ReservedMB);
    m_print(ST, u" MB\r\n");

    m_set_color(ST, EFI_TEXT_ATTR(EFI_WHITE, EFI_BACKGROUND_BLACK));
    m_print(ST, u"  • Total de Blocos Físicos  : ");
    m_print_uint(ST, (UINT32)sum.DescriptorCount);
    m_print(ST, u" blocos | MapKey: ");
    m_print_uint(ST, (UINT32)sum.MapKey);
    m_print(ST, u"\r\n\r\n");

    /* Amostra dos 6 primeiros blocos físicos */
    m_set_color(ST, EFI_TEXT_ATTR(EFI_YELLOW, EFI_BACKGROUND_BLACK));
    m_print(ST, u"AMOSTRA DE MAPEAMENTO FISICO (PRIMEIROS BLOCOS):\r\n");
    m_set_color(ST, EFI_TEXT_ATTR(EFI_DARKGRAY, EFI_BACKGROUND_BLACK));
    m_print(ST, u"  Endereco Base   | Paginas | Tipo de Memoria\r\n");
    m_print(ST, u"  ----------------+---------+---------------------------\r\n");

    UINTN display_limit = sum.DescriptorCount < 6 ? sum.DescriptorCount : 6;
    for (UINTN i = 0; i < display_limit; i++) {
        EFI_MEMORY_DESCRIPTOR *desc = (EFI_MEMORY_DESCRIPTOR*)(g_mmap_buffer + (i * sum.DescriptorSize));

        m_set_color(ST, EFI_TEXT_ATTR(EFI_WHITE, EFI_BACKGROUND_BLACK));
        m_print(ST, u"  ");
        m_print_hex32(ST, (UINT32)desc->PhysicalStart);
        m_print(ST, u"      | ");
        m_print_uint(ST, (UINT32)desc->NumberOfPages);
        m_print(ST, u"     | ");

        if (desc->Type == EfiConventionalMemory) {
            m_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTGREEN, EFI_BACKGROUND_BLACK));
        } else if (desc->Type == EfiMemoryMappedIO) {
            m_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTMAGENTA, EFI_BACKGROUND_BLACK));
        } else {
            m_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTGRAY, EFI_BACKGROUND_BLACK));
        }
        m_print(ST, m_type_to_str(desc->Type));
        m_print(ST, u"\r\n");
    }

    m_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTGRAY, EFI_BACKGROUND_BLACK));
    m_print(ST, u"\r\n----------------------------------------------------------------\r\n");
    m_set_color(ST, EFI_TEXT_ATTR(EFI_YELLOW, EFI_BACKGROUND_BLACK));
    m_print(ST, u"Pressione [Esc] ou [Enter] para retornar ao Menu Izanami...\r\n");
}
