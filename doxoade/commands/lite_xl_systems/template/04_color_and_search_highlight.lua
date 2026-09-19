-- doxoade/commands/lite_xl_systems/template/04_color_and_search_highlight.lua
--[[
  ⚡ DOXOADE HIGH-PERFORMANCE COLOR PREVIEW, INDENT GUIDES & SESSION DIFF (V3.6)
  - Escadaria / Cascata Ativa: Guia de indentação do escopo do cursor realçada em tempo real.
  - Marcador de Linhas Modificadas no Gutter: Amarelo (Dirty) e Verde (Saved).
  - Previews de Cor Inline (#HEX, rgb, rgba, {r,g,b,a}) com texto contrastado.
  - Highlight Persistente de Busca: Seleção ativa E digitação no Command View (Ctrl+F).
  - Blindagem Idempotente de Sintaxe Python: Protege f-strings e docstrings triplas.
  - Comandos de UX: doc:unindent (resiliente a TABs e espaços) e toggle-indent-guides (Ctrl+Alt+I).
  Compliance: ProDeNov 1.2.1, PASC-6.1.
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
  if not font or not text or text == "" then return end
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

-- =============================================================================
-- 2. BLINDAGEM IDEMPOTENTE DE SINTAXE PYTHON (RESTAURADA)
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
-- 3. CONFIGURAÇÃO DE CORES & PALETAS (Solid Color Baking - Zero Alpha Thrashing)
-- =============================================================================
config.draw_indent_guides  = config.draw_indent_guides ~= false
local INDENT_GUIDE_COLOR   = { 42, 40, 48, 255 }    -- Sólido opaco (Cache Hit no rencache)
local INDENT_GUIDE_ACTIVE  = { 88, 85, 98, 255 }    -- Sólido opaco (Cache Hit no rencache)
local HIGHLIGHT_BLUE       = { 12, 55, 120, 255 }   -- Sólido opaco (Cache Hit no rencache)
local GUTTER_DIVIDER_WIDTH = 3
local GUTTER_DIVIDER_COLOR = { 115, 110, 130, 255 }
local COLOR_DIRTY          = { 234, 179, 8, 255 }
local COLOR_SAVED          = { 34, 197, 94, 255 }

local function get_doc_indent_unit(doc)
  if doc and doc.filename then
    local fn = tostring(doc.filename):lower()
    if fn:find("%.lua$") then return 2 end
  end
  return config.indent_size or 4
end

local function get_contrast_color(col)
  local lum = (0.299 * col[1] + 0.587 * col[2] + 0.114 * col[3])
  return lum > 140 and { 20, 20, 20, 255 } or { 245, 245, 245, 255 }
end

-- Busca ativa: suporta seleção de texto E input no command view (Ctrl+F)
local function get_active_highlight_query()
  local view = core.active_view
  local doc = view and view.doc
  if doc and doc.has_selection and doc:has_selection() then
    local l1, c1, l2, c2 = doc:get_selection(true)
    if l1 == l2 and c1 ~= c2 then
      local query = doc:get_text(l1, c1, l2, c2)
      if query and #query >= 2 and #query <= 80 and not query:find("\n") and not query:match("^%s+$") then
        return query
      end
    end
  end
  if core.command_view and core.command_view.text and #core.command_view.text >= 2 then
    local cv_text = core.command_view.text
    if #cv_text <= 80 and not cv_text:find("\n") and not cv_text:match("^%s+$") then
      return cv_text
    end
  end
  return nil
end

-- =============================================================================
-- 4. CÁLCULO DE INDENTAÇÃO & ESCADARIA EM CASCATA
-- =============================================================================
local _indent_cache = {}
local _indent_cache_size = 0
local MAX_CACHE_ENTRIES = 2000

local function compute_line_indent(line_text, indent_unit)
  if not line_text or line_text == "" then return 0 end
  local cached = _indent_cache[line_text]
  if cached then return cached end

  local spaces = 0
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

local function get_active_cursor_indent(doc, indent_unit)
  if not doc or not doc.get_selection then return -1 end
  local cur_line = doc:get_selection(true)
  local text = doc.lines and doc.lines[cur_line]
  if not text or text:match("^%s*$") then
    for l = cur_line - 1, math.max(1, cur_line - 15), -1 do
      local prev_text = doc.lines[l]
      if prev_text and not prev_text:match("^%s*$") then
        return compute_line_indent(prev_text, indent_unit)
      end
    end
    return 0
  end
  return compute_line_indent(text, indent_unit)
end

-- =============================================================================
-- 5. PARSER DE CORES INLINE (#HEX, RGB, RGBA, TABELAS LUA)
-- =============================================================================
local _color_cache = {}
local _color_cache_size = 0

local function parse_colors_in_line(line_text)
  if not line_text or line_text == "" or (not line_text:find("#") and not line_text:find("rgb") and not line_text:find("{")) then
    return nil
  end

  local cached = _color_cache[line_text]
  if cached ~= nil then return cached end

  local results = nil

  -- 1. #HEX (3, 4, 6, 8 dígitos)
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
      results = results or {}
      table.insert(results, {
        col1 = s,
        col2 = s + len,
        text = line_text:sub(s, s + len),
        color = { r, g, b, a }
      })
    end
  end

  -- 2. rgb / rgba
  for s, full_match in line_text:gmatch("()(rgba?%s*%b())") do
    local args = full_match:match("%((.-)%)")
    if args then
      local r, g, b, a = args:match("^%s*(%d+)%s*[,%s]%s*(%d+)%s*[,%s]%s*(%d+)%s*[,/]?%s*([%d%.]*)")
      if r and g and b then
        local alpha = 255
        if a and a ~= "" then
          local num_a = tonumber(a)
          if num_a then alpha = num_a <= 1.0 and math.floor(num_a * 255) or math.min(255, math.floor(num_a)) end
        end
        results = results or {}
        table.insert(results, {
          col1 = s,
          col2 = s + #full_match - 1,
          text = full_match,
          color = { math.min(255, tonumber(r)), math.min(255, tonumber(g)), math.min(255, tonumber(b)), alpha }
        })
      end
    end
  end

  -- 3. Tabelas Lua { R, G, B } e { R, G, B, A } (Suporta espaços, floats e inteiros)
  for s, full_match in line_text:gmatch("()({%s*[%d%.]+%s*,%s*[%d%.]+%s*,%s*[%d%.]+[%s,%d%.]*})") do
    local inner = full_match:match("{(.-)}")
    if inner then
      -- ⚡ CORREÇÃO: ^%s* aceita espaços após a chave { sem falhar
      local r, g, b, a = inner:match("^%s*([%d%.]+)%s*,%s*([%d%.]+)%s*,%s*([%d%.]+)%s*,?%s*([%d%.]*)")
      if r and g and b then
        local nr, ng, nb = tonumber(r), tonumber(g), tonumber(b)
        if nr and ng and nb then
          -- Suporte a números normalizados 0.0-1.0 ou 0-255
          nr = (nr <= 1.0 and nr > 0) and math.floor(nr * 255) or math.min(255, math.floor(nr))
          ng = (ng <= 1.0 and ng > 0) and math.floor(ng * 255) or math.min(255, math.floor(ng))
          nb = (nb <= 1.0 and nb > 0) and math.floor(nb * 255) or math.min(255, math.floor(nb))

          local na = 255
          if a and a ~= "" then
            local num_a = tonumber(a)
            if num_a then
              na = (num_a <= 1.0) and math.floor(num_a * 255) or math.min(255, math.floor(num_a))
            end
          end

          results = results or {}
          table.insert(results, {
            col1 = s,
            col2 = s + #full_match - 1,
            text = full_match,
            color = { nr, ng, nb, na }
          })
        end
      end
    end
  end

  if _color_cache_size >= MAX_CACHE_ENTRIES then
    _color_cache = {}
    _color_cache_size = 0
  end
  _color_cache[line_text] = results or false
  _color_cache_size = _color_cache_size + 1

  return results
end

-- =============================================================================
-- 6. RASTREAMENTO ATÔMICO DE LINHAS DA SESSÃO (DIRTY VS SAVED)
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

-- =============================================================================
-- 7. DOCVIEW: DRAW_LINE_GUTTER (MARCADOR DIRTY/SAVED & DIVISOR GROSSO)
-- =============================================================================
local original_draw_line_gutter = DocView.draw_line_gutter
function DocView:draw_line_gutter(line_idx, x, y, ...)
  local res = original_draw_line_gutter and original_draw_line_gutter(self, line_idx, x, y, ...) or 0

  local gw = (self.get_gutter_width and self:get_gutter_width()) or 40
  local div_w = config.gutter_divider_width or GUTTER_DIVIDER_WIDTH
  local div_col = style.gutter_divider or style.divider or GUTTER_DIVIDER_COLOR
  local line_h = (self.get_line_height and self:get_line_height()) or 16

  local divider_x = x + gw - div_w - 2
  draw_rect_safe(divider_x, y, div_w, line_h, div_col)

  local doc = self.doc
  if doc and doc.session_modified and doc.session_modified[line_idx] then
    local state = doc.session_modified[line_idx]
    local marker_col = (state == "dirty") and COLOR_DIRTY or COLOR_SAVED
    draw_rect_safe(divider_x, y, div_w + 1, line_h, marker_col)
  end

  return res
end

-- =============================================================================
-- 8. DOCVIEW: DRAW_LINE_BODY (ESCADARIA ATIVA, BUSCA E CORES INLINE)
-- =============================================================================
local _last_frame_clock = 0
local _cached_highlight_query = nil
local _cached_active_indent = -1

local function update_frame_memo(doc, indent_unit)
  local now = os.clock()
  if now ~= _last_frame_clock then
    _last_frame_clock = now
    _cached_highlight_query = get_active_highlight_query()
    _cached_active_indent = get_active_cursor_indent(doc, indent_unit)
  end
end

local original_draw_line_body = DocView.draw_line_body
function DocView:draw_line_body(line_idx, x, y)
  local res = original_draw_line_body(self, line_idx, x, y)
  local doc = self.doc
  if not doc or not doc.lines or not doc.lines[line_idx] then
    return res
  end

  local line_text = doc.lines[line_idx]
  local line_h = self:get_line_height()
  local font = self:get_font()
  local space_w = font:get_width(" ")
  local indent_unit = get_doc_indent_unit(doc)

  -- Atualiza o cache do frame (roda uma única vez por frame)
  update_frame_memo(doc, indent_unit)

  -- A. Highlight persistente de busca (reutiliza query cacheada)
  local query = _cached_highlight_query
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

  -- B. Guias de indentação (usando cores sólidas sem alpha blending)
  if config.draw_indent_guides ~= false then
    local eff_indent = compute_line_indent(line_text, indent_unit)
    if eff_indent >= indent_unit then
      local active_indent = _cached_active_indent
      local levels = math.floor(eff_indent / indent_unit)
      local has_tab = line_text:find("\t", 1, true) ~= nil

      for lvl = 1, levels do
        local col_offset = (lvl - 1) * indent_unit
        local gx = x + (col_offset * space_w)
        if has_tab then
          gx = x + self:get_col_x_offset(line_idx, col_offset + 1)
        end

        local is_active = (active_indent > 0 and col_offset < active_indent and (col_offset + indent_unit) >= active_indent)
        local guide_color = is_active and INDENT_GUIDE_ACTIVE or INDENT_GUIDE_COLOR

        draw_rect_safe(gx, y, 1, line_h, guide_color)
      end
    end
  end

  -- C. Chips de cor inline (Fast-Path: só analisa se houver marcadores)
  if line_text:find("#", 1, true) or line_text:find("rgb", 1, true) or line_text:find("{", 1, true) then
    local colors = parse_colors_in_line(line_text)
    if colors then
      for _, item in ipairs(colors) do
        local rx = self:get_col_x_offset(line_idx, item.col1)
        local rw = self:get_col_x_offset(line_idx, item.col2 + 1) - rx
        if rw > 0 then
          local bx = x + rx
          local by = y + 1
          local bh = line_h - 2
          draw_rect_safe(bx, by, rw, bh, item.color)
          draw_rect_safe(bx, by, rw, 1, { 0, 0, 0, 255 })
          draw_rect_safe(bx, by + bh - 1, rw, 1, { 0, 0, 0, 255 })
          local text_col = get_contrast_color(item.color)
          draw_text_safe(font, item.text, bx, y, text_col)
        end
      end
    end
  end

  return res
end

-- Thread relaxada para atualização da escadaria ativa (0.15s)
core.add_thread(function()
  local last_cursor_line = -1
  while true do
    coroutine.yield(0.15)
    local view = core.active_view
    local doc = view and view.doc
    if doc and doc.get_selection then
      local cur_line = doc:get_selection(true)
      if cur_line ~= last_cursor_line then
        last_cursor_line = cur_line
        core.redraw = true
      end
    end
  end
end)

-- =============================================================================
-- 9. COMANDOS DE UX & KEYMAPS (RESILIENTE A TABS E ESPAÇOS)
-- =============================================================================
command.add("core.docview", {
  ["doc:unindent"] = function()
    local view = core.active_view
    local doc = view and view.doc
    if not doc or not doc.get_selection then return end
    local l1, c1, l2, c2 = doc:get_selection(true)
    local indent_unit = get_doc_indent_unit(doc)

    for line = (l1 or 1), (l2 or 1) do
      local text = doc.lines and doc.lines[line]
      if text and #text > 0 then
        local first_byte = text:byte(1)
        if first_byte == 9 then -- '\t'
          doc:remove(line, 1, line, 2)
        elseif first_byte == 32 then -- ' '
          local spaces = text:match("^( +)")
          if spaces then
            local count = #spaces
            local to_remove = (count >= indent_unit) and indent_unit or count
            doc:remove(line, 1, line, to_remove + 1)
          end
        end
      end
    end
  end
})

command.add(nil, {
  ["doxoade:toggle-indent-guides"] = function()
    config.draw_indent_guides = not config.draw_indent_guides
    if core.log then
      core.log("📐 Indent Guides: " .. (config.draw_indent_guides and "ATIVADAS" or "DESATIVADAS"))
    end
    core.redraw = true
  end
})

keymap.add {
  ["ctrl+alt+i"] = "doxoade:toggle-indent-guides",
}
