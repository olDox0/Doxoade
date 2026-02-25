# doxoade/tools/vulcan/abi_gate.py
import os, json, struct, time 
from pathlib import Path

def _host_info():
    """Retorna informações da arquitetura do sistema hospedeiro."""
    return {
        "os": os.name,
        "bits": struct.calcsize("P") * 8,
        "py_arch": f"{struct.calcsize('P')*8}-bit",
    }

def _is_valid_pyd(path: Path) -> tuple[bool, str]:
    """Valida a ABI de um arquivo .pyd (Windows PE Header)."""
    try:
        if path.stat().st_size < 1024:
            return False, "FILE_TOO_SMALL"

        with path.open("rb") as f:
            # 1. Verifica o "Magic Number" de um executável Windows (MZ)
            if f.read(2) != b"MZ":
                return False, "INVALID_PE_MAGIC"

            # 2. Encontra o offset do cabeçalho PE
            f.seek(0x3C)
            pe_header_offset = struct.unpack("<I", f.read(4))[0]
            f.seek(pe_header_offset + 4) # Pula a assinatura 'PE\0\0'

            # 3. Lê o Machine Type para verificar a arquitetura (32 vs 64 bit)
            machine_type = struct.unpack("<H", f.read(2))[0]

            host_bits = struct.calcsize("P") * 8
            # 0x8664 = x64, 0x014c = x86 (32-bit)
            if host_bits == 64 and machine_type != 0x8664:
                return False, "ARCH_MISMATCH (Host=64, Bin=32)"
            if host_bits == 32 and machine_type != 0x014C:
                return False, "ARCH_MISMATCH (Host=32, Bin=64)"

        return True, "OK"
    except Exception as e:
        return False, f"EXCEPTION:{e}"

def run_abi_gate(project_root: str) -> dict:
    """Orquestra a verificação e promoção/quarentena de artefatos."""
    from .artifact_manager import ensure_dirs, promote_to_bin, quarantine
    
    ensure_dirs(project_root) # Garante que as pastas staging, bin, quarantine existam
    base = Path(project_root) / ".doxoade" / "vulcan"
    staging = base / "staging"
    
    report = {
        "timestamp": time.time(),
        "host": _host_info(),
        "approved": [],
        "quarantined": [],
    }

    for pyd in staging.glob(f"*.{ 'pyd' if os.name == 'nt' else 'so' }"):
        is_ok, reason = (True, "OK") # No-op para Linux/macOS por enquanto
        if os.name == 'nt':
            is_ok, reason = _is_valid_pyd(pyd)
        
        if is_ok:
            promote_to_bin(project_root, pyd)
            report["approved"].append(pyd.name)
        else:
            quarantine(project_root, pyd, reason)
            report["quarantined"].append({"file": pyd.name, "reason": reason})

    (base / "abi_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report