/* ==========================================================================
 * # laurix/izanami/include/izanami_gop.h
 * ==========================================================================
 * [IZANAMI GRAPHICS] Protocolo GOP e Primitivas de Framebuffer Físico (UEFI 2.10).
 * Acesso direto à VRAM da placa de vídeo em 32-bit True Color (RGB/BGR).
 * Em estrita conformidade com o protocolo ProDeNov v2.0.
 * ========================================================================== */

#ifndef IZANAMI_GOP_H
#define IZANAMI_GOP_H

#include "izanami_types.h"

/* --------------------------------------------------------------------------
 * 1. Definição do GUID Oficial do GOP (UEFI 2.x)
 * 9042A9DE-23DC-4A38-96FB-7ADED080516A
 * -------------------------------------------------------------------------- */
typedef struct {
    UINT32 Data1;
    UINT16 Data2;
    UINT16 Data3;
    UINT8  Data4[8];
} EFI_GUID;

#define EFI_GRAPHICS_OUTPUT_PROTOCOL_GUID \
    { 0x9042a9de, 0x23dc, 0x4a38, { 0x96, 0xfb, 0x7a, 0xde, 0xd0, 0x80, 0x51, 0x6a } }

/* --------------------------------------------------------------------------
 * 2. Estruturas Canônicas do GOP
 * -------------------------------------------------------------------------- */
typedef enum {
    PixelRedGreenBlueReserved8BitPerColor,
    PixelBlueGreenRedReserved8BitPerColor,
    PixelBitMask,
    PixelBltOnly,
    PixelFormatMax
} EFI_GRAPHICS_PIXEL_FORMAT;

typedef struct {
    UINT32 RedMask;
    UINT32 GreenMask;
    UINT32 BlueMask;
    UINT32 ReservedMask;
} EFI_PIXEL_BITMASK;

typedef struct {
    UINT32                     Version;
    UINT32                     HorizontalResolution;
    UINT32                     VerticalResolution;
    EFI_GRAPHICS_PIXEL_FORMAT  PixelFormat;
    EFI_PIXEL_BITMASK          PixelInformation;
    UINT32                     PixelsPerScanLine;    /* Stride real da linha física */
} EFI_GRAPHICS_OUTPUT_MODE_INFORMATION;

typedef struct {
    UINT32                                MaxMode;
    UINT32                                Mode;
    EFI_GRAPHICS_OUTPUT_MODE_INFORMATION *Info;
    UINTN                                 SizeOfInfo;
    UINT64                                FrameBufferBase; /* PONTEIRO FÍSICO DA VRAM */
    UINTN                                 FrameBufferSize; /* Tamanho em bytes da VRAM */
} EFI_GRAPHICS_OUTPUT_PROTOCOL_MODE;

struct _EFI_GRAPHICS_OUTPUT_PROTOCOL;

typedef EFI_STATUS (EFIAPI *EFI_GRAPHICS_OUTPUT_PROTOCOL_QUERY_MODE)(
    struct _EFI_GRAPHICS_OUTPUT_PROTOCOL *This,
    UINT32 ModeNumber,
    UINTN *SizeOfInfo,
    EFI_GRAPHICS_OUTPUT_MODE_INFORMATION **Info
);

typedef EFI_STATUS (EFIAPI *EFI_GRAPHICS_OUTPUT_PROTOCOL_SET_MODE)(
    struct _EFI_GRAPHICS_OUTPUT_PROTOCOL *This,
    UINT32 ModeNumber
);

typedef struct _EFI_GRAPHICS_OUTPUT_PROTOCOL {
    EFI_GRAPHICS_OUTPUT_PROTOCOL_QUERY_MODE QueryMode;
    EFI_GRAPHICS_OUTPUT_PROTOCOL_SET_MODE   SetMode;
    VOID                                   *Blt;
    EFI_GRAPHICS_OUTPUT_PROTOCOL_MODE      *Mode;
} EFI_GRAPHICS_OUTPUT_PROTOCOL;

typedef EFI_STATUS (EFIAPI *EFI_LOCATE_PROTOCOL)(
    EFI_GUID *Protocol,
    VOID     *Registration,
    VOID    **Interface
);

/* --------------------------------------------------------------------------
 * 3. Paleta de Cores em 32-bit True Color (Formato Little-Endian BGRX nativo)
 * -------------------------------------------------------------------------- */
#define GOP_COLOR(r, g, b) (((UINT32)(r) << 16) | ((UINT32)(g) << 8) | (UINT32)(b))

#define COLOR_BLACK        GOP_COLOR(0, 0, 0)
#define COLOR_WHITE        GOP_COLOR(255, 255, 255)
#define COLOR_DARK_BG      GOP_COLOR(15, 23, 42)     /* Slate Dark #0F172A */
#define COLOR_CARD_BG      GOP_COLOR(30, 41, 59)     /* Card #1E293B */
#define COLOR_BORDER       GOP_COLOR(51, 65, 85)     /* Border #334155 */
#define COLOR_CYAN         GOP_COLOR(56, 189, 248)   /* Cyan Sky #38BDF8 */
#define COLOR_GREEN        GOP_COLOR(74, 222, 128)   /* Green #4ADE80 */
#define COLOR_YELLOW       GOP_COLOR(250, 204, 21)   /* Yellow #FACC15 */
#define COLOR_RED          GOP_COLOR(248, 113, 113)  /* Red #F87171 */
#define COLOR_PURPLE       GOP_COLOR(192, 132, 252)  /* Purple #C084FC */

/* --------------------------------------------------------------------------
 * 4. Interface Pública do Subsistema Gráfico Izanami
 * -------------------------------------------------------------------------- */
EFI_STATUS izanami_gop_init(EFI_SYSTEM_TABLE *ST);
void izanami_gop_put_pixel(UINT32 x, UINT32 y, UINT32 color);
void izanami_gop_fill_rect(UINT32 x, UINT32 y, UINT32 w, UINT32 h, UINT32 color);
void izanami_gop_clear(UINT32 color);
void izanami_gop_draw_string(UINT32 x, UINT32 y, const char *text, UINT32 color, UINT32 scale);
//void izanami_gop_draw_string(UINT32 x, UINT32 y, const char *text, UINT32 color);
void izanami_gop_render_dashboard(EFI_SYSTEM_TABLE *ST);

#endif /* IZANAMI_GOP_H */
