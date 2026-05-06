.text

# ---------------------------------------------------------------------------
# nexus_asm_search_char: Busca um byte em um buffer (16 bytes por ciclo)
# Windows x64: RCX=buf, RDX=len, R8=target_char
# ---------------------------------------------------------------------------
.globl nexus_asm_search_char
nexus_asm_search_char:
    movd %r8d, %xmm0        # Move o caractere alvo para o registrador SIMD
    pxor %xmm1, %xmm1       # Limpa xmm1
    pshufb %xmm1, %xmm0     # Distribui o caractere por todos os 16 bytes de xmm0
    
    xor %rax, %rax          # Índice = 0

search_loop:
    cmp %rdx, %rax
    jge not_found           # Se índice >= len, sai
    
    # Carrega 16 bytes do buffer
    movdqu (%rcx, %rax), %xmm2
    
    # Compara os 16 bytes com o alvo simultaneamente
    pcmpeqb %xmm0, %xmm2
    pmovmskb %xmm2, %r9d    # Gera uma máscara de bits dos resultados
    
    test %r9d, %r9d
    jnz found_match         # Se houver algum bit 1, achamos!
    
    add $16, %rax           # Pula 16 bytes de uma vez
    jmp search_loop

found_match:
    bsf %r9d, %r10d         # Acha a posição do primeiro bit setado
    add %r10, %rax
    ret

not_found:
    mov $-1, %rax
    ret
    
# ---------------------------------------------------------------------------
# nexus_asm_simd_match: Compara dois blocos de 16 bytes em um ciclo.
# Retorna 1 se forem idênticos, 0 se houver diferença.
# ---------------------------------------------------------------------------
.globl nexus_asm_simd_match
nexus_asm_simd_match:
    # RCX = ptr1, RDX = ptr2
    movdqu (%rcx), %xmm0    # Carrega 16 bytes do bloco 1
    movdqu (%rdx), %xmm1    # Carrega 16 bytes do bloco 2
    pcmpeqb %xmm1, %xmm0    # Compara byte a byte (SIMD)
    pmovmskb %xmm0, %eax    # Move a máscara de resultado para EAX
    xor $0xFFFF, %ax        # Inverte: se for 0, todos os bytes casaram
    setz %al                # Retorna 1 se AX era 0
    movzx %al, %rax
    ret
    
# ---------------------------------------------------------------------------
# nexus_asm_vec_search: Busca um byte em 16 posições simultaneamente (SSE4.2)
# ---------------------------------------------------------------------------
.globl nexus_asm_vec_search
nexus_asm_vec_search:
    test %rdx, %rdx
    jz vec_not_found

    # 1. Prepara o registrador de comparação
    movd %r8d, %xmm0        # Move o caractere para o início do xmm0
    pxor %xmm1, %xmm1       
    pshufb %xmm1, %xmm0     # Broadcast: espalha o caractere por todos os 16 bytes
    
    xor %rax, %rax          # rax = offset atual

vec_loop:
    # Verifica se faltam pelo menos 16 bytes
    mov %rdx, %r11
    sub %rax, %r11
    cmp $16, %r11
    jl scalar_fallback      # Se faltar menos de 16, vai pro modo lento final

    # 2. Carga e Comparação Atômica
    movdqu (%rcx, %rax), %xmm2 # Carrega 16 bytes da memória (unaligned)
    pcmpeqb %xmm0, %xmm2       # Compara os 16 de uma vez!
    pmovmskb %xmm2, %r10d      # Move os bits de resultado para r10d
    
    test %r10d, %r10d
    jnz vec_found              # Se não for zero, achamos um match!
    
    add $16, %rax              # Pula 16 bytes
    jmp vec_loop

vec_found:
    bsf %r10d, %r9d            # Bit Scan Forward: acha a posição do primeiro '1'
    add %r9, %rax
    ret

scalar_fallback:
    # Processa os últimos bytes um por um para evitar leitura fora do buffer
    cmp %rdx, %rax
    jge vec_not_found
    movzbl (%rcx, %rax), %r11d
    cmp %r8b, %r11b
    je scalar_done
    inc %rax
    jmp scalar_fallback

scalar_done:
    ret

vec_not_found:
    mov $-1, %rax
    ret

# ---------------------------------------------------------------------------
# nexus_asm_crc32: Hashing de Hardware SSE4.2
# Windows x64: RCX=buf, RDX=len
# ---------------------------------------------------------------------------
.globl nexus_asm_crc32
nexus_asm_crc32:
    xor %rax, %rax
    test %rdx, %rdx
    jz crc_end
crc_loop:
    cmp $8, %rdx
    jl crc_tail
    crc32q (%rcx), %rax     # Aceleração SSE4.2 do N2808
    add $8, %rcx
    sub $8, %rdx
    jnz crc_loop
crc_tail:
    test %rdx, %rdx
    jz crc_end
    crc32b (%rcx), %eax
    inc %rcx
    dec %rdx
    jnz crc_tail
crc_end:
    ret


