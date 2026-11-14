-- doxoade/commands/lite_xl_systems/template/18_search_results_dock.lua
--[[
🔍 SEARCH RESULTS DOCK (V49.0 — Lista Navegável)
Painel flutuante com LISTA rolável. ↑↓ navega, Enter abre, Esc/X fecha,
roda do mouse rola. F4/Alt+. e Shift+F4/Alt+, preservados.
Navegação foca aba existente ou abre nova (nunca substitui a ativa).
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local RootView = require "core.rootview"
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if not color or type(color) ~= "table" then color = { 128, 128, 128, 255 } end
  if rencache and rencache.draw_rect then pcall(rencache.draw_rect, x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then pcall(native_renderer.draw_rect, x, y, w, h, color) end
end
local function draw_text_safe(font, text, x, y, color)
  if not font or not text or text == "" then return end
  if not color or type(color) ~= "table" then color = { 255, 255, 255, 255 } end
  if rencache and rencache.draw_text then pcall(rencache.draw_text, font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then pcall(native_renderer.draw_text, font, text, x, y, color) end
end

local function get_search_state()
  local state = rawget(_G, "_DOXOADE_SEARCH_STATE")
  if not state then
    state = { is_searching=false, query="", results={}, total_hits=0, total_files=0, elapsed=0, current_result_idx=1 }
    rawset(_G, "_DOXOADE_SEARCH_STATE", state)
  end
  return state
end

local UIState = { visible=false, panel_rect=nil, close_rect=nil, scroll=0, hovered_idx=nil, row_rects={} }
rawset(_G, "_DOXOADE_SEARCH_UI_STATE", UIState)

local function flatten_results(results)
  local flat = {}
  for _, res in ipairs(results or {}) do
    for _, m in ipairs(res.matches or {}) do
      table.insert(flat, { path = res.path, line = m.line, text = m.text })
    end
  end
  return flat
end

local function open_search_panel()
  local state = get_search_state()
  if not state.query or state.query == "" then return end
  UIState.visible = true
  UIState.scroll = 0
  core.redraw = true
end

local function navigate_to_result(idx)
  local state = get_search_state()
  local flat = flatten_results(state.results)
  if #flat == 0 then return end
  if idx < 1 then idx = #flat end
  if idx > #flat then idx = 1 end
  state.current_result_idx = idx
  local item = flat[idx]
  local ok, doc = pcall(core.open_doc, item.path)
  if not (ok and doc) then
    if core.log then core.log("⚠ [SEARCH] Falha ao abrir: " .. tostring(item.path)) end
    return
  end
  local finder = rawget(_G, "DOXOADE_FIND_VIEW_FOR_DOC")
  if type(finder) == "function" then
    local ev, el = finder(doc)
    if ev and el then
      el.active_view = ev
      if core.root_view and core.root_view.set_active_node then pcall(core.root_view.set_active_node, core.root_view, el) end
      if core.set_active_view then pcall(core.set_active_view, ev) end
      pcall(doc.set_selection, doc, item.line, 1, item.line, 1)
      core.redraw = true; UIState.visible = true
      if core.log then pcall(core.log, string.format("📄 [SEARCH] Focado: %s:%d", item.path:match("[^/\\]+$") or item.path, item.line)) end
      return
    end
  end
  local opener = rawget(_G, "DOXOADE_OPEN_IN_NEW_TAB")
  if type(opener) == "function" then opener(doc) else core.root_view:open_doc(doc) end
  pcall(doc.set_selection, doc, item.line, 1, item.line, 1)
  core.redraw = true; UIState.visible = true
  if core.log then pcall(core.log, string.format("📄 [SEARCH] Nova Aba: %s:%d", item.path:match("[^/\\]+$") or item.path, item.line)) end
end

local original_rootview_draw = RootView.draw
function RootView:draw(...)
  original_rootview_draw(self, ...)
  if not UIState.visible then return end
  local state = get_search_state()
  local flat = flatten_results(state.results)
  if #flat == 0 then UIState.visible = false return end
  local sw, sh = self.size.x, self.size.y
  local font = style.font or style.code_font
  local row_h = font:get_height() + 6
  local header_h, footer_h = 30, 22
  local pw = math.min(sw - 80, 780)
  local rows = math.min(#flat, 12)
  local ph = header_h + rows * row_h + footer_h
  local px, py = math.floor((sw - pw) / 2), math.floor((sh - ph) / 2)
  UIState.panel_rect = { x=px, y=py, w=pw, h=ph }
  local cur = state.current_result_idx or 1
  if cur < 1 then cur = 1 end
  if cur > #flat then cur = #flat end
  local max_scroll = math.max(0, #flat - rows)
  if cur - 1 < UIState.scroll then UIState.scroll = cur - 1 end
  if cur - 1 >= UIState.scroll + rows then UIState.scroll = cur - rows end
  if UIState.scroll > max_scroll then UIState.scroll = max_scroll end
  if UIState.scroll < 0 then UIState.scroll = 0 end

  draw_rect_safe(px-2, py-2, pw+4, ph+4, { 0,0,0,120 })
  draw_rect_safe(px, py, pw, ph, { 10,10,12,245 })
  draw_rect_safe(px, py, pw, 2, style.accent or { 38,188,95,255 })
  local title = string.format("🔍 %q — %d ocorrência(s) em %d arquivo(s)", state.query or "", state.total_hits or #flat, state.total_files or 0)
  draw_text_safe(font, title, px+10, py+8, style.accent or { 38,188,95,255 })
  local cw = 24
  local cx = px + pw - cw - 4
  UIState.close_rect = { x=cx, y=py+4, w=cw, h=cw }
  draw_rect_safe(cx, py+4, cw, cw, { 60,30,30,255 })
  draw_text_safe(font, "X", cx+7, py+7, { 255,180,180,255 })
  draw_rect_safe(px, py+header_h-1, pw, 1, { 40,40,48,255 })

  UIState.row_rects = {}
  core.push_clip_rect(px, py+header_h, pw, rows*row_h)
  for i = 1, rows do
    local idx = UIState.scroll + i
    local item = flat[idx]
    if item then
      local ry = py + header_h + (i-1)*row_h
      local is_cur, is_hov = (idx == cur), (UIState.hovered_idx == idx)
      if is_cur then draw_rect_safe(px+2, ry, pw-4, row_h, { 30,50,40,255 })
      elseif is_hov then draw_rect_safe(px+2, ry, pw-4, row_h, { 25,25,32,255 }) end
      if is_cur then draw_rect_safe(px+2, ry, 3, row_h, style.accent or { 38,188,95,255 }) end
      local short = item.path:match("[^/\\]+$") or item.path
      local label = string.format("%s:%d", short, item.line)
      draw_text_safe(font, label, px+12, ry+3, is_cur and { 255,255,255,255 } or (style.text or { 210,220,230,255 }))
      local lw = font:get_width(label)
      draw_text_safe(font, (item.text or ""):sub(1, 120), px+12+lw+12, ry+3, style.dim or { 140,140,150,255 })
      UIState.row_rects[idx] = { x=px, y=ry, w=pw, h=row_h }
    end
  end
  core.pop_clip_rect()
  local fy = py + header_h + rows*row_h
  draw_rect_safe(px, fy, pw, 1, { 40,40,48,255 })
  draw_text_safe(font, string.format("[%d-%d/%d]  ↑↓ navegar · Enter abrir · F4/Alt+. próximo · Esc fechar",
    UIState.scroll+1, math.min(#flat, UIState.scroll+rows), #flat), px+10, fy+5, style.dim or { 140,140,150,255 })
end

local orig_mouse_moved = RootView.on_mouse_moved
function RootView:on_mouse_moved(x, y, dx, dy)
  if UIState.visible then
    local prev = UIState.hovered_idx
    UIState.hovered_idx = nil
    for idx, r in pairs(UIState.row_rects) do
      if x >= r.x and x <= r.x+r.w and y >= r.y and y <= r.y+r.h then UIState.hovered_idx = idx break end
    end
    if prev ~= UIState.hovered_idx then core.redraw = true end
  end
  return orig_mouse_moved(self, x, y, dx, dy)
end

local orig_mouse_pressed = RootView.on_mouse_pressed
function RootView:on_mouse_pressed(button, x, y, clicks)
  if UIState.visible and (button == "left" or button == 1) then
    local c = UIState.close_rect
    if c and x >= c.x and x <= c.x+c.w and y >= c.y and y <= c.y+c.h then
      command.perform("doxoade:close-search-panel"); return true
    end
    for idx, r in pairs(UIState.row_rects) do
      if x >= r.x and x <= r.x+r.w and y >= r.y and y <= r.y+r.h then
        navigate_to_result(idx); return true
      end
    end
    local p = UIState.panel_rect
    if p and x >= p.x and x <= p.x+p.w and y >= p.y and y <= p.y+p.h then return true end
    command.perform("doxoade:close-search-panel"); return true
  end
  return orig_mouse_pressed(self, button, x, y, clicks)
end

local orig_mouse_wheel = RootView.on_mouse_wheel
function RootView:on_mouse_wheel(y, x, ...)
  if UIState.visible then
    local p = UIState.panel_rect
    if p and x >= p.x and x <= p.x+p.w then
      UIState.scroll = math.max(0, UIState.scroll - (y > 0 and 3 or -3))
      core.redraw = true
      return true
    end
  end
  return orig_mouse_wheel(self, y, x, ...)
end

local function panel_focused()
  return UIState.visible and core.active_view ~= core.command_view
end

command.add(nil, {
  ["doxoade:search-next-result"] = function()
    local s = get_search_state(); local f = flatten_results(s.results)
    if #f == 0 then return end
    navigate_to_result((s.current_result_idx or 1) + 1)
  end,
  ["doxoade:search-prev-result"] = function()
    local s = get_search_state(); local f = flatten_results(s.results)
    if #f == 0 then return end
    navigate_to_result((s.current_result_idx or 1) - 1)
  end,
  ["doxoade:close-search-panel"] = function()
    if not UIState.visible then return end
    UIState.visible = false
    local s = get_search_state(); s.query = ""; s.results = {}
    core.redraw = true
    if core.log then pcall(core.log, "🔍 [SEARCH] Painel flutuante fechado.") end
  end,
  ["doxoade:open-search-dock"] = function() open_search_panel() end,
  ["doxoade:toggle-search-dock"] = function()
    if UIState.visible then command.perform("doxoade:close-search-panel") else open_search_panel() end
  end,
})
command.add(panel_focused, {
  ["doxoade:search-list-down"] = function()
    local s = get_search_state(); navigate_to_result((s.current_result_idx or 1) + 1)
  end,
  ["doxoade:search-list-up"] = function()
    local s = get_search_state(); navigate_to_result((s.current_result_idx or 1) - 1)
  end,
  ["doxoade:search-list-open"] = function()
    local s = get_search_state(); navigate_to_result(s.current_result_idx or 1)
  end,
  ["doxoade:search-list-close"] = function() command.perform("doxoade:close-search-panel") end,
})
keymap.add {
  ["ctrl+."]   = "doxoade:search-next-result",
  ["ctrl+,"]   = "doxoade:search-prev-result",
  ["f4"]       = "doxoade:search-next-result",
  ["shift+f4"] = "doxoade:search-prev-result",
  ["alt+,"]    = "doxoade:search-prev-result",
  ["alt+."]    = "doxoade:search-next-result",
  ["down"]     = "doxoade:search-list-down",
  ["up"]       = "doxoade:search-list-up",
  ["return"]   = "doxoade:search-list-open",
  ["escape"]   = "doxoade:search-list-close",
}
rawset(_G, "DOXOADE_RENDER_SEARCH_RESULTS", open_search_panel)
if core.log then core.log("🔍 [SEARCH] Search Results V49.0 (lista navegável) carregado.") end
