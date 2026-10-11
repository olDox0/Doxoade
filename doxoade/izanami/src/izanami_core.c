/* ==========================================================================
 * # laurix/izanami/src/izanami_core.c
 * ==========================================================================
 * [IZANAMI SYSTEMS] Motor de Menu TUI e Despachante de Boot Bare-Metal.
 * Interação de teclado com timeout automático e salvaguarda para o Windows 10.
 * Em estrita conformidade com o protocolo ProDeNov v2.0.
 * ========================================================================== */

#include "../include/izanami_gop.h"
#include "../include/izanami_kernel.h"
#include "../include/izanami_memory.h"
#include "../include/izanami_types.h"

static EFI_HANDLE g_image_handle = NULL;

/* --------------------------------------------------------------------------
 * Utilitários de Impressão e Cores
 * -------------------------------------------------------------------------- */
static void ui_print(EFI_SYSTEM_TABLE *ST, const CHAR16 *str) {
    if (ST && ST->ConOut && ST->ConOut->OutputString) {
        ST->ConOut->OutputString(ST->ConOut, str);
    }
}

static void ui_set_color(EFI_SYSTEM_TABLE *ST, UINTN attr) {
    if (ST && ST->ConOut && ST->ConOut->SetAttribute) {
        ST->ConOut->SetAttribute(ST->ConOut, attr);
    }
}

static void ui_print_digit(EFI_SYSTEM_TABLE *ST, UINTN digit) {
    CHAR16 buf[2];
    buf[0] = (CHAR16)(u'0' + (digit % 10));
    buf[1] = 0;
    ui_print(ST, buf);
}

/* --------------------------------------------------------------------------
 * Renderização da Interface Gráfica em Modo Texto
 * -------------------------------------------------------------------------- */
static void ui_render_banner(EFI_SYSTEM_TABLE *ST) {
    ui_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTCYAN, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"================================================================\r\n");
    ui_print(ST, u"  [IZANAMI SYSTEMS] - Gênese & Boot Manager Bare-Metal (IA-32)  \r\n");
    ui_print(ST, u"  Alvo: Intel Celeron N2808 | Positivo H14BT58                  \r\n");
    ui_print(ST, u"================================================================\r\n\r\n");

    ui_set_color(ST, EFI_TEXT_ATTR(EFI_WHITE, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"Escolha uma opcao de inicializacao:\r\n\r\n");

    ui_set_color(ST, EFI_TEXT_ATTR(EFI_YELLOW, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"  [1] ");
    ui_set_color(ST, EFI_TEXT_ATTR(EFI_WHITE, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"Izanami Kernel Handoff (Salto Soberano / ExitBootServices)\r\n");
//    ui_print(ST, u"Inspetor Forense de Memoria Fisica & MMIO\r\n");

    ui_set_color(ST, EFI_TEXT_ATTR(EFI_CYAN, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"  [2] ");
    ui_set_color(ST, EFI_TEXT_ATTR(EFI_WHITE, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"Izanami Graphics (Dashboard GOP True Color 32-bit)\r\n");

    ui_set_color(ST, EFI_TEXT_ATTR(EFI_GREEN, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"  [3] ");
    ui_set_color(ST, EFI_TEXT_ATTR(EFI_WHITE, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"Retornar ao Windows 10 (Chainload via Firmware)\r\n");

    ui_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTBLUE, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"  [4] ");
    ui_set_color(ST, EFI_TEXT_ATTR(EFI_WHITE, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"Reiniciar Computador (Reboot a frio)\r\n");

    ui_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTRED, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"  [5] ");
    ui_set_color(ST, EFI_TEXT_ATTR(EFI_WHITE, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"Desligar Computador (Shutdown ACPI)\r\n\r\n");

    ui_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTGRAY, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"----------------------------------------------------------------\r\n");
}

/* --------------------------------------------------------------------------
 * Ações de Inicialização (Declaradas ANTES de efi_main)
 * -------------------------------------------------------------------------- */
static void action_doxoade_payload(EFI_SYSTEM_TABLE *ST) {
   ui_set_color(ST, EFI_TEXT_ATTR(EFI_YELLOW, EFI_BACKGROUND_BLACK));
   ui_print(ST, u"\r\n\r\n[HANDOFF] Desconectando o firmware UEFI e ativando o Kernel...\r\n");

   if (ST->BootServices && ST->BootServices->Stall) {
      ST->BootServices->Stall(1000000); /* 1 segundo para leitura visual */
   }

   /* Dispara a morte da BIOS e a assunção do Kernel */
   EFI_STATUS st = izanami_kernel_handoff(g_image_handle, ST);

   /* Se falhar, exibe o erro e aguarda */
   if (st != EFI_SUCCESS) {
      ui_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTRED, EFI_BACKGROUND_BLACK));
      ui_print(ST, u"\r\nFalha no ExitBootServices. Pressione qualquer tecla para voltar...\r\n");
      ST->ConIn->Reset(ST->ConIn, FALSE);
      EFI_INPUT_KEY key;
      while (ST->ConIn->ReadKeyStroke(ST->ConIn, &key) != EFI_SUCCESS) {
            if (ST->BootServices && ST->BootServices->Stall) {
               ST->BootServices->Stall(50000);
            }
      }
   }
}

static void action_gop_dashboard(EFI_SYSTEM_TABLE *ST) {
    /* 1. Renderiza a interface gráfica diretamente nos pixels da VRAM */
    izanami_gop_render_dashboard(ST);

    /* 2. Aguarda tecla para voltar */
    ST->ConIn->Reset(ST->ConIn, FALSE);
    EFI_INPUT_KEY key;
    for (;;) {
        EFI_STATUS status = ST->ConIn->ReadKeyStroke(ST->ConIn, &key);
        if (status == EFI_SUCCESS) {
            if (key.ScanCode == SCAN_ESC || key.UnicodeChar == u'\r' ||
                key.UnicodeChar == u'q'  || key.UnicodeChar == u'Q') {
                break; /* Retorna ao Menu Izanami */
            }
        }
        if (ST->BootServices && ST->BootServices->Stall) {
            ST->BootServices->Stall(50000); /* 50 ms */
        }
    }
}

static void action_reboot(EFI_SYSTEM_TABLE *ST) {
    ui_set_color(ST, EFI_TEXT_ATTR(EFI_YELLOW, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"\r\n\r\nReiniciando a maquina...\r\n");
    if (ST->RuntimeServices && ST->RuntimeServices->ResetSystem) {
        ST->RuntimeServices->ResetSystem(EfiResetCold, EFI_SUCCESS, 0, NULL);
    }
}

static void action_shutdown(EFI_SYSTEM_TABLE *ST) {
    ui_set_color(ST, EFI_TEXT_ATTR(EFI_LIGHTRED, EFI_BACKGROUND_BLACK));
    ui_print(ST, u"\r\n\r\nDesligando a maquina...\r\n");
    if (ST->RuntimeServices && ST->RuntimeServices->ResetSystem) {
        ST->RuntimeServices->ResetSystem(EfiResetShutdown, EFI_SUCCESS, 0, NULL);
    }
}

/* --------------------------------------------------------------------------
 * Ponto de Entrada Principal (EFI_MAIN) com Polling e Timeout
 * -------------------------------------------------------------------------- */
__attribute__((cdecl))
EFI_STATUS efi_main(EFI_HANDLE ImageHandle, EFI_SYSTEM_TABLE *SystemTable) {
    g_image_handle = ImageHandle; /* <-- ADICIONE ESTA LINHA */
 
    if (!SystemTable || !SystemTable->ConOut || !SystemTable->ConIn) {
          return EFI_DEVICE_ERROR;
    }

    /* Loop principal do Izanami Manager */
    for (;;) {
        SystemTable->ConIn->Reset(SystemTable->ConIn, FALSE);
        SystemTable->ConOut->ClearScreen(SystemTable->ConOut);
        ui_render_banner(SystemTable);

        UINTN seconds_left = 10;
        EFI_INPUT_KEY key;
        BOOLEAN action_taken = FALSE;

        while (seconds_left > 0) {
            ui_set_color(SystemTable, EFI_TEXT_ATTR(EFI_LIGHTGRAY, EFI_BACKGROUND_BLACK));
            ui_print(SystemTable, u"\rRetornando ao Windows automaticamente em: ");
            ui_set_color(SystemTable, EFI_TEXT_ATTR(EFI_YELLOW, EFI_BACKGROUND_BLACK));
            ui_print_digit(SystemTable, seconds_left);
            ui_print(SystemTable, u"s  (Pressione 1-5) ");

            /* Sub-loop de 1 segundo dividido em 50 fatias de 20ms (Alta Sensibilidade) */
            for (UINTN tick = 0; tick < 50; tick++) {
                EFI_STATUS status = SystemTable->ConIn->ReadKeyStroke(SystemTable->ConIn, &key);
                if (status == EFI_SUCCESS) {
                    CHAR16 c = key.UnicodeChar;

                    if (c == u'1' || c == u'M' || c == u'm') {
                        action_doxoade_payload(SystemTable);
                        action_taken = TRUE;
                        break;
                    }
                    if (c == u'2' || c == u'G' || c == u'g') {
                        action_gop_dashboard(SystemTable);
                        action_taken = TRUE;
                        break;
                    }
                    if (c == u'3' || c == u'W' || c == u'w' || key.ScanCode == SCAN_ESC) {
                        ui_set_color(SystemTable, EFI_TEXT_ATTR(EFI_GREEN, EFI_BACKGROUND_BLACK));
                        ui_print(SystemTable, u"\r\n\r\nDevolvendo controle ao Windows 10...\r\n");
                        return EFI_SUCCESS;
                    }
                    if (c == u'4' || c == u'R' || c == u'r') {
                        action_reboot(SystemTable);
                        return EFI_SUCCESS;
                    }
                    if (c == u'5' || c == u'S' || c == u's') {
                        action_shutdown(SystemTable);
                        return EFI_SUCCESS;
                    }
                }

                /* Pausa ultra-curta de 20ms (20.000 microssegundos) */
                if (SystemTable->BootServices && SystemTable->BootServices->Stall) {
                    SystemTable->BootServices->Stall(20000);
                }
            }

            if (action_taken) {
                break;
            }

            seconds_left--;
        }

        /* Se o tempo esgotou sem o usuário interagir, devolve ao Windows */
        if (!action_taken) {
            ui_set_color(SystemTable, EFI_TEXT_ATTR(EFI_GREEN, EFI_BACKGROUND_BLACK));
            ui_print(SystemTable, u"\r\n\r\nTempo esgotado. Inicializando Windows 10...\r\n");
            return EFI_SUCCESS;
        }
    }
}
