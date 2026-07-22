# HBC6: Hermes Bytecode Compiler v6
## Relatório de Pesquisa, Arquitetura e Engenharia de Baixo Nível

**Data:** Julho de 2026  
**Status:** 🟢 Em Produção (Estável)  
**Autor:** Doxoade Research Team  
**Tags:** `#cpinternals` `#bytecode` `#lz4` `#varints` `#meta-path-finder`

---

## 1. Resumo Executivo

O **HBC6** é a sexta iteração do sistema de compressão e linkagem de bytecode do ecossistema Doxoade. Seu objetivo principal é mitigar o gargalo de I/O e parsing durante o *cold start* (boot) de aplicações Python complexas, substituindo a leitura e compilação de arquivos `.py` pelo carregamento direto de *code objects* pré-compilados, comprimidos e otimizados.

### 🏆 Resultados Empíricos em Produção
- **Speedup Médio de Import:** **21.62x** mais rápido que o Python Puro.
- **Speedup Pico:** **92.42x** (módulos com alta densidade de imports e strings longas).
- **Redução de Disco:** **-39.9%** no tamanho total dos artefatos (de 2.09 MB para 1.26 MB).
- **Sinergia HBC5 + HBC6:** 97.7% dos arquivos utilizam ambas as técnicas ortogonais.

---

## 2. Anatomia do Formato HBC6

O HBC6 abandona a abordagem de "zip de arquivos" e atua como um **Linker de Bytecode**. O formato binário é estritamente tipado e little-endian:

```text
┌─────────────────────────────────────────────────────────────┐
│ HEADER (6 bytes)                                            │
│  [0-3] Magic: "HBC6" (0x48 0x42 0x43 0x36)                 │
│  [4]   Version: 0x06                                        │
│  [5]   Flags: Bitfield (0x01=Strings, 0x02=Macros, 0x20=LZ4)│
├─────────────────────────────────────────────────────────────┤
│ HRT (Hermes Relocation Table)                               │
│  [4 bytes] Size                                             │
│  [N bytes] Entries: (co_index:4, offset:4, tid:2, len:2)    │
├─────────────────────────────────────────────────────────────┤
│ MACRO_DICT (Dicionário de N-grams com Varints LEB128)       │
│  [4 bytes] Size                                             │
│  [N bytes] Count(Varint) + [TokenID(Varint), Len(Varint)...]│
├─────────────────────────────────────────────────────────────┤
│ PAYLOAD (Marshal do CPython + LZ4 Block)                    │
│  [4 bytes] Size                                             │
│  [N bytes] LZ4 compressed marshal stream                    │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 Sinergia Ortogonal: HBC5 + HBC6
O HBC6 não substitui o HBC5, eles operam em domínios distintos do `PyCodeObject`:
- **HBC5 (Strings):** Atua em `co_consts`. Substitui strings longas e repetitivas (ex: `from pathlib import Path`) por caracteres Unicode da *Private Use Area* (`\uE000+`).
- **HBC6 (Bytecode):** Atua em `co_code`. Substitui sequências de instruções (N-grams) por macros de 2 bytes (`0xC0 + token_id`).

---

## 3. Desafios de Engenharia e Soluções

### 3.1 O Problema do Alinhamento Wordcode (Python 3.11+)
A partir do Python 3.11, o CPython adotou o formato **Wordcode**, onde *todas* as instruções ocupam exatamente 2 bytes (1 byte opcode + 1 byte argumento). 
Ao injetar uma macro de 2 bytes (`0xC0 0x05`) no lugar de um N-gram de 10 bytes, sobravam 8 bytes no `co_code`. Se deixados vazios ou com lixo, o CPython sofria **Access Violation (SegFault)** ao tentar ler argumentos como opcodes.

**A Solução (NOP Padding + HRT):**
1. O compressor preenche o espaço residual com instruções `NOP` (`0x09 0x00`).
2. O compressor grava na **HRT (Hermes Relocation Table)** o tamanho original do N-gram.
3. O loader, ao expandir a macro, consulta a HRT e pula exatamente os bytes necessários, removendo os NOPs e restaurando o alinhamento perfeito do Wordcode.

### 3.2 Varints LEB128 no MacroDict
Análises empíricas mostraram que a média de macros locais por arquivo era de apenas **1.52**. Usar `uint16` fixo (2 bytes) para os IDs era um desperdício de espaço no header.
Implementamos codificação **Varint (LEB128)**, reduzindo o overhead do MacroDict em até 50% para arquivos com poucos N-grams locais.

### 3.3 Compressão LZ4 no Payload
O `marshal.dumps()` gera um stream binário altamente redundante. Ao envolver o payload com `lz4.block.compress()`, ganhamos a corrida contra o I/O de disco. O custo de CPU para descomprimir o LZ4 na RAM (~1ms) é ordens de magnitude menor que o tempo de leitura de um SSD/HDD.

---

## 4. O MetaPathFinder (Redirecionamento Transparente)

Para que o HBC6 funcione em produção sem alterar o código-fonte dos módulos, implementamos um `importlib.abc.MetaPathFinder` instalado no `sys.meta_path` durante o `boot.py`.

**Fluxo de Interceptação:**
1. O Python tenta `import doxoade.commands.save`.
2. O `HBC6Finder` calcula o SHA-256 do `.py` original para localizar o `.hbc6` correspondente.
3. O `HermesLoader` lê o arquivo, descomprime o LZ4, reverte as strings (HBC5) e expande as macros (HBC6).
4. O `exec()` recebe um `code_obj` limpo e nativo.

### 4.1 Blacklist de Segurança
Módulos que utilizam C-extensions complexas, imports circulares no boot, ou que são o próprio sistema Hermes, são colocados em uma **Blacklist O(1)** para evitar recursão infinita e falhas de inicialização.

---

## 5. Dados Empíricos (Benchmark de Boot Real)

Teste realizado em ambiente de produção (Cold Start em subprocesso isolado):

| Módulo | Python Puro | HBC6 | Speedup |
| :--- | :--- | :--- | :--- |
| `vulcan_cmd` | 315.99 ms | 3.42 ms | **92.42x** 🔥 |
| `global_health` | 237.01 ms | 3.17 ms | **74.71x** 🔥 |
| `chronos` | 189.18 ms | 3.31 ms | **57.12x** |
| `intelligence_utils` | 25.99 ms | 3.18 ms | 8.18x |
| `check_utils` | 10.84 ms | 2.42 ms | 4.47x |
| **MÉDIA** | **424.13 ms** | **~20 ms** | **21.62x** |

---

## 6. Roadmap e Estudos Futuros

### 6.1 Reativação do Motor C (SSE 4.2)
O fallback Python atual é estável, mas a expansão de macros via C (usando `hermes_bridge.pyd` e instruções SIMD) pode reduzir o tempo de parse de ~2ms para <0.1ms. 
*Desafio:* O Motor C precisa ser atualizado para ler **Varints LEB128** e descomprimir **LZ4** nativamente antes de injetar o bytecode no CPython.

### 6.2 Carregamento Dinâmico de Dicionário (Tiered Loading)
Para arquivos `< 10KB`, o overhead de ler o `master.dict` global pode anular o ganho do HBC5. 
*Estudo:* Implementar um *Tiered Loader* que ignora a reversão de strings para arquivos minúsculos, ou carrega apenas um subconjunto do dicionário baseado no bitmap do header.

### 6.3 Otimização de N-grams com Machine Learning
Atualmente, os N-grams globais são extraídos via frequência estatística simples (`freq >= 50`).
*Estudo:* Usar análise de grafo de dependências para identificar "super-instruções" que são semanticamente seguras e stack-neutral, maximizando a compressão sem gerar HRTs gigantescas.

---