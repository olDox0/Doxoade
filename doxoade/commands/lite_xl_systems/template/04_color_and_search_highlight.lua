-- doxoade/commands/lite_xl_systems/template/04_color_and_search_highlight.lua
--[[
  Módulo Soberano de Destaque Visual, Cores Inline, Busca Persistente e Indentação.
  - Blindagem Ativa contra Vazamento de Sintaxe Python (Hook no syntax.add).
  - Suporte a F-Strings com aspas aninhadas e Raw Strings r"..." sem quebra.
  - Suporte a tabelas Lua de 3 ou 4 canais: { R, G, B } e { R, G, B, A } com contraste invertido.
  - Previews de cor com texto contrastado (#HEX, rgb(...), rgba(...), {r,g,b,a}).
  - Highlight persistente de texto/busca em todos os splits abertos.
  - Guias de indentação 4x4 (Python) e 2x2 (Lua) com realce do bloco ativo.
  - Marcadores de linhas modificadas na sessão (amarelo = dirty, cinza = saved).
  - Correção de desindentação para 0 espaços.
]]
local core = require "core"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local Doc = require "core.doc"
local DocView = require "core.docview"
local syntax = require "core.syntax"

-- Polyfills universais de renderização C
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

local function draw_text_safe(font, text, x, y, color)
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

-- =============================================================================
-- 🛡️ BLINDAGEM ATIVA DE SINTAXE PYTHON (HOOK NO SYNTAX.ADD)
-- =============================================================================
local function sanitize_python_syntax(syn)
  if not syn then return end
  local is_python = (syn.name == "Python") or 
                    (syn.files and type(syn.files) == "table" and syn.files[1] == "%.py$")
  if not is_python then return end

  local cleaned = {}
  for _, p in ipairs(syn.patterns or {}) do
    local is_leaky_table = false
    if type(p.pattern) == "table" then
      local start_token = tostring(p.pattern[1] or "")
      -- Expulsa qualquer delimitador multilinhas que não seja aspas triplas reais
      if not start_token:find('"""') and not start_token:find("'''") then
        is_leaky_table = true
      end
    end
    if not is_leaky_table then
      table.insert(cleaned, p)
    end
  end

  -- Padrões seguros de strings (Docstrings multilinhas + Strings atômicas de linha única)
  local safe_patterns = {
    -- 1. Aspas Triplas Legítimas (Únicas com permissão multilinhas)
    { pattern = { '"""', '"""', '\\' }, type = "string" },
    { pattern = { "'''", "'''", '\\' }, type = "string" },
    { pattern = { '[rRbBuUfF]"""', '"""', '\\' }, type = "string" },
    { pattern = { "[rRbBuUfF]'''", "'''", '\\' }, type = "string" },
    { pattern = { '[rR][fF]"""', '"""', '\\' }, type = "string" },
    { pattern = { "[rR][fF]'''", "'''", '\\' }, type = "string" },
    { pattern = { '[fF][rR]"""', '"""', '\\' }, type = "string" },
    { pattern = { "[fF][rR]'''", "'''", '\\' }, type = "string" },
    { pattern = { '[bB][rR]"""', '"""', '\\' }, type = "string" },
    { pattern = { "[bB][rR]'''", "'''", '\\' }, type = "string" },
    { pattern = { '[rR][bB]"""', '"""', '\\' }, type = "string" },
    { pattern = { "[rR][bB]'''", "'''", '\\' }, type = "string" },

    -- 2. Strings de linha única fechadas (Atômicas, nunca vazam de linha)
    { pattern = '[fFrRbBuU]?[rRbB]?"[^"\\]*"', type = "string" },
    { pattern = "[fFrRbBuU]?[rRbB]?'[^'\\]*'", type = "string" },
    { pattern = '[fFrRbBuU]?[rRbB]?"..-"', type = "string" },
    { pattern = "[fFrRbBuU]?[rRbB]?'.--'", type = "string" },
    { pattern = '[fFrRbBuU]?[rRbB]?"[^"\r\n]*"', type = "string" },
    { pattern = "[fFrRbBuU]?[rR]?'[^'\r\n]*'", type = "string" },

    -- 3. Blocker de fim de linha (Trava o vazamento caso uma aspa fique aberta)
    { pattern = '[fFrRbBuU]?[rRbB]?"[^\r\n]*$', type = "string" },
    { pattern = "[fFrRbBuU]?[rRbB]?'[^\r\n]*$", type = "string" },
  }

  local final_patterns = {}
  for _, sp in ipairs(safe_patterns) do table.insert(final_patterns, sp) end
  for _, cp in ipairs(cleaned) do table.insert(final_patterns, cp) end

  syn.patterns = final_patterns
end

-- Hook global no syntax.add para interceptar carregamentos tardios de plugins
if syntax and syntax.add then
  local original_syntax_add = syntax.add
  syntax.add = function(syn, ...)
    pcall(sanitize_python_syntax, syn)
    return original_syntax_add(syn, ...)
  end
end

-- Sanitiza imediatamente todos os syntaxes já existentes na memória
if syntax and syntax.items then
  for _, syn in ipairs(syntax.items) do
    pcall(sanitize_python_syntax, syn)
  end
end

-- =============================================================================
-- CONFIGURAÇÕES VISUAIS E CORES
-- =============================================================================
config.draw_indent_guides = config.draw_indent_guides ~= false
local INDENT_GUIDE_COLOR = { 45, 42, 48, 160 }       -- Guia inativa (Piano Black)
local INDENT_GUIDE_ACTIVE = { 76, 69, 82, 240 }      -- Guia do bloco ativo
local HIGHLIGHT_BLUE      = { 0, 108, 255, 130 }     -- Highlight azul persistente
local COLOR_DIRTY         = { 234, 179, 8, 255 }      -- Amarelo (não salvo)
local COLOR_SAVED         = { 110, 110, 120, 180 }    -- Cinza (salvo na sessão)

-- =============================================================================
-- CÁLCULO DE LUMINÂNCIA (CONTRASTE INVERTIDO AUTOMÁTICO)
-- =============================================================================
local function get_contrast_color(r, g, b)
  local lum = (0.299 * (r or 0) + 0.587 * (g or 0) + 0.114 * (b or 0))
  if lum > 135 then
    return { 15, 15, 15, 255 }    -- Fundo claro -> texto escuro
  else
    return { 250, 250, 250, 255 } -- Fundo escuro -> texto claro
  end
end

-- =============================================================================
-- RASTREAMENTO DE LINHAS DA SESSÃO (DIRTY VS SAVED)
-- =============================================================================
local original_doc_insert = Doc.insert
function Doc:insert(line, col, text)
  self.session_modified = self.session_modified or {}
  self.session_modified[line] = "dirty"
  return original_doc_insert(self, line, col, text)
end

local original_doc_remove = Doc.remove
function Doc:remove(line1, col1, line2, col2)
  self.session_modified = self.session_modified or {}
  self.session_modified[line1] = "dirty"
  return original_doc_remove(self, line1, col1, line2, col2)
end

local original_doc_save = Doc.save
function Doc:save(...)
  if self.session_modified then
    for line, state in pairs(self.session_modified) do
      if state == "dirty" then
        self.session_modified[line] = "saved"
      end
    end
  end
  return original_doc_save(self, ...)
end

local original_draw_line_gutter = DocView.draw_line_gutter
function DocView:draw_line_gutter(line_idx, x, y, width)
  local h = original_draw_line_gutter(self, line_idx, x, y, width)
  if self.doc and self.doc.session_modified and self.doc.session_modified[line_idx] then
    local state = self.doc.session_modified[line_idx]
    local marker_color = (state == "dirty") and COLOR_DIRTY or COLOR_SAVED
    draw_rect_safe(x + width + 18, y, 3, self:get_line_height(), marker_color)
  end
  return h
end

-- =============================================================================
-- BLOCKERS DE SINTAXE (EVITA VAZAMENTO DE COR EM STRINGS)
-- =============================================================================
pcall(function()
  local syntax = require "core.syntax"
  for _, syn in ipairs(syntax.items or {}) do
    if syn.name == "Python" or (syn.files and type(syn.files) == "table" and syn.files[1] == "%.py$") then
      table.insert(syn.patterns, 1, { pattern = { '[rRbBuUfF]?"""', '"""', '\\' }, type = "string" })
      table.insert(syn.patterns, 1, { pattern = { "[rRbBuUfF]?'''", "'''", '\\' }, type = "string" })
      table.insert(syn.patterns, 1, { pattern = { 'rf"""', '"""', '\\' }, type = "string" })
      table.insert(syn.patterns, 1, { pattern = { "rf'''", "'''", '\\' }, type = "string" })
      break
    end
  end
end)

-- Rastreamento de linhas modificadas não salvas
local original_doc_save = Doc.save
function Doc:save(...)
  self.modified_lines = {}
  return original_doc_save(self, ...)
end

local function get_active_highlight_query()
  local active_view = core.active_view
  if active_view and active_view.doc and active_view.doc:has_selection() then
    local l1, c1, l2, c2 = active_view.doc:get_selection(true)
    if l1 == l2 and c1 ~= c2 then
      local sel = active_view.doc:get_text(l1, c1, l2, c2)
      if sel and #sel >= 1 and #sel <= 100 and not sel:find("\n") and not sel:match("^%s+$") then
        return sel
      end
    end
  end
  if core.command_view and core.command_view.text and #core.command_view.text > 0 then
    local cv_text = core.command_view.text
    if #cv_text >= 1 and #cv_text <= 100 and not cv_text:find("\n") and not cv_text:match("^%s+$") then
      return cv_text
    end
  end
  return nil
end

local function get_col_x(view, line_text, col)
  if not line_text or col <= 1 then return 0 end
  return view:get_font():get_width(line_text:sub(1, col - 1))
end

-- =============================================================================
-- CORREÇÃO DO BUG DE DESINDENTAÇÃO (PERMITE ZERAR ESPAÇOS RESIDUAIS)
-- =============================================================================
command.add("core.docview", {
  ["doc:unindent"] = function()
    local view = core.active_view
    local doc = view and view.doc
    if not doc or not doc.get_selection then return end
    local l1, c1, l2, c2 = doc:get_selection(true)
    local indent_size = config.indent_size or 4
    if doc.filename and doc.filename:lower():find("%.lua$") then
      indent_size = 2
    end
    for line = (l1 or 1), (l2 or 1) do
      local text = doc.lines and doc.lines[line]
      if text then
        local spaces = text:match("^( +)")
        if spaces then
          local count = #spaces
          local to_remove = (count >= indent_size) and indent_size or count
          if doc.remove then
            doc:remove(line, 1, line, to_remove + 1)
          end
        end
      end
    end
  end
})

-- =============================================================================
-- FUNÇÕES AUXILIARES DE OFFSET, INDENTAÇÃO E BUSCA PERSISTENTE
-- =============================================================================
local function get_col_x(view, line_idx, col)
  if not view or not view.doc or not view.doc.lines[line_idx] then return 0 end
  local line_text = view.doc.lines[line_idx]
  local font = view:get_font()
  return font:get_width(line_text:sub(1, math.max(0, col - 1)))
end

local function get_doc_indent_size(doc)
  if not doc then return 4 end
  local fn = tostring(doc.filename or ""):lower()
  if fn:find("%.lua$") then return 2 end
  return config.indent_size or 4
end

local function get_active_highlight_query()
  local active_view = core.active_view
  if active_view and active_view.doc and active_view.doc.has_selection and active_view.doc:has_selection() then
    local l1, c1, l2, c2 = active_view.doc:get_selection(true)
    if l1 == l2 and c1 ~= c2 then
      local sel = active_view.doc:get_text(l1, c1, l2, c2)
      if sel and #sel >= 1 and #sel <= 120 and not sel:find("\n") and not sel:match("^%s+$") then
        return sel
      end
    end
  end
  if core.command_view and core.command_view.text and #core.command_view.text > 0 then
    local cv_text = core.command_view.text
    if #cv_text >= 1 and #cv_text <= 120 and not cv_text:find("\n") and not cv_text:match("^%s+$") then
      return cv_text
    end
  end
  return nil
end

-- =============================================================================
-- PARSER UNIVERSAL DE CORES (HEX, RGB, RGBA, TABELAS 3 OU 4 CANAIS)
-- =============================================================================
local function parse_any_color(text)
  if not text then return nil end
  
  -- Hexadecimal #RRGGBBAA, #RRGGBB, #RGB
  local hex = text:match("^#([0-9a-fA-F]+)$")
  if hex then
    if #hex == 6 then
      return { tonumber(hex:sub(1, 2), 16), tonumber(hex:sub(3, 4), 16), tonumber(hex:sub(5, 6), 16), 255 }
    elseif #hex == 8 then
      return { tonumber(hex:sub(1, 2), 16), tonumber(hex:sub(3, 4), 16), tonumber(hex:sub(5, 6), 16), tonumber(hex:sub(7, 8), 16) }
    elseif #hex == 3 then
      return { tonumber(hex:sub(1, 1):rep(2), 16), tonumber(hex:sub(2, 2):rep(2), 16), tonumber(hex:sub(3, 3):rep(2), 16), 255 }
    end
  end

  -- CSS rgb(...) e rgba(...)
  local r, g, b, a = text:match("^rgba?%s*%(%s*(%d+)%s*,%s*(%d+)%s*,%s*(%d+)%s*,?%s*(%d*)%s*%)$")
  if r and g and b then
    local alpha = (a ~= "" and tonumber(a)) or 255
    return { tonumber(r), tonumber(g), tonumber(b), alpha }
  end

  -- Tabelas Lua { R, G, B } ou { R, G, B, A }
  local tr, tg, tb, ta = text:match("^{%s*(%d+)%s*,%s*(%d+)%s*,%s*(%d+)%s*,?%s*(%d*)%s*}")
  if tr and tg and tb then
    local alpha = (ta ~= "" and tonumber(ta)) or 255
    return { tonumber(tr), tonumber(tg), tonumber(tb), alpha }
  end

  return nil
end

-- =============================================================================
-- RENDERIZAÇÃO DO CORPO DA LINHA (HIGHLIGHTS, CHIPS DE COR E GUIAS)
-- =============================================================================
local original_draw_line_body = DocView.draw_line_body
function DocView:draw_line_body(line_idx, x, y)
  local line_h = original_draw_line_body(self, line_idx, x, y)
  if not self.doc or not self.doc.lines[line_idx] then return line_h end

  local text = self.doc.lines[line_idx]
  local font = self:get_font()

  -- 1. DESENHO DAS GUIAS DE INDENTAÇÃO
  if config.draw_indent_guides ~= false then
    local spaces = text:match("^( +)")
    local count = spaces and #spaces or 0
    local indent_size = get_doc_indent_size(self.doc)
    if count >= indent_size then
      local levels = math.floor(count / indent_size)
      for i = 1, levels do
        local col_pos = (i - 1) * indent_size + 1
        local col_x = get_col_x(self, line_idx, col_pos)
        draw_rect_safe(x + col_x, y, 1, line_h, INDENT_GUIDE_COLOR)
      end
    end
  end

  -- 2. HIGHLIGHT DE BUSCA / SELEÇÃO PERSISTENTE
  local query = get_active_highlight_query()
  if query and #query > 0 then
    local s_idx = 1
    while true do
      local s, e = text:find(query, s_idx, true)
      if not s then break end
      local start_x = get_col_x(self, line_idx, s)
      local end_x   = get_col_x(self, line_idx, e + 1)
      draw_rect_safe(x + start_x, y, math.max(2, end_x - start_x), line_h, HIGHLIGHT_BLUE)
      s_idx = e + 1
    end
  end

  -- 3. CHIPS DE COR COM CONTRASTE INVERTIDO
  -- 3.1 Tabelas Lua { R, G, B } e { R, G, B, A } (Suporta 3 ou 4 números)
  for s_idx, rgb_str in text:gmatch("()({%s*%d+%s*,%s*%d+%s*,%s*%d+%s*,?%s*%d*%s*})") do
    local col = parse_any_color(rgb_str)
    if col then
      local start_x = get_col_x(self, line_idx, s_idx)
      local text_w  = font:get_width(rgb_str)
      local chip_x  = x + start_x
      
      -- Fundo sólido com a cor real
      draw_rect_safe(chip_x, y + 2, text_w, line_h - 4, { col[1], col[2], col[3], 255 })
      
      -- Texto com contraste inteligente (preto para claros, branco para escuros)
      local text_col = get_contrast_color(col[1], col[2], col[3])
      local text_y = y + (line_h - font:get_height()) / 2
      draw_text_safe(font, rgb_str, chip_x, text_y, text_col)
    end
  end

  -- 3.2 Hexadecimais #RRGGBBAA e #RRGGBB
  for s_idx, hex_str in text:gmatch("()(#%x%x%x%x%x%x%x?%x?)") do
    local col = parse_any_color(hex_str)
    if col then
      local start_x = get_col_x(self, line_idx, s_idx)
      local text_w  = font:get_width(hex_str)
      local chip_x  = x + start_x
      draw_rect_safe(chip_x, y + 2, text_w, line_h - 4, { col[1], col[2], col[3], 255 })
      local text_col = get_contrast_color(col[1], col[2], col[3])
      local text_y = y + (line_h - font:get_height()) / 2
      draw_text_safe(font, hex_str, chip_x, text_y, text_col)
    end
  end

  return line_h
end

-- 📐 Resolução de Tamanho de Indentação (Python = 4x4 estrito, Lua = 2x2)
local function get_doc_indent_size(doc)
  if not doc then return 4 end
  if doc.indent_size then return doc.indent_size end

  local fn = tostring(doc.filename or ""):lower()
  if fn:find("%.pyw?$") or (doc.syntax and doc.syntax.name == "Python") then
    return 4
  end
  if fn:find("%.lua$") or (doc.syntax and doc.syntax.name == "Lua") then
    return 2
  end
  return config.indent_size or 4
end

-- 📐 Métrica e Nível de Indentação por Linha
local function get_raw_line_indent(doc, line_idx, indent_size)
  if not doc then return 0 end
  doc._doxoade_indent_cache = doc._doxoade_indent_cache or { raw = {}, active = nil }
  local raw_cache = doc._doxoade_indent_cache.raw

  if raw_cache[line_idx] then
    return raw_cache[line_idx]
  end

  local text = doc.lines[line_idx]
  local result = 0

  if not text then
    result = 0
  elseif text:match("^%s*$") then
    result = -1
  else
    local s, e = text:find("^[ \t]+")
    if not s then
      result = 0
    else
      local indent_str = text:sub(s, e)
      local total = 0
      for i = 1, #indent_str do
        local byte_val = indent_str:byte(i)
        if byte_val == 9 then
          total = total + indent_size
        elseif byte_val == 32 then
          total = total + 1
        end
      end
      result = total
    end
  end

  raw_cache[line_idx] = result
  return result
end

-- 🔗 Interpolação de Linhas Vazias
local function get_effective_line_indent(doc, line_idx, indent_size)
  local raw = get_raw_line_indent(doc, line_idx, indent_size)
  if raw >= 0 then return raw end

  local prev_indent = 0
  for prev_idx = line_idx - 1, math.max(1, line_idx - 20), -1 do
    local ind = get_raw_line_indent(doc, prev_idx, indent_size)
    if ind >= 0 then
      prev_indent = ind
      break
    end
  end

  local next_indent = 0
  for next_idx = line_idx + 1, math.min(#doc.lines, line_idx + 20) do
    local ind = get_raw_line_indent(doc, next_idx, indent_size)
    if ind >= 0 then
      next_indent = ind
      break
    end
  end

  return math.min(prev_indent, next_indent)
end

-- 📍 Nível de Indentação do Cursor Ativo
local function get_active_cursor_indent(doc, indent_size)
  if not doc then return -1 end
  doc._doxoade_indent_cache = doc._doxoade_indent_cache or { raw = {}, active = nil }

  local line = doc:get_selection(true)
  local cache = doc._doxoade_indent_cache

  if cache.active_line == line and cache.active_indent then
    return cache.active_indent
  end

  local v = get_effective_line_indent(doc, line, indent_size)
  cache.active_line = line
  cache.active_indent = v
  return v
end

-- 🎨 RENDERIZADOR DO CORPO DA LINHA (DRAW_LINE_BODY)
local original_draw_line_body = DocView.draw_line_body

-- 📍 Converte coluna em posição X de pixel
local function get_col_x(view, line_text, col)
  if not line_text or col <= 1 then return 0 end
  local ok, w = pcall(function()
    return view:get_font():get_width(line_text:sub(1, col - 1))
  end)
  if ok and w then
    return w
  end
  return 0
end

function DocView:draw_line_body(line, x, y)
  pcall(function()
    local doc = self.doc
    if not doc or not doc.lines then return end
    local line_text = doc.lines[line]
    if not line_text then return end
    local line_h = self.get_line_height and self:get_line_height() or 16
    local font = self:get_font()
    local space_w = font:get_width(" ")

    -- 1. 📐 RENDERIZAÇÃO DAS LINHAS DE INDENTAÇÃO (4x4 PYTHON / 2x2 LUA)
    if config.draw_indent_guides then
      local indent_size = get_doc_indent_size(doc)
      local eff_indent = get_effective_line_indent(doc, line, indent_size)
      local active_indent = get_active_cursor_indent(doc, indent_size)

      if eff_indent >= indent_size then
        local max_level = math.floor(eff_indent / indent_size)
        for level = 1, max_level do
          local col_offset = (level - 1) * indent_size
          local guide_col = col_offset + 1

          -- Cálculo de pixel X seguro contra line_text nulo
          local first_tab = line_text and line_text:find("\t", 1, true)
          local guide_x

          if first_tab and first_tab < guide_col then
            -- Linha com tab no trecho: métrica de fonte precisa
            guide_x = x + get_col_x(self, line_text, guide_col)
          else
            -- Prefixo com espaços: cálculo aritmético direto
            guide_x = x + (col_offset * space_w)
          end

          -- Realce da guia ativa correspondente ao escopo do cursor
          local is_active_guide = (active_indent > 0 and col_offset < active_indent and (col_offset + indent_size) >= active_indent)
          local guide_color = is_active_guide and INDENT_GUIDE_ACTIVE or INDENT_GUIDE_COLOR

          draw_rect_safe(guide_x, y, 1, line_h, guide_color)
        end
      end
    end

    -- 2. 🔍 HIGHLIGHT DE BUSCA / SELEÇÃO GLOBAL
    local search_text = get_active_highlight_query()
    if search_text then
      local start_idx = 1
      while true do
        local s_idx, e_idx = line_text:find(search_text, start_idx, true)
        if not s_idx then break end
        local x1 = x + get_col_x(self, line_text, s_idx)
        local x2 = x + get_col_x(self, line_text, e_idx + 1)
        local w = x2 - x1
        if w > 0 then
          draw_rect_safe(x1, y, w, line_h, HIGHLIGHT_BLUE)
        end
        start_idx = e_idx + 1
      end
    end

    -- 3. 🎨 FUNDO DE COR PARA #HEX
    local s_hex = 1
    while true do
      local s_idx, e_idx, hex_code = line_text:find("(#([%da-fA-F]+))", s_hex)
      if not s_idx then break end
      local parsed = parse_any_color(hex_code)
      if parsed then
        local x1 = x + get_col_x(self, line_text, s_idx)
        local x2 = x + get_col_x(self, line_text, e_idx + 1)
        draw_rect_safe(x1, y, x2 - x1, line_h, parsed)
      end
      s_hex = e_idx + 1
    end

    -- 4. 🎨 FUNDO DE COR PARA TABELAS { R, G, B }
    local s_tbl = 1
    while true do
      local s_idx, e_idx, tbl_code = line_text:find("({%s*%d+%s*,%s*%d+%s*,%s*%d+[%s,%d]*})", s_tbl)
      if not s_idx then break end
      local parsed = parse_any_color(tbl_code)
      if parsed then
        local x1 = x + get_col_x(self, line_text, s_idx)
        local x2 = x + get_col_x(self, line_text, e_idx + 1)
        draw_rect_safe(x1, y, x2 - x1, line_h, parsed)
      end
      s_tbl = e_idx + 1
    end
  end)

  return original_draw_line_body(self, line, x, y)
end

command.add("core.docview", {
  ["doc:unindent"] = function()
    local view = core.active_view
    local doc = view and view.doc
    if not doc or not doc.get_selection then return end
    local l1, c1, l2, c2 = doc:get_selection(true)
    local indent_size = config.indent_size or 4
    if doc.filename and doc.filename:lower():find("%.lua$") then
      indent_size = 2
    end
    for line = (l1 or 1), (l2 or 1) do
      local text = doc.lines and doc.lines[line]
      if text then
        local spaces = text:match("^( +)")
        if spaces then
          local count = #spaces
          local to_remove = (count >= indent_size) and indent_size or count
          if doc.remove then
            doc:remove(line, 1, line, to_remove + 1)
          end
        end
      end
    end
  end
})

-- ⌨️ Comando e Atalho para Alternar Guias de Indentação
command.add(nil, {
  ["doxoade:toggle-indent-guides"] = function()
    config.draw_indent_guides = not config.draw_indent_guides
    core.log("Indent Guides: " .. (config.draw_indent_guides and "ATIVADAS" or "DESATIVADAS"))
    core.redraw = true
end})

keymap.add {
  ["ctrl+alt+i"] = "doxoade:toggle-indent-guides",
}
