# Protocolo de Qualidade (Cânone & Regressão)

O Doxoade utiliza um sistema de **Regressão Relativa**. Não exigimos que o código seja perfeito, exigimos que ele não piore.

## Os Três Pilares

### 1. Test Mapper (`test-map`)
Garante que todo arquivo de código tenha um arquivo de teste correspondente.
*   `doxoade test-map`: Mostra a matriz de cobertura.
*   `doxoade test-map --generate`: Cria esqueletos de teste (`skel`) automaticamente para arquivos órfãos.

### 2. Canonização (`canonize`)
Tira uma "foto" (Snapshot) do estado atual do projeto.
*   Salva: Erros de Lint conhecidos + Status dos Testes (Pass/Fail).
*   Comando: `doxoade canonize --all`
*   *Quando usar:* Quando você aceita o estado atual como o "Novo Normal" estável.

### 3. Teste de Regressão (`regression-test`)
Compara o código atual com o Cânone.
*   **Sucesso:** Se os erros forem os mesmos do cânone.
*   **Falha:** Se surgirem *novos* erros ou se testes que passavam começarem a falhar.
*   *Uso:* O `doxoade save` roda isso automaticamente (via check).

## Auto-Fixer (Cirurgião)
O comando `check --fix` utiliza estratégias cirúrgicas:
*   **Smart Import:** Remove apenas o módulo não usado de uma linha `from X import A, B`.
*   **Block Comment:** Comenta funções inteiras redefinidas, não apenas a assinatura.