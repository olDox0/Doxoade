-- doxoade/commands/lite_xl_systems/template/python_docstring_override.lua
--[[
  🐍 DOXOADE PYTHON SYNTAX & DOCSTRING OVERRIDE (V3.0 Sovereign)
  - Docstrings (""" ... """ e ''' ... ''') em verde esmeralda exclusivo (#22c55e).
  - Variáveis e identificadores em branco suave (#e2e8f0), eliminando o "mar de verde".
  - Palavras-chave (def, class, if, return, async, await) em laranja (#f97316).
  - Tipos e literais (int, str, Path, None, True, False) em dourado (#facc15).
  - Funções e métodos em ciano (#38bdf8); strings normais em salmão/rosa (#f472b6).
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local style = require "core.style"
local syntax = require "core.syntax"

-- =============================================================================
-- 🎨 PALETA CANÔNICA DE CORES
-- =============================================================================
local COLOR_DOCSTRING  = { 34, 197, 94, 255 }   -- #22c55e (Verde Esmeralda)
local COLOR_DOC_DELIM  = { 22, 163, 74, 255 }   -- #16a34a (Verde Escuro)
local COLOR_KEYWORD    = { 249, 115, 22, 255 }  -- #f97316 (Laranja Coral)
local COLOR_TYPE       = { 250, 204, 21, 255 }  -- #facc15 (Dourado/Amarelo)
local COLOR_FUNCTION   = { 56, 189, 248, 255 }  -- #38bdf8 (Ciano Claro)
local COLOR_VARIABLE   = { 226, 232, 240, 255 } -- #e2e8f0 (Branco Gelo Suave)
local COLOR_STRING     = { 244, 114, 182, 255 } -- #f472b6 (Salmão/Rosa)
local COLOR_COMMENT    = { 113, 113, 122, 255 } -- #71717a (Cinza Fosco)
local COLOR_NUMBER     = { 192, 132, 252, 255 } -- #c084fc (Roxo Lavanda)

style.syntax = style.syntax or {}
style.syntax["string.docstring"]           = COLOR_DOCSTRING
style.syntax["string.docstring.delimiter"] = COLOR_DOC_DELIM
style.syntax["symbol"]                     = COLOR_VARIABLE  -- 🎯 Restaura variáveis em branco suave
style.syntax["keyword"]                    = COLOR_KEYWORD
style.syntax["keyword2"]                   = COLOR_TYPE
style.syntax["function"]                   = COLOR_FUNCTION
style.syntax["string"]                     = COLOR_STRING
style.syntax["comment"]                    = COLOR_COMMENT
style.syntax["number"]                     = COLOR_NUMBER

-- =============================================================================
-- 🔧 GRAMÁTICA PRECISA DO PYTHON
-- =============================================================================
local function override_python_syntax()
  local python_syn = nil
  if syntax and syntax.items then
    for _, syn in ipairs(syntax.items) do
      if syn.name == "Python" or (syn.files and syn.files[1] == "%.py$") then
        python_syn = syn
        break
      end
    end
  end

  if not python_syn then return end
  if python_syn._doxoade_syntax_v3 then return end
  python_syn._doxoade_syntax_v3 = true

  -- Substitui os patterns pela gramática balanceada
  python_syn.patterns = {
    -- 1. Comentários (cinza)
    { pattern = "#.*", type = "comment" },

    -- 2. Docstrings Triplas (Verde Esmeralda exclusivo)
    { pattern = { '"""', '"""', '\\' }, type = "string.docstring" },
    { pattern = { "'''", "'''", '\\' }, type = "string.docstring" },

    -- 3. Definição de Classes e Funções (Keyword + Nome destacado)
    { pattern = "def%s+()[%a_][%w_]*",   type = { "keyword", "function" } },
    { pattern = "class%s+()[%a_][%w_]*", type = { "keyword", "keyword2" } },

    -- 4. Decoradores (@decorador)
    { pattern = "@[%a_][%w_.]*", type = "operator" },

    -- 5. Strings com prefixos (f"", r"", b"", u"") e strings comuns (Rosa/Salmão)
    { pattern = { '[fFrRbBuU]?"""', '"""', '\\' }, type = "string" },
    { pattern = { "[fFrRbBuU]?'''", "'''", '\\' }, type = "string" },
    { pattern = { '[fFrRbBuU]?"', '"', '\\' },     type = "string" },
    { pattern = { "[fFrRbBuU]?'", "'", '\\' },     type = "string" },

    -- 6. Números
    { pattern = "0x[%da-fA-F]+",   type = "number" },
    { pattern = "0b[01]+",         type = "number" },
    { pattern = "0o[0-7]+",        type = "number" },
    { pattern = "-?%d+[%d%.eE]*",  type = "number" },
    { pattern = "-?%.?%d+",        type = "number" },

    -- 7. Operadores e Pontuação
    { pattern = "%->",                   type = "operator" },
    { pattern = "[%+%-=/%*%^%%<>!~|&:]", type = "operator" },

    -- 8. Chamadas de Função (Ciano)
    { pattern = "[%a_][%w_]*%f[(]", type = "function" },

    -- 9. Variáveis e Identificadores normais (Branco Suave / Symbol)
    { pattern = "[%a_][%w_]*", type = "symbol" },
  }

  -- Tabela de Símbolos Reservados (Garante def, class e builtins corretos)
  python_syn.symbols = python_syn.symbols or {}
  
  -- Palavras-chave principais (Laranja)
  local keywords = {
    "def", "class", "return", "yield", "if", "elif", "else", "while", "for",
    "in", "try", "except", "finally", "with", "as", "import", "from", "pass",
    "break", "continue", "raise", "assert", "lambda", "global", "nonlocal",
    "async", "await", "del", "and", "or", "not", "is"
  }
  for _, kw in ipairs(keywords) do
    python_syn.symbols[kw] = "keyword"
  end

  -- Literais e Builtins comuns (Dourado/Amarelo)
  local builtins = {
    "True", "False", "None", "self", "cls",
    "int", "str", "bool", "float", "list", "dict", "set", "tuple", "bytes",
    "Path", "Optional", "Union", "List", "Dict", "Tuple", "Any", "Callable"
  }
  for _, bi in ipairs(builtins) do
    python_syn.symbols[bi] = "keyword2"
  end

  if core.log then
    core.log("🐍 [DOXOADE] Gramática Python calibrada com sucesso!")
  end
end

-- Ativação assíncrona após o boot
core.add_thread(function()
  coroutine.yield(0.3)
  pcall(override_python_syntax)
end)

-- Hook para carregamentos futuros do syntax
if syntax and syntax.add then
  local original_add = syntax.add
  syntax.add = function(syn, ...)
    local result = original_add(syn, ...)
    if syn.name == "Python" or (syn.files and syn.files[1] == "%.py$") then
      core.add_thread(function()
        coroutine.yield(0.1)
        pcall(override_python_syntax)
      end)
    end
    return result
  end
end
