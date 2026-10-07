-- doxoade/commands/lite_xl_systems/template/19d_bottom_shelf_hub.lua
--[[
  🖥️ DOXOADE BOTTOM SHELF HUB — ESCADA DINÂMICA TRIPLA & MULTI-PROJETOS (V41.0)
  - Escada Adaptativa de 3 Andares para resoluções verticais estreitas:
      • Andar 1: Abas Mestras + Badge de Escada ([3L·A]) + Maximizar + Fechar [X].
      • Andar 2: Sessões de Projetos Concorrentes ([ 1: doxoade ], [ 2: SysUtils ], [+]) + CWD HUD.
      • Andar 3: Ações do PTY ([CMD], [Ctrl+C], [Copiar], [Colar], [Limpar], [Externo], [Admin]).
  - Fundo sutil com matiz única por projeto e marca d'água centralizada.
  - Funções de cor em escopo estrito no topo (zero crash de strict.lua).
  - Canvas SDL2, prints inline e sketch 100% preservados.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local RootView = require "core.rootview"
local command = require "core.command"
local keymap = require "core.keymap"
local style = require "core.style"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

-- ── Paleta Estática ───────────────────────────────────────────────────────────
local COLOR_BG_PANEL    = { 10, 10, 10, 255 }
local COLOR_HEADER_BG   = { 16, 16, 16, 255 }
local COLOR_BORDER_LINE = { 35, 35, 35, 255 }
local COLOR_PROMPT_DIR  = { 34, 197, 94, 255 }
local COLOR_TEXT_DIM    = { 150, 150, 150, 255 }
local COLOR_TEXT_BRIGHT = { 255, 255, 255, 255 }

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

-- ── Gerador de Cor de Fundo Ultra-Escura & Fiel por Projeto (EM ESCOPO TOPO) ──
local function hash_string(str)
  local h = 5381
  for i = 1, #str do
    h = ((h * 33) + str:byte(i)) % 2147483647
  end
  return h
end

local function get_project_tint(proj_str)
  if not proj_str or proj_str == "" then return { 10, 10, 12, 255 } end
  local h = hash_string(proj_str:lower())
  local hue = (h % 360) / 360
  local s = 0.28   -- Saturação suave
  local l = 0.055  -- 🎯 Luminosidade ultra-escura (tons entre 8 e 20)

  local function hue2rgb(p, q, t)
    if t < 0 then t = t + 1 end
    if t > 1 then t = t - 1 end
    if t < 1/6 then return p + (q - p) * 6 * t end
    if t < 1/2 then return q end
    if t < 2/3 then return p + (q - p) * (2/3 - t) * 6 end
    return p
  end

  local q = l < 0.5 and (l * (1 + s)) or (l + s - l * s)
  local p = 2 * l - q
  local r = math.floor(hue2rgb(p, q, hue + 1/3) * 255)
  local g = math.floor(hue2rgb(p, q, hue) * 255)
  local b = math.floor(hue2rgb(p, q, hue - 1/3) * 255)
  return { r, g, b, 255 }
end

local ShelfHub = {
  visible = false,
  is_maximized = false,
  layout_mode = "auto", -- "auto" | "triple" | "dual" | "single"
  header_height = 30,
  active_tab = "terminal",
  hovered_tab = nil,
  hovered_btn = nil,
  hovered_session = nil,
  hovered_layout = false,
  hovered_close = false,
  is_selecting_output = false,
  is_selecting_input = false,
  tabs = {
    { id = "terminal", label = "Terminal", short_label = "Terminal" },
    { id = "canvas",   label = "Canvas SDL2", short_label = "Canvas" },
  },
  action_buttons = {},
  session_buttons = {},
}

rawset(_G, "_DOXOADE_SHELF_HUB", ShelfHub)

local function get_tier_count(total_w, total_h)
  if ShelfHub.layout_mode == "triple" then return 3 end
  if ShelfHub.layout_mode == "dual"   then return 2 end
  if ShelfHub.layout_mode == "single" then return 1 end

  if (total_h > total_w) or (total_w < 780) then
    return 3
  elseif total_w < 980 then
    return 2
  end
  return 1
end

function ShelfHub:toggle_layout_mode()
  if self.layout_mode == "auto" then
    self.layout_mode = "triple"
    core.log("📐 [SHELF] Modo Forçado: 3 Andares (Escada Tripla).")
  elseif self.layout_mode == "triple" then
    self.layout_mode = "dual"
    core.log("📐 [SHELF] Modo Forçado: 2 Andares.")
  elseif self.layout_mode == "dual" then
    self.layout_mode = "single"
    core.log("📐 [SHELF] Modo Forçado: 1 Andar (Compacto).")
  else
    self.layout_mode = "auto"
    core.log("📐 [SHELF] Modo Responsivo Automático.")
  end
  core.redraw = true
end

function ShelfHub:ensure_initialized(tab_id)
  tab_id = tab_id or self.active_tab
  if tab_id == "terminal" then
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term and term.ensure_started then term:ensure_started() end
  end
end

local function sanitize_project_label(name, cwd)
  local label = name or ""
  label = label:gsub("%s*%[.-%]$", "")
  if label:lower() == "venv" or label:lower() == ".venv" or label == "" then
    if cwd then
      local parent = cwd:match("([^/\\\\]+)[/\\]%.?venv$") or cwd:match("([^/\\\\]+)[/\\]env$") or cwd:match("([^/\\\\]+)$")
      if parent then label = parent end
    end
  end
  return (label ~= "" and label) or "Projeto"
end

local function get_input_char_from_x(font, text, click_x, start_x)
  local rel_x = click_x - start_x
  if rel_x <= 0 then return 1 end
  local len = #text
  for idx = 1, len do
    local w = font:get_width(text:sub(1, idx))
    if w >= rel_x then
      local prev_w = font:get_width(text:sub(1, idx - 1))
      return (rel_x - prev_w < w - rel_x) and idx or (idx + 1)
    end
  end
  return len + 1
end

function ShelfHub:draw()
  if not self.visible then return end
  if not self._is_ready then
    self:ensure_initialized()
    self._is_ready = true
  end

  local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
  local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
  local mgr = rawget(_G, "_DOXOADE_TERMINAL_SESSION_MGR")
  local font = (term and term:get_font()) or style.font
  local screen_w = core.root_view.size.x
  local screen_h = core.root_view.size.y

  local x, y, w, h
  if self.is_maximized then
    x, y, w, h = 8, 8, screen_w - 16, screen_h - 16
  else
    w = math.min(screen_w - 24, math.max(680, math.floor(screen_w * 0.90)))
    h = math.min(screen_h - 24, math.max(520, math.floor(screen_h * 0.88)))
    x = math.floor((screen_w - w) / 2)
    y = math.floor((screen_h - h) / 2)
  end
  self.card_rect = { x = x, y = y, w = w, h = h }

  local tiers = get_tier_count(w, h)
  local ROW_H = 26
  self.header_height = (tiers * ROW_H) + 4

  -- Moldura Principal
  draw_rect_safe(x - 2, y - 2, w + 4, h + 4, COLOR_BORDER_LINE)
  draw_rect_safe(x, y, w, h, COLOR_BG_PANEL)
  draw_rect_safe(x, y, w, 2, style.accent or COLOR_PROMPT_DIR)
  draw_rect_safe(x, y + 2, w, self.header_height, COLOR_HEADER_BG)
  draw_rect_safe(x, y + self.header_height + 1, w, 1, COLOR_BORDER_LINE)

  if tiers >= 2 then draw_rect_safe(x, y + ROW_H + 2, w, 1, { 28, 28, 32, 255 }) end
  if tiers >= 3 then draw_rect_safe(x, y + (ROW_H * 2) + 2, w, 1, { 28, 28, 32, 255 }) end

  local y1 = y + 4
  local y2 = y + ROW_H + 4
  local y3 = y + (ROW_H * 2) + 4

  -- ═══════════════════════════════════════════════════════════════════════════
  -- ANDAR 1: ABAS MESTRAS & CONTROLES GLOBAIS ([3L], [□], [X])
  -- ═══════════════════════════════════════════════════════════════════════════
  local tab_x = x + 10
  for i, tab in ipairs(self.tabs) do
    local is_active = (self.active_tab == tab.id)
    local is_hovered = (self.hovered_tab == i)
    local label = tab.label
    local tab_w = font:get_width(label) + 16
    local tab_h = ROW_H - 4

    if is_active then
      draw_rect_safe(tab_x, y1, tab_w, tab_h, { 0, 0, 0, 255 })
      draw_rect_safe(tab_x, y1, tab_w, 2, style.accent or { 38, 188, 95, 255 })
    elseif is_hovered then
      draw_rect_safe(tab_x, y1, tab_w, tab_h, { 30, 30, 30, 255 })
    end

    local text_color = is_active and (style.accent or { 38, 188, 95, 255 }) or { 150, 150, 150, 255 }
    draw_text_safe(font, label, tab_x + 8, y1 + 3, text_color)
    tab.rect = { x = tab_x, y = y1, w = tab_w, h = tab_h }
    tab_x = tab_x + tab_w + 6
  end

  local right_x = x + w - 8

  -- Botão Fechar [X]
  local close_w = 24
  right_x = right_x - close_w
  if self.hovered_close then draw_rect_safe(right_x, y1, close_w, ROW_H - 4, { 220, 38, 38, 255 }) end
  draw_text_safe(font, "[X]", right_x + 3, y1 + 3, self.hovered_close and { 255, 255, 255, 255 } or { 150, 150, 150, 255 })
  self.close_rect = { x = right_x, y = y1, w = close_w, h = ROW_H - 4 }

  -- Botão Maximizar [□]
  local max_label = self.is_maximized and "[□]" or "[■]"
  local max_w = font:get_width(max_label) + 8
  right_x = right_x - max_w - 4
  draw_text_safe(font, max_label, right_x + 4, y1 + 3, { 140, 140, 150, 255 })
  self.max_rect = { x = right_x, y = y1, w = max_w, h = ROW_H - 4 }

  -- Badge do Modo Escada ([3L·A] / [2L] / [1L])
  local mode_badge = string.format("%dL", tiers)
  if self.layout_mode == "auto" then mode_badge = mode_badge .. "·A" end
  local badge_w = font:get_width(mode_badge) + 10
  right_x = right_x - badge_w - 4
  if self.hovered_layout then draw_rect_safe(right_x, y1, badge_w, ROW_H - 4, { 45, 45, 55, 255 }) end
  draw_text_safe(font, mode_badge, right_x + 5, y1 + 3, self.hovered_layout and (style.accent or { 56, 189, 248, 255 }) or { 130, 130, 145, 255 })
  self.layout_rect = { x = right_x, y = y1, w = badge_w, h = ROW_H - 4 }

  -- ═══════════════════════════════════════════════════════════════════════════
  -- ANDAR 2: SESSÕES DE PROJETOS CONCORRENTES & INDICADOR DE DIRETÓRIO (CWD)
  -- ═══════════════════════════════════════════════════════════════════════════
  self.session_buttons = {}
  local session_y = (tiers >= 2) and y2 or y1
  local sess_x = (tiers >= 2) and (x + 10) or (tab_x + 8)
  local sess_max_x = (tiers >= 2) and (x + w - 10) or right_x

  if self.active_tab == "terminal" and mgr and mgr.list_sessions then
    local sessions = mgr.list_sessions()
    for _, s in ipairs(sessions) do
      local clean_proj = sanitize_project_label(s.name, s.cwd)
      local s_label = string.format("[%d: %s]", s.index, clean_proj)
      local sw = font:get_width(s_label) + 8
      local sh = ROW_H - 5
      local is_hover = (self.hovered_session == s.index)

      if sess_x + sw < sess_max_x then
        local bg_col = s.is_active and { 24, 45, 32, 255 } or (is_hover and { 30, 30, 35, 255 } or { 18, 18, 22, 255 })
        local text_col = s.is_active and (style.accent or { 34, 197, 94, 255 }) or { 150, 150, 160, 255 }
        draw_rect_safe(sess_x, session_y, sw, sh, bg_col)
        if s.is_active then draw_rect_safe(sess_x, session_y, sw, 1, style.accent or { 34, 197, 94, 255 }) end
        draw_text_safe(font, s_label, sess_x + 4, session_y + 2, text_col)

        table.insert(self.session_buttons, {
          index = s.index,
          rect = { x = sess_x, y = session_y, w = sw, h = sh },
          action = function() mgr.switch_session(s.index) end
        })
        sess_x = sess_x + sw + 4
      end
    end

    -- Botão [+] Nova Sessão de Terminal
    local add_w = font:get_width("[+]") + 8
    if sess_x + add_w < sess_max_x then
      draw_text_safe(font, "[+]", sess_x + 4, session_y + 2, { 120, 180, 240, 255 })
      table.insert(self.session_buttons, {
        index = "new",
        rect = { x = sess_x, y = session_y, w = add_w, h = ROW_H - 5 },
        action = function() command.perform("doxoade:terminal-new-tab") end
      })
      sess_x = sess_x + add_w + 10
    end

    -- 🌟 HUD DO DIRETÓRIO ATIVO (CWD)
    local cur_cwd = term and term:get_cwd() or ""
    if cur_cwd ~= "" and sess_x + 80 < sess_max_x then
      local cwd_label = "📁 " .. cur_cwd
      local max_cwd_w = sess_max_x - sess_x - 8
      if font:get_width(cwd_label) > max_cwd_w then
        cwd_label = "📁 …" .. cur_cwd:sub(-math.floor(max_cwd_w / font:get_width("W") * 1.5))
      end
      draw_text_safe(font, cwd_label, sess_x + 6, session_y + 2, { 110, 190, 230, 210 })
    end
  end

  -- ═══════════════════════════════════════════════════════════════════════════
  -- ANDAR 3: AÇÕES DO SHELL
  -- ═══════════════════════════════════════════════════════════════════════════
  self.action_buttons = {}
  local action_y = (tiers >= 3) and y3 or ((tiers == 2) and y2 or y1)
  local act_x = (tiers >= 3) and (x + 10) or (sess_x + 14)
  local act_max_x = x + w - 10

  local dynamic_buttons = {}
  if self.active_tab == "terminal" then
    dynamic_buttons = {
      { id = "shell",     label = string.format("[%s]", term and term:short_shell_label() or "SHELL"), action = function() if term then term:cycle_shell() end end, color = { 56, 189, 248, 255 } },
      { id = "interrupt", label = "[Ctrl+C]",   action = function() if term then term:send_interrupt() end end, color = { 239, 68, 68, 255 } },
      { id = "copy",      label = "[Copiar]",   action = function() command.perform("bottom-shelf:copy") end, color = { 147, 197, 253, 255 } },
      { id = "paste",     label = "[Colar]",    action = function() command.perform("bottom-shelf:paste") end, color = { 180, 180, 190, 255 } },
      { id = "clear",     label = "[Limpar]",   action = function() if term then term:clear_screen() end end, color = { 180, 180, 190, 255 } },
      { id = "term_ext",  label = "[> Externo]",action = function() if term then term:launch_external_terminal(false) end end, color = { 110, 231, 183, 255 } },
      { id = "admin",     label = "[Admin]",    action = function() if term then term:launch_external_terminal(true) end end, color = { 245, 158, 11, 255 } },
    }
  elseif self.active_tab == "canvas" and canvas then
    dynamic_buttons = {
      { id = "paste_img", label = "[Colar Print]", action = function() canvas:paste_clipboard_image() end, color = { 56, 189, 248, 255 } },
      { id = "copy_img",  label = "[Copiar]",     action = function() canvas:copy_image_to_clipboard() end, color = { 147, 197, 253, 255 } },
      { id = "open_ext",  label = "[Externo]",    action = function() canvas:open_image_external() end,     color = { 110, 231, 183, 255 } },
      { id = "mode_1to1", label = canvas.mode_1to1 and "[Ajustar]" or "[1:1 Real]", action = function() canvas.mode_1to1 = not canvas.mode_1to1; canvas.zoom = 1.0; core.redraw = true end, color = { 245, 158, 11, 255 } },
      { id = "clear_img", label = "[Limpar]",     action = function() canvas:clear() end, color = { 239, 68, 68, 255 } },
    }
  end

  for i, btn in ipairs(dynamic_buttons) do
    local bw = font:get_width(btn.label) + 8
    local bh = ROW_H - 5
    local is_hover = (self.hovered_btn == i)

    if act_x + bw < act_max_x then
      if is_hover then draw_rect_safe(act_x, action_y, bw, bh, { 35, 35, 45, 255 }) end
      draw_text_safe(font, btn.label, act_x + 4, action_y + 2, is_hover and { 255, 255, 255, 255 } or (btn.color or { 56, 189, 248, 255 }))
      btn.rect = { x = act_x, y = action_y, w = bw, h = bh }
      table.insert(self.action_buttons, btn)
      act_x = act_x + bw + 4
    end
  end

  -- ═══════════════════════════════════════════════════════════════════════════
  -- VIEWPORT DE CONTEÚDO (FUNDO COLORIDO SUTIL & MARCA D'ÁGUA POR PROJETO)
  -- ═══════════════════════════════════════════════════════════════════════════
  local canvas_y = y + self.header_height + 2
  local canvas_h = h - self.header_height - 34
  self.terminal_viewport_rect = { x = x + 2, y = canvas_y, w = w - 4, h = canvas_h }

  -- 🎯 1. FUNDO EXCLUSIVO COM COR SUTIL POR PROJETO
  local cur_proj = (term and term:get_display_name()) or ""
  local cur_cwd  = (term and term:get_cwd()) or ""
  local proj_tint = get_project_tint(cur_cwd ~= "" and cur_cwd or cur_proj)

  if self.active_tab == "terminal" then
    draw_rect_safe(x + 2, canvas_y, w - 4, canvas_h, proj_tint)
  end

  core.push_clip_rect(x + 2, canvas_y, w - 4, canvas_h)

  -- 🎯 2. MARCA D'ÁGUA SUTIL COM O NOME DO PROJETO NO CENTRO
  if self.active_tab == "terminal" and cur_proj ~= "" then
    local wm_font = style.big_font or font
    if wm_font:get_width(cur_proj) > w - 40 then
      wm_font = font
    end
    local wm_w = wm_font:get_width(cur_proj)
    local wm_h = wm_font:get_height()
    local wm_x = x + math.floor((w - wm_w) / 2)
    local wm_y = canvas_y + math.floor((canvas_h - wm_h) / 2)

    local wm_color = {
      math.min(255, proj_tint[1] + 24),
      math.min(255, proj_tint[2] + 28),
      math.min(255, proj_tint[3] + 34),
      65
    }
    draw_text_safe(wm_font, cur_proj, wm_x, wm_y, wm_color)
  end

  if self.active_tab == "terminal" and term then
    term:update_viewport(w - 8, canvas_h + 30)

    local line_h = term:_line_height()
    local max_line_w = w - 24

    local total_lines = #term.lines
    local start_idx = math.max(1, math.floor(term.scroll_y / line_h))
    local visible_count = math.ceil(canvas_h / line_h) + 3
    local end_idx = math.min(total_lines, start_idx + visible_count)

    local cur_y = canvas_y + 4 + ((start_idx - 1) * line_h) - term.scroll_y

    -- Faixa de seleção de texto no terminal
    local has_char_sel = (term.sel_s_line and term.sel_e_line and (term.sel_s_line ~= term.sel_e_line or term.sel_s_col ~= term.sel_e_col))
    local s_line, s_col, e_line, e_col
    if has_char_sel then
      if term.sel_s_line < term.sel_e_line or (term.sel_s_line == term.sel_e_line and term.sel_s_col <= term.sel_e_col) then
        s_line, s_col, e_line, e_col = term.sel_s_line, term.sel_s_col, term.sel_e_line, term.sel_e_col
      else
        s_line, s_col, e_line, e_col = term.sel_e_line, term.sel_e_col, term.sel_s_line, term.sel_s_col
      end
    end

    for i = start_idx, end_idx do
      local item = term.lines[i]
      local seg_x = x + 14

      if item and item.segments then
        local line_char_offset = 1

        for _, seg in ipairs(item.segments) do
          local text_val = seg.text or ""
          local seg_len = #text_val
          local style_col = (seg.style and seg.style.fg) or seg.fg or { 220, 220, 220, 255 }

          if text_val:find("^%(venv%)") or text_val:find("^[a-zA-Z]:\\.*>") then
            style_col = COLOR_PROMPT_DIR
          end

          local text_w = font:get_width(text_val)

          if seg_x + text_w > x + max_line_w and seg_x > x + 14 then
            cur_y = cur_y + line_h
            seg_x = x + 14
          end

          -- Realce cirúrgico de seleção
          if has_char_sel and i >= s_line and i <= e_line then
            local hl_start_col = (i == s_line) and s_col or 1
            local hl_end_col   = (i == e_line) and e_col or (line_char_offset + seg_len)

            local seg_start = line_char_offset
            local seg_end   = line_char_offset + seg_len - 1

            if hl_end_col >= seg_start and hl_start_col <= seg_end then
              local c_from = math.max(1, hl_start_col - seg_start + 1)
              local c_to   = math.min(seg_len, hl_end_col - seg_start + 1)

              local hl_x_offset = font:get_width(text_val:sub(1, c_from - 1))
              local hl_w        = font:get_width(text_val:sub(c_from, c_to))
              draw_rect_safe(seg_x + hl_x_offset, cur_y - 1, hl_w, line_h, { 56, 189, 248, 85 })
            end
          end

          draw_text_safe(font, text_val, seg_x, cur_y, style_col)
          seg_x = seg_x + text_w
          line_char_offset = line_char_offset + seg_len
        end
      end
      cur_y = cur_y + line_h
    end

    -- Prompt Ativo (Sempre desenhado sem omissão)
    local cur_line_segs = term._client and term._client.current_line
    if cur_line_segs and #cur_line_segs > 0 then
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

  -- ═══════════════════════════════════════════════════════════════════════════
  -- BARRA DE ENTRADA INFERIOR HARMONIZADA
  -- ═══════════════════════════════════════════════════════════════════════════
  local input_y = y + h - 30
  self.input_rect = { x = x + 1, y = input_y, w = w - 2, h = 29 }
  local in_bg = (self.active_tab == "terminal") and proj_tint or { 10, 10, 10, 255 }
  draw_rect_safe(x + 1, input_y, w - 2, 29, in_bg)
  draw_rect_safe(x + 1, input_y, w - 2, 1, style.accent or { 38, 188, 95, 255 })

  if self.active_tab == "terminal" and term then
    local tag = term.is_executing and "[RODANDO]" or "[PTY]"
    local tag_col = term.is_executing and { 251, 191, 36, 255 } or (style.accent or { 38, 188, 95, 255 })
    draw_text_safe(font, tag, x + 14, input_y + 6, tag_col)
    local p_off = font:get_width(tag) + 24
    local text_start_x = x + p_off + font:get_width("> ")

    local sel_s = term.input_sel_from and term.input_cursor and math.min(term.input_sel_from, term.input_cursor)
    local sel_e = term.input_sel_from and term.input_cursor and math.max(term.input_sel_from, term.input_cursor)

    if term._all_selected and #term.input_text > 0 then
      local sel_w = font:get_width("> " .. term.input_text)
      draw_rect_safe(x + p_off, input_y + 4, sel_w + 4, font:get_height() + 4, { 56, 189, 248, 90 })
    elseif sel_s and sel_e and sel_s < sel_e then
      local before_w = font:get_width(term.input_text:sub(1, sel_s - 1))
      local sel_w = font:get_width(term.input_text:sub(sel_s, sel_e - 1))
      draw_rect_safe(text_start_x + before_w, input_y + 4, sel_w + 2, font:get_height() + 4, { 56, 189, 248, 90 })
    end

    draw_text_safe(font, "> " .. term.input_text, x + p_off, input_y + 6, { 255, 255, 255, 255 })

    -- Ghost Text
    if #term.suggestions > 0 and term.input_text ~= "" and not term._all_selected then
      local top_sug = term.suggestions[term.suggestion_idx or 1]
      if top_sug and top_sug:sub(1, #term.input_text):lower() == term.input_text:lower() then
        local ghost_part = top_sug:sub(#term.input_text + 1)
        local ghost_x = x + p_off + font:get_width("> " .. term.input_text)
        draw_text_safe(font, ghost_part, ghost_x, input_y + 6, { 110, 110, 110, 220 })
      end
    end

    -- Cursor
    local text_before = term.input_text:sub(1, term.input_cursor - 1)
    local cx = text_start_x + font:get_width(text_before)
    draw_rect_safe(cx, input_y + 6, 2, font:get_height(), style.accent or { 38, 188, 95, 255 })
  elseif self.active_tab == "canvas" and canvas then
    local mode_str = canvas.mode_1to1 and "1:1 Real" or "Ajustado"
    local zoom_lbl = string.format("[%s | Zoom: %d%%] ", mode_str, math.floor(canvas.zoom * 100))
    draw_text_safe(font, zoom_lbl, x + 14, input_y + 6, style.accent or { 38, 188, 95, 255 })
    draw_text_safe(font, canvas.status_msg or "", x + 14 + font:get_width(zoom_lbl), input_y + 6, { 150, 150, 150, 255 })
  end
end

-- =============================================================================
-- HOOKS DE MOUSE & SELEÇÃO CIRÚRGICA
-- =============================================================================
local original_rootview_draw = RootView.draw
function RootView:draw(...)
  original_rootview_draw(self, ...)
  if ShelfHub.visible then ShelfHub:draw() end
end

local function resolve_term_char_at_pos(term, font, px, py, vp)
  local line_h = term:_line_height()
  local line_idx = math.floor((py - vp.y + term.scroll_y - 4) / line_h) + 1
  line_idx = math.max(1, math.min(#term.lines + 1, line_idx))

  local line_item = term.lines[line_idx]
  if not line_item or not line_item.segments then
    return line_idx, 1
  end

  local full_text = ""
  for _, s in ipairs(line_item.segments) do full_text = full_text .. (s.text or "") end

  local rel_x = px - (vp.x + 12)
  if rel_x <= 0 then return line_idx, 1 end

  local col = 1
  for i = 1, #full_text do
    local w = font:get_width(full_text:sub(1, i))
    if w >= rel_x then
      local pw = font:get_width(full_text:sub(1, i - 1))
      col = (rel_x - pw < w - rel_x) and i or (i + 1)
      return line_idx, col
    end
  end
  return line_idx, #full_text + 1
end

local original_rootview_on_mouse_moved = RootView.on_mouse_moved
function RootView:on_mouse_moved(x, y, dx, dy)
  if ShelfHub.visible then
    local r = ShelfHub.card_rect
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
    local font = (term and term:get_font()) or style.font

    ShelfHub.hovered_tab = nil
    ShelfHub.hovered_btn = nil
    ShelfHub.hovered_session = nil
    ShelfHub.hovered_layout = false
    ShelfHub.hovered_close = false

    -- Panning do Canvas
    if canvas and canvas.is_panning and ShelfHub.active_tab == "canvas" then
      canvas.pan_x = canvas.pan_x + dx
      canvas.pan_y = canvas.pan_y + dy
      core.redraw = true
      return true
    end

    -- Arrasto de seleção no terminal
    if ShelfHub.is_selecting_output and term and ShelfHub.terminal_viewport_rect then
      local vp = ShelfHub.terminal_viewport_rect
      local l_idx, c_idx = resolve_term_char_at_pos(term, font, x, y, vp)
      term.sel_e_line = l_idx
      term.sel_e_col  = c_idx
      core.redraw = true
      return true
    end

    -- Arrasto de seleção no input bar
    if ShelfHub.is_selecting_input and term and ShelfHub.input_rect then
      local tag = term.is_executing and "[RODANDO]" or "[PTY]"
      local p_off = font:get_width(tag) + 24
      local text_start_x = ShelfHub.card_rect.x + p_off + font:get_width("> ")
      term.input_cursor = get_input_char_from_x(font, term.input_text, x, text_start_x)
      core.redraw = true
      return true
    end

    if r and x >= r.x and x <= r.x + r.w and y >= r.y and y <= r.y + r.h then
      for i, tab in ipairs(ShelfHub.tabs) do
        if tab.rect and x >= tab.rect.x and x <= tab.rect.x + tab.rect.w and y >= tab.rect.y and y <= tab.rect.y + tab.rect.h then
          ShelfHub.hovered_tab = i; core.redraw = true; return true
        end
      end
      for _, s_btn in ipairs(ShelfHub.session_buttons) do
        if s_btn.rect and x >= s_btn.rect.x and x <= s_btn.rect.x + s_btn.rect.w and y >= s_btn.rect.y and y <= s_btn.rect.y + s_btn.rect.h then
          ShelfHub.hovered_session = s_btn.index; core.redraw = true; return true
        end
      end
      for i, btn in ipairs(ShelfHub.action_buttons) do
        if btn.rect and x >= btn.rect.x and x <= btn.rect.x + btn.rect.w and y >= btn.rect.y and y <= btn.rect.y + btn.rect.h then
          ShelfHub.hovered_btn = i; core.redraw = true; return true
        end
      end
      if ShelfHub.layout_rect and x >= ShelfHub.layout_rect.x and x <= ShelfHub.layout_rect.x + ShelfHub.layout_rect.w and
         y >= ShelfHub.layout_rect.y and y <= ShelfHub.layout_rect.y + ShelfHub.layout_rect.h then
        ShelfHub.hovered_layout = true; core.redraw = true; return true
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
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
    local font = (term and term:get_font()) or style.font

    if r and (x < r.x or x > r.x + r.w or y < r.y or y > r.y + r.h) then
      ShelfHub.visible = false; core.redraw = true; return true
    end

    if (button == "right" or button == 2) and term and term.sel_s_line then
      command.perform("bottom-shelf:copy")
      return true
    end

    -- Panning do Canvas
    if ShelfHub.active_tab == "canvas" and canvas and (button == "left" or button == 1) then
      canvas.is_panning = true
      return true
    end

    -- Seleção cirúrgica no terminal
    local vp = ShelfHub.terminal_viewport_rect
    if (button == "left" or button == 1) and vp and (x >= vp.x and x <= vp.x + vp.w and y >= vp.y and y <= vp.y + vp.h) and term then
      local l_idx, c_idx = resolve_term_char_at_pos(term, font, x, y, vp)
      ShelfHub.is_selecting_output = true
      term.sel_s_line = l_idx
      term.sel_s_col  = c_idx
      term.sel_e_line = l_idx
      term.sel_e_col  = c_idx
      core.redraw = true
      return true
    end

    -- Cursor no input bar
    local inp = ShelfHub.input_rect
    if (button == "left" or button == 1) and inp and (x >= inp.x and x <= inp.x + inp.w and y >= inp.y and y <= inp.y + inp.h) and term then
      local tag = term.is_executing and "[RODANDO]" or "[PTY]"
      local p_off = font:get_width(tag) + 24
      local text_start_x = ShelfHub.card_rect.x + p_off + font:get_width("> ")
      local char_idx = get_input_char_from_x(font, term.input_text, x, text_start_x)

      term.input_cursor = char_idx
      term.input_sel_from = char_idx
      term._all_selected = false
      ShelfHub.is_selecting_input = true
      core.redraw = true
      return true
    end

    -- Abas e Botões
    for i, tab in ipairs(ShelfHub.tabs) do
      if tab.rect and x >= tab.rect.x and x <= tab.rect.x + tab.rect.w and y >= tab.rect.y and y <= tab.rect.y + tab.rect.h then
        ShelfHub.active_tab = tab.id
        ShelfHub:ensure_initialized(tab.id)
        core.redraw = true
        return true
      end
    end
    for _, s_btn in ipairs(ShelfHub.session_buttons) do
      if s_btn.rect and x >= s_btn.rect.x and x <= s_btn.rect.x + s_btn.rect.w and y >= s_btn.rect.y and y <= s_btn.rect.y + s_btn.rect.h then
        if s_btn.action then s_btn.action(); return true end
      end
    end
    for _, btn in ipairs(ShelfHub.action_buttons) do
      if btn.rect and x >= btn.rect.x and x <= btn.rect.x + btn.rect.w and y >= btn.rect.y and y <= btn.rect.y + btn.rect.h then
        if btn.action then btn.action(); return true end
      end
    end
    if ShelfHub.layout_rect and x >= ShelfHub.layout_rect.x and x <= ShelfHub.layout_rect.x + ShelfHub.layout_rect.w and
       y >= ShelfHub.layout_rect.y and y <= ShelfHub.layout_rect.y + ShelfHub.layout_rect.h then
      ShelfHub:toggle_layout_mode()
      return true
    end
    if ShelfHub.max_rect and x >= ShelfHub.max_rect.x and x <= ShelfHub.max_rect.x + ShelfHub.max_rect.w and
       y >= ShelfHub.max_rect.y and y <= ShelfHub.max_rect.y + ShelfHub.max_rect.h then
      command.perform("doxoade:bottom-shelf-toggle-maximize")
      return true
    end
    if ShelfHub.hovered_close then
      ShelfHub.visible = false; core.redraw = true; return true
    end
    return true
  end
  if original_rootview_on_mouse_pressed then return original_rootview_on_mouse_pressed(self, button, x, y, clicks) end
end

local original_rootview_on_mouse_released = RootView.on_mouse_released
function RootView:on_mouse_released(button, x, y)
  if ShelfHub.visible then
    local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")

    if canvas then canvas.is_panning = false end

    if ShelfHub.is_selecting_output then
      ShelfHub.is_selecting_output = false
      if term and term.sel_s_line == term.sel_e_line and term.sel_s_col == term.sel_e_col then
        term.sel_s_line = nil
        term.sel_e_line = nil
      end
      core.redraw = true
    end

    if ShelfHub.is_selecting_input then
      ShelfHub.is_selecting_input = false
      if term and term.input_sel_from == term.input_cursor then
        term.input_sel_from = nil
      end
      core.redraw = true
    end
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
    if not text or text == "" or text:find("^[%z\1-\31\127]") then return true end
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      local s_from = term.input_sel_from and term.input_cursor and math.min(term.input_sel_from, term.input_cursor)
      local s_to   = term.input_sel_from and term.input_cursor and math.max(term.input_sel_from, term.input_cursor)

      if term._all_selected then
        term.input_text = text
        term.input_cursor = #text + 1
        term._all_selected = false
        term.input_sel_from = nil
      elseif s_from and s_to and s_from < s_to then
        term.input_text = term.input_text:sub(1, s_from - 1) .. text .. term.input_text:sub(s_to)
        term.input_cursor = s_from + #text
        term.input_sel_from = nil
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
-- COMANDOS E KEYMAPS SOBERANOS
-- =============================================================================
command.add(nil, {
  ["doxoade:toggle-bottom-shelf"] = function()
    ShelfHub.visible = not ShelfHub.visible
    if ShelfHub.visible then ShelfHub:ensure_initialized() end
    core.redraw = true
  end,
  ["doxoade:bottom-shelf-toggle-maximize"] = function()
    if ShelfHub.visible then
      ShelfHub.is_maximized = not ShelfHub.is_maximized
      core.redraw = true
    end
  end,
  ["doxoade:bottom-shelf-toggle-layout"] = function()
    if ShelfHub.visible then ShelfHub:toggle_layout_mode() end
  end,
})

command.add(function() return ShelfHub.visible end, {
  ["bottom-shelf:close"] = function() ShelfHub.visible = false; core.redraw = true; return true end,
  ["bottom-shelf:escape"] = function() return command.perform("bottom-shelf:close") end,
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

  -- 📋 Cópia cirúrgica de caracteres ou linhas selecionadas
  ["bottom-shelf:copy"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if not term then return true end

    -- 1. Se houver seleção no input bar
    local s_from = term.input_sel_from and term.input_cursor and math.min(term.input_sel_from, term.input_cursor)
    local s_to   = term.input_sel_from and term.input_cursor and math.max(term.input_sel_from, term.input_cursor)

    if term._all_selected and #term.input_text > 0 then
      if system and system.set_clipboard then system.set_clipboard(term.input_text) end
      core.log("📋 Comando copiado.")
      return true
    elseif s_from and s_to and s_from < s_to then
      local sel_str = term.input_text:sub(s_from, s_to - 1)
      if system and system.set_clipboard then system.set_clipboard(sel_str) end
      core.log("📋 Trecho selecionado copiado.")
      return true
    end

    -- 2. Cópia cirúrgica da saída do terminal
    if term.sel_s_line and term.sel_e_line then
      local s_l, s_c, e_l, e_c
      if term.sel_s_line < term.sel_e_line or (term.sel_s_line == term.sel_e_line and term.sel_s_col <= term.sel_e_col) then
        s_l, s_c, e_l, e_c = term.sel_s_line, term.sel_s_col, term.sel_e_line, term.sel_e_col
      else
        s_l, s_c, e_l, e_c = term.sel_e_line, term.sel_e_col, term.sel_s_line, term.sel_s_col
      end

      local parts = {}
      for l = s_l, e_l do
        local line_item = term.lines[l]
        if line_item and line_item.segments then
          local l_text = ""
          for _, s in ipairs(line_item.segments) do l_text = l_text .. (s.text or "") end
          if s_l == e_l then
            table.insert(parts, l_text:sub(s_c, e_c))
          elseif l == s_l then
            table.insert(parts, l_text:sub(s_c))
          elseif l == e_l then
            table.insert(parts, l_text:sub(1, e_c))
          else
            table.insert(parts, l_text)
          end
        end
      end

      local out = table.concat(parts, "\n")
      if out ~= "" and system and system.set_clipboard then
        system.set_clipboard(out)
        core.log(string.format("📋 %d caractere(s) do terminal copiados.", #out))
        return true
      end
    end

    term:copy_output()
    return true
  end,

  ["bottom-shelf:paste"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      local clip = system.get_clipboard and system.get_clipboard()
      if clip and clip ~= "" then
        clip = clip:gsub("[\r\n]+", " ")
        local s_from = term.input_sel_from and term.input_cursor and math.min(term.input_sel_from, term.input_cursor)
        local s_to   = term.input_sel_from and term.input_cursor and math.max(term.input_sel_from, term.input_cursor)

        if term._all_selected then
          term.input_text = clip
          term.input_cursor = #clip + 1
          term._all_selected = false
          term.input_sel_from = nil
        elseif s_from and s_to and s_from < s_to then
          term.input_text = term.input_text:sub(1, s_from - 1) .. clip .. term.input_text:sub(s_to)
          term.input_cursor = s_from + #clip
          term.input_sel_from = nil
        else
          local cur = term.input_cursor or (#term.input_text + 1)
          term.input_text = term.input_text:sub(1, cur - 1) .. clip .. term.input_text:sub(cur)
          term.input_cursor = cur + #clip
        end
        core.redraw = true
      end
    end
    return true
  end,

  ["bottom-shelf:submit"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      term._all_selected = false
      term.input_sel_from = nil
      term:execute_command(term.input_text)
    end
    return true
  end,

  ["bottom-shelf:history-prev"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term and term.history_prev then term:history_prev() end
    return true
  end,
  ["bottom-shelf:history-next"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term and term.history_next then term:history_next() end
    return true
  end,

  ["bottom-shelf:start-of-line"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term.input_cursor = 1; term._all_selected = false; term.input_sel_from = nil; core.redraw = true end
    return true
  end,
  ["bottom-shelf:end-of-line"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term.input_cursor = #term.input_text + 1; term._all_selected = false; term.input_sel_from = nil; core.redraw = true end
    return true
  end,

  ["bottom-shelf:word-left"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term and term.move_word_left then term:move_word_left() end
    return true
  end,
  ["bottom-shelf:word-right"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term and term.move_word_right then term:move_word_right() end
    return true
  end,

  ["bottom-shelf:backspace"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      local s_from = term.input_sel_from and term.input_cursor and math.min(term.input_sel_from, term.input_cursor)
      local s_to   = term.input_sel_from and term.input_cursor and math.max(term.input_sel_from, term.input_cursor)

      if term._all_selected then
        term.input_text = ""
        term.input_cursor = 1
        term._all_selected = false
        term.input_sel_from = nil
      elseif s_from and s_to and s_from < s_to then
        term.input_text = term.input_text:sub(1, s_from - 1) .. term.input_text:sub(s_to)
        term.input_cursor = s_from
        term.input_sel_from = nil
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
      local s_from = term.input_sel_from and term.input_cursor and math.min(term.input_sel_from, term.input_cursor)
      local s_to   = term.input_sel_from and term.input_cursor and math.max(term.input_sel_from, term.input_cursor)

      if term._all_selected then
        term.input_text = ""
        term.input_cursor = 1
        term._all_selected = false
        term.input_sel_from = nil
      elseif s_from and s_to and s_from < s_to then
        term.input_text = term.input_text:sub(1, s_from - 1) .. term.input_text:sub(s_to)
        term.input_cursor = s_from
        term.input_sel_from = nil
      elseif term.input_cursor <= #term.input_text then
        term.input_text = term.input_text:sub(1, term.input_cursor - 1) .. term.input_text:sub(term.input_cursor + 1)
      end
      term:update_suggestions()
      core.redraw = true
    end
    return true
  end,

  ["bottom-shelf:select-all"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then
      term._all_selected = true
      term.input_sel_from = nil
      term.input_cursor = #term.input_text + 1
      core.redraw = true
    end
    return true
  end,
  ["bottom-shelf:previous-char"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term.input_sel_from = nil; term._all_selected = false; term.input_cursor = math.max(1, term.input_cursor - 1); core.redraw = true end
    return true
  end,
  ["bottom-shelf:next-char"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term.input_sel_from = nil; term._all_selected = false; term.input_cursor = math.min(#term.input_text + 1, term.input_cursor + 1); core.redraw = true end
    return true
  end,
  ["bottom-shelf:tab-complete"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term:handle_tab_completion() end
    return true
  end,
  ["bottom-shelf:page-up"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term:scroll_by(300) end
  end,
  ["bottom-shelf:page-down"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term:scroll_by(-300) end
  end,
  ["bottom-shelf:smart-ctrl-c"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if not term then return true end

    local has_input_sel = (term._all_selected and #term.input_text > 0) or
      (term.input_sel_from and term.input_cursor and term.input_sel_from ~= term.input_cursor)
    local has_term_sel  = (term.sel_s_line and term.sel_e_line and
      (term.sel_s_line ~= term.sel_e_line or term.sel_s_col ~= term.sel_e_col))

    if has_input_sel or has_term_sel then
      return command.perform("bottom-shelf:copy")
    else
      return command.perform("bottom-shelf:interrupt")
    end
  end,
})

keymap.add {
  ["ctrl+`"]          = "doxoade:toggle-bottom-shelf",
  ["ctrl+j"]          = "doxoade:toggle-bottom-shelf",
  ["alt+return"]      = "doxoade:bottom-shelf-toggle-maximize",
  ["escape"]          = "bottom-shelf:close",
  ["ctrl+shift+c"]   = "bottom-shelf:copy",
  ["ctrl+c"]          = "bottom-shelf:smart-ctrl-c",
  ["ctrl+c"]          = "bottom-shelf:copy",
  ["ctrl+v"]          = "bottom-shelf:paste",
  ["ctrl+a"]          = "bottom-shelf:select-all",
  ["return"]          = "bottom-shelf:submit",
  ["keypad enter"]    = "bottom-shelf:submit",
  ["backspace"]       = "bottom-shelf:backspace",
  ["delete"]          = "bottom-shelf:delete",
  ["tab"]             = "bottom-shelf:tab-complete",
  ["up"]              = "bottom-shelf:history-prev",
  ["down"]            = "bottom-shelf:history-next",
  ["home"]            = "bottom-shelf:start-of-line",
  ["end"]             = "bottom-shelf:end-of-line",
  ["left"]            = "bottom-shelf:previous-char",
  ["right"]           = "bottom-shelf:next-char",
  ["ctrl+left"]       = "bottom-shelf:word-left",
  ["ctrl+right"]      = "bottom-shelf:word-right",
  ["pageup"]          = "bottom-shelf:page-up",
  ["pagedown"]        = "bottom-shelf:page-down",
}
