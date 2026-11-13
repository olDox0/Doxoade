-- doxoade/commands/lite_xl_systems/template/18_search_results_dock.lua
--[[
🔍 SEARCH RESULTS DOCK (V48.0 — Painel Flutuante Desacoplado)
- O painel flutuante (centro) é controlado por `UIState.visible`.
- Ao buscar (Alt+F), o painel abre mas NÃO abre aba [Busca].
- Navegação (`<` / `>`) abre o arquivo no painel ATUAL (substitui), mas mantém
  o painel flutuante visível.
- `[X]` fecha o painel. `Esc` também fecha.
- Zero splits, zero race, zero dependência de aba virtual.
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local RootView = require "core.rootview"

-- [FASE 6.5] Importações críticas
local rencache = rawget(_G, "rencache")
  or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer")
  or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if not color or type(color) ~= "table" then color = { 128, 128, 128, 255 } end
  if rencache and rencache.draw_rect then
    pcall(rencache.draw_rect, x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    pcall(native_renderer.draw_rect, x, y, w, h, color)
  end
end

local function draw_text_safe(font, text, x, y, color)
  if not font or not text or text == "" then return end
  if not color or type(color) ~= "table" then color = { 255, 255, 255, 255 } end
  if rencache and rencache.draw_text then
    pcall(rencache.draw_text, font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    pcall(native_renderer.draw_text, font, text, x, y, color)
  end
end

-- ============================================================================
-- Estado (model + UI)
-- ============================================================================
local function get_search_state()
  local state = rawget(_G, "_DOXOADE_SEARCH_STATE")
  if not state then
    state = {
      is_searching = false, query = "", results = {},
      total_hits = 0, total_files = 0, elapsed = 0,
      current_result_idx = 1,
    }
    rawset(_G, "_DOXOADE_SEARCH_STATE", state)
  end
  return state
end

local UIState = {
  visible = false,           -- [FASE 7.0] Controla se o painel aparece
  buttons = {},
  hovered_btn = nil,
  panel_rect = nil,
  close_rect = nil,
}
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

-- ============================================================================
-- Abrir busca (NÃO abre aba)
-- ============================================================================
local function open_search_panel()
  local state = get_search_state()
  if not state.query or state.query == "" then return end

  -- 🛡️ [FASE 3.1] NÃO fecha splits. O painel flutuante desenha por cima
  -- de qualquer layout (RootView:draw já itera todos os nós).
  UIState.visible = true
  core.redraw = true
end

-- ============================================================================
-- Navegação (abre arquivo em NOVA ABA ou foca o existente)
-- ============================================================================
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

  -- 🎯 1. Já está aberto em algum painel? Apenas foca e pula para a linha.
  local finder = rawget(_G, "DOXOADE_FIND_VIEW_FOR_DOC")
  if type(finder) == "function" then
    local existing_view, existing_leaf = finder(doc)
    if existing_view and existing_leaf then
      existing_leaf.active_view = existing_view
      if core.root_view and core.root_view.set_active_node then
        pcall(core.root_view.set_active_node, core.root_view, existing_leaf)
      end
      if core.set_active_view then
        pcall(core.set_active_view, existing_view)
      end
      pcall(doc.set_selection, doc, item.line, 1, item.line, 1)
      core.redraw = true
      UIState.visible = true
      if core.log then
        pcall(core.log, string.format("📄 [SEARCH] Focado: %s:%d", item.path:match("[^/\\]+$") or item.path, item.line))
      end
      return
    end
  end

  -- 🎯 2. Arquivo fechado? Usa a função global para criar nova aba com segurança.
  local opener = rawget(_G, "DOXOADE_OPEN_IN_NEW_TAB")
  if type(opener) == "function" then
    opener(doc)
  else
    core.root_view:open_doc(doc) -- Fallback
  end
  
  pcall(doc.set_selection, doc, item.line, 1, item.line, 1)
  core.redraw = true
  UIState.visible = true
  if core.log then
    pcall(core.log, string.format("📄 [SEARCH] Nova Aba: %s:%d", item.path:match("[^/\\]+$") or item.path, item.line))
  end
end

-- ============================================================================
-- OVERLAY: Painel flutuante (desenhado sempre que UIState.visible)
-- ============================================================================
local original_rootview_draw = RootView.draw

function RootView:draw(...)
  original_rootview_draw(self, ...)

  if not UIState.visible then return end

  local state = get_search_state()
  local flat = flatten_results(state.results)
  if #flat == 0 then
    UIState.visible = false
    return
  end

  local screen_w = self.size.x
  local screen_h = self.size.y
  local font = style.font or style.code_font

  -- Painel centralizado
  local panel_w = math.min(screen_w - 80, 600)
  local panel_h = 52
  local panel_x = math.floor((screen_w - panel_w) / 2)
  local panel_y = math.floor((screen_h - panel_h) / 2)

  UIState.panel_rect = { x = panel_x, y = panel_y, w = panel_w, h = panel_h }

  -- Fundo + borda
  local bg = { 10, 10, 12, 245 }
  local border = style.accent or { 38, 188, 95, 255 }
  draw_rect_safe(panel_x - 2, panel_y - 2, panel_w + 4, panel_h + 4, { 0, 0, 0, 120 })
  draw_rect_safe(panel_x, panel_y, panel_w, panel_h, bg)
  draw_rect_safe(panel_x, panel_y, panel_w, 2, border)

  -- Botão [X] no canto superior direito
  local close_w = 24
  local close_x = panel_x + panel_w - close_w - 4
  local close_y = panel_y + 4
  UIState.close_rect = { x = close_x, y = close_y, w = close_w, h = close_w }
  draw_rect_safe(close_x, close_y, close_w, close_w, { 60, 30, 30, 255 })
  draw_text_safe(font, "X", close_x + 7, close_y + 3, { 255, 180, 180, 255 })

  -- Botões < e >
  local btn_w = 40
  local btn_h = 34
  local btn_y = panel_y + math.floor((panel_h - btn_h) / 2)
  local btn_left_x = panel_x + 10
  local btn_right_x = panel_x + panel_w - btn_w - 40

  local function draw_btn(x, y, w, h, label, id)
    local is_hover = (UIState.hovered_btn == id)
    local bcol = is_hover and { 50, 60, 75, 255 } or { 40, 40, 48, 255 }
    draw_rect_safe(x, y, w, h, bcol)
    draw_text_safe(font, label, x + 12, y + 8, { 255, 255, 255, 255 })
    UIState.buttons[id] = { x = x, y = y, w = w, h = h }
  end

  draw_btn(btn_left_x, btn_y, btn_w, btn_h, "<", "prev")
  draw_btn(btn_right_x, btn_y, btn_w, btn_h, ">", "next")

  -- Texto central: [N/M] arquivo:linha
  local cur_idx = state.current_result_idx or 1
  if cur_idx > #flat then cur_idx = 1 end
  local item = flat[cur_idx]
  local short_path = item.path:match("[^/\\]+$") or item.path
  local info = string.format("[%d/%d]  %s:%d", cur_idx, #flat, short_path, item.line)
  local info_w = font:get_width(info)
  local text_x = panel_x + math.floor((panel_w - info_w) / 2)
  local text_y = panel_y + math.floor((panel_h - font:get_height()) / 2)
  draw_text_safe(font, info, text_x, text_y, { 210, 210, 220, 255 })
end

-- ============================================================================
-- Interação com o painel
-- ============================================================================
local original_rootview_mouse_pressed = RootView.on_mouse_pressed

function RootView:on_mouse_pressed(button, x, y, clicks)
  if UIState.visible then
    -- [FASE 7.1] Bloqueia TODOS os cliques enquanto o painel está visível
    -- para evitar vazamento para o editor/bottom-shelf atrás.
    if button == "left" or button == 1 then
      if UIState.close_rect and
         x >= UIState.close_rect.x and x <= UIState.close_rect.x + UIState.close_rect.w and
         y >= UIState.close_rect.y and y <= UIState.close_rect.y + UIState.close_rect.h then
        command.perform("doxoade:close-search-panel")
        return true
      end
      for id, r in pairs(UIState.buttons or {}) do
        if x >= r.x and x <= r.x + r.w and y >= r.y and y <= r.y + r.h then
          if id == "prev" then command.perform("doxoade:search-prev-result")
          elseif id == "next" then command.perform("doxoade:search-next-result") end
          return true
        end
      end
      if UIState.panel_rect and
         x >= UIState.panel_rect.x and x <= UIState.panel_rect.x + UIState.panel_rect.w and
         y >= UIState.panel_rect.y and y <= UIState.panel_rect.y + UIState.panel_rect.h then
        return true
      end
      -- [FASE 7.1] Clique fora do painel fecha o painel (UX comum).
      command.perform("doxoade:close-search-panel")
      return true
    end
    -- Bloqueia cliques de botão direito/middle também.
    return true
  end
  return original_rootview_mouse_pressed(self, button, x, y, clicks)
end

local original_rootview_mouse_moved = RootView.on_mouse_moved

function RootView:on_mouse_moved(x, y, dx, dy)
  if UIState.visible then
    local prev = UIState.hovered_btn
    UIState.hovered_btn = nil
    for id, r in pairs(UIState.buttons or {}) do
      if x >= r.x and x <= r.x + r.w and y >= r.y and y <= r.y + r.h then
        UIState.hovered_btn = id
        break
      end
    end
    if prev ~= UIState.hovered_btn then core.redraw = true end
  end
  return original_rootview_mouse_moved(self, x, y, dx, dy)
end

-- ============================================================================
-- Comandos
-- ============================================================================
command.add(nil, {
  ["doxoade:search-next-result"] = function()
    local state = get_search_state()
    local flat = flatten_results(state.results)
    if #flat == 0 then return end
    navigate_to_result((state.current_result_idx or 1) + 1)
  end,

  ["doxoade:search-prev-result"] = function()
    local state = get_search_state()
    local flat = flatten_results(state.results)
    if #flat == 0 then return end
    navigate_to_result((state.current_result_idx or 1) - 1)
  end,

  ["doxoade:close-search-panel"] = function()
    if not UIState.visible then return end  -- [FASE 7.1] No-op se já fechado
    UIState.visible = false
    local state = get_search_state()
    state.query = ""
    state.results = {}
    core.redraw = true
    if core.log then
      pcall(core.log, "🔍 [SEARCH] Painel flutuante fechado.")
    end
  end,

  ["doxoade:open-search-dock"] = function()
    open_search_panel()
  end,

  ["doxoade:toggle-search-dock"] = function()
    if UIState.visible then
      command.perform("doxoade:close-search-panel")
    else
      open_search_panel()
    end
  end,
})

-- ============================================================================
-- Keymaps
-- ============================================================================
keymap.add {
  ["ctrl+."]          = "doxoade:search-next-result",
  ["ctrl+,"]          = "doxoade:search-prev-result",
  ["f4"]              = "doxoade:search-next-result",
  ["shift+f4"]        = "doxoade:search-prev-result",
  ["alt+,"]           = "doxoade:search-prev-result",
  ["alt+."]           = "doxoade:search-next-result",
}

-- ============================================================================
-- API pública (chamada pelo módulo 07 quando busca termina)
-- ============================================================================
rawset(_G, "DOXOADE_RENDER_SEARCH_RESULTS", open_search_panel)

if core.log then
  core.log("🔍 [SEARCH] Search Results V48.0 (painel desacoplado) carregado.")
end
