# 📜 BLITZPLAN — MK ADVANCED NEXUS
**Motor Alvo:** `doxoade/commands/mk_systems/` (`mk_commands.py`, `mk_engine.py`, `mk_utils.py`)  
**Protocolo de Conformidade:** ProDeNov 1.2.1 (Planos A, B e C | W5 | Limite < 50KB por arquivo)  
**Data:** 09/09/2026 | **Autor:** Nexus Core / Hefesto & Zeus

---

## 1. Contextualização e Objetivos (W5 / 5 Perguntas)

* **O quê:** Evolução substancial do motor `doxoade mk` para suportar:
  1. **Tree Parser Inteligente:** Compreensão nativa de saídas formatadas com caracteres de árvore (`├──`, `└──`, `│`, `───`, etc.), com eliminação automática de ruídos, comentários inline (`# ...`) e anotações de tamanho (`(~10KB)`).
  2. **Content Engine Multilinha `[[ ... ]]`:** Nova sintaxe de injeção de código `nome[[ <código multilinha> ]].ext` permitindo embutir blocos reais de Python/Lua/C com docstrings e indentação preservada, sem escapes feios (`\n`).
  3. **Segurança ProDeNov 5.3 (Dry-Run por Padrão):** Por padrão, qualquer invocação do `mk` apenas simulará a forja no terminal. A gravação real em disco exigirá a flag `--apply` (`-a`).
  4. **Targeted Tree Explorer (`mk -t [PASTA]`):** Expansão da flag `-t / --tree` para aceitar um caminho arbitrário (ex: `doxoade mk -t doxoade/commands/check_systems/`).
* **Quem:** Desenvolvedores e agentes forjando topologias complexas e rascunhando arquiteturas rapidamente.
* **Onde:** `doxoade/commands/mk_systems/` (`mk_commands.py`, `mk_engine.py`, `mk_utils.py`).
* **Quando:** Durante a concepção de novos silos, criação rápida de módulos na IDE e inspeção estrutural de pastas.
* **Por quê:** Atualmente, o `mk` exige arquivos de arquitetura rígidos (`mk_arch.txt`) ou sintaxe de chaves limitadas (`folder/{a,b}`), forçando a criação imediata em disco sem prévia visual e sem capacidade de rascunhar código multilinha direto no diagrama.
* **Origem & Consequências:** Demandas frequentes de colar diagramas de árvore extraídos de documentações (Markdown) ou do próprio terminal e esperar que o `mk` gere a estrutura fielmente, sem criar pastas com nomes de galhos (`├──`).

---

## 2. Taxonomia das 4 Novas Capacidades

### 2.1. Tree Glyph Stripper & Hierarchy Inferer
O motor reconhecerá e normalizará os seguintes padrões:
```text
doxoade/
├── tools/
│   └── editor_dispatch.py                     # [NOVO] Despachante universal (~10KB)
├── commands/
│   ├── mk_systems/
│   │   ├── mk_commands.py                     # Delegação para EditorDispatcher (~4KB)
│   │   └── mk_utils.py                        # Aliasing e deprecation wrapper (~5KB)
└── rescue.py                                  # Autópsia Sotéria com salto Doxly (~28KB)
```
* **Processamento:**
  * Calcula a profundidade hierárquica baseando-se no offset do nome do nó (ignorando `│   `, `├── `, `└── `, `├───`, etc.).
  * Elimina comentários inline (`# ...`) e anotações entre parênteses/colchetes (`(~10KB)`).
  * Reconhece pastas pela barra final (`tools/`) ou pela ausência de extensão (`is_directory`).

### 2.2. Multilinha em Bloco `nome[[ ... ]].ext`
Permite definir o esqueleto de código completo diretamente na árvore:
```text
doxoade/commands/
    exemplo/
        cmd_exemplo[[
# esse exemplo é muito bom, porqu traz um dinamismo muito grande
""" texto de exemplo """

def exemple_funcion():
    ...
]].py
        exemplo_engine[[
# outro exemplo de arquivo
class Engine:
    pass
]].py
```
* **Processamento:**
  * State Machine com estados: `READING_TREE` e `INSIDE_MULTILINE_BLOCK`.
  * Preserva linhas em branco, quebras de linha e indentação interna do bloco.
  * O nome final do arquivo é resolvido unindo o prefixo e o sufixo: `cmd_exemplo` + `.py` ➔ `cmd_exemplo.py`.

### 2.3. Salvaguarda Industrial (DRY-RUN por Padrão)
* **Comportamento Padrão (`doxoade mk ...`):**
  * Não toca o disco.
  * Exibe no terminal a árvore planejada formatada com `doxcolors`:
    * `[PLANNED (NOVO)]`: Arquivos que serão criados.
    * `[MANTIDO]`: Arquivos que já existem e não serão sobrescritos.
    * `[DIRETÓRIO]`: Pastas que serão criadas.
  * Emite aviso: `💡 Modo DRY-RUN (simulação). Use --apply / -a para criar no disco.`
* **Comportamento com `--apply` / `-a`:**
  * Grava no disco e dispara `--up` (Doxly) se solicitado.

### 2.4. Targeted Tree Rendering (`mk -t [CAMINHO]`)
* Invocação flexível:
  * `doxoade mk -t` ➔ Renderiza a árvore a partir do diretório atual (`.`).
  * `doxoade mk -t doxoade/commands/check_systems/` ➔ Renderiza a árvore focada especificamente nessa pasta.

---

## 3. Planos de Execução (Regra 1.2.1 ProDeNov)

### 🔹 Plano A (Principal — Parser Hierárquico State-Machine + Clean Lexer)
1. **Parser de State Machine em `mk_utils.py`:**
   * Uma função geradora `parse_topology_stream(lines_iterable)` que processa linhas tanto de arquivos (`-a`, `-l`) quanto de argumentos da CLI.
   * Suporte nativo ao estado `INSIDE_MULTILINE_BLOCK`.
2. **Normalizador de Galhos de Árvore (`clean_tree_glyphs`):**
   * Regex abrangente para caracteres Unicode de árvore: `r'^(?:[\s│|]*[├└\+\\][─\-]{1,4}\s*)*'`.
   * Determinação do nível de indentação real pelo recuo da coluna onde o nome do arquivo começa.
3. **Despachante de Ação em `mk_engine.py`:**
   * Flag `apply: bool = False`. Em modo simulação, apenas computa a lista de `affected_files` e gera o relatório no terminal sem chamar `os.makedirs` ou `open(..., 'w')`.

### 🔹 Plano B (Fallback — Parser Clássico Indent-Based)
* Se uma linha não contiver caracteres de árvore nem blocos `[[`, o sistema chaveia automaticamente para a sintaxe clássica do Doxoade (`clean_path_and_content` e expansão de chaves `{a,b}`).

### 🔹 Plano C (Contingência & Exportação)
* Se a interpretação de uma árvore colada tiver ambiguidades de recuo, o `mk` exibe a prévia no terminal em modo dry-run alertando os níveis de indentação calculados antes de qualquer escrita.

---

## 4. Mapeamento de Arquivos e Limites (< 50KB)

```
doxoade/commands/mk_systems/
├── mk_commands.py         # Opções Click (--apply, -t flexível, help atualizado) (~8KB)
├── mk_engine.py           # Orquestrador com flag apply e state machine (~26KB)
└── mk_utils.py            # Lexer de árvore Unicode, stripper e parser multilinha [[ (~16KB)
```
*Todos os arquivos permanecem bem abaixo do teto de 50KB.*

---

## 5. Especificação Técnica da Engenharia

### 5.1. Normalizador de Linhas de Árvore (`mk_utils.py`)

```python
RE_TREE_GLYPHS = re.compile(r'^(?:[\s│|]*[├└\+\\][─\-]{1,4}\s*)+')
RE_INLINE_COMMENT = re.compile(r'\s+#.*$')
RE_SIZE_ANNOTATION = re.compile(r'\s*\(\s*~?\s*\d+\s*(?:KB|MB|B|linhas)?\s*\)', re.IGNORECASE)

def clean_tree_node_line(raw_line: str) -> Tuple[int, str]:
    """
    Remove caracteres de árvore (├──, └──, │), comentários inline e anotações,
    calculando o nível de indentação real da linha.
    """
    # Preserva indentação inicial para cálculo de coluna
    expanded = raw_line.replace('\t', '    ')
    
    # Encontra onde começa o nome real após os glifos de árvore
    glyph_match = RE_TREE_GLYPHS.search(expanded.lstrip())
    if glyph_match:
        # Posição absoluta onde o nome começa
        leading_spaces = len(expanded) - len(expanded.lstrip())
        name_col = leading_spaces + glyph_match.end()
        content = expanded[name_col:]
        indent_level = name_col
    else:
        indent_level = len(expanded) - len(expanded.lstrip())
        content = expanded.lstrip()

    # Remove comentários inline (# ...) e anotações (~10KB)
    content = RE_INLINE_COMMENT.sub('', content)
    content = RE_SIZE_ANNOTATION.sub('', content)
    content = content.strip()

    return indent_level, content
```

### 5.2. State Machine para `[[ ... ]]` Multilinha (`mk_engine.py` / `mk_utils.py`)

```python
def parse_topology_stream(lines: Iterable[str]) -> Iterator[Tuple[int, str, str]]:
    """
    Iterador inteligente que processa árvores, comentários e blocos [[ ... ]].
    Retorna tuplas (indent_level, filename, file_content).
    """
    in_block = False
    block_indent = 0
    block_prefix = ""
    block_content_lines = []

    for line in lines:
        raw = line.rstrip('\r\n')
        
        if in_block:
            # Verifica se o bloco fecha nesta linha: ]].ext ou ]]
            if "]]" in raw:
                idx = raw.find("]]")
                inside_part = raw[:idx]
                suffix = raw[idx + 2:].strip()
                if inside_part:
                    block_content_lines.append(inside_part)
                
                full_name = f"{block_prefix}{suffix}".strip()
                full_content = "\n".join(block_content_lines) + "\n"
                yield (block_indent, full_name, full_content)
                
                in_block = False
                block_content_lines = []
            else:
                block_content_lines.append(raw)
            continue

        indent, clean = clean_tree_node_line(raw)
        if not clean or clean.startswith('#'):
            continue

        # Verifica abertura de bloco [[
        if "[[" in clean:
            prefix, rest = clean.split("[[", 1)
            if "]]" in rest:
                # Bloco em linha única: nome[[conteudo]].ext
                inside_part, suffix = rest.split("]]", 1)
                full_name = f"{prefix.strip()}{suffix.strip()}"
                yield (indent, full_name, inside_part.replace('\\n', '\n'))
            else:
                # Início de bloco multilinha
                in_block = True
                block_indent = indent
                block_prefix = prefix.strip()
                block_content_lines = [rest] if rest.strip() else []
        else:
            # Linha padrão (arquivo ou pasta, ou [...] clássico)
            path, content = clean_path_and_content(clean)
            for expanded in expand_braces(path):
                yield (indent, expanded, content)
```

### 5.3. Click CLI com Dry-Run por Padrão e `-t [CAMINHO]` Flexível

```python
# mk_commands.py
def register_mk_options(f):
    f = click.option('--apply', '-a', is_flag=True, help='Efetiva a criação no disco (sai do modo DRY-RUN).')(f)
    f = click.option('--tree', '-t', 'tree_path', is_flag=False, flag_value='.', default=None,
                     help='Renderiza a árvore topológica (opcionalmente de uma pasta específica).')(f)
    f = click.option('--architecture', '-arch', type=click.Path(exists=True), help='Cria estrutura baseada em arquivo.')(f)
    f = click.option('--learning', '-l', type=click.Path(exists=True), help='Cria estrutura baseada em aprendizado.')(f)
    f = click.option('--up', is_flag=True, help='Abre os arquivos criados/modificados no Doxly (Lite XL).')(f)
    f = click.option('--gitignore', '-gi', is_flag=True, help='Forja ou atualiza o .gitignore soberano na raiz.')(f)
    return f
```

---

## 6. Tasklist & Checklist de Implementação

- [ ] **Fase 1: Lexer de Árvore e Parser Multilinha (`mk_utils.py`)**
  - [ ] Implementar `clean_tree_node_line` (stripper de caracteres Unicode `├──`, `└──`, `│`, `#`, etc.).
  - [ ] Implementar o parser de streaming com suporte a blocos `[[ ... ]]`.
  - [ ] Testar unitariamente com diagramas colados da documentação.

- [ ] **Fase 2: Motor de Topologia com Dry-Run (`mk_engine.py`)**
  - [ ] Adicionar suporte a `apply: bool = False`.
  - [ ] Integrar `parse_topology_stream` no `parse_architecture_file` e no processamento de argumentos.
  - [ ] Renderizar tabela com cores no terminal: `[PLANNED (NOVO)]`, `[MANTIDO]`, `[DIRETÓRIO]`.

- [ ] **Fase 3: Opções CLI Flexíveis (`mk_commands.py`)**
  - [ ] Configurar `--apply / -a` para sair do modo Dry-Run.
  - [ ] Configurar `-t / --tree [PASTA]` aceitando argumento opcional.
  - [ ] Conectar `--up` com `EditorDispatcher` (já homologado).

- [ ] **Fase 4: Validação Prática e Homologação**
  - [ ] Testar `doxoade mk -t doxoade/commands/check_systems/`.
  - [ ] Testar dry-run com a árvore de exemplo fornecida pelo usuário.
  - [ ] Testar criação real com `--apply` e sintaxe `cmd_exemplo[[ ... ]].py`.
  - [ ] Rodar `doxoade regret` para garantir conformidade contínua.

---

**Plano delineado segundo o ProDeNov.**  
Podemos iniciar a **Fase 1** (Lexer de Árvore Unicode e Parser `[[ ... ]]`)?
