-- doxoade/commands/lite_xl_systems/template/04_color_and_search_highlight.lua
--[[
  ⚡ DOXOADE HIGH-PERFORMANCE COLOR PREVIEW & INDENT GUIDES (V2.1 Calibrada)
  - Line Memoization O(1): Cache de regex de cores e guias de indentação.
  - Previews de cor contrastados (#HEX, rgb, rgba, {r,g,b,a}).
  - Highlight persistente de busca e seleção em todos os splits abertos.
  - Blindagem idempotente de sintaxe Python (F-strings e raw strings sem duplicatas).
  - Alinhamento de guias com suporte a TABs (\t) e espaços.
]]
local core = require "core"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local Doc = require "core.doc"
local DocView = require "core.docview"
local syntax = require "core.syntax"

-- =============================================================================
-- 1. POLYFILLS DE RENDERIZAÇÃO SEGURA
-- =============================================================================
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
-- 2. BLINDAGEM IDEMPOTENTE DE SINTAXE PYTHON
-- =============================================================================
local function sanitize_python_syntax(syn)
  if not syn or type(syn.patterns) ~= "table" then return end
  if syn._doxoade_python_shielded then return end

  local is_python = (syn.name == "Python") or
      (syn.files and type(syn.files) == "table" and syn.files[1] == "%.py$")
  if not is_python then return end
  syn._doxoade_python_shielded = true

  local safe_patterns = {
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
  }

  for i = #safe_patterns, 1, -1 do
    table.insert(syn.patterns, 1, safe_patterns[i])
  end
end

if syntax and syntax.add then
  local original_syntax_add = syntax.add
  syntax.add = function(syn, ...)
    pcall(sanitize_python_syntax, syn)
    return original_syntax_add(syn, ...)
  end
end

if syntax and syntax.items then
  for _, syn in ipairs(syntax.items) do
    pcall(sanitize_python_syntax, syn)
  end
end

-- =============================================================================
-- 3. LINE MEMOIZATION CACHE & PARSERS O(1)
-- =============================================================================
config.draw_indent_guides = config.draw_indent_guides ~= false
local INDENT_GUIDE_COLOR = { 45, 42, 48, 160 }       
local HIGHLIGHT_BLUE      = { 0, 108, 255, 130 }     
local COLOR_DIRTY         = { 234, 179, 8, 255 }      
local COLOR_SAVED         = { 110, 110, 120, 180 }    

local _color_cache = {}
local _color_cache_size = 0
local _indent_cache = {}
local _indent_cache_size = 0
local MAX_CACHE_ENTRIES = 2500

local function get_contrast_color(col)
  local lum = (0.299 * col[1] + 0.587 * col[2] + 0.114 * col[3])
  return lum > 140 and { 20, 20, 20, 255 } or { 245, 245, 245, 255 }
end

local function parse_colors_in_line(line_text)
  if not line_text or line_text == "" then return {} end

  local cached = _color_cache[line_text]
  if cached then return cached end

  local results = {}

  -- 1. Regex #HEX (3, 4, 6 ou 8 dígitos)
  for s, hex in line_text:gmatch("()#([0-9a-fA-F]+)") do
    local len = #hex
    if len == 3 or len == 4 or len == 6 or len == 8 then
      local r, g, b, a = 255, 255, 255, 255
      if len == 3 or len == 4 then
        r = tonumber(hex:sub(1,1):rep(2), 16) or 255
        g = tonumber(hex:sub(2,2):rep(2), 16) or 255
        b = tonumber(hex:sub(3,3):rep(2), 16) or 255
        if len == 4 then a = tonumber(hex:sub(4,4):rep(2), 16) or 255 end
      else
        r = tonumber(hex:sub(1,2), 16) or 255
        g = tonumber(hex:sub(3,4), 16) or 255
        b = tonumber(hex:sub(5,6), 16) or 255
        if len == 8 then a = tonumber(hex:sub(7,8), 16) or 255 end
      end
      table.insert(results, { col1 = s, col2 = s + len, color = { r, g, b, a } })
    end
  end

  -- 2. Regex rgb(...) e rgba(...)
  for s, func_name, args in line_text:gmatch("()(rgba?)%s*%((.-)%)") do
    local r, g, b, a = args:match("^%s*(%d+)%s*[,%s]%s*(%d+)%s*[,%s]%s*(%d+)%s*[,/]?%s*([%d%.]*)")
    if r and g and b then
      local alpha = 255
      if a and a ~= "" then
        local num_a = tonumber(a)
        if num_a then alpha = num_a <= 1.0 and math.floor(num_a * 255) or math.min(255, math.floor(num_a)) end
      end
      table.insert(results, {
        col1 = s,
        col2 = s + #func_name + #args + 2,
        color = { math.min(255, tonumber(r)), math.min(255, tonumber(g)), math.min(255, tonumber(b)), alpha }
      })
    end
  end

  -- 3. Regex Tabelas Lua { R, G, B } e { R, G, B, A }
  for s, inner in line_text:gmatch("(){%s*(%d+%s*,%s*%d+%s*,%s*%d+[%s,%d]*)%s*}") do
    local r, g, b, a = inner:match("^(%d+)%s*,%s*(%d+)%s*,%s*(%d+)%s*,?%s*(%d*)")
    if r and g and b then
      local nr, ng, nb = tonumber(r), tonumber(g), tonumber(b)
      if nr <= 255 and ng <= 255 and nb <= 255 then
        local na = 255
        if a and a ~= "" then na = math.min(255, tonumber(a) or 255) end
        table.insert(results, {
          col1 = s,
          col2 = s + #inner + 2,
          color = { nr, ng, nb, na }
        })
      end
    end
  end

  if _color_cache_size >= MAX_CACHE_ENTRIES then
    _color_cache = {}
    _color_cache_size = 0
  end
  _color_cache[line_text] = results
  _color_cache_size = _color_cache_size + 1

  return results
end

local function get_cached_line_indent(line_text)
  if not line_text then return 0 end
  local cached = _indent_cache[line_text]
  if cached then return cached end

  local spaces = 0
  local indent_unit = config.indent_size or 4
  for i = 1, #line_text do
    local b = line_text:byte(i)
    if b == 32 then
      spaces = spaces + 1
    elseif b == 9 then
      spaces = spaces + indent_unit
    else
      break
    end
  end

  if _indent_cache_size >= MAX_CACHE_ENTRIES then
    _indent_cache = {}
    _indent_cache_size = 0
  end
  _indent_cache[line_text] = spaces
  _indent_cache_size = _indent_cache_size + 1
  return spaces
end

local function get_active_highlight_query()
  local view = core.active_view
  local doc = view and view.doc
  if not doc or not doc.has_selection or not doc:has_selection() then
    return nil
  end
  local l1, c1, l2, c2 = doc:get_selection(true)
  if l1 ~= l2 then return nil end
  local query = doc:get_text(l1, c1, l2, c2)
  if not query or #query < 2 or #query > 80 then return nil end
  return query
end

-- =============================================================================
-- 4. RASTREAMENTO DE LINHAS DA SESSÃO (DIRTY VS SAVED)
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
-- 5. HOOK NO DOCVIEW:DRAW_LINE_BODY (Renderização de Destaques, Cores e Guias)
-- =============================================================================
local original_draw_line_body = DocView.draw_line_body
function DocView:draw_line_body(line_idx, x, y)
  local line_h = self:get_line_height()
  local font = self:get_font()
  local doc = self.doc

  if doc and doc.lines and doc.lines[line_idx] then
    local line_text = doc.lines[line_idx]

    -- A. HIGHLIGHT PERSISTENTE DE BUSCA / SELEÇÃO
    local query = get_active_highlight_query()
    if query and #query > 0 then
      local s_idx = 1
      while true do
        local s, e = line_text:find(query, s_idx, true)
        if not s then break end
        local start_x = self:get_col_x_offset(line_idx, s)
        local end_x   = self:get_col_x_offset(line_idx, e + 1)
        draw_rect_safe(x + start_x, y, math.max(2, end_x - start_x), line_h, HIGHLIGHT_BLUE)
        s_idx = e + 1
      end
    end

    -- B. GUIAS DE INDENTAÇÃO (Suporte a TABs e Espaços)
    if config.draw_indent_guides ~= false then
      local indent_spaces = get_cached_line_indent(line_text)
      local indent_size = config.indent_size or 4
      if indent_spaces >= indent_size then
        local guide_color = style.guide or style.divider or INDENT_GUIDE_COLOR
        local guide_count = math.floor(indent_spaces / indent_size)

        for g = 1, guide_count do
          local col_char = (g - 1) * indent_size + 1
          local col_offset = self:get_col_x_offset(line_idx, col_char)
          draw_rect_safe(x + col_offset, y, 1, line_h, guide_color)
        end
      end
    end

    -- C. CHIPS DE PRÉVIA DE COR INLINE
    if line_text:find("#") or line_text:find("rgb") or line_text:find("{") then
      local color_boxes = parse_colors_in_line(line_text)
      if #color_boxes > 0 then
        for _, box in ipairs(color_boxes) do
          local x1 = self:get_col_x_offset(line_idx, box.col1)
          local x2 = self:get_col_x_offset(line_idx, box.col2)
          local box_w = math.max(12, x2 - x1)
          local box_h = line_h - 2

          draw_rect_safe(x + x1, y + 1, box_w, box_h, box.color)
          draw_rect_safe(x + x1, y + 1, box_w, 1, { 255, 255, 255, 70 })
        end
      end
    end
  end

  return original_draw_line_body(self, line_idx, x, y)
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
