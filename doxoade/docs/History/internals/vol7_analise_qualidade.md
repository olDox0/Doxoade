# Doxoade Internals - Vol. 7: Análise e Qualidade

**Versão:** 1.0
**Foco:** Motores de Inspeção

## Motores de Análise Estática

### 1. Check (O Auditor Geral)
`doxoade check [path]`
*   **Função:** Linter primário.
*   **Pipeline:** Sintaxe -> Pyflakes -> Hunter (Risco) -> DRY (Clones).
*   **Flags:** `--fix` (tenta corrigir), `--clones` (ativa detecção de duplicatas), `--no-imports` (ignora erros de import).

### 2. Deepcheck (Raio-X)
`doxoade deepcheck arquivo.py`
*   **Função:** Análise profunda de fluxo de dados em um único arquivo.
*   **Saída:** Mostra complexidade ciclomática, variáveis usadas/não usadas e fluxo de funções. Útil para refatoração.

### 3. Style (O Arquiteto)
`doxoade style [path]`
*   **Função:** Validação arquitetural baseada no *Modern Power of Ten* (NASA/JPL).
*   **Regras:**
    *   Funções < 60 linhas.
    *   Sem `global`.
    *   Programação defensiva (asserts).
    *   Documentação presente (`--comment`).

### 4. Health & Global-Health
*   **`health`:** Mede a saúde do projeto (Cobertura de testes + Complexidade média). Gera uma "nota".
*   **`global-health`:** Verifica a instalação do Doxoade (PATH, dependências, conflitos de versão, pip).

## Motores de Teste Dinâmico

### 1. Test (Unit Testing)
`doxoade test [path]`
*   Wrapper para o `pytest`.
*   Captura falhas e registra no banco de dados de incidentes para aprendizado.

### 2. Regression-Test (O Cânone)
`doxoade regression-test`
*   **Conceito:** Snapshot Testing.
*   **Funcionamento:** Roda o `check` em todo o projeto e compara o JSON de saída com um "cânone" salvo (`regression_tests/canon/`). Se a saída mudou, alerta sobre regressão ou mudança de comportamento.

### 3. Verilog (Hardware)
`doxoade verilog`
*   Sonda especializada para arquivos `.v` (SystemVerilog).
*   Usa `iverilog` com Smart Linking.