-- doxoade/commands/lite_xl_systems/template/19d_bottom_shelf_hub.lua
--[[
  🖥️ DOXOADE BOTTOM SHELF HUB & ROUTING (V32.0 PTY & Canvas Alinhados)
  - Integração total com o TerminalRealEngine (PTY Nativo) e CanvasStudio (HD).
  - Isolamento estrito de input de teclado (zero vazamento para o DocView).
  - Botões do header sincronizados com ações reais do PTY e alternância de Shells.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local RootView = require "core.rootview"
local command = require "core.command"
local keymap = require "core.keymap"
local style = require "core.style"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

-- =============================================================================
-- 🎨 PILAR 3: PALETA ESTÁTICA PINNED (Zero Churn de Tabelas na Heap)
-- =============================================================================
local COLOR_BG_PANEL    = { 10, 10, 10, 255 }
local COLOR_HEADER_BG   = { 16, 16, 16, 255 }
local COLOR_BORDER_LINE = { 35, 35, 35, 255 }
local COLOR_PROMPT_DIR  = { 34, 197, 94, 255 }
local COLOR_TEXT_DIM    = { 150, 150, 150, 255 }
local COLOR_TEXT_BRIGHT = { 255, 255, 255, 255 }
local COLOR_DEF_TEXT    = { 220, 220, 220, 255 }
local COLOR_BTN_HOVER   = { 35, 35, 35, 255 }
local COLOR_BTN_ACTIVE  = { 0, 0, 0, 255 }

local function draw_rect_safe(x, y, w, h, color)
  if not color or type(color) ~= "table" then color = { 128, 128, 128, 255 } end
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

local ShelfHub = {
  visible = false,
  is_maximized = false,
  header_height = 30,
  active_tab = "terminal",
  hovered_tab = nil,
  hovered_btn = nil,
  hovered_close = false,
  tabs = {
    { id = "terminal", label = "Terminal (PTY Real)" },
    { id = "canvas",   label = "Canvas SDL2 (Prints)" },
  },
  action_buttons = {},
}

rawset(_G, "_DOXOADE_SHELF_HUB", ShelfHub)

function ShelfHub:ensure_initialized(tab_id)
  tab_id = tab_id or self.active_tab
  if tab_id == "terminal" then
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term and term.ensure_started then
      term:ensure_started()
    end
  end
end

function ShelfHub:draw()
  if not self.visible then return end
  if not self._is_ready then
    self:ensure_initialized()
    self._is_ready = true
  end

  local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
  local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
  local font = (term and term:get_font()) or style.font
  local screen_w = core.root_view.size.x
  local screen_h = core.root_view.size.y

  -- 🎯 PILAR 3: Elimina o draw_rect_safe de 2 milhões de pixels (Economia de ~45ms no SDL2!)
  -- Em vez de escurecer a tela inteira com alpha, calcula a moldura sólida:
  local x, y, w, h
  if self.is_maximized then
    x, y, w, h = 8, 8, screen_w - 16, screen_h - 16
  else
    w = math.min(screen_w - 24, math.max(850, math.floor(screen_w * 0.88)))
    h = math.min(screen_h - 24, math.max(540, math.floor(screen_h * 0.84)))
    x = math.floor((screen_w - w) / 2)
    y = math.floor((screen_h - h) / 2)
  end
  self.card_rect = { x = x, y = y, w = w, h = h }

  -- Moldura sólida de alta performance (sem alpha blending na CPU)
  draw_rect_safe(x - 2, y - 2, w + 4, h + 4, COLOR_BORDER_LINE)
  draw_rect_safe(x, y, w, h, COLOR_BG_PANEL)
  draw_rect_safe(x, y, w, 2, style.accent or COLOR_PROMPT_DIR)
  draw_rect_safe(x, y + 2, w, self.header_height, COLOR_HEADER_BG)
  draw_rect_safe(x, y + self.header_height + 1, w, 1, COLOR_BORDER_LINE)

  -- 3. Abas do Header
  local tab_x = x + 12
  for i, tab in ipairs(self.tabs) do
    local is_active = (self.active_tab == tab.id)
    local is_hovered = (self.hovered_tab == i)
    local tab_w = font:get_width(tab.label) + 18
    local tab_h = self.header_height - 6

    if is_active then
      draw_rect_safe(tab_x, y + 4, tab_w, tab_h, { 0, 0, 0, 255 })
      draw_rect_safe(tab_x, y + 4, tab_w, 2, style.accent or { 38, 188, 95, 255 })
    elseif is_hovered then
      draw_rect_safe(tab_x, y + 4, tab_w, tab_h, { 30, 30, 30, 255 })
    end

    local text_color = is_active and (style.accent or { 38, 188, 95, 255 }) or { 150, 150, 150, 255 }
    draw_text_safe(font, tab.label, tab_x + 9, y + 7, text_color)
    tab.rect = { x = tab_x, y = y + 4, w = tab_w, h = tab_h }
    tab_x = tab_x + tab_w + 6
  end

  -- 4. Botões Dinâmicos de Ação
  local dynamic_buttons = {}
  if self.active_tab == "terminal" then
    dynamic_buttons = {
      {
        id = "shell",
        label = string.format("[%s]", term and term:short_shell_label() or "SHELL"),
        action = function() if term then term:cycle_shell() end end,
      },
      {
        id = "interrupt",
        label = "[⛔ Ctrl+C]",
        action = function() if term then term:send_interrupt() end end,
      },
      {
        id = "copy",
        label = "[Copiar]",
        action = function() if term then term:copy_output() end end,
      },
      {
        id = "paste",
        label = "[Colar]",
        action = function() if term then term:paste_clipboard() end end,
      },
      {
        id = "clear",
        label = "[Limpar]",
        action = function() if term then term:clear_screen() end end,
      },
      {
        id = "term_ext",
        label = "[> Externo]",
        action = function() if term then term:launch_external_terminal(false) end end,
      },
      {
        id = "admin",
        label = "[🛡️ Admin]",
        action = function() if term then term:launch_external_terminal(true) end end,
      },
      {
        id = "maximize",
        label = self.is_maximized and "[Restaurar]" or "[Tela Cheia]",
        action = function() command.perform("doxoade:bottom-shelf-toggle-maximize") end,
      },
    }
  elseif self.active_tab == "canvas" and canvas then
    dynamic_buttons = {
      { id = "paste_img", label = "[Colar Print (Ctrl+V)]", action = function() canvas:paste_clipboard_image() end },
      { id = "copy_img",  label = "[Copiar Imagem]",        action = function() canvas:copy_image_to_clipboard() end },
      { id = "open_ext",  label = "[Abrir Externo]",        action = function() canvas:open_image_external() end },
      { id = "mode_1to1", label = canvas.mode_1to1 and "[Ajustar]" or "[1:1 Real]", action = function()
          canvas.mode_1to1 = not canvas.mode_1to1
          canvas.zoom = 1.0; canvas.pan_x = 0; canvas.pan_y = 0
          core.redraw = true
        end
      },
      { id = "clear_img", label = "[Limpar]", action = function() canvas:clear() end },
    }
  end
  self.action_buttons = dynamic_buttons

  local btn_x = tab_x + 16
  for i, btn in ipairs(self.action_buttons) do
    local bw = font:get_width(btn.label) + 10
    local bh = self.header_height - 8
    local is_hovered = (self.hovered_btn == i)

    if btn_x + bw < x + w - 32 then
      if is_hovered then draw_rect_safe(btn_x, y + 5, bw, bh, { 35, 35, 35, 255 }) end
      draw_text_safe(font, btn.label, btn_x + 5, y + 7, is_hovered and (style.accent or { 38, 188, 95, 255 }) or { 56, 189, 248, 255 })
      btn.rect = { x = btn_x, y = y + 5, w = bw, h = bh }
      btn_x = btn_x + bw + 6
    end
  end

  -- Botão Fechar [X]
  local close_w = 22
  local close_x = x + w - close_w - 10
  local close_y = y + 4
  if self.hovered_close then draw_rect_safe(close_x, close_y, close_w, self.header_height - 6, { 200, 50, 50, 200 }) end
  draw_text_safe(font, "[X]", close_x + 2, close_y + 3, self.hovered_close and { 255, 255, 255, 255 } or { 150, 150, 150, 255 })
  self.close_rect = { x = close_x, y = close_y, w = close_w, h = self.header_height - 6 }

  -- 5. Viewport de Conteúdo (Terminal ou Canvas)
  local canvas_y = y + self.header_height + 2
  local canvas_h = h - self.header_height - 34

  core.push_clip_rect(x + 2, canvas_y, w - 4, canvas_h)

  if self.active_tab == "terminal" and term then
    local line_h = font:get_height() + 2
    local max_line_w = w - 32

    -- 🎯 VIEWPORT CULLING O(1): Calcula estritamente a janela visível
    local total_lines = #term.lines
    local start_idx = math.max(1, math.floor(term.scroll_y / line_h))
    local visible_count = math.ceil(canvas_h / line_h) + 2
    local end_idx = math.min(total_lines, start_idx + visible_count)

    local cur_y = canvas_y + 6 + ((start_idx - 1) * line_h) - term.scroll_y

    -- Itera APENAS nas ~25 linhas visíveis na tela
    for i = start_idx, end_idx do
      local item = term.lines[i]
      local seg_x = x + 14

      if item and item.segments then
        for _, seg in ipairs(item.segments) do
          local text_val = seg.text or ""
          local style_col = (seg.style and seg.style.fg) or seg.fg or { 220, 220, 220, 255 }

          if text_val:find("^%(venv%)") or text_val:find("^[a-zA-Z]:\\.*>") then
            --style_col = { 34, 197, 94, 255 }
            style_col = COLOR_PROMPT_DIR
          end

          local text_w = font:get_width(text_val)

          if seg_x + text_w > x + max_line_w and seg_x > x + 14 then
            cur_y = cur_y + line_h
            seg_x = x + 14
          end

          if cur_y + line_h > canvas_y and cur_y < canvas_y + canvas_h then
            draw_text_safe(font, text_val, seg_x, cur_y, style_col)
          end
          seg_x = seg_x + text_w
        end
      end
      cur_y = cur_y + line_h
    end

    -- Desenha o prompt ativo
    local cur_line_segs = term._client and term._client.current_line
    if cur_line_segs and #cur_line_segs > 0 and cur_y < canvas_y + canvas_h then
      local seg_x = x + 14
      for _, seg in ipairs(cur_line_segs) do
        local text_val = seg.text or ""
        local style_col = (seg.style and seg.style.fg) or seg.fg or { 34, 197, 94, 255 }
        draw_text_safe(font, text_val, seg_x, cur_y, style_col)
        seg_x = seg_x + font:get_width(text_val)
      end
    end
  elseif self.active_tab == "canvas" and canvas then
    canvas:draw_viewport(x + 2, canvas_y, w - 4, canvas_h)
  end

  core.pop_clip_rect()

  -- 6. Barra Inferior de Entrada e Autocomplete
  local input_y = y + h - 30
  draw_rect_safe(x + 1, input_y, w - 2, 29, { 10, 10, 10, 255 })
  draw_rect_safe(x + 1, input_y, w - 2, 1, style.accent or { 38, 188, 95, 255 })

  if self.active_tab == "terminal" and term then
    local tag = term.is_executing and "[RODANDO]" or "[PTY]"
    local tag_col = term.is_executing and { 251, 191, 36, 255 } or (style.accent or { 38, 188, 95, 255 })
    draw_text_safe(font, tag, x + 14, input_y + 6, tag_col)
    local p_off = font:get_width(tag) + 24

    if term._all_selected and #term.input_text > 0 then
      local sel_w = font:get_width("> " .. term.input_text)
      draw_rect_safe(x + p_off, input_y + 4, sel_w + 4, font:get_height() + 4, { 56, 189, 248, 80 })
    end

    draw_text_safe(font, "> " .. term.input_text, x + p_off, input_y + 6, { 255, 255, 255, 255 })

    -- Ghost Text Inline
    if #term.suggestions > 0 and term.input_text ~= "" and not term._all_selected then
      local top_sug = term.suggestions[term.suggestion_idx or 1]
      if top_sug and top_sug:sub(1, #term.input_text):lower() == term.input_text:lower() then
        local ghost_part = top_sug:sub(#term.input_text + 1)
        local ghost_x = x + p_off + font:get_width("> " .. term.input_text)
        draw_text_safe(font, ghost_part, ghost_x, input_y + 6, { 110, 110, 110, 220 })
      end
    end

    -- Cursor piscante
    local text_before = term.input_text:sub(1, term.input_cursor - 1)
    local cx = x + p_off + font:get_width("> " .. text_before)
    draw_rect_safe(cx, input_y + 6, 2, font:get_height(), style.accent or { 38, 188, 95, 255 })

    -- Dropdown de sugestões
    if #term.suggestions > 0 and term.input_text ~= "" then
      local sug_count = math.min(5, #term.suggestions)
      local item_h = font:get_height() + 4
      local drop_h = (sug_count * item_h) + 6
      local drop_y = input_y - drop_h - 2
      local drop_w = math.min(w - 28, 520)

      draw_rect_safe(x + 14, drop_y, drop_w, drop_h, { 18, 18, 22, 245 })
      draw_rect_safe(x + 14, drop_y, drop_w, 1, style.accent or { 38, 188, 95, 255 })
      draw_rect_safe(x + 14, drop_y, 2, drop_h, style.accent or { 38, 188, 95, 255 })

      for s_i = 1, sug_count do
        local sug_str = term.suggestions[s_i]
        local is_active_sug = (s_i == term.suggestion_idx)
        local s_y = drop_y + 3 + (s_i - 1) * item_h
        if is_active_sug then
          draw_rect_safe(x + 16, s_y, drop_w - 4, item_h, { 35, 40, 50, 255 })
          draw_text_safe(font, "> " .. sug_str, x + 20, s_y + 2, style.accent or { 38, 188, 95, 255 })
        else
          draw_text_safe(font, "  " .. sug_str, x + 20, s_y + 2, { 180, 180, 180, 255 })
        end
      end
    end
  elseif canvas then
    local mode_str = canvas.mode_1to1 and "1:1 Real" or "Ajustado"
    local zoom_lbl = string.format("[%s | Zoom: %d%%] ", mode_str, math.floor(canvas.zoom * 100))
    draw_text_safe(font, zoom_lbl, x + 14, input_y + 6, style.accent or { 38, 188, 95, 255 })
    draw_text_safe(font, canvas.status_msg or "", x + 14 + font:get_width(zoom_lbl), input_y + 6, { 150, 150, 150, 255 })
  end
end

-- =============================================================================
-- 🖱️ HOOKS GLOBAIS DE JANELA, MOUSE E ROLAGEM
-- =============================================================================
local original_rootview_draw = RootView.draw
function RootView:draw(...)
  original_rootview_draw(self, ...)
  if ShelfHub.visible then ShelfHub:draw() end
end

local original_rootview_on_mouse_moved = RootView.on_mouse_moved
function RootView:on_mouse_moved(x, y, dx, dy)
  if ShelfHub.visible then
    local r = ShelfHub.card_rect
    local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
    ShelfHub.hovered_tab = nil
    ShelfHub.hovered_btn = nil
    ShelfHub.hovered_close = false

    if canvas and canvas.is_panning and ShelfHub.active_tab == "canvas" then
      canvas.pan_x = canvas.pan_x + dx
      canvas.pan_y = canvas.pan_y + dy
      core.redraw = true
      return true
    end

    if r and x >= r.x and x <= r.x + r.w and y >= r.y and y <= r.y + r.h then
      for i, tab in ipairs(ShelfHub.tabs) do
        if tab.rect and x >= tab.rect.x and x <= tab.rect.x + tab.rect.w and y >= tab.rect.y and y <= tab.rect.y + tab.rect.h then
          ShelfHub.hovered_tab = i; core.redraw = true; return true
        end
      end
      for i, btn in ipairs(ShelfHub.action_buttons) do
        if btn.rect and x >= btn.rect.x and x <= btn.rect.x + btn.rect.w and y >= btn.rect.y and y <= btn.rect.y + btn.rect.h then
          ShelfHub.hovered_btn = i; core.redraw = true; return true
        end
      end
      if ShelfHub.close_rect and x >= ShelfHub.close_rect.x and x <= ShelfHub.close_rect.x + ShelfHub.close_rect.w and
         y >= ShelfHub.close_rect.y and y <= ShelfHub.close_rect.y + ShelfHub.close_rect.h then
        ShelfHub.hovered_close = true; core.redraw = true; return true
      end
      core.redraw = true
      return true
    end
    core.redraw = true
    return true
  end
  if original_rootview_on_mouse_moved then return original_rootview_on_mouse_moved(self, x, y, dx, dy) end
end

local original_rootview_on_mouse_pressed = RootView.on_mouse_pressed
function RootView:on_mouse_pressed(button, x, y, clicks)
  if ShelfHub.visible then
    local r = ShelfHub.card_rect
    local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")

    if r and (x < r.x or x > r.x + r.w or y < r.y or y > r.y + r.h) then
      ShelfHub.visible = false; core.redraw = true; return true
    end
    for i, tab in ipairs(ShelfHub.tabs) do
      if tab.rect and x >= tab.rect.x and x <= tab.rect.x + tab.rect.w and y >= tab.rect.y and y <= tab.rect.y + tab.rect.h then
        ShelfHub.active_tab = tab.id
        ShelfHub:ensure_initialized(tab.id)
        core.redraw = true
        return true
      end
    end
    for _, btn in ipairs(ShelfHub.action_buttons) do
      if btn.rect and x >= btn.rect.x and x <= btn.rect.x + btn.rect.w and y >= btn.rect.y and y <= btn.rect.y + btn.rect.h then
        if btn.action then btn.action(); return true end
      end
    end
    if ShelfHub.hovered_close then
      ShelfHub.visible = false; core.redraw = true; return true
    end
    if ShelfHub.active_tab == "canvas" and canvas and (button == "left" or button == 1) then
      canvas.is_panning = true
      return true
    end
    return true
  end
  if original_rootview_on_mouse_pressed then return original_rootview_on_mouse_pressed(self, button, x, y, clicks) end
end

local original_rootview_on_mouse_released = RootView.on_mouse_released
function RootView:on_mouse_released(button, x, y)
  if ShelfHub.visible then
    local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
    if canvas then canvas.is_panning = false end
    core.redraw = true
    return true
  end
  if original_rootview_on_mouse_released then return original_rootview_on_mouse_released(self, button, x, y) end
end

local original_rootview_on_mouse_wheel = RootView.on_mouse_wheel
function RootView:on_mouse_wheel(delta)
  if ShelfHub.visible then
    local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")

    if ShelfHub.active_tab == "terminal" and term then
      term:scroll_by(delta * 40)
      core.redraw = true
      return true
    elseif ShelfHub.active_tab == "canvas" and canvas then
      canvas.zoom = (delta > 0) and math.min(6.0, canvas.zoom * 1.2) or math.max(0.1, canvas.zoom * 0.8)
      core.redraw = true
      return true
    end
    return true
  end
  return original_rootview_on_mouse_wheel(self, delta)
end

local original_rootview_on_text_input = RootView.on_text_input
function RootView:on_text_input(text)
  if ShelfHub.visible and ShelfHub.active_tab == "terminal" then
    if not text or text == "" or text:find("^[%z\1-\31\127]") then
      return true
    end
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      if term._all_selected then
        term.input_text = text
        term.input_cursor = #text + 1
        term._all_selected = false
      else
        term.input_text = term.input_text:sub(1, term.input_cursor - 1) .. text .. term.input_text:sub(term.input_cursor)
        term.input_cursor = term.input_cursor + #text
      end
      term:update_suggestions()
      core.redraw = true
      return true
    end
  end
  return original_rootview_on_text_input(self, text)
end

-- =============================================================================
-- ⌨️ COMANDOS E KEYMAPS SOBERANOS DO BOTTOM SHELF
-- =============================================================================
command.add(nil, {
  ["doxoade:toggle-bottom-shelf"] = function()
    ShelfHub.visible = not ShelfHub.visible
    if ShelfHub.visible then
      ShelfHub:ensure_initialized()
    end
    core.redraw = true
    if core.log then
      core.log(ShelfHub.visible and "🖥️ Console Studio aberto." or "🖥️ Console Studio recolhido.")
    end
  end,
  ["doxoade:bottom-shelf-toggle-maximize"] = function()
    if ShelfHub.visible then
      ShelfHub.is_maximized = not ShelfHub.is_maximized
      core.redraw = true
    end
  end,
  -- ✅ ALIAS DE RETROCOMPATIBILIDADE RESTAURADO:
  ["doxoade:terminal-launch-admin-venv"] = function()
    command.perform("doxoade:terminal-launch-admin")
  end,
})

-- Comandos Condicionais com Foco Ativo (Elimina 100% dos órfãos da auditoria)
command.add(function() return ShelfHub.visible end, {
  ["bottom-shelf:close"] = function()
    ShelfHub.visible = false
    core.redraw = true
    return true
  end,
  ["bottom-shelf:escape"] = function()
    return command.perform("bottom-shelf:close")
  end,
  ["bottom-shelf:interrupt"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term:send_interrupt() end
    return true
  end,
  ["bottom-shelf:clear"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term:clear_screen() end
    return true
  end,
  ["bottom-shelf:select-all"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term and term.select_all_or_home then
      term:select_all_or_home()
    end
    return true
  end,

  ["bottom-shelf:delete-word"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term and term.delete_word_backwards then
      term:delete_word_backwards()
    end
    return true
  end,

  ["bottom-shelf:paste"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
    local clip = system.get_clipboard and system.get_clipboard()
--      local clip = system.get_clipboard()
      if clip and clip ~= "" then
        clip = clip:gsub("[\r\n]+", " ")
        if term._all_selected then
          term.input_text = clip
          term._all_selected = false
        else
          local cur = term.input_cursor or (#term.input_text + 1)
          local before = term.input_text:sub(1, cur - 1)
          local after = term.input_text:sub(cur)
          term.input_text = before .. clip .. after
        end
        term.input_cursor = (term.input_cursor or 1) + #clip
        core.redraw = true
      end
    end
    return true
  end,
  ["bottom-shelf:copy"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if ShelfHub.active_tab == "canvas" then
      local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
      if canvas then canvas:copy_image_to_clipboard() end
    elseif ShelfHub.active_tab == "terminal" and term then
      if term._all_selected and #term.input_text > 0 then
        if system and system.set_clipboard then system.set_clipboard(term.input_text) end
      else
        term:copy_output()
      end
    end
    return true
  end,
  ["bottom-shelf:submit"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      term._all_selected = false
      term:execute_command(term.input_text)
    end
    return true
  end,
  ["bottom-shelf:tab-complete"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term:handle_tab_completion() end
    return true
  end,
  ["bottom-shelf:backspace"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      if term._all_selected then
        term.input_text = ""
        term.input_cursor = 1
        term._all_selected = false
      elseif term.input_cursor > 1 then
        term.input_text = term.input_text:sub(1, term.input_cursor - 2) .. term.input_text:sub(term.input_cursor)
        term.input_cursor = term.input_cursor - 1
      end
      term:update_suggestions()
      core.redraw = true
    end
    return true
  end,
  ["bottom-shelf:delete"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      if term._all_selected then
        term.input_text = ""
        term.input_cursor = 1
        term._all_selected = false
      elseif term.input_cursor <= #term.input_text then
        term.input_text = term.input_text:sub(1, term.input_cursor - 1) .. term.input_text:sub(term.input_cursor + 1)
      end
      term:update_suggestions()
      core.redraw = true
    end
    return true
  end,
  ["bottom-shelf:start-of-line"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      term.input_cursor = 1
      term._all_selected = false
      core.redraw = true
    end
    return true
  end,
  ["bottom-shelf:end-of-line"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      term.input_cursor = #term.input_text + 1
      term._all_selected = false
      core.redraw = true
    end
    return true
  end,
  ["bottom-shelf:previous-char"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      term.input_cursor = math.max(1, term.input_cursor - 1)
      term._all_selected = false
      core.redraw = true
    end
    return true
  end,
  ["bottom-shelf:next-char"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      term.input_cursor = math.min(#term.input_text + 1, term.input_cursor + 1)
      term._all_selected = false
      core.redraw = true
    end
    return true
  end,
  ["bottom-shelf:nav-up"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if not term then return true end
    if #term.suggestions > 0 and term.input_text ~= "" then
      term.suggestion_idx = (term.suggestion_idx - 2 + #term.suggestions) % #term.suggestions + 1
      core.redraw = true
      return true
    end
    if #term.history > 0 then
      term.history_idx = math.max(1, term.history_idx - 1)
      term.input_text = term.history[term.history_idx] or ""
      term.input_cursor = #term.input_text + 1
      term._all_selected = false
      core.redraw = true
    end
    return true
  end,
  ["bottom-shelf:nav-down"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if not term then return true end
    if #term.suggestions > 0 and term.input_text ~= "" then
      term.suggestion_idx = (term.suggestion_idx % #term.suggestions) + 1
      core.redraw = true
      return true
    end
    if term.history_idx < #term.history then
      term.history_idx = term.history_idx + 1
      term.input_text = term.history[term.history_idx] or ""
      term.input_cursor = #term.input_text + 1
    else
      term.history_idx = #term.history + 1
      term.input_text = ""
      term.input_cursor = 1
    end
    term._all_selected = false
    core.redraw = true
    return true
  end,
  ["bottom-shelf:interrupt"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term:send_interrupt() end
  end,
  ["bottom-shelf:page-up"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term:scroll_by(300) end
  end,
  ["bottom-shelf:page-down"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term:scroll_by(-300) end
  end,
})
   
 keymap.add {

 }

keymap.add {
  ["ctrl+`"]       = "doxoade:toggle-bottom-shelf",
  ["ctrl+j"]       = "doxoade:toggle-bottom-shelf",
  ["alt+return"]   = "doxoade:bottom-shelf-toggle-maximize",
  ["escape"]       = "bottom-shelf:close",
  ["ctrl+sift+c"]  = "bottom-shelf:copy",
  ["ctrl+c"]       = "bottom-shelf:interrupt",
  ["pageup"]       = "bottom-shelf:page-up",
  ["pagedown"]     = "bottom-shelf:page-down",
  ["ctrl+v"]       = "bottom-shelf:paste",
  ["ctrl+a"]       = "bottom-shelf:select-all",
  ["ctrl+backspace"]= "bottom-shelf:delete-word",
  ["return"]       = "bottom-shelf:submit",
  ["keypad enter"] = "bottom-shelf:submit",
  ["tab"]          = "bottom-shelf:tab-complete",
  ["backspace"]    = "bottom-shelf:backspace",
  ["delete"]       = "bottom-shelf:delete",
  ["home"]         = "bottom-shelf:start-of-line",
  ["end"]          = "bottom-shelf:end-of-line",
  ["left"]         = "bottom-shelf:previous-char",
  ["right"]        = "bottom-shelf:next-char",
  ["up"]           = "bottom-shelf:nav-up",
  ["down"]         = "bottom-shelf:nav-down",
}
