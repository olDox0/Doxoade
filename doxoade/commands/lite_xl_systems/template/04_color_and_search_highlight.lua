-- doxoade/commands/lite_xl_systems/template/04_color_and_search_highlight.lua
-- =============================================================================
-- 04. HIGHLIGHT GLOBAL (SPLITS) + CORES INLINE (#HEX, {R,G,B}) + INDENT GUIDES 4x4
-- =============================================================================
local core = require "core"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local Doc = require "core.doc"
local DocView = require "core.docview"

-- 🛡️ Polyfill Universal de Renderização
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

-- ⚙️ Configurações das Guias de Indentação
config.draw_indent_guides = config.draw_indent_guides ~= false
local INDENT_GUIDE_COLOR = { 45, 42, 48, 160 }       -- Guia inativa sutil (Piano Black)
local INDENT_GUIDE_ACTIVE = { 76, 69, 82, 240 }      -- Guia ativa do bloco do cursor
local HIGHLIGHT_BLUE = { 0, 108, 255, 140 }

-- Rastreamento de Linhas da Sessão (Dirty vs Saved)
local COLOR_DIRTY = { 234, 179, 8, 255 }      -- Amarelo (não salvo)
local COLOR_SAVED = { 110, 110, 120, 180 }    -- Cinza/Neutro (modificado na sessão e já salvo)

local original_doc_insert = Doc.insert
function Doc:insert(line, col, text)
  self.session_modified = self.session_modified or {}
  self.session_modified[line] = "dirty"
  self._doxoade_indent_cache = { raw = {}, active = nil }
  return original_doc_insert(self, line, col, text)
end

local original_doc_remove = Doc.remove
function Doc:remove(line1, col1, line2, col2)
  self.session_modified = self.session_modified or {}
  self.session_modified[line1] = "dirty"
  self._doxoade_indent_cache = { raw = {}, active = nil }
  return original_doc_remove(self, line1, col1, line2, col2)
end

-- Ao salvar: transforma todas as linhas "dirty" em "saved" (preserva o histórico da sessão)
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

-- Hook de desenho na Gutter (Margem ao lado dos números de linha)

-- Expande a largura da gutter em +6px para o marcador nunca sobrepor os números
local original_get_gutter_width = DocView.get_gutter_width
function DocView:get_gutter_width()
  return original_get_gutter_width(self)
end

-- Desenho da barra colada na extremidade direita da margem
local original_draw_line_gutter = DocView.draw_line_gutter
function DocView:draw_line_gutter(line_idx, x, y, width)
  local h = original_draw_line_gutter(self, line_idx, x, y, width)

  if self.doc and self.doc.session_modified and self.doc.session_modified[line_idx] then
    local state = self.doc.session_modified[line_idx]
    local marker_color = (state == "dirty") and COLOR_DIRTY or COLOR_SAVED

    -- Barra de 3px na borda direita da gutter (divisor natural)
    draw_rect_safe(x + width + 18, y, 3, self:get_line_height(), marker_color)
  end

  return h
end

-- 🐍 Patch de Sintaxe Python: Suporte a Raw Strings Multilinhas r''' e r"""
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

local function parse_any_color(text)
  local hex = text:match("^#([%da-fA-F]+)$")
  if hex then
    local len = #hex
    if len == 3 or len == 4 then
      local r = tonumber(hex:sub(1, 1):rep(2), 16) or 0
      local g = tonumber(hex:sub(2, 2):rep(2), 16) or 0
      local b = tonumber(hex:sub(3, 3):rep(2), 16) or 0
      return { r, g, b, 220 }
    elseif len == 6 or len == 8 then
      local r = tonumber(hex:sub(1, 2), 16) or 0
      local g = tonumber(hex:sub(3, 4), 16) or 0
      local b = tonumber(hex:sub(5, 6), 16) or 0
      return { r, g, b, 220 }
    end
  end
  local r, g, b = text:match("^{%s*(%d+)%s*,%s*(%d+)%s*,%s*(%d+)")
  if r and g and b then
    local nr, ng, nb = tonumber(r) or 0, tonumber(g) or 0, tonumber(b) or 0
    if nr <= 255 and ng <= 255 and nb <= 255 then
      return { nr, ng, nb, 220 }
    end
  end
  return nil
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
