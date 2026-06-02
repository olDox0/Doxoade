# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/diagnostic/soteria/native_diagnostics.py
from .crash_signatures import WIN_SIGNALS, NATIVE_LOGIC_PATTERNS

def diagnose_native_error(exit_code: int, tags: dict) -> tuple:
    """Especialista Analítico: Conecta sintomas físicos a causas lógicas."""
    
    # 1. Obter base dos sinais
    code = exit_code & 0xFFFFFFFF if exit_code is not None else 0
    status, explanation = WIN_SIGNALS.get(code, ("NATIVE_FAULT", "Falha não classificada."))
#    status, explanation = WIN_SIGNALS.get(exit_code, ("NATIVE_FAULT", "Falha não classificada."))
    
    # --- HEURÍSTICA DE DETETIVE (Chief Intelligence) ---
    
    detail = tags.get('DETAIL', '').upper()
    motivo = tags.get('MOTIVO', '').upper()
    fault_addr = tags.get('FAULT_ADDR', '').lower()

    # Sintoma A: AccessViolation em endereços "suspeitos" (ex: 0x58585858 ou muito baixos)
    # Se o endereço de falha for uma repetição de bytes (como 'X' ou '0'), é Smashing certeiro.
    if exit_code == 0xc0000005:
        if "CORRUPTION" in motivo or "CANARY" in motivo:
            status = "MemoryCorruption"
            explanation = "Um ponteiro tentou acessar memória proibida após corromper a Zona de Guarda."
        if any("provocar_colapso" in str(tag) for tag in tags.values()):
             status = "STACK_SMASH_DETECTED"
             explanation = "Falha Crítica de Segurança: O código destruiu o próprio endereço de retorno na pilha."
        if "0x00000000" in fault_addr or "0x00000001" in fault_addr:
            status = "NullPointerDereference"
            explanation = "O binário tentou ler ou escrever no endereço ZERO. Geralmente causado por um ponteiro não inicializado."
        if "585858" in fault_addr or "414141" in fault_addr:
            status = "CRITICAL_STACK_SMASH"
            explanation = "O endereço de retorno foi atropelado por lixo. Causa provável: Buffer Overflow."
        if "PONTEIRO NULO" in detail or "0x00000000" in fault_addr:
            status = "NullPointerDereference"
            explanation = "O binário tentou escrever ou ler no endereço ZERO da RAM. Isso é um erro de lógica de ponteiros."
        elif "0x" in fault_addr:
            status = "AccessViolation"
            explanation = f"Tentativa ilegal de acessar a memória no endereço {fault_addr}."

    # Sintoma B: Stack Buffer Overrun explícito (Vetor de Segurança)
    if exit_code == 0xc0000409:
        status = "SECURITY_VIOLATION (StackSmash)"
        explanation = "A integridade da pilha foi destruída por um buffer overflow. O Windows interrompeu o processo para evitar exploit."
    
    # Sintoma C: Corrupção de Arena
    if "SILENT_CORRUPTION" in motivo:
        status = "MemoryCorruption (HadesSentinel)"
        explanation = "A Zona de Guarda (Canário) foi violada. Escrita detectada fora do limite do malloc."

    for key, err, exp in NATIVE_LOGIC_PATTERNS:
        if key in motivo or key in detail:
            return err, exp

    return status, explanation