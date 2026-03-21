import platform

def _flags_linux():
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.lower().startswith("flags"):
                    return set(line.split(":")[1].strip().split())
    except Exception:
        pass
    return set()

def _flags_windows():
    try:
        import cpuinfo
        info = cpuinfo.get_cpu_info()
        return set(info.get("flags", []))
    except Exception:
        return set()

def cpu_flags():
    system = platform.system().lower()

    if system == "linux":
        return _flags_linux()

    if system == "windows":
        return _flags_windows()

    return set()
    
def simd_level(flags=None):
    if flags is None:
        flags = cpu_flags()

    if "avx512f" in flags:
        return "AVX512"

    if "avx2" in flags:
        return "AVX2"

    if "avx" in flags:
        return "AVX"

    if "sse4_2" in flags:
        return "SSE4"

    if "sse2" in flags:
        return "SSE2"

    return "SCALAR"
    
def simd_report():
    flags = cpu_flags()

    report = {
        "sse4_2": "sse4_2" in flags,
        "avx": "avx" in flags,
        "avx2": "avx2" in flags,
        "avx512": any(f.startswith("avx512") for f in flags),
        "level": simd_level(flags)
    }

    return report
    
def simd_compile_flags(level=None):
    if level is None:
        level = simd_level()

    system = platform.system()

    # Windows / MSVC
    if system == "Windows":
        if level == "AVX2":
            return ["/O2", "/arch:AVX2"]

        if level == "AVX":
            return ["/O2", "/arch:AVX"]

        return ["/O2", "/arch:SSE2"]

    # GCC / Clang
    flags = ["-O3"]

    if level == "AVX512":
        flags += ["-mavx512f"]

    elif level == "AVX2":
        # FMA é garantida em todas as CPUs com AVX2 (Intel Haswell+, AMD Zen+)
        flags += ["-mavx2", "-mfma", "-mbmi", "-mbmi2"]

    elif level == "AVX":
        # Sem -mfma aqui: nem toda CPU com AVX tem FMA (ex: Sandy Bridge).
        # simd_compiler.py acrescenta -mfma via SIMDCapabilities quando detectado.
        flags += ["-mavx"]

    elif level == "SSE4":
        flags += ["-msse4.2", "-mpopcnt"]

    elif level == "SSE2":
        flags += ["-msse2"]

    return flags