### doxoade/docs/Research/mercury_research_HBC6.md

# 🧬 DOSSIER DE PESQUISA: MERCURY ENGINE (HBC6)
**Projeto:** Doxoade OADE | **Módulo:** Hermes Systems (Mercury Bridge)  
**Foco:** Compressão Semântica de Bytecode (Patch-in-RAM)  
**Status da Fase:** Consolidado (Limites do CPython 3.11+ Mapeados)  
**Regra de Ouro:** Anti-Blackbox & Data-Oriented Design  

---

## 1. 📑 Resumo Executivo
O formato **HBC6 (Hermes Binary Compressed v6)** foi projetado para realizar a **Compressão Semântica de Opcodes** em tempo de execução. A ideia central é identificar sequências repetitivas de bytecode (N-grams) no disco, substituí-las por um único "Macro Token" no arquivo, e reconstruí-las na RAM em microssegundos durante o boot, economizando memória e acelerando o carregamento.

**A Grande Descoberta Científica:** Durante a implementação do *Patch-in-RAM*, esbarramos e mapeamos uma barreira física intransponível do **CPython 3.11+**: O validador interno de *Stack Effect*. Esta pesquisa documenta como contornamos crashes fatais do interpretador criando o **C-Sentinel (Motor Forense)** e como pivotamos a arquitetura do HBC6 para um **Formato de Empacotamento Zero-LZMA de Alta Velocidade**.

---

## 2. 🏗️ Arquitetura Dual-Phase (O Caminho A)

A arquitetura do HBC6 foi dividida em duas frentes para garantir estabilidade e performance:

### 2.1. O Compressor Python (`hermes_compress_hbc6.py`)
Atua como o "Linker" estático. Ele não altera o bytecode final, mas gera o mapa de guerra:
1. **Compilação:** Compila o `.py` para `code_obj` com `optimize=2`.
2. **Mapeamento DFS:** Atribui um ID único para cada `CodeObject` aninhado.
3. **O Campo Minado (Jump Analysis):** Varre o bytecode procurando N-grams (ex: `IMPORT_NAME`, `STORE_NAME`). Para evitar corromper o fluxo de execução, ele descarta qualquer N-gram que esteja no "Campo Minado" (alvos ou origens de *Jumps*).
4. **Geração da HRT (Hermes Relocation Table):** Cria uma tabela binária contendo: `co_index`, `offset`, `token_id`, `orig_ngram_len`.
5. **Serialização Intacta:** Salva o `marshal.dumps()` do bytecode **100% intacto** no payload do HBC6.

### 2.2. O Motor C / Mercury Bridge (`hermes_hbc6_patches.c`)
Atua como o "Cirurgião de RAM". No boot, ele:
1. Faz o `mmap` do arquivo HBC6 (Zero-Copy).
2. Lê a HRT e o Dicionário Global (`master.bin`).
3. Carrega o `marshal` intacto via `PyMarshal_ReadObjectFromString`.
4. Executa um **DFS (Depth-First Search)** nativo em C, traversando os `co_consts`.
5. Aplica os patches na RAM substituindo os N-grams pelos Macro Tokens.

---

## 3. 🚨 A Barreira do CPython 3.11+: O Paradoxo do Stack Effect

### O Experimento
Tentamos injetar o opcode `NOP` (`0x09`) combinado com o `token_id` como argumento no lugar dos N-grams originais. Como o tamanho do buffer não mudava (usando *NOP Padding*), teoricamente o `co_linetable` continuaria válido.

### O Crash Silencioso (Hard Crash)
Ao chamar `code.replace(co_code=new_bytes)`, o CPython 3.11+ não apenas rejeitou a operação, mas **abortou o processo inteiro** sem deixar rastros na C-API padrão.

### A Causa Raiz (Forense)
O CPython 3.11+ introduz um validador interno rigoroso (`_PyCode_Validate`) que calcula o **Stack Effect** (Efeito na Pilha) de cada instrução.
* Opcodes reais (como `CALL`, `BINARY_OP`, `IMPORT_NAME`) empilham e desempilham valores na pilha virtual do Python.
* O opcode `NOP` é invisível para a pilha (Stack Effect = 0).
* Quando o validador percebe que a sequência de instruções (agora com NOPs) não fecha a pilha em zero, ele dispara um **`Py_FatalError("code_replace: stack effect mismatch")`** ou um `SystemError: bad argument to internal function` (em `tupleobject.c:116`).

**Conclusão Científica:** A compressão de opcodes via injeção de NOPs é **fisicamente inviável** em CPython 3.11+ sem modificar o código-fonte do interpretador (`ceval.c`).

---

## 4. 🛡️ O C-Sentinel: Motor Forense Anti-Blackbox

Para lidar com os crashes silenciosos do CPython e manter a regra *Anti-Blackbox*, desenvolvemos o **C-Sentinel** no Motor C.

Sempre que o CPython tenta validar um `replace()` e falha, o Sentinel:
1. Intercepta a exceção fantasma usando `PyErr_Fetch()`.
2. Gera um **Dossiê Forense** no `stderr` (Tamanho original, Linetable, Tipo de Erro).
3. Executa `PyErr_Clear()` para limpar o estado do interpretador.
4. Executa o **Fallback Seguro**: Descarta o patch e mantém o `CodeObject` original intacto.

*Graças ao C-Sentinel, o Motor C nunca contamina a memória do host, garantindo que o boot do Doxoade continue estável mesmo que 100% dos patches sejam rejeitados pelo CPython.*

---

## 5. 🔄 A Pivotagem: HBC6 como Zero-LZMA Packager

Diante do limite físico do *Stack Effect*, a arquitetura do HBC6 foi pivotada com sucesso para o que ela faz de melhor:

**O HBC6 não é mais um compressor de opcodes na RAM. Ele é um Formatador de Empacotamento de Alta Velocidade (Zero-LZMA).**

### Ganhos Reais Consolidados:
1. **Zero Decompressão LZMA:** O `marshal` é carregado direto do `mmap` em C, bypassando o `zlib/lzma`.
2. **Parse Otimizado em C:** O Motor C lê o header HBC6 e a HRT em microssegundos.
3. **Entrega Intacta e Segura:** O CPython recebe um `CodeObject` 100% nativo, válido e executável, sem risco de `Py_FatalError`.
4. **Telemetria de Bytecode:** A HRT embutida no arquivo serve como um "mapa de DNA" do módulo, útil para futuras otimizações de *Frame Evaluation*.

---
