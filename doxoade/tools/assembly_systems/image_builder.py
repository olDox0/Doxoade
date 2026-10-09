# -*- coding: utf-8 -*-
"""
[HEFESTO] Image Builder v2 — Forja de Imagens Bootáveis c/ Auto-Alinhamento Ma'at.
"""
import math
import struct
from pathlib import Path

SECTOR = 512
FLOPPY_SIZE = 1440 * 1024


class ImageBuilder:
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()

    def _dap_index(self, bl: bytes):
        return bl.find(b"\x10\x00")

    def audit_dap(self, bl: bytes):
        i = self._dap_index(bl)
        return struct.unpack_from("<H", bl, i + 2)[0] if i >= 0 else None

    def check_signature(self, bl: bytes) -> bool:
        return bl[510:512] == b"\x55\xaa"

    def build(self, bootloader="core/bootloader.bin",
              kernel_flat="kernel_flat.bin",
              output="laurix.img", disk_size=FLOPPY_SIZE) -> dict:
        bl = bytearray((self.root / bootloader).read_bytes())
        kf = (self.root / kernel_flat).read_bytes()

        needed = math.ceil(len(kf) / SECTOR)
        dap = self.audit_dap(bytes(bl))
        patched = False

        # ⚖️ MA'AT: se o DAP estático não cobre o kernel, alinha na cópia da imagem
        if dap is not None and dap < needed:
            struct.pack_into("<H", bl, self._dap_index(bytes(bl)) + 2, needed)
            dap = needed
            patched = True

        pad = b"\x00" * (SECTOR - len(bl)) if len(bl) < SECTOR else b""
        image = bytes(bl) + pad + kf
        if len(image) > disk_size:
            raise ValueError(f"Kernel nao cabe no disco: {len(image)} > {disk_size}")
        image += b"\x00" * (disk_size - len(image))

        out = self.root / output
        out.write_bytes(image)
        return {
            "output": str(out), "bytes": len(image),
            "bootloader_bytes": len(bl), "kernel_flat_bytes": len(kf),
            "sectors_needed": needed, "dap_sectors": dap,
            "dap_ok": (dap or 0) >= needed, "dap_patched": patched,
            "mbr_ok": self.check_signature(bytes(bl)),
        }
