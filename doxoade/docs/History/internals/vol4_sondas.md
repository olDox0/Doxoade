# Doxoade Internals - Vol. 4: Sondas e Diagnósticos

**Versão do Documento:** 1.0 (Gênese V14)
**Data:** 01/12/2025
**Pasta:** `doxoade/probes/`

## 1. Filosofia de Isolamento (Sandbox)

Como uma ferramenta de engenharia, o Doxoade frequentemente precisa analisar código que está quebrado, malicioso ou instável. Se o Doxoade importasse esses módulos diretamente em seu processo principal (`cli.py`), um `SyntaxError` ou um `segfault` no código do usuário derrubaria a própria ferramenta.

**Solução:** Arquitetura de Sondas.
Cada análise crítica roda em um **subprocesso independente** Python. O Doxoade invoca a sonda, passa argumentos (via CLI ou STDIN/JSON) e lê o resultado (via STDOUT/JSON ou STDERR).

Se a sonda travar, o Doxoade apenas reporta o erro e continua analisando os outros arquivos.

---

## 2. As Sondas Estáticas

Essas sondas analisam o código sem executá-lo.

### A. Syntax Probe (`syntax_probe.py`)
*   **Função:** O porteiro "Fail-Fast".
*   **Mecanismo:** Tenta apenas fazer o parse do arquivo para uma AST (`ast.parse(content)`).
*   **Por que existe?** Se o arquivo tem erro de sintaxe, ferramentas como Pyflakes ou Hunter vão falhar catastroficamente. O Syntax Probe protege as etapas subsequentes.

### B. Static Probe (`static_probe.py`)
*   **Função:** Linter clássico.
*   **Tecnologia:** Wrapper sobre a biblioteca `pyflakes`.
*   **Inovação:** Em vez de imprimir texto para humanos, ele formata a saída de modo que o `check.py` possa categorizar erros (ex: distinguir `imported but unused` [DEADCODE] de `undefined name` [RISCO]).

### C. Hunter Probe (`hunter_probe.py`)
*   **Função:** Análise Semântica de Risco e Segurança.
*   **Mecanismo:** Percorre a AST procurando padrões que são sintaticamente válidos, mas perigosos.
*   **Detecta:**
    *   `eval()`, `exec()` (Risco de Injeção).
    *   `def foo(l=[])` (Argumentos padrão mutáveis).
    *   `except:` (Captura cega de exceções).
    *   `== None` (Estilo, prefira `is None`).

### D. Clone Probe (`clone_probe.py`) - *Novo na V14*
*   **Função:** Detecção de duplicatas (DRY - Don't Repeat Yourself).
*   **Desafio:** Código copiado raramente é idêntico byte-a-byte (nomes de variáveis mudam).
*   **Solução (Structural Normalizer):**
    1.  Parseia a AST.
    2.  Remove docstrings, comentários e anotações de tipo.
    3.  **Anonimização:** Renomeia todas as variáveis para `var_0`, `var_1` e argumentos para `arg_0`.
    4.  Gera um hash MD5 da estrutura resultante.
*   **Resultado:** `def soma(a, b): return a+b` e `def add(x, y): return x+y` geram o mesmo hash e são marcados como clones.

---

## 3. As Sondas Dinâmicas

Essas sondas executam o código do usuário em um ambiente controlado.

### A. Flow Runner (`flow_runner.py`)
*   **Função:** O visualizador "Matrix" (`run --flow`).
*   **Tecnologia:** `sys.settrace()`.
*   **Mecanismo:** Intercepta cada linha de código executada pelo interpretador Python.
*   **Recursos:**
    *   **Time Travel:** Calcula o tempo gasto em cada linha.
    *   **Var Watch:** Compara o dicionário `locals()` antes e depois da linha para mostrar o que mudou (ex: `x: 5 -> 10`).
    *   **Filtro de Ruído:** Ignora arquivos internos do Python (`<frozen>`, `threading`) para focar no código do usuário.
*   **Integração Gênese:** Se o script do usuário quebra (exceção não tratada), o Flow Runner captura o *traceback*, formata e passa para o `doxoade` registrar o incidente, fechando o ciclo de aprendizado de Runtime.

### B. Import Probe (`import_probe.py`)
*   **Função:** Validação de ambiente.
*   **Mecanismo:** Tenta importar módulos listados no código dentro do ambiente virtual (`venv`) alvo.
*   **Uso:** Verifica se o `requirements.txt` está sincronizado com o código real.

---

## 4. Protocolo de Comunicação

Para garantir robustez, as sondas seguem um protocolo estrito de I/O:

1.  **Entrada:** Argumentos via linha de comando (para 1 arquivo) ou JSON via STDIN (para lote de arquivos, evitando limites de caracteres do Shell).
2.  **Saída Sucesso:** JSON estruturado no `STDOUT` (ex: lista de dicionários de erros).
3.  **Saída Debug/Erro:** Texto livre no `STDERR`. O Doxoade captura isso se a flag `--debug` estiver ativa (como vimos no debug do `clone_probe`).
4.  **Exit Code:**
    *   0: Execução da sonda com sucesso (mesmo que tenha achado erros no código).
    *   != 0: Falha interna da sonda ou erro de sintaxe fatal (no caso do syntax probe).

---