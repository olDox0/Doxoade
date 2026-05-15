# fast_search.s - Motor de Busca SSE2 Ultra-Veloce
# ABI: Windows x64 (RCX = buf, RDX = len, R8 = target_char)
# Otimizado para Intel Atom N2808

.text
.globl nexus_asm_fast_tag_check

nexus_asm_fast_tag_check:
    # 1. Setup Inicial
    testq %rdx, %rdx            # Se len == 0, sai fora
    jz .not_found
    
    # 2. BROADCAST: Preenche XMM0 com 16 cópias do target_char
    # Isso é Zero-Allocation: preparamos o alvo no "ar" (registradores)
    movd %r8d, %xmm0            # Move target (R8) para XMM0
    punpcklbw %xmm0, %xmm0      # 1 -> 2 bytes
    punpcklwd %xmm0, %xmm0      # 2 -> 4 bytes
    pshufd $0, %xmm0, %xmm0     # 4 -> 16 bytes (Broadcast completo)

.loop_simd:
    cmpq $16, %rdx              # Temos 16 bytes para processar?
    jl .scalar_tail             # Se não, vai para o resto (limpeza)

    # 3. LEITURA VETORIAL: Carrega 16 bytes do arquivo sem alocar nada
    movdqu (%rcx), %xmm1        # Carrega 16 bytes (unaligned para seguranca)
    
    # 4. COMPARAÇÃO PARALELA: Compara 16 bytes simultaneamente
    pcmpeqb %xmm0, %xmm1        # Compara XMM1 com XMM0 (Target)
    
    # 5. EXTRAÇÃO DE MÁSCARA: Transforma resultado em bits (1 bit por caractere)
    pmovmskb %xmm1, %eax        # Se houver match, EAX terá bits em 1
    
    testl %eax, %eax            # Algum caractere bateu?
    jnz .found                  # Se sim, pula para o sucesso

    # 6. AVANÇO DE PONTEIRO: Pula 16 bytes de uma vez
    addq $16, %rcx
    subq $16, %rdx
    jmp .loop_simd

.scalar_tail:
    # Processa os bytes restantes (< 16) um por um
    testq %rdx, %rdx
    jz .not_found
    cmpb (%rcx), %r8b
    je .found
    incq %rcx
    decq %rdx
    jmp .scalar_tail

.found:
    movq $1, %rax               # Retorna 1 (True) no registrador RAX
    ret

.not_found:
    xorq %rax, %rax             # Retorna 0 (False)
    ret
    
    
# Adicione ao seu fast_search.s
.globl nexus_asm_structural_weight

# Windows x64 ABI: RCX=buf, RDX=len
# Retorna: RAX (nodes), RDX (loops), R8 (depth) via ponteiros ou compactado
nexus_asm_structural_weight:
    xorq %rax, %rax             # Contador de Nodes ( ( [ { = )
    xorq %r8, %r8              # Contador de Loops ( f w )
    
.weight_loop:
    cmpq $0, %rdx
    jz .weight_done
    
    movb (%rcx), %bl
    
    # Check de Nodes: ( [ { = 
    cmpb $40, %bl   # '('
    je .is_node
    cmpb $91, %bl   # '['
    je .is_node
    cmpb $123, %bl
    je .is_node
    cmpb $61, %bl
    je .is_node
    jmp .check_loop

.is_node:
    incq %rax
    jmp .next_byte

.check_loop:
    # Check de Loops: 'f' (for) ou 'w' (while)
    cmpb $102, %bl  # 'f'
    je .is_loop
    cmpb $119, %bl  # 'w'
    je .is_loop
    jmp .next_byte

.is_loop:
    incq %r8

.next_byte:
    incq %rcx
    decq %rdx
    jmp .weight_loop

.weight_done:
    # Retorna o peso combinado em RAX (Bits 0-31: Nodes, Bits 32-63: Loops)
    shlq $32, %r8
    orq %r8, %rax
    ret
    
    
