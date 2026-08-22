-- doxoade/commands/lite_xl_systems/template/04_color_and_search_highlight.lua
-- =============================================================================
-- 04. HIGHLIGHT DE SELEÇÃO GLOBAL (SPLITS) + CORES INLINE (#HEX, {R, G, B})
--     + LINHA AMARELA NO GUTTER (esquerda do número da linha)
-- =============================================================================
local core = require "core"
local Doc = require "core.doc"
local DocView = require "core.docview"

-- 🔧 Carrega rencache com fallback para o renderer C global
local rencache = nil
pcall(function() rencache = require "core.rencache" end)
local native_renderer = renderer  -- renderer é um global C no Lite XL

-- Função segura de desenho com fallback
local function draw_rect_safe(x, y, w, h, color)
  if rencache then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

-- -----------------------------------------------------------------------------
-- 1. RASTREADOR DE LINHAS MODIFICADAS
-- -----------------------------------------------------------------------------
local original_doc_insert = Doc.insert
function Doc:insert(line, col, text)
  self.modified_lines = self.modified_lines or {}
  self.modified_lines[line] = true
  return original_doc_insert(self, line, col, text)
end

local original_doc_remove = Doc.remove
function Doc:remove(line1, col1, line2, col2)
  self.modified_lines = self.modified_lines or {}
  self.modified_lines[line1] = true
  return original_doc_remove(self, line1, col1, line2, col2)
end

local original_doc_save = Doc.save
function Doc:save(...)
  self.modified_lines = {}
  return original_doc_save(self, ...)
end

-- -----------------------------------------------------------------------------
-- 2. CAPTURA REATIVA DE SELEÇÃO E BUSCA
-- -----------------------------------------------------------------------------
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

-- -----------------------------------------------------------------------------
-- 3. HOOK DE DESENHO: CORES INLINE + HIGHLIGHT DE SELEÇÃO
-- -----------------------------------------------------------------------------
local HIGHLIGHT_BLUE = { 0, 108, 255, 140 }       -- #006CFF (Brandeis Blue)
local MODIFIED_YELLOW = { 234, 179, 8, 200 }     -- #EAB308

local original_draw_line_body = DocView.draw_line_body
function DocView:draw_line_body(line, x, y)
  pcall(function()
    local doc = self.doc
    if not doc or not doc.lines then return end
    local line_text = doc.lines[line]
    if not line_text then return end
    local line_h = self.get_line_height and self:get_line_height() or 16

    -- A) Highlight de seleção global síncrono (em todos os splits)
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

    -- B) Fundo de cor para #HEX e tabelas Lua { R, G, B }
    if line_text:find("#") or line_text:find("{") then
      local s_hex = 1
      while true do
        local s_idx, e_idx, hex_code = line_text:find("(#([%da-fA-F]+))", s_hex)
        if not s_idx then break end
        local parsed = parse_any_color(hex_code)
        if parsed then
          local x1 = x + get_col_x(self, line_text, s_idx)
          local x2 = x + get_col_x(self, line_text, e_idx + 1)
          local w = x2 - x1
          if w > 0 then draw_rect_safe(x1, y, w, line_h, parsed) end
        end
        s_hex = e_idx + 1
      end

      local s_tbl = 1
      while true do
        local s_idx, e_idx, tbl_code = line_text:find("({%s*%d+%s*,%s*%d+%s*,%s*%d+[%s,%d]*})", s_tbl)
        if not s_idx then break end
        local parsed = parse_any_color(tbl_code)
        if parsed then
          local x1 = x + get_col_x(self, line_text, s_idx)
          local x2 = x + get_col_x(self, line_text, e_idx + 1)
          local w = x2 - x1
          if w > 0 then draw_rect_safe(x1, y, w, line_h, parsed) end
        end
        s_tbl = e_idx + 1
      end
    end
  end)

  return original_draw_line_body(self, line, x, y)
end

-- -----------------------------------------------------------------------------
-- 4. LINHA AMARELA NO GUTTER (esquerda do número da linha)
-- -----------------------------------------------------------------------------
local original_draw_line_gutter = DocView.draw_line_gutter
function DocView:draw_line_gutter(line, x, y, width)
  local res = original_draw_line_gutter(self, line, x, y, width)
  if self.doc and self.doc.modified_lines and self.doc.modified_lines[line] then
    local line_h = self.get_line_height and self:get_line_height() or 16
    draw_rect_safe(x, y, 3, line_h, MODIFIED_YELLOW)
  end
  return res
end
