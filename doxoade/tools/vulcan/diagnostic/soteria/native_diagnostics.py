# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/diagnostic/soteria/native_diagnostics.py
from .crash_signatures import WIN_SIGNALS, NATIVE_LOGIC_PATTERNS

def diagnose_native_error(exit_code: int, tags: dict) -> tuple:
    """Especialista Analítico: Conecta sintomas físicos a causas lógicas."""
    try:
        # 1. Obter base dos sinais
        code = exit_code & 0xFFFFFFFF if exit_code is not None else 0
        status, explanation = WIN_SIGNALS.get(code, ("NATIVE_FAULT", "Falha não classificada."))
        
        # --- HEURÍSTICA DE DETETIVE (Chief Intelligence) ---
        detail = tags.get('DETAIL', '').upper()
        motivo = tags.get('MOTIVO', '').upper()
        fault_addr = tags.get('FAULT_ADDR', '').lower()

        if "MIXED_ALLOCATOR_USAGE" in motivo: return (
                "Mixed Allocator Violation",
                f"FALHA CRÍTICA: {detail}. Memória alocada por uma API e liberada por outra. Isso corrompe as estruturas de controle do Heap."
            )
        if "INVALID_FREE" in motivo: return (
                "Invalid Free Attempt",
                "SEGURANÇA: O código tentou liberar (free) um endereço que não está no registro de alocações vivas. Pode ser um ponteiro para a Pilha ou um endereço corrompido."
            )
        if "MEMORY_LEAK_REPORT" in motivo: return (
                "Resource Leak Detected",
                "O processo encerrou com recursos órfãos. Verifique a lista de TAG_LEAK_ENTRY no dossiê para identificar as linhas de código que não liberaram a memória."
            )

        if "DANGLING_STACK" in tags.get('MOTIVO', ''): return (
            "Dangling Pointer (Stack)", 
            "Risco de Corrupção de Dados: O programa tentou acessar uma memória que pertencia a uma função que já retornou." )
        if "DANGLING_STACK" in motivo: return (
            "Dangling Pointer (Stack)", 
            "Risco de Corrupção: programa tentou acessar variável local que não existe mais (escopo fechou).")
        if "USE_AFTER_FREE" in motivo: return (
            "Use-After-Free (UAF)", 
            "binário tentou ler ou escrever em ponteiro 'Zumbi' (memória já liberada pelo free).")

        if "SILENT_CORRUPTION" in motivo or "CORRUPTION" in detail:
            if "TAG_IO_EVENT: free" in str(tags): return (
                "Use-After-Free (UAF)", 
                "binário tentou escrever em bloco de memória que já foi devolvido ao sistema (Zombie Pointer).")
            return ("Memory Corruption / Overrun", "Violação de limite de buffer detectada na Arena Hades.")

        # Sintoma A: AccessViolation em endereços "suspeitos" (ex: 0x58585858 ou muito baixos)
        # Se o endereço de falha for uma repetição de bytes (como 'X' ou '0'), é Smashing certeiro.
        if exit_code == 0xc0000005:
            fault_addr, addr_str = tags.get('FAULT_ADDR', '0x0')

            try: addr_int = int(addr_str, 16)
            except: addr_int = 0

            if addr_int < 0x1000: return (
                "Null Pointer Dereference", 
                "programa tentou ler ou escrever no endereço ZERO. Isso é uma falha de inicialização crítica.")
            
            if "DOUBLE_FREE" in tags.get('MOTIVO', ''): return (
                "Heap Corruption (Double Free)",
                "sistema tentou liberar memória já desalocada.")
                
            return ("Memory Violation / Wild Pointer", 
                    f"Acesso ilegal em {addr_str}. Pode ser um Use-After-Free ou um ponteiro não inicializado.")


            if fault_addr in ["0x0", "0x00000000", "0x0000000000000000"]: return (
                "Null Pointer Dereference",
                "programa tentou ler ou escrever no endereço ZERO." )
            
            if "DOUBLE_FREE" in motivo: return (
                "Heap Corruption (Double Free)",
                "sistema tentou liberar memória que já estava livre.")
                
            if "provocar_colapso" in str(tags): # Exemplo de linha 51
                status      = "STACK_SMASH_DETECTED"
                explanation = "Falha Crítica: Código destruiu endereço de retorno na pilha."
                
            if "CORRUPTION" in motivo or "CANARY" in motivo:
                status      = "MemoryCorruption"
                explanation = "ponteiro tentou acessar memória proibida após corromper Zona de Guarda."
            if any("provocar_colapso" in str(tag) for tag in tags.values()):
                 status      = "STACK_SMASH_DETECTED"
                 explanation = "Falha Crítica de Segurança: código destruiu próprio endereço de retorno na pilha."
            if "0x00000000" in fault_addr or "0x00000001" in fault_addr:
                status = "NullPointerDereference"
                explanation = "binário tentou ler ou escrever no endereço ZERO. Geralmente causado por ponteiro não inicializado."
            if "585858" in fault_addr or "414141" in fault_addr:
                status = "CRITICAL_STACK_SMASH"
                explanation = "endereço de retorno foi atropelado por lixo. Causa provável: Buffer Overflow."
            if "PONTEIRO NULO" in detail or "0x00000000" in fault_addr:
                status = "NullPointerDereference"
                explanation = "binário tentou escrever ou ler no endereço ZERO da RAM. Isso é erro de lógica de ponteiros."
            if "0x" in fault_addr:
                status = "AccessViolation"
                explanation = f"Tentativa ilegal de acessar a memória no endereço {fault_addr}."
            if exit_code == 0xC0000374:
                status = "Heap Corruption (Critical)"
                explanation = "gerenciador de memória detectou que Heap fora violado (provável Double Free ou Buffer Overrun em memória dinâmica)."

#             return ("Access Violation / Use-After-Free", f"Tentativa ilegal de acessar {fault_addr}. Pode ser um ponteiro solto (Dangling) ou memória já liberada (UAF).")

        # Sintoma B: Stack Buffer Overrun explícito (Vetor de Segurança)
        if exit_code == 0xc0000409:
            status      = "SECURITY_VIOLATION (StackSmash)"
            explanation = "integridade da pilha foi destruída por um buffer overflow. O Windows interrompeu o processo para evitar exploit."
        
        # Sintoma C: Corrupção de Arena
        if "SILENT_CORRUPTION" in motivo:
            status      = "MemoryCorruption (HadesSentinel)"
            explanation = "Zona de Guarda (Canário) foi violada. Escrita detectada fora do limite do malloc."

        if "DOUBLE_FREE" in motivo: return (
            "Heap Corruption (Double Free)", 
            "Falha Crítica de Lógica: binário tentou liberar bloco de memória que já foi desalocado.")
        
        if "SILENT_CORRUPTION" in motivo: return (
            "Memory Overrun (HadesSentinel)", 
            "Zona de Guarda (Canário) foi violada. Houve escrita fora dos limites permitidos.")

        if "STACK_SMASH" in motivo: return (
            "Stack Smashing Detected", 
            "Buffer Overflow: pilha de execução foi corrompida, ameaçando integridade do retorno da função.")

        for key, err, exp in NATIVE_LOGIC_PATTERNS:
            if key in motivo or key in detail:
                return err, exp

        return status, explanation
        
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context="activate_protocol", debug=True)