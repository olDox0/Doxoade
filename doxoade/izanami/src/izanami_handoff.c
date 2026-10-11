/* ==========================================================================
 * # laurix/izanami/src/izanami_handoff.c
 * ==========================================================================
 * [IZANAMI KERNEL] Desligamento de Firmware (ExitBootServices) & GDT 64-bit.
 * O salto atômico da CPU para soberania em Anel 0 (Ring 0).
 * Em estrita conformidade com o protocolo ProDeNov v2.0.
 * ========================================================================== */

#include "../include/izanami_kernel.h"
#include "../include/izanami_memory.h"
#include "../include/izanami_gop.h"

/* --------------------------------------------------------------------------
 * Tabela GDT Soberana de 64 bits (3 Entradas: Null, Code 0x08, Data 0x10)
 * -------------------------------------------------------------------------- */
static GDT_ENTRY g_gdt[3] __attribute__((aligned(16))) = {
    /* 0x00: Null Descriptor obrigatório */
    {0, 0, 0, 0, 0, 0},

    /* 0x08: Kernel Code 64-bit (Ring 0, Exec/Read, L=1, D=0) */
    {0xFFFF, 0x0000, 0x00, 0x9A, 0xAF, 0x00},

    /* 0x10: Kernel Data 64-bit (Ring 0, Read/Write, Writable) */
    {0xFFFF, 0x0000, 0x00, 0x92, 0xCF, 0x00}
};

static GDT_POINTER g_gdt_ptr = {
    sizeof(g_gdt) - 1,
    (UINT64)(UINTN)&g_gdt
};

typedef EFI_STATUS (EFIAPI *EFI_EXIT_BOOT_SERVICES)(
    EFI_HANDLE ImageHandle,
    UINTN      MapKey
);

/* --------------------------------------------------------------------------
 * Renderizador Gráfico Pós-Firmware (100% VRAM Direta, Zero BIOS)
 * -------------------------------------------------------------------------- */
static void render_sovereign_post_screen(void) {
    /* Limpa a tela com fundo Azul Noturno (VRAM pura) */
    izanami_gop_clear(COLOR_DARK_BG);

    /* Barra Superior */
    izanami_gop_fill_rect(0, 0, 1366, 64, COLOR_CARD_BG);
    izanami_gop_fill_rect(0, 62, 1366, 2, COLOR_GREEN);
    izanami_gop_draw_string(32, 22, "[IZANAMI KERNEL] - SOBERANIA BARE-METAL ATIVA (RING 0)", COLOR_GREEN, 2);

    /* Cartão de Estado da Máquina */
    UINT32 card_x = 48, card_y = 100, card_w = 700, card_h = 300;
    izanami_gop_fill_rect(card_x, card_y, card_w, card_h, COLOR_CARD_BG);
    izanami_gop_fill_rect(card_x, card_y, card_w, 2, COLOR_BORDER);
    izanami_gop_fill_rect(card_x, card_y + card_h - 2, card_w, 2, COLOR_BORDER);
    izanami_gop_fill_rect(card_x, card_y, 2, card_h, COLOR_BORDER);
    izanami_gop_fill_rect(card_x + card_w - 2, card_y, 2, card_h, COLOR_BORDER);

    izanami_gop_draw_string(card_x + 24, card_y + 24, "DIAGNOSTICO DE CONTROLE FISICO:", COLOR_YELLOW, 2);
    izanami_gop_draw_string(card_x + 24, card_y + 70,  "FIRMWARE UEFI : DESLIGADO PERMANENTEMENTE (EXIT)", COLOR_RED, 1);
    izanami_gop_draw_string(card_x + 24, card_y + 105, "MODO DA CPU   : 64-BIT LONG MODE (RING 0 NATIVO)", COLOR_GREEN, 1);
    izanami_gop_draw_string(card_x + 24, card_y + 140, "TABELA GDT    : CARREGADA SOBERANAMENTE (0X08/0X10)", COLOR_CYAN, 1);
    izanami_gop_draw_string(card_x + 24, card_y + 175, "INTERRUPCOES  : DESATIVADAS (CLI ATIVO)", COLOR_YELLOW, 1);
    izanami_gop_draw_string(card_x + 24, card_y + 210, "VIDEO VRAM    : LINEAR FRAMEBUFFER VIVO E PROPRIO", COLOR_WHITE, 1);
    izanami_gop_draw_string(card_x + 24, card_y + 245, "STATUS HARDWARE: O PROCESSADOR PERTENCE AO IZANAMI", COLOR_GREEN, 1);

    /* Barra Inferior */
    izanami_gop_fill_rect(0, 720, 1366, 48, COLOR_CARD_BG);
    izanami_gop_fill_rect(0, 720, 1366, 1, COLOR_BORDER);
    izanami_gop_draw_string(32, 736, "MAQUINA SOB CONTROLE DO NUCLEO PROPRIO. REINICIE NO BOTAO OU AGUARDE.", COLOR_YELLOW, 1);
}

/* --------------------------------------------------------------------------
 * Ponto de Execução do Kernel Soberano (Pós-Firmware)
 * -------------------------------------------------------------------------- */
void izanami_kernel_entry(void) {
    /* Renderiza o painel final direto na memória física */
    render_sovereign_post_screen();

    /* Loop de espera definitivo em Anel 0 com CPU em repouso elétrico */
    for (;;) {
        __asm__ volatile("hlt");
    }
}

/* --------------------------------------------------------------------------
 * A Rotina de Transição Atômica (ExitBootServices)
 * -------------------------------------------------------------------------- */
EFI_STATUS izanami_kernel_handoff(EFI_HANDLE ImageHandle, EFI_SYSTEM_TABLE *ST) {
    if (!ST || !ST->BootServices) {
        return EFI_INVALID_PARAMETER;
    }

    /* 1. Inicializa o GOP e congela os ponteiros de VRAM ANTES de matar a BIOS */
    if (izanami_gop_init(ST) != EFI_SUCCESS) {
        return EFI_UNSUPPORTED;
    }

    /* 2. Coleta o mapa de memória e obtém o MapKey atualizado */
    IZANAMI_MEMORY_SUMMARY sum;
    EFI_STATUS st = izanami_probe_memory(ST, &sum);
    if (st != EFI_SUCCESS) {
        return st;
    }

    /* 3. Desativa o Firmware da Placa-Mãe (ExitBootServices) */
    EFI_EXIT_BOOT_SERVICES ExitBootServices = (EFI_EXIT_BOOT_SERVICES)ST->BootServices->ExitBootServices;
    st = ExitBootServices(ImageHandle, sum.MapKey);

    /* Se o MapKey mudou por concorrência, tenta mais uma vez imediatamente */
    if (st != EFI_SUCCESS) {
        st = izanami_probe_memory(ST, &sum);
        if (st == EFI_SUCCESS) {
            st = ExitBootServices(ImageHandle, sum.MapKey);
        }
    }

    if (st != EFI_SUCCESS) {
        return st; /* Aborta se o firmware não aceitar */
    }

    /* ======================================================================
     * [O SILÍCIO É LIVRE] A partir daqui, a BIOS está morta.
     * NENHUM serviço do firmware existe mais.
     * ====================================================================== */

    /* 4. Desativa interrupções antigas do firmware */
    __asm__ volatile("cli");

    /* 5. Carrega a nova GDT Soberana de 64 bits */
    __asm__ volatile("lgdt %0" : : "m"(g_gdt_ptr));

    /* 6. Atualiza os registradores de segmento para o seletor de dados 0x10 */
    __asm__ volatile(
        "mov $0x10, %%ax\n\t"
        "mov %%ax, %%ds\n\t"
        "mov %%ax, %%es\n\t"
        "mov %%ax, %%ss\n\t"
        "mov %%ax, %%fs\n\t"
        "mov %%ax, %%gs\n\t"
        : : : "ax"
    );

    /* 7. Salta para o corpo soberano do Kernel */
    izanami_kernel_entry();

    return EFI_SUCCESS;
}
