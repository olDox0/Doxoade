-- doxoade/commands/lite_xl_systems/template/00_03_tokenizer_shield.lua
--[[
  💉 DOXOADE SYNTAX VACCINE & TOKENIZER ACTIVE SHIELD (V2.3 Resiliente)
  Objetivo:
  1. Purga segura de patterns corrompidos (Syntax Vaccine sem quebra de índices).
  2. Short-circuit para arquivos binários (Zero Nil/Crash em Bytecode \x1bLua e \0).
  3. Suporte universal a estados de Tokenizer (table, number e nil).
  4. Lexer Semântico O(N) de Alta Disponibilidade para alimentar o Autocomplete.
  5. Auto-bootstrap de user_settings.lua sem risco de sobrescrita destrutiva.
]]
local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)
local user_dir = USERDIR or "."
local sep = PATHSEP or "/"

-- =============================================================================
-- 1. TELEMETRIA E CONTROLE DE ESTADO
-- =============================================================================
local stats = {
  vaccinated = 0,
  neutralized_entries = 0,
  syntaxes_cleaned = 0,
  patched_add = false,
  tokenizer_shield_active = false,
  binary_bypasses = 0,
  semantic_fallbacks = 0,
}
rawset(_G, "_DOXOADE_SYNTAX_VACCINE", stats)

local function log_vaccine(msg)
  if core and core.log then
    core.log("💉 [SYNTAX SHIELD] " .. msg)
  end
end

-- =============================================================================
-- 2. VACINA DE DADOS EM SINTAXES (Preservação Estrita de Índices)
-- =============================================================================
local _vaccinated = setmetatable({}, { __mode = "k" })

local function entry_is_valid(p)
  if type(p) ~= "table" then return false end
  local pat = p.pattern
  if pat == nil then return false end
  if type(pat) == "string" then return true end
  if type(pat) == "table" then
    if type(pat[1]) ~= "string" then return false end
    if type(pat[2]) ~= "string" then return false end
    return true
  end
  return false
end

local function vaccinate_syntax(syn, origin)
  if not syn or type(syn) ~= "table" then return end
  if _vaccinated[syn] then return end
  _vaccinated[syn] = true

  if type(syn.patterns) ~= "table" then return end

  local neutralized = 0
  for idx, p in ipairs(syn.patterns) do
    if not entry_is_valid(p) then
      -- Substitui por no-op seguro para manter o mapeamento de índices do tokenizer intacto
      syn.patterns[idx] = { pattern = "$^", type = "normal" }
      neutralized = neutralized + 1
    end
  end

  stats.vaccinated = stats.vaccinated + 1
  if neutralized > 0 then
    stats.neutralized_entries = stats.neutralized_entries + neutralized
    stats.syntaxes_cleaned = stats.syntaxes_cleaned + 1
  end
end

local syntax_ok, syntax_mod = pcall(require, "core.syntax")
if not syntax_ok or type(syntax_mod) ~= "table" then
  syntax_mod = rawget(_G, "syntax")
end

if syntax_mod and type(syntax_mod) == "table" then
  local items = syntax_mod.items or {}
  for _, syn in ipairs(items) do
    pcall(vaccinate_syntax, syn, "boot")
  end

  if type(syntax_mod.add) == "function" and not stats.patched_add then
    local original_add = syntax_mod.add
    syntax_mod.add = function(syn, ...)
      local r1, r2, r3 = original_add(syn, ...)
      pcall(vaccinate_syntax, syn, "syntax.add")
      return r1, r2, r3
    end
    stats.patched_add = true
  end
end

-- =============================================================================
-- 3. LEXER SEMÂNTICO DE CONTINGÊNCIA (Alimentador O(N) do Autocomplete)
-- =============================================================================
local function safe_lex_semantic_line(text, symbols)
  if not text or text == "" then
    return { "normal", "" }
  end
  local res = {}
  local i = 1
  local len = #text
  while i <= len do
    local s, e = text:find("[%a_][%w_]*", i)
    if not s then
      table.insert(res, "normal")
      table.insert(res, text:sub(i))
      break
    end
    if s > i then
      table.insert(res, "normal")
      table.insert(res, text:sub(i, s - 1))
    end
    local word = text:sub(s, e)
    local ttype = (symbols and symbols[word]) or "symbol"
    table.insert(res, ttype)
    table.insert(res, word)
    i = e + 1
  end
  return res
end

-- =============================================================================
-- 4. ESCUDO DE CONTRATO DO TOKENIZER + SHORT-CIRCUIT BINÁRIO
-- =============================================================================
local tokenizer_ok, tokenizer = pcall(require, "core.tokenizer")
if not tokenizer_ok or type(tokenizer) ~= "table" then
  tokenizer = rawget(_G, "tokenizer")
end

if tokenizer and type(tokenizer.tokenize) == "function" and not rawget(_G, "_DOXOADE_TOKENIZER_PATCHED") then
  rawset(_G, "_DOXOADE_TOKENIZER_PATCHED", true)
  local original_tokenize = tokenizer.tokenize
  local last_rescue_log = 0

  local fallback_syntax = {
    name = "Plain Text Fallback",
    patterns = {},
    symbols = {}
  }

  tokenizer.tokenize = function(incoming_syntax, text, state)
    -- Invariante 1: O texto nunca pode ser nulo
    if text == nil then
      return { "normal", "" }, nil
    elseif type(text) ~= "string" then
      text = tostring(text)
    end

    -- Invariante 2: Short-circuit para arquivos binários / bytecodes
    if text:find("%z") or text:find("^\x1bLua") then
      stats.binary_bypasses = stats.binary_bypasses + 1
      return { "normal", text }, nil
    end

    -- Invariante 3: Sintaxe íntegra
    local syn = incoming_syntax
    if not syn or type(syn) ~= "table" or type(syn.patterns) ~= "table" then
      syn = (syntax_mod and syntax_mod.plain_text_syntax) or fallback_syntax
    end

    -- Execução supervisionada (aceita table, number ou nil como state válido)
    local ok, res, next_state = pcall(original_tokenize, syn, text, state)
    if ok and type(res) == "table" then
      return res, next_state
    end

    -- RECUPERAÇÃO SEMÂNTICA (Preserva símbolos para o Autocomplete)
    stats.semantic_fallbacks = stats.semantic_fallbacks + 1
    local now = os.clock()
    if now - last_rescue_log >= 5.0 then
      last_rescue_log = now
      log_vaccine("⚠ Tokenizer acionou Lexer Semântico O(N) (Autocomplete preservado).")
    end

    local semantic_tokens = safe_lex_semantic_line(text, syn.symbols)
    return semantic_tokens, nil
  end

  stats.tokenizer_shield_active = true
  log_vaccine("🛡️ Tokenizer Active Shield V2.3 ativo (Contrato Universal preservado).")
end

-- =============================================================================
-- 5. BINARY DOC GUARD (Preserva doc.highlighter intacto)
-- =============================================================================
if core and type(core.open_doc) == "function" and not rawget(_G, "_DOXOADE_OPEN_DOC_PATCHED") then
  rawset(_G, "_DOXOADE_OPEN_DOC_PATCHED", true)
  local original_open_doc = core.open_doc

  core.open_doc = function(filename)
    local doc = original_open_doc(filename)
    if doc and doc.lines and #doc.lines > 0 then
      local first_line = doc.lines[1] or ""
      if first_line:find("^\x1bLua") or first_line:find("%z") then
        local ptext = (syntax_mod and syntax_mod.plain_text_syntax) or {
          name = "Plain Text",
          patterns = {},
          symbols = {}
        }
        doc.syntax = ptext
        if doc.highlighter and type(doc.highlighter.reset) == "function" then
          doc.highlighter:reset()
        end
        if core.log then
          core.log(string.format("🛡️ [BINARY GUARD] Buffer '%s' associado à sintaxe Plain Text.",
            tostring(filename or "buffer")))
        end
      end
    end
    return doc
  end
end

-- =============================================================================
-- 6. AUTO-BOOTSTRAP SEGURO DE USER_SETTINGS.LUA & LIMPEZA FORENSE
-- =============================================================================
pcall(function()
  local settings_path = user_dir .. sep .. "user_settings.lua"
  local needs_init = true

  -- Validação robusta via compilação real (loadfile)
  local ok_load, chunk = pcall(loadfile, settings_path)
  if ok_load and type(chunk) == "function" then
    local run_ok, val = pcall(chunk)
    if run_ok and type(val) == "table" then
      needs_init = false
    end
  end

  -- Se o arquivo já existe no disco, nunca sobrescreva cegamente
  if needs_init then
    local f_check = io.open(settings_path, "r")
    if f_check then
      local content = f_check:read("*a") or ""
      f_check:close()
      if content:find("return") then
        needs_init = false
      end
    end
  end

  if needs_init then
    local f_out = io.open(settings_path, "w")
    if f_out then
      f_out:write('return {\n  ["config"] = {\n    ["fps"] = 60,\n    ["transitions"] = false\n  }\n}\n')
      f_out:flush()
      f_out:close()
      log_vaccine("📄 user_settings.lua inicializado com retorno explícito de tabela.")
    end
  end

  -- Limpeza e arquivamento forense do error.txt
  local err_path = user_dir .. sep .. "error.txt"
  local f_err = io.open(err_path, "r")
  if f_err then
    local content = f_err:read("*a") or ""
    f_err:close()
    if content ~= "" and not content:find("%[DOXOADE PROBE%]") then
      local arc_dir = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics"
      if system and system.mkdir then pcall(system.mkdir, arc_dir) end
      local out = io.open(arc_dir .. sep .. "error_" .. os.date("%Y%m%d_%H%M%S") .. ".txt", "w")
      if out then
        out:write(content)
        out:close()
      end
      os.remove(err_path)
    end
  end
end)
