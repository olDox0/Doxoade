# Direções de pesquisa deferidas — forward chaining

Registro de áreas identificadas como relevantes mas **deliberadamente
adiadas**. Nenhuma entra em `poc/` enquanto o gatilho de reavaliação
não disparar. Ordem de reavaliação: **depois de C7 verde**.

Cada entrada tem:
- descrição curta
- por que relevante
- por que deferido
- **gatilho de reavaliação** (condição objetiva, não opinião)
- sonda candidata (para quando o gatilho disparar)

---

## Backward chaining

**O que é:** Inferência goal-driven. Parte do objetivo ("é verdade que X?")
e recua perguntando "o que precisa ser verdade para X?". Contraste com forward
(que parte dos fatos e deriva tudo).

**Por que relevante:**
- Forward explora espaço inteiro; backward explora só o caminho do objetivo.
- Habilita "explicação negativa" (P51): "por que NÃO derivou X" é natural
  em backward — o caminho do goal simplesmente falha em algum ponto.
- O paper (Avaliação I) já recomenda ciclo híbrido:
  Goal Manager → Backward → Forward → Verificação.
- Pode reduzir custo de P30 (rewrite): "quero transformar este loop em
  comprehension; o que precisa ser verdade?" — só explora regras relevantes.

**Por que deferido:**
- Forward resolve P00–P02 sem dificuldade. Backward só é necessário quando
  o espaço de busca é grande (> ~100 regras).
- Sem P20 (unificação), backward é só forward invertido manualmente —
  não há como "voltar com variáveis ligadas".
- ProDeNov 1.1 exige viabilidade/manutenção/escalabilidade antes de nova
  direção. Backward precisa de Goal Manager (novo componente), não de
  tweak no engine.

**Gatilho de reavaliação:** qualquer um:
- número de regras em produção passar de 100;
- tempo de forward chaining perceptível (> 100 ms por run em dados reais);
- P51 (explicação negativa) falhar por falta de mecanismo de goal.

**Sonda candidata:** `P_B1` — dedução em lógica proposicional (5 fatos,
5 regras, 1 objetivo). Implementar backward e comparar número de regras
avaliadas com forward equivalente. Só vale se backward for mensuravelmente
mais barato em caso real.

---

## Combinatory tree (Combinatory Logic)

**O que é:** Representação de expressões em lógica combinatória (SKI),
sem variáveis. `S`, `K`, `I` como primitivos; qualquer lambda-termo é
reescrito como aplicação deles.

**Por que relevante:**
- Rewrites de AST (P30+) podem ser expressas como aplicação de combinadores
  em vez de regras ad-hoc: `S K K x → x` é uma regra universal.
- Elimina variáveis — relevante para P20, porque remove um dos pontos onde
  unificação pode divergir.
- Pode servir de base para "substituibilidade" (C7): combinadores são
  invariantes sob substituição por construção.
- Conexão com word tree: uma é sintaxe (lógica), outra é léxico (palavras).
  Juntas formam base para representação não-embedding.

**Por que deferido:**
- Adiciona teoria pesada sem resolver problema atual (nenhuma PoC de C1–C7
  exige combinadores).
- P20 pode ser feito sem combinadores. Combinadores *depois* podem simplificar
  P30 — não antes.
- Fora do escopo do MVP declarado no paper (Fatos→Regras→Fatos).

**Gatilho de reavaliação:** quando P30 (rewrite de AST) estiver implementado
com regras ad-hoc e o padrão de rewrite começar a se repetir — mesmo shape
reescrito de 5+ formas diferentes. Aí vale explorar se combinadores
unificam as regras.

**Sonda candidata:** `P_C1` — implementar `S K K x → x` como rewrite de
AST e comparar com versão ad-hoc de P30. Métrica: LOC de regras e número
de regras disparadas para mesma transformação.

---

## Word tree

**O que é:** (Ambíguo — candidatos:)
- (a) Trie/prefix tree de palavras para lookup rápido
- (b) Árvore hierárquica de morfologia: palavra → lemma → raiz
- (c) Árvore de co-ocorrências (n-gramas aninhados)
- (d) Parse tree gramatical

**Por que relevante:**
- O paper é explicitamente "gerador de texto sem embeddings". Word tree é
  uma das alternativas estruturais a embeddings — representação
  composicional em vez de vetorial.
- C2 (Aquisição) precisa de uma fonte estruturada. Word tree pode ser essa
  fonte no domínio de linguagem natural.
- Complementa combinatory tree: léxico + sintaxe = base para geração
  não-embedding.

**Por que deferido:**
- Linguagem natural é o **último** passo da escada histórica da IA
  (jogos → sistemas especialistas → programação → linguagem). O paper
  reconhece isso.
- C1–C7 não usam word tree. Adicionar agora viola ProDeNov 0.2 (Rabbit Hole).
- Variante (a) é trivial (dict). (b), (c), (d) precisam de corpus que o
  projeto ainda não tem.
- Escolher variante antes de ter caso de uso é exatamente o Long Shot que
  ProDeNov 3.1.6 proíbe.

**Gatilho de reavaliação:** quando C7 estiver verde **e** P50 (representação)
precisar de estrutura para gerar texto. Antes disso, não escolher variante.

**Sonda candidata:** `P_W1` — dado um conjunto de 20 palavras com
lemma/raiz conhecidas, construir tree e responder 10 queries
(e.g., "palavras cuja raiz é X"). Comparar com dict plano. Só vale se tree
ganhar em alguma métrica mensurável (lookup de raiz, iteração por prefixo).

---

## Relação entre as três — ordenação sugerida

| Direção | Custo de integração | Ganho no curto prazo | Prioridade |
|---|---|---|---|
| **Backward chaining** | alto (Goal Manager novo) | alto (eficiência + explicação negativa) | **1º** |
| **Combinatory tree** | médio (informa P30) | médio (universalidade de rewrite) | 2º |
| **Word tree** | alto (corpus, variante a escolher) | baixo | 3º |

A ordem é **estimativa**. Deve ser reavaliada após C7 com dados reais
de custo de forward. Não é decreto.

---

## Como este arquivo se mantém honesto

Cada entrada tem **gatilho objetivo**. Se o gatilho nunca dispara, a direção
continua deferida — morre por desnecessária, não por esquecimento.
Se o gatilho dispara:
1. A entrada vira uma PoC em `poc/`;
2. A entrada migra deste arquivo para `poc_notes.md` com status `in_progress`;
3. Se a PoC falha, `poc_notes.md` registra o "porquê falhou" e a entrada
   volta para cá com gatilho refinado.

A regra é a mesma de toda PoC: **nada entra no sistema principal sem
sonda que responda pergunta binária.**

---

## Negação explícita (P22 candidata)

**Gatilho:** P30 (rewrite) precisar expressar proibição com prova positiva.
**Diferença de P21:** P21 é NAF (procedural); P22 é negação declarativa
com fatos `(X, ¬r, Y)` e semântica de contradição.
**Custo:** alto (modelo de fatos estendido, resolution de X r Y ∧ X ¬r Y).
**Bloqueante até então:** NAF cobre P21 e 90% de casos práticos.

---

## Doctor de producao (pre-flight, semantic checks)

**Estado atual (PoC):** `_doctor.py` implementa diagnostico estrutural,
fix de `.bat` e pre-flight. Cobre 7 PoCs, ~150 LOC.

**Estado futuro (producao):** quando o sistema tiver dezenas de modulos,
o doctor precisa cobrir:

- **Coerencia semantica** entre modulos: contrato C1 declarado bate com
  o que o modulo importa?
- **Compatibilidade de fatos**: `Fact` de P00 e compativel com `TripleFact`
  de P20? Ou sao incompatíveis (e por isso nao devem coexistir em producao)?
- **Detectores de regressao**: se uma PoC antiga passa mas um novo PR
  muda seu output, alertar antes do merge.
- **Integridade de artefatos**: `expected.txt` versionado bate com o
  output atual? Se nao, aviso antes de rodar.
- **Pre-flight de deploy**: o que precisa estar verde para promover.

**Gatilho:** quando o projeto passar de ~20 PoCs ou quando o primeiro
modulo for promovido para `src/`. Antes disso, `_doctor.py` e suficiente.

**Nao confundir:** o doctor NAO e o `pytest`. `pytest` testa comportamento;
doctor testa **estrutura do laboratorio**. Um PoC pode ter 100% pytest
verde e doctor vermelho (arquivos trocados), ou vice-versa (engine errado
mas .bat correto). Sao checagens ortogonais.
