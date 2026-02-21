# DoxoNet Architecture: A Neuro-Symbolic Approach
**Versão:** 1.0 (Cortex v14 / Ouroboros v13)
**Data:** 16/12/2025
**Autor:** olDox222 & AI Assistant

## 1. Resumo
O DoxoNet é uma engine de Inteligência Artificial proprietária, escrita em Python puro (NumPy), focada em eficiência extrema e execução em hardware limitado (CPU/Mobile). Diferente de LLMs massivos, o DoxoNet utiliza uma abordagem **Neuro-Simbólica**, combinando uma rede neural recorrente (LSTM) com um autômato de pilha rigoroso (Arquiteto Lógico) para garantir a validade sintática do código gerado.

## 2. Componentes Principais

### 2.1. O Córtex (Sistema 1 - Intuição)
*   **Arquitetura:** LSTM (Long Short-Term Memory) com *Fused Gates* para otimização de CPU.
*   **Otimização:**
    *   **Adam Optimizer:** Com persistência de estado (momentos $m$ e $v$).
    *   **Quantização 8-bit:** Redução de armazenamento (~90KB) com dequantização dinâmica para Float32 durante a inferência.
    *   **Ativação DoxoAct:** $f(x) = x \cdot \sigma(x) + 0.1\sin(x)$. Uma variante experimental da Swish que introduz não-linearidade periódica.
*   **Input:** Tokenizer em nível de palavra com vocabulário dinâmico.

### 2.2. O Arquiteto (Sistema 2 - Lógica)
*   **Tecnologia:** Autômato Finito Determinístico (DFA) com Pilha.
*   **Função:** Monitora o fluxo de tokens gerados pela LSTM em tempo real.
*   **Regras Imutáveis:**
    *   Balanceamento de parênteses.
    *   Proibição de alucinação de variáveis (apenas variáveis definidas nos argumentos são permitidas no corpo).
    *   Imposição de estrutura (`def` $\to$ `(` $\to$ `args` $\to$ `)` $\to$ `:` $\to$ `return`).

### 2.3. O Agente Ouroboros (Ciclo de Vida)
Um loop de feedback autônomo que:
1.  **Gera** hipóteses de código.
2.  **Valida** via execução em sandbox (`subprocess`).
3.  **Aprende** via *Online Learning* (atualiza os pesos da LSTM imediatamente após um sucesso).
4.  **Memoriza** soluções comprovadas em um Banco Vetorial e SQL.

## 3. Segurança e Portabilidade
*   **JSON-Only:** Todo a persistência de estado foi migrada de `pickle` para `json` para eliminar riscos de Execução Remota de Código (RCE).
*   **No-Deps:** Zero dependências de frameworks pesados (PyTorch/TensorFlow). Roda onde houver NumPy.

## 4. Métricas Finais
*   **Tamanho do Modelo:** < 500KB.
*   **Tempo de Convergência (Sintaxe):** ~50 épocas.
*   **Taxa de Sucesso (Linear Tasks):** > 90% após *fine-tuning*.