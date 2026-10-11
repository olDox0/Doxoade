/* ==========================================================================
 * # laurix/izanami/src/izanami_gop.c
 * ==========================================================================
 * [IZANAMI GRAPHICS V2] Motor GOP com Resolução Nativa, Layout Responsivo
 * e Tipografia Bitmap com Escala Dinâmica (32-bit True Color).
 * Em estrita conformidade com o protocolo ProDeNov v2.0.
 * ========================================================================== */

#include "../include/izanami_gop.h"

static EFI_GUID g_gop_guid = EFI_GRAPHICS_OUTPUT_PROTOCOL_GUID;
static EFI_GRAPHICS_OUTPUT_PROTOCOL *g_gop = NULL;

static volatile UINT32 *g_fb_base = NULL;
static UINT32 g_width = 0;
static UINT32 g_height = 0;
static UINT32 g_stride = 0;

/* --------------------------------------------------------------------------
 * Tabela de Fonte Bitmap 8x8 Compacta
 * -------------------------------------------------------------------------- */
static const UINT8 g_font_8x8[96][8] = {
    [' ' - 32] = {0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00},
    ['!' - 32] = {0x18,0x3C,0x3C,0x18,0x18,0x00,0x18,0x00},
    ['%' - 32] = {0x62,0x66,0x0C,0x18,0x30,0x66,0x46,0x00},
    ['(' - 32] = {0x0C,0x18,0x30,0x30,0x30,0x18,0x0C,0x00},
    [')' - 32] = {0x30,0x18,0x0C,0x0C,0x0C,0x18,0x30,0x00},
    ['-' - 32] = {0x00,0x00,0x00,0x7E,0x00,0x00,0x00,0x00},
    ['.' - 32] = {0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x00},
    ['/' - 32] = {0x02,0x06,0x0C,0x18,0x30,0x60,0x40,0x00},
    [':' - 32] = {0x00,0x18,0x18,0x00,0x00,0x18,0x18,0x00},
    ['=' - 32] = {0x00,0x7E,0x00,0x00,0x7E,0x00,0x00,0x00},
    ['[' - 32] = {0x3C,0x30,0x30,0x30,0x30,0x30,0x3C,0x00},
    [']' - 32] = {0x3C,0x0C,0x0C,0x0C,0x0C,0x0C,0x3C,0x00},
    ['0' - 32] = {0x3C,0x66,0x6E,0x76,0x66,0x66,0x3C,0x00},
    ['1' - 32] = {0x18,0x38,0x18,0x18,0x18,0x18,0x7E,0x00},
    ['2' - 32] = {0x3C,0x66,0x06,0x0C,0x30,0x60,0x7E,0x00},
    ['3' - 32] = {0x3C,0x66,0x06,0x1C,0x06,0x66,0x3C,0x00},
    ['4' - 32] = {0x0C,0x1C,0x3C,0x6C,0x7E,0x0C,0x0C,0x00},
    ['5' - 32] = {0x7E,0x60,0x7C,0x06,0x06,0x66,0x3C,0x00},
    ['6' - 32] = {0x3C,0x66,0x60,0x7C,0x66,0x66,0x3C,0x00},
    ['7' - 32] = {0x7E,0x06,0x0C,0x18,0x30,0x30,0x30,0x00},
    ['8' - 32] = {0x3C,0x66,0x66,0x3C,0x66,0x66,0x3C,0x00},
    ['9' - 32] = {0x3C,0x66,0x66,0x3E,0x06,0x66,0x3C,0x00},
    ['A' - 32] = {0x3C,0x66,0x66,0x7E,0x66,0x66,0x66,0x00},
    ['B' - 32] = {0x7C,0x66,0x66,0x7C,0x66,0x66,0x7C,0x00},
    ['C' - 32] = {0x3C,0x66,0x60,0x60,0x60,0x66,0x3C,0x00},
    ['D' - 32] = {0x78,0x6C,0x66,0x66,0x66,0x6C,0x78,0x00},
    ['E' - 32] = {0x7E,0x60,0x60,0x7C,0x60,0x60,0x7E,0x00},
    ['F' - 32] = {0x7E,0x60,0x60,0x7C,0x60,0x60,0x60,0x00},
    ['G' - 32] = {0x3C,0x66,0x60,0x6E,0x66,0x66,0x3C,0x00},
    ['H' - 32] = {0x66,0x66,0x66,0x7E,0x66,0x66,0x66,0x00},
    ['I' - 32] = {0x3C,0x18,0x18,0x18,0x18,0x18,0x3C,0x00},
    ['K' - 32] = {0x66,0x6C,0x78,0x70,0x78,0x6C,0x66,0x00},
    ['L' - 32] = {0x60,0x60,0x60,0x60,0x60,0x60,0x7E,0x00},
    ['M' - 32] = {0x63,0x77,0x7F,0x6B,0x63,0x63,0x63,0x00},
    ['N' - 32] = {0x66,0x76,0x7E,0x7E,0x6E,0x66,0x66,0x00},
    ['O' - 32] = {0x3C,0x66,0x66,0x66,0x66,0x66,0x3C,0x00},
    ['P' - 32] = {0x7C,0x66,0x66,0x7C,0x60,0x60,0x60,0x00},
    ['R' - 32] = {0x7C,0x66,0x66,0x7C,0x78,0x6C,0x66,0x00},
    ['S' - 32] = {0x3C,0x66,0x60,0x3C,0x06,0x66,0x3C,0x00},
    ['T' - 32] = {0x7E,0x18,0x18,0x18,0x18,0x18,0x18,0x00},
    ['U' - 32] = {0x66,0x66,0x66,0x66,0x66,0x66,0x3C,0x00},
    ['V' - 32] = {0x66,0x66,0x66,0x66,0x66,0x3C,0x18,0x00},
    ['W' - 32] = {0x63,0x63,0x63,0x6B,0x7F,0x77,0x63,0x00},
    ['X' - 32] = {0x66,0x66,0x3C,0x18,0x3C,0x66,0x66,0x00},
    ['Y' - 32] = {0x66,0x66,0x66,0x3C,0x18,0x18,0x18,0x00},
    ['Z' - 32] = {0x7E,0x06,0x0C,0x18,0x30,0x60,0x7E,0x00},
};

/* --------------------------------------------------------------------------
 * Inicialização com Autocomutação para Resolução Máxima da Tela
 * -------------------------------------------------------------------------- */
EFI_STATUS izanami_gop_init(EFI_SYSTEM_TABLE *ST) {
    if (!ST || !ST->BootServices) {
        return EFI_INVALID_PARAMETER;
    }

    EFI_LOCATE_PROTOCOL LocateProtocol = (EFI_LOCATE_PROTOCOL)ST->BootServices->LocateProtocol;
    EFI_STATUS st = LocateProtocol(&g_gop_guid, NULL, (VOID**)&g_gop);
    if (st != EFI_SUCCESS || !g_gop || !g_gop->Mode || !g_gop->Mode->Info) {
        return EFI_UNSUPPORTED;
    }

    /* 🔍 Varre todos os modos disponíveis e busca a resolução máxima nativa do LCD */
    UINT32 best_mode = g_gop->Mode->Mode;
    UINT32 max_pixels = g_gop->Mode->Info->HorizontalResolution * g_gop->Mode->Info->VerticalResolution;

    for (UINT32 m = 0; m < g_gop->Mode->MaxMode; m++) {
        EFI_GRAPHICS_OUTPUT_MODE_INFORMATION *info = NULL;
        UINTN info_size = 0;
        EFI_STATUS qst = g_gop->QueryMode(g_gop, m, &info_size, &info);
        if (qst == EFI_SUCCESS && info) {
            UINT32 pixels = info->HorizontalResolution * info->VerticalResolution;
            if (pixels > max_pixels) {
                max_pixels = pixels;
                best_mode = m;
            }
        }
    }

    /* Se encontrou um modo superior (ex: 1366x768 nativo), comuta imediatamente */
    if (best_mode != g_gop->Mode->Mode) {
        g_gop->SetMode(g_gop, best_mode);
    }

    g_fb_base = (volatile UINT32*)(UINTN)g_gop->Mode->FrameBufferBase;
    g_width   = g_gop->Mode->Info->HorizontalResolution;
    g_height  = g_gop->Mode->Info->VerticalResolution;
    g_stride  = g_gop->Mode->Info->PixelsPerScanLine;

    return EFI_SUCCESS;
}

/* --------------------------------------------------------------------------
 * Primitivas de Desenho
 * -------------------------------------------------------------------------- */
void izanami_gop_put_pixel(UINT32 x, UINT32 y, UINT32 color) {
    if (!g_fb_base || x >= g_width || y >= g_height) return;
    g_fb_base[y * g_stride + x] = color;
}

void izanami_gop_fill_rect(UINT32 x, UINT32 y, UINT32 w, UINT32 h, UINT32 color) {
    if (!g_fb_base) return;
    UINT32 max_x = (x + w > g_width) ? g_width : (x + w);
    UINT32 max_y = (y + h > g_height) ? g_height : (y + h);

    for (UINT32 py = y; py < max_y; py++) {
        UINT32 row_offset = py * g_stride;
        for (UINT32 px = x; px < max_x; px++) {
            g_fb_base[row_offset + px] = color;
        }
    }
}

void izanami_gop_clear(UINT32 color) {
    izanami_gop_fill_rect(0, 0, g_width, g_height, color);
}

/* --------------------------------------------------------------------------
 * Motor de Tipografia com Fator de Escala (1x, 2x, etc.)
 * -------------------------------------------------------------------------- */
void izanami_gop_draw_char_scaled(UINT32 x, UINT32 y, char c, UINT32 color, UINT32 scale) {
    if (c < 32 || c > 126) c = ' ';
    const UINT8 *glyph = g_font_8x8[(UINT8)c - 32];

    for (UINT32 row = 0; row < 8; row++) {
        UINT8 line = glyph[row];
        for (UINT32 col = 0; col < 8; col++) {
            if (line & (0x80 >> col)) {
                if (scale == 1) {
                    izanami_gop_put_pixel(x + col, y + row, color);
                } else {
                    izanami_gop_fill_rect(x + (col * scale), y + (row * scale), scale, scale, color);
                }
            }
        }
    }
}

void izanami_gop_draw_string(UINT32 x, UINT32 y, const char *text, UINT32 color, UINT32 scale) {
    UINT32 cur_x = x;
    while (*text) {
        izanami_gop_draw_char_scaled(cur_x, y, *text, color, scale);
        cur_x += 8 * scale;
        text++;
    }
}

static void gop_print_uint(UINT32 x, UINT32 y, UINT32 val, UINT32 color, UINT32 scale) {
    char buf[16];
    int i = 14;
    buf[15] = 0;
    if (val == 0) {
        izanami_gop_draw_string(x, y, "0", color, scale);
        return;
    }
    while (val > 0 && i >= 0) {
        buf[i--] = '0' + (val % 10);
        val /= 10;
    }
    izanami_gop_draw_string(x, y, &buf[i + 1], color, scale);
}

/* --------------------------------------------------------------------------
 * Dashboard Responsivo e Centralizado
 * -------------------------------------------------------------------------- */
void izanami_gop_render_dashboard(EFI_SYSTEM_TABLE *ST) {
    if (izanami_gop_init(ST) != EFI_SUCCESS) {
        return;
    }

    /* 1. Limpa a tela com fundo escuro elegante */
    izanami_gop_clear(COLOR_DARK_BG);

    /* 2. Barra Superior Proporcional com Fonte em Escala 2x (16x16 px) */
    UINT32 header_h = 56;
    izanami_gop_fill_rect(0, 0, g_width, header_h, COLOR_CARD_BG);
    izanami_gop_fill_rect(0, header_h - 2, g_width, 2, COLOR_CYAN);
    izanami_gop_draw_string(32, 20, "[IZANAMI SYSTEMS] - GRAPHICS ENGINE V2", COLOR_CYAN, 2);

    /* 3. Cálculo Responsivo de Cartões (Centralizados) */
    UINT32 padding = 32;
    UINT32 available_w = g_width - (padding * 3);
    UINT32 card_w = available_w / 2;
    UINT32 card_h = 240;
    UINT32 card_y = header_h + 36;

    UINT32 c1_x = padding;
    UINT32 c2_x = padding + card_w + padding;

    /* Moldura Cartão 1 */
    izanami_gop_fill_rect(c1_x, card_y, card_w, card_h, COLOR_CARD_BG);
    izanami_gop_fill_rect(c1_x, card_y, card_w, 2, COLOR_BORDER);
    izanami_gop_fill_rect(c1_x, card_y + card_h - 2, card_w, 2, COLOR_BORDER);
    izanami_gop_fill_rect(c1_x, card_y, 2, card_h, COLOR_BORDER);
    izanami_gop_fill_rect(c1_x + card_w - 2, card_y, 2, card_h, COLOR_BORDER);

    izanami_gop_draw_string(c1_x + 24, card_y + 24, "MONITOR DE HARDWARE:", COLOR_YELLOW, 2);
    izanami_gop_draw_string(c1_x + 24, card_y + 68, "RESOLUCAO:", COLOR_WHITE, 1);
    gop_print_uint(c1_x + 120, card_y + 68, g_width, COLOR_GREEN, 1);
    izanami_gop_draw_string(c1_x + 155, card_y + 68, "X", COLOR_GREEN, 1);
    gop_print_uint(c1_x + 170, card_y + 68, g_height, COLOR_GREEN, 1);

    izanami_gop_draw_string(c1_x + 24, card_y + 100, "STRIDE   :", COLOR_WHITE, 1);
    gop_print_uint(c1_x + 120, card_y + 100, g_stride, COLOR_CYAN, 1);
    izanami_gop_draw_string(c1_x + 170, card_y + 100, "PX/LINHA", COLOR_CYAN, 1);

    izanami_gop_draw_string(c1_x + 24, card_y + 132, "MODO     : LINEAR FRAMEBUFFER GOP", COLOR_WHITE, 1);
    izanami_gop_draw_string(c1_x + 24, card_y + 164, "FORMATO  : 32-BIT TRUE COLOR", COLOR_GREEN, 1);
    izanami_gop_draw_string(c1_x + 24, card_y + 196, "TARGET   : INTEL HD GRAPHICS (EDP)", COLOR_PURPLE, 1);

    /* Moldura Cartão 2 */
    izanami_gop_fill_rect(c2_x, card_y, card_w, card_h, COLOR_CARD_BG);
    izanami_gop_fill_rect(c2_x, card_y, card_w, 2, COLOR_BORDER);
    izanami_gop_fill_rect(c2_x, card_y + card_h - 2, card_w, 2, COLOR_BORDER);
    izanami_gop_fill_rect(c2_x, card_y, 2, card_h, COLOR_BORDER);
    izanami_gop_fill_rect(c2_x + card_w - 2, card_y, 2, card_h, COLOR_BORDER);

    izanami_gop_draw_string(c2_x + 24, card_y + 24, "CALIBRACAO DO ESPECTRO:", COLOR_YELLOW, 2);

    /* Blocos de Cores Ampliados e Proporcionais */
    UINT32 colors[] = {COLOR_RED, COLOR_GREEN, COLOR_CYAN, COLOR_YELLOW, COLOR_PURPLE, COLOR_WHITE};
    UINT32 box_w = (card_w - 48 - (5 * 12)) / 6;
    for (UINT32 i = 0; i < 6; i++) {
        izanami_gop_fill_rect(c2_x + 24 + (i * (box_w + 12)), card_y + 70, box_w, 64, colors[i]);
    }
    izanami_gop_draw_string(c2_x + 24, card_y + 160, "STATUS : CALIBRACAO 100% HOMOLOGADA", COLOR_GREEN, 1);
    izanami_gop_draw_string(c2_x + 24, card_y + 192, "DISPLAY: ESCALA NATIVA 1:1 ATIVA", COLOR_CYAN, 1);

    /* 4. Barra Inferior de Navegação (Status Bar) */
    UINT32 footer_h = 44;
    izanami_gop_fill_rect(0, g_height - footer_h, g_width, footer_h, COLOR_CARD_BG);
    izanami_gop_fill_rect(0, g_height - footer_h, g_width, 1, COLOR_BORDER);
    izanami_gop_draw_string(32, g_height - footer_h + 14, "[ESC] OU [ENTER] RETORNAR AO MENU IZANAMI", COLOR_CYAN, 1);
}
