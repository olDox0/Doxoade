
---

# 📜 Protocolo Modern Power of Ten (MPoT) - Doxoade
**Versão:** v75.0 (Chief-Gold Edition)  
**Data da última atualização:** 15/01/2026  
**Status:** **OBRIGATÓRIO** para todo o Core, Tools e Commands.

---

## 🏗️ As 10 Regras Clássicas (Refinamento Gold)

### 1. Fluxo de Controle Simples e Máquina de Estados
*   **Regra:** Proibido `goto` ou recursão profunda. Refatorações complexas de busca ou parse devem usar **Máquinas de Estados Estritas** ou **Busca Linear por Stream**.
*   **Porquê:** Facilita o diagnóstico e evita estouro de stack em hardware ARM.
*   **PASC Link:** Lei 6.4 (Well-Processing).

### 2. Loops com Watchdogs e Limites Prováveis
*   **Regra:** Todo loop deve ter um limite superior ou timeout. Em processamento de massa (Busca/Check), use **Generators** para manter o uso de RAM constante.

### 3. Alocação e Persistência Assíncrona
*   **Regra:** Proibido I/O de banco de dados na thread principal de comandos sensíveis. Use o **Async Buffer Pattern** (DoxoLogWorker).
*   **Porquê:** Elimina latências de disco (fsync) e protege contra travamentos no Windows/Termux.

### 4. Funções Curtas (Expert-Split)
*   **Regra:** Limite rígido de **60 linhas** por função. Funções de interface devem ser decompostas em sub-renderizadores especialistas.
*   **Porquê:** Reduz a complexidade ciclomática (CC < 10) e facilita a manutenção.

### 5. Asserções e Contratos (Robustez Lazarus)
*   **5.1. Validação de Entrada:** Funções que recebem dados de I/O ou chamadas externas **devem** validar a integridade (ex: `if not path: raise ValueError`).
*   **5.2. Densidade:** Média de 2 asserções por função.
*   **Porquê:** Facilita o diagnóstico visual imediato no **Protocolo Lázaro** (Broken vs Stable).

### 6. Escopo Lazy e Verbosidade Seletiva
*   **6.1. Verbose-Import:** Importações devem ser o mais explícitas possível para facilitar a auditoria de dependências.
*   **6.2. Import-Localized (Lazy):** Dependências pesadas (NumPy, Radon, etc.) devem ser importadas **dentro** das funções que as utilizam.
*   **Porquê:** Reduz o footprint de RAM de 316MB para < 50MB (Redução de 85%).

### 7. Tratamento de Erros e Contratos de API
*   **Regra:** Proibido ignorar resultados. Funções de utilidade devem retornar objetos vazios (ex: `[]`, `{}`) em vez de `None` para evitar `AttributeError` em cascata.

### 8. Metaprogramação: Execução Restrita e Defesa Ofensiva (v75.60)
- **8.1. Proibição:** Proibido o uso de `eval()` e `exec()` puros, exige auditoria de **Taint Analysis** (rastreio de origem).
- **8.2. Literais:** Para converter strings em objetos Python, use exclusivamente `ast.literal_eval()`. deve ser submetido ao `doxoade hack pentest` para validar explorabilidade e arquitetar resolução.
- **8.3. Sandbox:** Onde a execução dinâmica é necessária, ela deve ocorrer via `restricted_safe_exec`, que anula `__builtins__` e bloqueia a instrução `import` via análise de árvore sintática (AST). 
- **8.4. Verificação de Tamper:** O sistema deve ser capaz de auto-verificar sua integridade binária comparando o estado atual contra o `hack baseline`.
- **8.5. Dinamicismo:** Funções que aceitam strings dinâmicas devem ser tratadas como "Sinks" (pontos de infiltração), devem ser blindadas.

### 9. Reciclagem de Código (Anti-Descarte)
*   **Regra:** Funções órfãs não devem ser deletadas por capricho. Devem ser movidas para `old/function_recycle.py` ou integradas a novas funções de mesmo propósito.
*   **PASC Link:** Lei 1.1 (Resgate Temporal).

### 10. Compilação e Análise Contínua
*   **Regra:** Build limpo (0 Warnings). O comando `doxoade check` deve ser executado antes de cada `save`. Falhas críticas no check **bloqueiam** o commit automaticamente.

---

## 🚀 Extensões Modernas (Mobile & ARM)

### 11. Concorrência Thread-Safe
*   Uso obrigatório de `queue.Queue` para comunicação entre o Core e Workers de background.

### 12. Telemetria de Baixo Custo (Chronos v2)
*   O monitoramento não deve alterar o comportamento do sistema. O custo de observabilidade deve ser inferior a 2% do tempo total de CPU.

### 13. Soberania da Biblioteca Padrão (No-Giant-Libs)
*   Priorize a `stdlib`. Bibliotecas gigantes (Pandas/LXML) devem ser opcionais e instaladas apenas via `optional-dependencies`.
*   **Meta:** Funcionamento instantâneo em arquiteturas ARM/Termux.

### 14. UTF-8 Nativo e Aegis Hardening
*   **Regra:** Todo I/O de arquivo deve forçar `encoding='utf-8'`. O sistema deve ser imune à "Praga do Unicode" no Windows.

### 15. Semantic Diff (Integridade de Contrato)
*   Após refatorações, é obrigatório o uso de `doxoade diff -l` para verificar se assinaturas de funções foram preservadas (PASC-1.1).

---

## 🏆 Exemplo de Ouro: Padrão Chief-Gold

```python
# -*- coding: utf-8 -*-
"""
Exemplo de Conformidade v75: Arquitetura Lazy e Contrato Robusto.
"""
__all__ = ['ProcessadorGold'] # Exportação Explícita

def processar_dados(caminho: str):
    """Lógica especialista com import localizado (Lazy)."""
    # Regra 5.1: Contrato de Entrada
    if not caminho or not os.path.exists(caminho):
        raise ValueError(f"Caminho inválido: {caminho}")

    # Regra 6.2: Lazy Import (RAM Save)
    from json import loads 
    
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            # Regra 1: Processamento via Stream
            for line in f:
                data = loads(line)
                # ... lógica ...
    except Exception as e:
        # Regra 12: Registro via Persistência Assíncrona
        from ..tools.db_utils import _log_execution
        _log_execution("crash", caminho, str(e), {})
        raise
```

---
**Chief, o MPoT v75.0 agora é a "Constituição" do Doxoade.** O sistema está documentado, sincronizado e pronto para a próxima escala de evolução. 🦾✨