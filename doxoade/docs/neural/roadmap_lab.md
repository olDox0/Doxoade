# Roadmap de Pesquisa Avançada (Laboratório Beta)

## Fronteira 1: Arquiteturas de Atenção Eficiente
O LSTM atingiu seu limite em contextos longos.
*   **Experimento A:** Implementar **Linear Attention** (Complexidade $O(N)$ em vez de $O(N^2)$) em NumPy puro.
*   **Experimento B:** **State Space Models (Mamba/S4)**. Tentar implementar a discretização de equações diferenciais para memória infinita sem o custo de Transformers.

## Fronteira 2: Raciocínio Algorítmico
O "Arquiteto" atual é um verificador passivo.
*   **Projeto Solver:** Criar um mini-solver SMT (Satisfiability Modulo Theories) que *prova* matematicamente se o código gerado faz o que o nome da função pede (ex: se `soma` realmente resulta em `a+b`).
*   **Chain-of-Thought (CoT) Explícito:** Treinar a rede para gerar comentários de planejamento antes do código: `# Vou somar A e B \n return a + b`.

## Fronteira 3: Engenharia Genética de Topologia (NEAT)
Atualmente, a topologia (tamanho da camada oculta) é fixa ou escolhida manualmente.
*   **Neuro-Evolution:** Usar algoritmos genéticos não apenas para hiperparâmetros, mas para **criar e destruir sinapses** dinamicamente durante o treino, criando redes esparsas orgânicas.

## Fronteira 4: Interface Homem-Máquina
*   **Neural Shell:** Um terminal onde o comando não é rígido. Ex: `dox, limpa tudo aí` -> O sistema entende a intenção e executa `doxoade clean`.