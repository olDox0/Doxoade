# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/simd_detector.py

"""
──────────────────────────────────────────────────────────────────────────────
Detecção de capacidades SIMD do processador atual.

Estratégias (em ordem de precisão):
  1. py-cpuinfo (se instalado)          — mais completo
  2. /proc/cpuinfo flags (Linux)        — nativo, sem deps
  3. CPUID via ctypes inline (x86/x64)  — baixo nível
  4. Fallback conservador               — sse2 garantido em x86_64

API pública:
    detect() -> SIMDCapabilities          # singleton cacheado
    SIMDCapabilities.gcc_flags            # list[str]  para GCC/Clang
    SIMDCapabilities.msvc_flags           # list[str]  para MSVC
    SIMDCapabilities.best                 # nome do nível mais alto
    SIMDCapabilities.cython_directives    # dict p/ cythonize()
"""

from __future__ import annotations

import os
import platform
import struct
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from typing import FrozenSet

# ──────────────────────────────────────────────────────────────────────────────
# Dataclass de capacidades
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SIMDCapabilities:
    """Conjunto de extensões SIMD disponíveis na CPU atual."""

    # x86 / x86_64
    mmx:     bool = False
    sse:     bool = False
    sse2:    bool = False
    sse3:    bool = False
    ssse3:   bool = False
    sse4_1:  bool = False
    sse4_2:  bool = False
    avx:     bool = False
    avx2:    bool = False
    avx512f: bool = False
    fma:     bool = False
    bmi1:    bool = False
    bmi2:    bool = False
    popcnt:  bool = False

    # ARM
    neon:    bool = False
    sve:     bool = False

    # Meta
    arch:    str  = "unknown"
    vendor:  str  = "unknown"

    # ── Nível máximo ──────────────────────────────────────────────────────────
    @property
    def best(self) -> str:
        if self.avx512f: return "avx512f"
        if self.avx2:    return "avx2"
        if self.avx:     return "avx"
        if self.sse4_2:  return "sse4.2"
        if self.sse4_1:  return "sse4.1"
        if self.sse2:    return "sse2"
        if self.neon:    return "neon"
        return "none"

    @property
    def level(self) -> int:
        """Nível numérico 0-6 para comparação."""
        _map = {"avx512f": 6, "avx2": 5, "avx": 4,
                "sse4.2": 3, "sse4.1": 2, "sse2": 1, "neon": 1}
        return _map.get(self.best, 0)

    # ── Flags de compilação ───────────────────────────────────────────────────
    @property
    def gcc_flags(self) -> list[str]:
        """
        Flags para GCC / Clang.
        Usa -march=native apenas quando level_cap='native' ou 'auto' com avx+.
        Para caps explícitas (avx2, avx512f), usa flags específicas para portabilidade.
        """
        flags = ["-O3", "-funroll-loops"]

        if self.avx512f: flags += ["-mavx512f", "-mavx512cd", "-mfma", "-mavx2"]
        elif self.avx2:  flags += ["-mavx2", "-mfma"]
        elif self.avx:   flags.append("-mavx")
        elif self.sse4_2: flags += ["-msse4.2", "-msse4.1"]
        elif self.sse4_1: flags.append("-msse4.1")
        elif self.sse2:   flags.append("-msse2")

        if self.fma and not self.avx2:   flags.append("-mfma")
        if self.bmi2:   flags.append("-mbmi2")
        if self.bmi1 and not self.bmi2:  flags.append("-mbmi")
        if self.popcnt: flags.append("-mpopcnt")

        if self.neon:
            flags += ["-mfpu=neon", "-mfloat-abi=hard"]

        return flags

    @property
    def native_flags(self) -> list[str]:
        """Flags para compilação nativa (máxima performance, binário não portável)."""
        return ["-O3", "-march=native", "-funroll-loops", "-ffast-math"]

    @property
    def msvc_flags(self) -> list[str]:
        """Flags para MSVC (Windows cl.exe)."""
        flags = ["/O2", "/GL", "/Gy"]

        if self.avx512f: flags.append("/arch:AVX512")
        elif self.avx2:  flags.append("/arch:AVX2")
        elif self.avx:   flags.append("/arch:AVX")
        elif self.sse2:  flags.append("/arch:SSE2")

        return flags

    @property
    def cflags(self) -> list[str]:
        """Flags para a plataforma atual."""
        if os.name == "nt":
            return self.msvc_flags
        return self.gcc_flags

    @property
    def cython_directives(self) -> dict:
        """
        Diretivas Cython recomendadas para melhor aproveitamento SIMD.
        Passadas para `cythonize(..., compiler_directives=...)`.
        """
        base = {
            "boundscheck":  False,
            "wraparound":   False,
            "cdivision":    True,
            "nonecheck":    False,
            "language_level": 3,
        }
        if self.level >= 4:          # avx ou superior
            base["initializedcheck"] = False
            base["overflowcheck"]    = False
        return base

    @property
    def define_macros(self) -> list[tuple[str, str | None]]:
        """Macros C para usar com Extension(define_macros=...)."""
        macros: list[tuple] = []
        if self.sse2:    macros.append(("VULCAN_HAS_SSE2",    None))
        if self.avx:     macros.append(("VULCAN_HAS_AVX",     None))
        if self.avx2:    macros.append(("VULCAN_HAS_AVX2",    None))
        if self.avx512f: macros.append(("VULCAN_HAS_AVX512F", None))
        if self.fma:     macros.append(("VULCAN_HAS_FMA",     None))
        if self.neon:    macros.append(("VULCAN_HAS_NEON",    None))
        return macros

    # ── Serialização legível ──────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "arch":    self.arch,
            "vendor":  self.vendor,
            "best":    self.best,
            "level":   self.level,
            "flags": {
                "sse2": self.sse2, "sse4_1": self.sse4_1, "sse4_2": self.sse4_2,
                "avx": self.avx, "avx2": self.avx2, "avx512f": self.avx512f,
                "fma": self.fma, "bmi1": self.bmi1, "bmi2": self.bmi2,
                "neon": self.neon,
            },
            "gcc_flags":  self.gcc_flags,
            "msvc_flags": self.msvc_flags,
        }

    def __str__(self) -> str:
        active = [k for k, v in self.to_dict()["flags"].items() if v]
        return (
            f"SIMDCapabilities(arch={self.arch}, best={self.best}, "
            f"active=[{', '.join(active)}])"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Estratégia 1: py-cpuinfo
# ──────────────────────────────────────────────────────────────────────────────

def _detect_cpuinfo() -> SIMDCapabilities | None:
    """Usa py-cpuinfo se disponível."""
    try:
        import cpuinfo  # type: ignore
        info = cpuinfo.get_cpu_info()
        flags_raw = set(info.get("flags", []))

        return SIMDCapabilities(
            mmx      = "mmx"      in flags_raw,
            sse      = "sse"      in flags_raw,
            sse2     = "sse2"     in flags_raw,
            sse3     = "sse3"     in flags_raw,
            ssse3    = "ssse3"    in flags_raw,
            sse4_1   = "sse4_1"   in flags_raw,
            sse4_2   = "sse4_2"   in flags_raw,
            avx      = "avx"      in flags_raw,
            avx2     = "avx2"     in flags_raw,
            avx512f  = "avx512f"  in flags_raw,
            fma      = "fma"      in flags_raw,
            bmi1     = "bmi1"     in flags_raw,
            bmi2     = "bmi2"     in flags_raw,
            popcnt   = "popcnt"   in flags_raw,
            neon     = "neon"     in flags_raw,
            arch     = info.get("arch_string_raw", platform.machine()),
            vendor   = info.get("vendor_id_raw",   ""),
        )
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Estratégia 2: /proc/cpuinfo (Linux)
# ──────────────────────────────────────────────────────────────────────────────

def _detect_proc_cpuinfo() -> SIMDCapabilities | None:
    """Lê /proc/cpuinfo no Linux."""
    if sys.platform not in ("linux", "linux2"):
        return None
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read().lower()

        flags_set: set[str] = set()
        vendor = ""
        for line in text.splitlines():
            if line.startswith("flags"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    flags_set.update(parts[1].split())
            elif line.startswith("vendor_id"):
                parts = line.split(":", 1)
                vendor = parts[1].strip() if len(parts) == 2 else ""

        if not flags_set:
            return None

        return SIMDCapabilities(
            mmx      = "mmx"      in flags_set,
            sse      = "sse"      in flags_set,
            sse2     = "sse2"     in flags_set,
            sse3     = "sse3"     in flags_set or "pni" in flags_set,
            ssse3    = "ssse3"    in flags_set,
            sse4_1   = "sse4_1"   in flags_set,
            sse4_2   = "sse4_2"   in flags_set,
            avx      = "avx"      in flags_set,
            avx2     = "avx2"     in flags_set,
            avx512f  = "avx512f"  in flags_set,
            fma      = "fma"      in flags_set,
            bmi1     = "bmi1"     in flags_set,
            bmi2     = "bmi2"     in flags_set,
            popcnt   = "popcnt"   in flags_set,
            neon     = "neon"     in flags_set,
            arch     = platform.machine(),
            vendor   = vendor,
        )
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Estratégia 3: CPUID via ctypes (x86 / x86_64)
# ──────────────────────────────────────────────────────────────────────────────

def _cpuid(leaf: int, subleaf: int = 0) -> tuple[int, int, int, int]:
    """Executa a instrução CPUID e retorna (eax, ebx, ecx, edx)."""
    import ctypes, ctypes.util

    machine = platform.machine().lower()
    if machine not in ("x86_64", "amd64", "i386", "i686"):
        return (0, 0, 0, 0)

    # Tenta via ctypes inline — funciona em Linux/macOS
    try:
        import ctypes.util
        libc_name = ctypes.util.find_library("c")
        if not libc_name:
            return (0, 0, 0, 0)

        # shellcode CPUID: mov eax,leaf; mov ecx,subleaf; cpuid; (armazena via ponteiros)
        # Abordagem: compilar pequeno helper C em tempo de execução é pesado.
        # Usamos struct + array de bytes para chamar via mmap (Linux/macOS).
        import mmap

        # Código de máquina x86_64 para:
        #   push rbx
        #   mov eax, [rdi]   ; leaf
        #   mov ecx, [rsi]   ; subleaf
        #   cpuid
        #   mov [rdi], eax
        #   mov [rsi], ebx   ; ← via ponteiro temporário (usamos rdi+4 trick)
        #   mov [rdx], ecx
        #   mov [rcx], edx   ; já temos ecx, usamos r8
        #   pop rbx
        #   ret
        # (Complexo para fazer inline seguro — pulamos para abordagem mais simples)
        raise NotImplementedError("inline cpuid skipped — usar /proc/cpuinfo")

    except Exception:
        return (0, 0, 0, 0)


def _detect_cpuid() -> SIMDCapabilities | None:
    """Detecção via CPUID usando ctypes + subprocess C."""
    try:
        import subprocess, tempfile, textwrap

        probe_src = textwrap.dedent(r"""
        #include <stdio.h>
        #ifdef _MSC_VER
        #include <intrin.h>
        static void cpuid(int out[4], int leaf, int subleaf) {
            __cpuidex(out, leaf, subleaf);
        }
        #else
        #include <cpuid.h>
        static void cpuid(int out[4], int leaf, int subleaf) {
            __cpuid_count(leaf, subleaf, out[0], out[1], out[2], out[3]);
        }
        #endif
        int main(void) {
            int r[4];
            /* leaf 1: ecx/edx flags */
            cpuid(r, 1, 0);
            int ecx1 = r[2], edx1 = r[3];
            /* leaf 7, sub 0: ebx/ecx flags */
            cpuid(r, 7, 0);
            int ebx7 = r[1], ecx7 = r[2];
            /* leaf 0x80000001: ecx for FMA */
            cpuid(r, 0x80000001, 0);

            /* SSE2   = edx1[26]  */
            /* SSE4.1 = ecx1[19]  */
            /* SSE4.2 = ecx1[20]  */
            /* AVX    = ecx1[28]  */
            /* FMA    = ecx1[12]  */
            /* POPCNT = ecx1[23]  */
            /* AVX2   = ebx7[5]   */
            /* AVX512F= ebx7[16]  */
            /* BMI1   = ebx7[3]   */
            /* BMI2   = ebx7[8]   */
            printf("sse2=%d\n",    (edx1 >> 26) & 1);
            printf("sse4_1=%d\n",  (ecx1 >> 19) & 1);
            printf("sse4_2=%d\n",  (ecx1 >> 20) & 1);
            printf("avx=%d\n",     (ecx1 >> 28) & 1);
            printf("fma=%d\n",     (ecx1 >> 12) & 1);
            printf("popcnt=%d\n",  (ecx1 >> 23) & 1);
            printf("avx2=%d\n",    (ebx7 >>  5) & 1);
            printf("avx512f=%d\n", (ebx7 >> 16) & 1);
            printf("bmi1=%d\n",    (ebx7 >>  3) & 1);
            printf("bmi2=%d\n",    (ebx7 >>  8) & 1);
            return 0;
        }
        """)

        machine = platform.machine().lower()
        if machine not in ("x86_64", "amd64", "i386", "i686"):
            return None

        with tempfile.TemporaryDirectory() as tmp:
            src  = os.path.join(tmp, "probe_simd.c")
            exe  = os.path.join(tmp, "probe_simd" + (".exe" if os.name == "nt" else ""))
            with open(src, "w") as fh:
                fh.write(probe_src)

            compiler = "cl" if os.name == "nt" else "gcc"
            compile_args = (
                [compiler, src, f"/Fe{exe}", "/nologo"]
                if os.name == "nt"
                else [compiler, src, "-o", exe, "-O0"]
            )
            r = subprocess.run(compile_args, capture_output=True, timeout=15)
            if r.returncode != 0:
                return None

            r2 = subprocess.run([exe], capture_output=True, text=True, timeout=5)
            if r2.returncode != 0:
                return None

            flags: dict[str, bool] = {}
            for line in r2.stdout.splitlines():
                k, _, v = line.partition("=")
                flags[k.strip()] = v.strip() == "1"

        return SIMDCapabilities(
            sse2     = flags.get("sse2",    False),
            sse4_1   = flags.get("sse4_1",  False),
            sse4_2   = flags.get("sse4_2",  False),
            avx      = flags.get("avx",     False),
            avx2     = flags.get("avx2",    False),
            avx512f  = flags.get("avx512f", False),
            fma      = flags.get("fma",     False),
            bmi1     = flags.get("bmi1",    False),
            bmi2     = flags.get("bmi2",    False),
            popcnt   = flags.get("popcnt",  False),
            arch     = platform.machine(),
        )
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Estratégia 3b: Windows — IsProcessorFeaturePresent (kernel32)
# ──────────────────────────────────────────────────────────────────────────────

def _detect_windows_kernel32() -> SIMDCapabilities | None:
    """
    Windows: usa IsProcessorFeaturePresent (kernel32) para SSE e
    CPUID inline via VirtualAlloc/shellcode para AVX/AVX2/AVX-512.

    IsProcessorFeaturePresent retorna False para AVX em VMs e Hyper-V
    (XSAVE não exposto), então combinamos as duas abordagens.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes

        k32 = ctypes.windll.kernel32
        _pf = k32.IsProcessorFeaturePresent
        _pf.restype = ctypes.c_bool
        _pf.argtypes = [ctypes.c_uint]

        def pf(n: int) -> bool:
            try:
                return bool(_pf(n))
            except Exception:
                return False

        # SSE/SSE2/SSE4: kernel32 é 100% confiável para estas
        sse2   = pf(10)   # PF_XMMI64_INSTRUCTIONS_AVAILABLE
        sse4_1 = pf(37)   # PF_SSE4_1_INSTRUCTIONS_AVAILABLE
        sse4_2 = pf(38)   # PF_SSE4_2_INSTRUCTIONS_AVAILABLE

        if not sse2:
            return None   # x86_64 garante SSE2 — falha real

        # AVX/AVX2/AVX512: usar CPUID inline (bypass da restrição XSAVE em VMs)
        avx, avx2, avx512f, fma, bmi1, bmi2, popcnt = _cpuid_windows_inline()

        # Se CPUID inline falhou, kernel32 como fallback (pode ser False em VMs)
        if avx is None:
            avx    = pf(39)   # PF_AVX_INSTRUCTIONS_AVAILABLE
            avx2   = pf(40)   # PF_AVX2_INSTRUCTIONS_AVAILABLE
            avx512f = pf(44)  # PF_AVX512F_INSTRUCTIONS_AVAILABLE
            fma    = avx2     # Haswell+: AVX2 ⟹ FMA
            bmi1   = avx2
            bmi2   = avx2
            popcnt = sse4_2

        # Refina FMA/BMI via gcc se disponível (MinGW)
        _gcc = _detect_gcc_march_flags()
        if _gcc:
            fma  = _gcc.get("fma",  fma)
            bmi1 = _gcc.get("bmi",  bmi1)
            bmi2 = _gcc.get("bmi2", bmi2)

        vendor = _windows_cpu_vendor()

        return SIMDCapabilities(
            sse2     = sse2,
            sse4_1   = sse4_1,
            sse4_2   = sse4_2,
            avx      = avx or False,
            avx2     = avx2 or False,
            avx512f  = avx512f or False,
            fma      = fma or False,
            bmi1     = bmi1 or False,
            bmi2     = bmi2 or False,
            popcnt   = popcnt or sse4_2,
            arch     = platform.machine(),
            vendor   = vendor,
        )
    except Exception:
        return None


def _cpuid_windows_inline() -> tuple:
    """
    Executa CPUID no Windows sem shellcode (VirtualAlloc bloqueado por AV).

    Estratégias em ordem:
    1. Subprocess: compila probe.c com cl.exe ou gcc e executa
    2. Python puro: usa cpuid via struct trick no módulo _struct (não disponível)
    3. Leitura do registro: inferência por CPU model string

    Retorna (avx, avx2, avx512f, fma, bmi1, bmi2, popcnt) como bools,
    ou (None,) * 7 se tudo falhar.
    """
    # Estratégia 1: probe C compilado
    result = _cpuid_via_c_probe()
    if result[0] is not None:
        return result

    # Estratégia 2: inferência por model string (registro do Windows)
    return _cpuid_via_model_string()


def _cpuid_via_c_probe() -> tuple:
    """
    Compila e executa probe C para ler CPUID.

    Usa inline assembly GCC (funciona com w64devkit/MinGW sem cpuid.h)
    e __cpuidex para MSVC. Tenta gcc primeiro, depois cl.exe.
    """
    import subprocess, tempfile, shutil, os

    # Inline asm: funciona em GCC/MinGW (inclui w64devkit) sem depender de cpuid.h
    PROBE_SRC = r"""
#include <stdio.h>

#if defined(_MSC_VER)
#  include <intrin.h>
static void do_cpuid(unsigned r[4], unsigned leaf, unsigned sub) {
    __cpuidex((int*)r, (int)leaf, (int)sub);
}
#elif defined(__GNUC__) && (defined(__i386__) || defined(__x86_64__))
static void do_cpuid(unsigned r[4], unsigned leaf, unsigned sub) {
    __asm__ volatile (
        "cpuid"
        : "=a"(r[0]), "=b"(r[1]), "=c"(r[2]), "=d"(r[3])
        : "a"(leaf), "c"(sub)
    );
}
#else
#  error "architecture not supported"
#endif

int main(void) {
    unsigned r[4];
    do_cpuid(r, 1u, 0u);
    unsigned ecx1 = r[2];
    do_cpuid(r, 7u, 0u);
    unsigned ebx7 = r[1];
    printf("avx=%u\n",    (ecx1>>28)&1u);
    printf("fma=%u\n",    (ecx1>>12)&1u);
    printf("popcnt=%u\n", (ecx1>>23)&1u);
    printf("avx2=%u\n",   (ebx7>> 5)&1u);
    printf("avx512f=%u\n",(ebx7>>16)&1u);
    printf("bmi1=%u\n",   (ebx7>> 3)&1u);
    printf("bmi2=%u\n",   (ebx7>> 8)&1u);
    return 0;
}
"""

    # Procura gcc (w64devkit, MinGW, MSYS2) e cl.exe (MSVC)
    # shutil.which respeita o PATH atual — se w64devkit está no PATH, acha gcc
    compilers = []
    if shutil.which("gcc"):
        compilers.append(("gcc", ["gcc", "-O1", "{src}", "-o", "{exe}"]))
    if shutil.which("x86_64-w64-mingw32-gcc"):
        compilers.append(("mingw64", ["x86_64-w64-mingw32-gcc", "-O1", "{src}", "-o", "{exe}"]))
    if shutil.which("cl"):
        compilers.append(("msvc", ["cl", "/nologo", "/O1", "{src}", "/Fe{exe}"]))

    if not compilers:
        return (None,) * 7

    try:
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "cpuid_probe.c")
            exe = os.path.join(tmp, "cpuid_probe.exe")
            with open(src, "w") as fh:
                fh.write(PROBE_SRC)

            compiled = False
            last_err = ""
            for name, cmd_tmpl in compilers:
                cmd = [
                    part.replace("{src}", src).replace("{exe}", exe)
                    for part in cmd_tmpl
                ]
                try:
                    r = subprocess.run(
                        cmd, capture_output=True, timeout=20, cwd=tmp
                    )
                    if r.returncode == 0 and os.path.exists(exe):
                        compiled = True
                        break
                    last_err = (r.stderr or r.stdout or b"").decode("utf-8", errors="ignore")
                except Exception as e:
                    last_err = str(e)

            if not compiled:
                return (None,) * 7

            r2 = subprocess.run(
                [exe], capture_output=True, text=True, timeout=5
            )
            if r2.returncode != 0:
                return (None,) * 7

            flags: dict[str, bool] = {}
            for line in r2.stdout.splitlines():
                k, _, v = line.partition("=")
                flags[k.strip()] = v.strip() == "1"

            if not flags:
                return (None,) * 7

            return (
                flags.get("avx",     None),
                flags.get("avx2",    None),
                flags.get("avx512f", None),
                flags.get("fma",     None),
                flags.get("bmi1",    None),
                flags.get("bmi2",    None),
                flags.get("popcnt",  None),
            )
    except Exception:
        return (None,) * 7



def _cpuid_via_model_string() -> tuple:
    """
    Inferência de AVX/AVX2 a partir do model string da CPU.

    Fontes tentadas em ordem:
    1. Registro do Windows (ProcessorNameString)
    2. /proc/cpuinfo model name (Linux fallback)
    3. platform.processor()

    Retorna (avx, avx2, avx512f, fma, bmi1, bmi2, popcnt) ou (None,...) * 7.
    """
    name = _get_cpu_model_name()
    if not name:
        return (None,) * 7

    name = name.lower()

    # ── Intel Core i-series ──────────────────────────────────────────────────
    import re

    # "Core i7-12700K", "Core i5-1135G7", etc.
    intel_match = re.search(r'i[3579]-(\d{4,5}[a-z]*)', name)
    if intel_match:
        model_str = intel_match.group(1)
        # Gen 10+ usa 5 dígitos: i5-10400 → gen=10, i7-12700K → gen=12
        # Gen 1-9 usa 4 dígitos: i7-8750H → gen=8, i5-4460 → gen=4
        digits = re.match(r'(\d+)', model_str).group(1)
        if len(digits) == 5:
            gen = int(digits[:2])   # primeiros 2 dígitos = geração
        else:
            gen = int(digits[0])    # primeiro dígito = geração

        # Geração 14: AVX2, potencialmente sem AVX-512 (desabilitado por Intel)
        if gen >= 12:
            return True, True, False, True, True, True, True
        # Gen 11 (Tiger Lake): tem AVX-512
        if gen == 11:
            return True, True, True, True, True, True, True
        # Gen 8-10 (Coffee/Ice Lake): AVX2, sem AVX-512 nos desktop/mobile
        if gen >= 8:
            return True, True, False, True, True, True, True
        # Gen 6-7 (Skylake/Kaby Lake): AVX2
        if gen >= 6:
            return True, True, False, True, True, True, True
        # Gen 4-5 (Haswell/Broadwell): AVX2
        if gen >= 4:
            return True, True, False, True, True, True, True
        # Gen 2-3 (Sandy/Ivy Bridge): AVX mas não AVX2
        if gen >= 2:
            return True, False, False, False, False, False, True

    # ── Intel Xeon ───────────────────────────────────────────────────────────
    if "xeon" in name:
        # Xeon Scalable (Skylake-SP e posteriores): AVX-512
        if re.search(r'(platinum|gold|silver|bronze)\s*\d{4}', name):
            return True, True, True, True, True, True, True
        # Xeon E5/E7 v4+ (Broadwell): AVX2
        if re.search(r'e[57]-\d{4}\s*v[4-9]', name):
            return True, True, False, True, True, True, True
        # Xeon E5/E7 v3 (Haswell): AVX2
        if re.search(r'e[57]-\d{4}\s*v3', name):
            return True, True, False, True, True, True, True
        # Xeon E3/E5 mais antigo: AVX
        return True, False, False, False, False, False, True

    # ── Intel Core Ultra (Meteor Lake / Arrow Lake, gen 1+) ──────────────────
    if "ultra" in name and "core" in name:
        return True, True, False, True, True, True, True

    # ── AMD Ryzen / Threadripper / EPYC ──────────────────────────────────────
    if any(x in name for x in ("ryzen", "threadripper", "epyc")):
        # Zen 4 / Ryzen 7000+: AVX-512
        zen4 = bool(re.search(r'ryzen\s*[579]\s*[789]\d{3}', name)) or "zen 4" in name
        return True, True, zen4, True, True, True, True

    # ── AMD FX (Bulldozer / Piledriver): AVX mas não AVX2 ────────────────────
    if re.search(r'amd\s*fx', name):
        return True, False, False, False, False, False, True

    # ── Genérico Intel com AVX no nome ────────────────────────────────────────
    if "intel" in name and "avx" in name:
        has_avx2 = "avx2" in name
        return True, has_avx2, False, has_avx2, has_avx2, has_avx2, True

    return (None,) * 7


def _get_cpu_model_name() -> str:
    """Retorna o model name da CPU de múltiplas fontes."""
    # Windows: registro
    if os.name == "nt":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
            return str(name).strip()
        except Exception:
            pass

    # Linux: /proc/cpuinfo
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass

    # Fallback: platform
    return platform.processor()




def _detect_gcc_march_flags() -> dict | None:
    """
    Tenta `gcc -march=native -Q --help=target` para obter flags ativas.
    Funciona em Windows com MinGW/MSYS2 no PATH.
    Retorna dict {flag_name: bool} ou None se gcc não disponível.
    """
    import shutil, subprocess
    if not shutil.which("gcc"):
        return None
    try:
        r = subprocess.run(
            ["gcc", "-march=native", "-Q", "--help=target"],
            capture_output=True, text=True, timeout=8,
        )
        if r.returncode != 0:
            return None

        result: dict[str, bool] = {}
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                flag = parts[0].lstrip("-")
                val  = parts[-1]
                result[flag] = val == "[enabled]"

        return result if result else None
    except Exception:
        return None


def _windows_cpu_vendor() -> str:
    """Lê vendor da CPU no registro do Windows (sem WMI nem admin)."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        )
        vendor, _ = winreg.QueryValueEx(key, "VendorIdentifier")
        winreg.CloseKey(key)
        return str(vendor)
    except Exception:
        return "unknown"


# ──────────────────────────────────────────────────────────────────────────────
# Estratégia 4: macOS — sysctl
# ──────────────────────────────────────────────────────────────────────────────

def _detect_sysctl() -> SIMDCapabilities | None:
    """macOS: usa sysctl hw.optional.*"""
    if sys.platform != "darwin":
        return None
    try:
        import subprocess

        def sysctl_bool(key: str) -> bool:
            try:
                r = subprocess.run(
                    ["sysctl", "-n", key],
                    capture_output=True, text=True, timeout=3
                )
                return r.stdout.strip() == "1"
            except Exception:
                return False

        # macOS Apple Silicon
        machine = platform.machine().lower()
        if machine == "arm64":
            return SIMDCapabilities(
                neon   = True,
                arch   = "arm64",
                vendor = "Apple",
            )

        return SIMDCapabilities(
            sse2     = sysctl_bool("hw.optional.sse2"),
            sse4_1   = sysctl_bool("hw.optional.sse4_1"),
            sse4_2   = sysctl_bool("hw.optional.sse4_2"),
            avx      = sysctl_bool("hw.optional.avx1_0"),
            avx2     = sysctl_bool("hw.optional.avx2_0"),
            avx512f  = sysctl_bool("hw.optional.avx512f"),
            fma      = sysctl_bool("hw.optional.fma"),
            arch     = platform.machine(),
            vendor   = "Intel",
        )
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Estratégia 5: fallback conservador
# ──────────────────────────────────────────────────────────────────────────────

def _detect_fallback() -> SIMDCapabilities:
    """
    Fallback seguro: x86_64 garante SSE2 pela ABI;
    ARM64 garante NEON.
    """
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return SIMDCapabilities(sse2=True, arch=machine, vendor="unknown")
    if machine in ("aarch64", "arm64"):
        return SIMDCapabilities(neon=True, arch=machine, vendor="unknown")
    if machine.startswith("arm"):
        return SIMDCapabilities(arch=machine, vendor="unknown")
    return SIMDCapabilities(arch=machine, vendor="unknown")


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def detect() -> SIMDCapabilities:
    """
    Detecta capacidades SIMD da CPU atual.

    Estratégia: coleta resultados de TODAS as fontes disponíveis e
    retorna o de maior nível (melhor detecção). Isso resolve o caso
    em que py-cpuinfo ou kernel32 retornam SSE4.2 sob Hyper-V enquanto
    o model string ou o probe C detectam AVX2 corretamente.

    Resultado é cacheado — chame quantas vezes quiser.
    """
    strategies = [
        ("py-cpuinfo",    _detect_cpuinfo),
        ("/proc/cpuinfo", _detect_proc_cpuinfo),
        ("kernel32",      _detect_windows_kernel32),
        ("sysctl",        _detect_sysctl),
        ("cpuid-probe",   _detect_cpuid),
    ]

    candidates: list[SIMDCapabilities] = []

    for name, fn in strategies:
        try:
            caps = fn()
            if caps is not None:
                candidates.append(caps)
        except Exception:
            continue

    if not candidates:
        return _detect_fallback()

    # Escolhe o candidato com maior nível SIMD
    best = max(candidates, key=lambda c: c.level)

    # Refinamento: se melhor resultado ainda é <= sse4.2 em x86_64,
    # tenta inferência via model string (útil sob Hyper-V onde todas
    # as estratégias anteriores são limitadas pelo OS)
    if best.level <= 3 and platform.machine().lower() in ("x86_64", "amd64"):
        refined = _refine_via_model_string(best)
        if refined.level > best.level:
            best = refined

    return best


def _refine_via_model_string(base: SIMDCapabilities) -> SIMDCapabilities:
    """
    Tenta melhorar 'base' com inferência pelo ProcessorNameString.
    Retorna base inalterado se não conseguir inferir nada melhor.
    """
    try:
        inferred = _cpuid_via_model_string()
        # inferred retorna (avx, avx2, avx512f, fma, bmi1, bmi2, popcnt)
        avx, avx2, avx512f, fma, bmi1, bmi2, popcnt = inferred
        if avx is None:
            return base

        from dataclasses import replace
        return replace(
            base,
            avx     = avx     or base.avx,
            avx2    = avx2    or base.avx2,
            avx512f = avx512f or base.avx512f,
            fma     = fma     or base.fma,
            bmi1    = bmi1    or base.bmi1,
            bmi2    = bmi2    or base.bmi2,
            popcnt  = popcnt  or base.popcnt,
        )
    except Exception:
        return base


def invalidate_cache() -> None:
    """Limpa o cache — necessário apenas em testes."""
    detect.cache_clear()


# ──────────────────────────────────────────────────────────────────────────────
# CLI rápido (python -m simd_detector)
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    caps = detect()
    print(json.dumps(caps.to_dict(), indent=2))