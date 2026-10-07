-- =============================================================================
-- 13d_frameless_hud.lua — TOOLBAR DUAL-TIER COM TOOLTIPS, CLIQUES & CHECKS VIVOS
-- =============================================================================
local core = require "core"
local style = require "core.style"
local config = require "core.config"
local command = require "core.command"
local keymap = require "core.keymap"
local StatusView = require "core.statusview"
local RootView = require "core.rootview"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

-- ── 1. RENDERIZADORES SEGUROS ─────────────────────────────────────────────────
local function draw_rect_safe(x, y, w, h, c)
  if rencache and rencache.draw_rect then rencache.draw_rect(x, y, w, h, c)
  elseif native_renderer and native_renderer.draw_rect then native_renderer.draw_rect(x, y, w, h, c) end
end

local function draw_text_safe(font, text, x, y, c)
  if not font or not text or text == "" then return end
  if rencache and rencache.draw_text then rencache.draw_text(font, text, x, y, c)
  elseif native_renderer and native_renderer.draw_text then native_renderer.draw_text(font, text, x, y, c) end
end

-- ── 2. MOTOR RLE DE ÍCONES (HEFESTO) COM FALLBACK ASCII ───────────────────────
local _ICON_CACHE = {}

local function get_icons_dir()
  local home = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
  return home .. (PATHSEP or "/") .. ".doxoade" .. (PATHSEP or "/") .. "assets" .. (PATHSEP or "/") .. "icons" .. (PATHSEP or "/")
end

local function load_rle_icon(name)
  if _ICON_CACHE[name] ~= nil then return _ICON_CACHE[name] end
  local path = get_icons_dir() .. name .. ".icon.rlebin"
  local f = io.open(path, "rb")
  if not f then
    _ICON_CACHE[name] = false
    return false
  end
  local data = f:read("*a")
  f:close()
  if not data or #data < 20 then
    _ICON_CACHE[name] = false
    return false
  end

  local magic, ver, w, h, ow, oh, count, pos = string.unpack("<c7 I1 I2 I2 I2 I2 I4", data)
  if magic ~= "DOXRLE1" then
    _ICON_CACHE[name] = false
    return false
  end

  local rects = {}
  for _ = 1, count do
    if pos > #data then break end
    local rx, ry, rw, r, g, b, next_pos = string.unpack("<I2 I2 I2 I1 I1 I1", data, pos)
    pos = next_pos
    table.insert(rects, { rx, ry, rw, r, g, b })
  end

  local icon_obj = { w = w, h = h, rects = rects }
  _ICON_CACHE[name] = icon_obj
  return icon_obj
end

local function draw_rle_icon(name, x, y, tint_color)
  local icon = load_rle_icon(name)
  if not icon or not icon.rects then return false end
  for _, rc in ipairs(icon.rects) do
    local c = tint_color or { rc[4], rc[5], rc[6], 255 }
    draw_rect_safe(x + rc[1], y + rc[2], rc[3], 1, c)
  end
  return true
end

-- ── 3. ESTADOS E DESCRIÇÕES PARA AS LEGENDAS (TOOLTIPS) ──────────────────────
local _state = {
  t = 0,
  leap_active = false,
  leap_mode = "idle",
  sl_on = false,
  layout_mode = "auto", -- "auto" | "dual" | "single"
  hovered = nil,
}

local DESCRIPTIONS = {
  check  = "Auditoria Ma'at — clique para executar análise de integridade",
  notes  = "Notas e Agenda P2P — clique para abrir o painel de notas",
  search = "Docs Hub & Busca Global — clique para localizar no projeto",
  term   = "Terminal / Console — clique para abrir o prompt inferior",
  leap   = "Leap KVM — clique para alternar serviço Host/Cliente",
  scroll = "Scroll Lock — se vermelho, desative a tecla no teclado",
  indent = "Indentação — clique para alternar tamanho (2 / 4 / OFF)",
  sel    = "Seleção ativa no documento",
  layout = "Alternador de Escada: clique para alternar 1 Linha ou 2 Linhas (Alt+T)",
}

local function refresh_states()
  local now = os.clock()
  if now - _state.t < 1.0 then return end
  _state.t = now

  -- Leap State
  local home = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
  local lf = io.open(home .. (PATHSEP or "/") .. ".doxoade" .. (PATHSEP or "/") .. "leap_state.json", "r")
  if lf then
    local c = lf:read("*a") or ""; lf:close()
    _state.leap_active = c:find('"active":%s*true') ~= nil
    _state.leap_mode = c:match('"mode":%s*"([^"]+)"') or "idle"
  else
    _state.leap_active = false
  end

  -- Scroll Lock State
  local tmp = os.getenv("TEMP") or os.getenv("TMP") or "."
  local sf = io.open(tmp .. (PATHSEP or "/") .. "doxoade_scroll_lock.txt", "r")
  if sf then
    local l = sf:read("*l") or ""; sf:close()
    _state.sl_on = (l == "1")
  else
    _state.sl_on = false
  end
end

-- ── 4. RESOLUTOR DE CAMINHO RELATIVO (ECONOMIA DE ESPAÇO) ────────────────────
local function get_relative_project_path(path)
  if not path or path == "" then return "Sem Título" end
  local norm = path:gsub("\\", "/")

  if core.project_directories then
    for _, d in ipairs(core.project_directories) do
      local base = (type(d) == "table" and d.name or tostring(d)):gsub("\\", "/")
      if not base:find("/$") then base = base .. "/" end
      if norm:sub(1, #base):lower() == base:lower() then
        return norm:sub(#base + 1)
      end
    end
  end

  if core.project_dir then
    local base = core.project_dir:gsub("\\", "/")
    if not base:find("/$") then base = base .. "/" end
    if norm:sub(1, #base):lower() == base:lower() then
      return norm:sub(#base + 1)
    end
  end

  return norm:match("([^/]+/[^/]+/[^/]+)$") or norm:match("[^/]+/[^/]+$") or norm:match("[^/]+$") or norm
end

-- ── 5. SENSOR DE ORIENTAÇÃO (PORTRAIT vs LANDSCAPE) ───────────────────────────
local function is_two_rows_active(total_w, total_h)
  if _state.layout_mode == "dual" then return true end
  if _state.layout_mode == "single" then return false end
  return (total_h > total_w) or (total_w < 920)
end

local function toggle_rows_mode()
  if _state.layout_mode == "auto" then
    _state.layout_mode = "dual"
    core.log("📐 [TOOLBAR] Modo Forçado: 2 Andares (Escada Dupla).")
  elseif _state.layout_mode == "dual" then
    _state.layout_mode = "single"
    core.log("📐 [TOOLBAR] Modo Forçado: 1 Andar (Compacto).")
  else
    _state.layout_mode = "auto"
    core.log("📐 [TOOLBAR] Modo Responsivo Automático.")
  end
  core.redraw = true
end

command.add(nil, {
  ["doxoade:toggle-toolbar-layout"] = toggle_rows_mode
})
keymap.add { ["alt+t"] = "doxoade:toggle-toolbar-layout" }

-- ── 6. AÇÕES DE DISPARO DOS BOTÕES ───────────────────────────────────────────
local function open_notes_action()
  if command.map and command.map["doxoade:toggle-doxnote-panel"] then
    command.perform("doxoade:toggle-doxnote-panel")
  elseif command.map and command.map["doxoade:open-shared-notes"] then
    command.perform("doxoade:open-shared-notes")
  elseif command.map and command.map["doxoade:note-status-click"] then
    command.perform("doxoade:note-status-click")
  else
    command.perform("core:open-file", "shared_notes.md")
  end
end

local function trigger_check_action()
  if command.map and command.map["doxoade:trigger-active-check"] then
    command.perform("doxoade:trigger-active-check")
  elseif command.map and command.map["doxoade:run-check"] then
    command.perform("doxoade:run-check")
  else
    command.perform("core:find-file")
  end
end

-- Alternador robusto em ciclo de 3 estados (2 -> 4 -> OFF -> 2)
local function toggle_indent_action()
  local doc = core.active_view and core.active_view.doc
  local is_on = (config.draw_indent_guides ~= false)
  local cur_sz = (doc and doc.indent_size) or config.indent_size or 4

  if not is_on then
    config.draw_indent_guides = true
    config.indent_size = 2
    if doc then doc.indent_size = 2 end
    core.log("📐 [INDENT] Guias Ativadas: 2 Espaços.")
  elseif cur_sz == 2 then
    config.draw_indent_guides = true
    config.indent_size = 4
    if doc then doc.indent_size = 4 end
    core.log("📐 [INDENT] Guias Ativadas: 4 Espaços.")
  else
    config.draw_indent_guides = false
    core.log("📐 [INDENT] Guias Desativadas (OFF).")
  end

  if command.map and command.map["doxoade:toggle-indent-guides"] then
    pcall(command.perform, "doxoade:toggle-indent-guides")
  end
  core.redraw = true
end

-- ── 7. CONSTRUÇÃO COMPLETA DOS CHIPS ──────────────────────────────────────────
local function build_action_chips(is_two_rows, total_w)
  refresh_states()
  local chips = {}

  local function add(id, icon, ascii, label, bg, fg, cmd_target)
    local text = (is_two_rows or total_w >= 1100) and (icon .. " " .. label) or icon
    table.insert(chips, {
      id = id, icon = icon, ascii = ascii, label = label, text = text,
      bg = bg, fg = fg, cmd = cmd_target
    })
  end

  local doc = core.active_view and core.active_view.doc

  -- 1. Chip de Seleção Ativa
  if doc and doc.has_selection and doc:has_selection() then
    local l1, c1, l2, c2 = doc:get_selection(true)
    local sel_txt = (l2 > l1) and string.format("%dL", l2 - l1 + 1) or string.format("%dC", math.abs(c2 - c1))
    add("sel", "indent", "SEL", sel_txt, { 25, 45, 60, 255 }, { 56, 189, 248, 255 }, nil)
  end

  -- 2. Chip de Guias de Indentação (Ciclo: 2 / 4 / OFF)
  local ion = (config.draw_indent_guides ~= false)
  local isz = (doc and doc.indent_size) or config.indent_size or 4
  local ind_lbl = ion and tostring(isz) or "OFF"
  local ind_fg = ion and { 110, 231, 183, 255 } or { 120, 120, 128, 255 }
  add("indent", "indent", "IN", ind_lbl, { 20, 40, 30, 255 }, ind_fg, toggle_indent_action)

  -- 3. Chip de Check / Ma'at
  local c_txt, c_col = "OK", { 52, 211, 153, 255 }
  if rawget(_G, "_DOXOADE_AUDIT_RUNNING") then
    c_txt, c_col = "…", { 234, 179, 8, 255 }
  else
    local sum = rawget(_G, "_DOXOADE_AUDIT_SUMMARY")
    if sum and type(sum) == "table" then
      local err_count = tonumber(sum.errors) or 0
      local warn_count = tonumber(sum.warnings) or 0
      if err_count > 0 then c_txt, c_col = tostring(err_count) .. "E", { 239, 68, 68, 255 }
      elseif warn_count > 0 then c_txt, c_col = tostring(warn_count) .. "W", { 234, 179, 8, 255 } end
    end
  end
  add("check", "check", "OK", c_txt, { 20, 50, 35, 255 }, c_col, trigger_check_action)

  -- 4. Botão de Notas e Agenda
  add("notes", "note", "N", "NOTAS", { 45, 30, 60, 255 }, { 216, 180, 254, 255 }, open_notes_action)

  -- 5. Busca Global / Docs Hub
  local s_txt, s_col = "BUSCA", { 147, 197, 253, 255 }
  local st = rawget(_G, "_DOXOADE_SEARCH_STATE")
  if st and st.is_searching then s_txt, s_col = "…", { 234, 179, 8, 255 } end
  local search_cmd = (command.map and command.map["doxoade:open-search-docs-hub"]) and "doxoade:open-search-docs-hub" or "doxoade:execute-pot-search"
  add("search", "search", "Q", s_txt, { 30, 50, 70, 255 }, s_col, search_cmd)

  -- 6. Terminal CLI (Bottom Shelf)
  add("term", "term", ">_", "CLI", { 25, 45, 60, 255 }, { 56, 189, 248, 255 }, "doxoade:toggle-bottom-shelf")

  -- 7. Leap KVM
  local leap_fg = _state.leap_active and { 110, 231, 183, 255 } or { 120, 120, 128, 255 }
  local leap_lbl = _state.leap_active and (_state.leap_mode == "host" and "HST" or "CLI") or "OFF"
  local leap_cmd = (command.map and command.map["doxoade:leap-toggle"]) and "doxoade:leap-toggle" or "doxoade:toggle-leap-service"
  add("leap", "leap", "<>", leap_lbl, { 20, 45, 35, 255 }, leap_fg, leap_cmd)

  -- 8. Scroll Lock
  local sl_fg = _state.sl_on and { 239, 68, 68, 255 } or { 120, 120, 128, 255 }
  add("scroll", "lock", "SL", "SL", { 35, 30, 35, 255 }, sl_fg, function()
    core.log("💡 Dica: Pressione Scroll Lock no teclado físico para alternar.")
  end)

  return chips
end

-- ── 8. HOOK DE UPDATE: ALTURA DAS ESCADAS ─────────────────────────────────────
local orig_statusview_update = StatusView.update
local ROW_H = 22

function StatusView:update(...)
  if orig_statusview_update then orig_statusview_update(self, ...) end
  local root_w = core.root_view and core.root_view.size.x or 1200
  local root_h = core.root_view and core.root_view.size.y or 800
  local two_rows = is_two_rows_active(root_w, root_h)
  self.size.y = two_rows and (ROW_H * 2) or ROW_H
end

-- ── 9. RENDERIZADOR PRINCIPAL DA TOOLBAR ──────────────────────────────────────
local _active_rects = {}

function StatusView:draw(...)
  local font = style.font
  local total_w = self.size.x
  local total_h = self.size.y
  local two_rows = (total_h > ROW_H + 5)
  local pos_x = self.position.x
  local pos_y = self.position.y
  _active_rects = {}

  -- Fundo Geral da Barra
  draw_rect_safe(pos_x, pos_y, total_w, total_h, style.background2 or { 24, 24, 28, 255 })
  draw_rect_safe(pos_x, pos_y, total_w, 1, style.line_number or { 45, 45, 50, 255 })

  local y1 = pos_y + 2
  local y2 = pos_y + (two_rows and ROW_H or 0) + 2

  if two_rows then
    draw_rect_safe(pos_x, pos_y + ROW_H, total_w, 1, { 35, 35, 40, 255 })
  end

  -- ═══════════════════════════════════════════════════════════════════════════
  -- ANDAR 1 (SUPERIOR): FERRAMENTAS & BOTÕES (CALIBRAÇÃO DE TELA)
  -- ═══════════════════════════════════════════════════════════════════════════
  local chips = build_action_chips(two_rows, total_w)
  local cur_x = pos_x + 6

  for _, chip in ipairs(chips) do
    local icon_w = 16
    local label_w = (chip.text:find(" ") and font:get_width(chip.label) + 6) or 0
    local chip_w = icon_w + label_w + 12
    local chip_h = ROW_H - 4
    local is_hover = (_state.hovered == chip.id)

    local bg_color = is_hover and { chip.bg[1] + 20, chip.bg[2] + 20, chip.bg[3] + 20, 255 } or chip.bg
    draw_rect_safe(cur_x, y1, chip_w, chip_h, bg_color)
    draw_rect_safe(cur_x, y1, chip_w, 1, is_hover and (style.accent or { 56, 189, 248, 255 }) or { chip.bg[1] + 30, chip.bg[2] + 30, chip.bg[3] + 30, 255 })

    local icon_y = y1 + math.floor((chip_h - 16) / 2)
    local icon_ok = draw_rle_icon(chip.icon, cur_x + 5, icon_y, chip.fg)
    if not icon_ok then
      draw_text_safe(font, chip.ascii, cur_x + 5, y1 + math.floor((chip_h - font:get_height()) / 2), chip.fg)
    end

    if label_w > 0 then
      local tx = cur_x + icon_w + 8
      local ty = y1 + math.floor((chip_h - font:get_height()) / 2)
      draw_text_safe(font, chip.label, tx, ty, chip.fg)
    end

    table.insert(_active_rects, {
      id = chip.id,
      x = cur_x, y = y1, w = chip_w, h = chip_h,
      cmd = chip.cmd
    })

    cur_x = cur_x + chip_w + 4
  end

  -- Botão de Layout Manual ([2L] / [1L])
  local mode_badge = two_rows and "2L" or "1L"
  if _state.layout_mode == "auto" then mode_badge = mode_badge .. "·A" end
  local badge_w = font:get_width(mode_badge) + 12
  local badge_x = pos_x + total_w - badge_w - 6
  local is_layout_hover = (_state.hovered == "layout")
  draw_rect_safe(badge_x, y1, badge_w, ROW_H - 4, is_layout_hover and { 50, 50, 65, 255 } or { 35, 35, 45, 255 })
  draw_text_safe(font, mode_badge, badge_x + 6, y1 + 2, { 180, 180, 200, 255 })
  table.insert(_active_rects, {
    id = "layout",
    x = badge_x, y = y1, w = badge_w, h = ROW_H - 4,
    cmd = toggle_rows_mode
  })

  -- ═══════════════════════════════════════════════════════════════════════════
  -- ANDAR 2 (INFERIOR): DIRETÓRIO RELATIVO & METADADOS COMPLETOS
  -- ═══════════════════════════════════════════════════════════════════════════
  local doc_x = two_rows and (pos_x + 8) or (cur_x + 10)
  local av = core.active_view
  local doc = av and av.doc

  if doc then
    local raw_path = doc.filename or (doc.get_name and doc:get_name()) or "Sem Título"
    local rel_path = get_relative_project_path(raw_path)
    local display_doc = two_rows and rel_path or (raw_path:match("[^/\\\\]+$") or raw_path)
    if doc.is_dirty and doc:is_dirty() then display_doc = display_doc .. " *" end

    draw_rle_icon("note", doc_x, y2 + 1, style.accent or { 110, 231, 183, 255 })
    local ty = y2 + math.floor((ROW_H - font:get_height()) / 2)
    local doc_fg = (doc.is_dirty and doc:is_dirty()) and { 234, 179, 8, 255 } or (style.text or { 220, 220, 220, 255 })
    draw_text_safe(font, display_doc, doc_x + 20, ty, doc_fg)

    -- Lado Direito: Linhas, Seleção, Indentação, EOL, Encoding e Sintaxe
    local right_info = {}

    -- 1. Posição e Total de Linhas
    if doc.get_selection then
      local l1, c1, l2, c2 = doc:get_selection(true)
      local total_lines = (doc.lines and #doc.lines) or 1
      table.insert(right_info, string.format("Ln %d/%d, Col %d", l1, total_lines, c1))

      -- 2. Seleção Ativa Detalhada
      if l1 ~= l2 or c1 ~= c2 then
        local sel_desc = (l2 > l1)
          and string.format("%d lin. sel.", l2 - l1 + 1)
          or string.format("%d carac. sel.", math.abs(c2 - c1))
        table.insert(right_info, sel_desc)
      end
    end

    -- 3. Modo e Tamanho de Indentação
    local tab_type = config.tab_type or "soft"
    local indent_sz = (doc.indent_size) or config.indent_size or 4
    local tab_desc = (tab_type == "hard") and ("tabs: " .. indent_sz) or ("spaces: " .. indent_sz)
    table.insert(right_info, tab_desc)

    -- 4. Quebra de linha (CRLF / LF)
    table.insert(right_info, (doc.crlf == true) and "CRLF" or "LF")

    -- 5. Codificação do Arquivo (Encoding)
    local enc = doc.encoding or "UTF-8"
    table.insert(right_info, enc:upper())

    -- 6. Sintaxe Ativa
    if doc.syntax and doc.syntax.name then
      table.insert(right_info, doc.syntax.name)
    end

    if #right_info > 0 then
      local info_str = table.concat(right_info, "  |  ")
      local info_w = font:get_width(info_str)
      local info_x = pos_x + total_w - info_w - 10
      local rty = y2 + math.floor((ROW_H - font:get_height()) / 2)
      draw_text_safe(font, info_str, info_x, rty, style.dim or { 150, 150, 160, 255 })
    end
  end
end

-- ── 10. LEGENDA FLUTUANTE (TOOLTIP) & TOAST DE NOTIFICAÇÃO ───────────────────
local function draw_tooltip()
  if not _state.hovered then return end
  local text = DESCRIPTIONS[_state.hovered]
  if not text or text == "" then return end

  local font = style.font
  local tw = font:get_width(text) + 16
  local th = font:get_height() + 8
  local sv = core.status_view
  if not sv then return end

  local target_btn = nil
  for _, b in ipairs(_active_rects) do
    if b.id == _state.hovered then target_btn = b; break end
  end

  local tx = target_btn and target_btn.x or 10
  local ty = sv.position.y - th - 6
  local max_x = (core.root_view.size.x or 1200) - tw - 6
  tx = math.max(6, math.min(tx, max_x))

  draw_rect_safe(tx - 1, ty - 1, tw + 2, th + 2, { 10, 10, 12, 220 })
  draw_rect_safe(tx, ty, tw, th, { 25, 25, 30, 250 })
  draw_rect_safe(tx, ty, tw, 1, style.accent or { 56, 189, 248, 255 })
  draw_text_safe(font, text, tx + 8, ty + 4, { 240, 240, 240, 255 })
end

local function draw_log_toast()
  local sv = core.status_view
  if not sv or not sv.visible or not sv.message then return end
  local msg = sv.message

  local now = (system and system.get_time and system.get_time()) or os.clock()
  local timeout = sv.message_timeout or 0
  if timeout > 0 and now > timeout then
    sv.message = nil
    return
  end

  local text = ""
  if type(msg) == "string" then
    text = msg
  elseif type(msg) == "table" then
    if msg.text then
      text = tostring(msg.text)
    else
      local parts = {}
      for _, p in ipairs(msg) do
        if type(p) == "string" then table.insert(parts, p) end
      end
      text = table.concat(parts, " ")
    end
  end

  if not text or text:match("^%s*$") then return end

  local font = style.font
  local tw = math.min(font:get_width(text) + 24, (core.root_view.size.x or 1200) - 24)
  local th = 24
  local tx = sv.position.x + 8
  local ty = sv.position.y - th - 6

  draw_rect_safe(tx - 1, ty - 1, tw + 2, th + 2, { 8, 14, 24, 160 })
  draw_rect_safe(tx, ty, tw, th, { 24, 82, 155, 245 })
  draw_rect_safe(tx, ty, tw, 1, { 56, 189, 248, 255 })
  draw_text_safe(font, text, tx + 10, ty + math.floor((th - font:get_height()) / 2), { 255, 255, 255, 255 })
end

-- ── 11. DESPACHO SEGURO COM DEBOUNCE ANTI-REENTRADA ──────────────────────────
local _last_click_t = 0

local function handle_action_click(x, y)
  local now = os.clock()
  if now - _last_click_t < 0.20 then
    return true
  end

  for _, btn in ipairs(_active_rects) do
    if x >= btn.x and x <= (btn.x + btn.w) and y >= btn.y and y <= (btn.y + btn.h) then
      _last_click_t = now
      if type(btn.cmd) == "function" then
        btn.cmd()
        core.redraw = true
        return true
      elseif type(btn.cmd) == "string" then
        command.perform(btn.cmd)
        core.redraw = true
        return true
      end
    end
  end
  return false
end

-- ── 12. HOOKS NO ROOTVIEW ─────────────────────────────────────────────────────
local orig_rootview_draw = RootView.draw
function RootView:draw(...)
  orig_rootview_draw(self, ...)
  pcall(draw_tooltip)
  pcall(draw_log_toast)
end

local orig_rootview_on_mouse_moved = RootView.on_mouse_moved
function RootView:on_mouse_moved(px, py, ...)
  local old_h = _state.hovered
  _state.hovered = nil

  for _, b in ipairs(_active_rects) do
    if px >= b.x and px <= (b.x + b.w) and py >= b.y and py <= (b.y + b.h) then
      _state.hovered = b.id
      break
    end
  end

  if _state.hovered ~= old_h then
    core.redraw = true
  end

  if orig_rootview_on_mouse_moved then
    return orig_rootview_on_mouse_moved(self, px, py, ...)
  end
end

local orig_rootview_on_mouse_pressed = RootView.on_mouse_pressed
function RootView:on_mouse_pressed(button, x, y, clicks)
  if button == "left" and handle_action_click(x, y) then
    return true
  end
  if orig_rootview_on_mouse_pressed then
    return orig_rootview_on_mouse_pressed(self, button, x, y, clicks)
  end
end

-- Remove item fantasma legado que causava conflito de assert no Lite XL
pcall(function()
  if core.status_view and core.status_view.remove_item then
    core.status_view:remove_item("doxoade:indent_status")
  end
end)

-- ── Blindagem do StatusView contra conflitos de itens e chamadas legadas ──────
local orig_statusview_add_item = StatusView.add_item
function StatusView:add_item(options, ...)
  -- 1. Normaliza chamada legada: add_item(predicate_fn, name, alignment, ...) -> tabela
  if type(options) == "function" then
    local extra = { ... }
    options = {
      predicate = options,
      name = extra[1],
      alignment = extra[2],
      get_item = extra[3],
      command = extra[4],
      position = extra[5]
    }
  end

  -- 2. Se for tabela e o item já existir, remove antes para não disparar assert no Lite XL
  if type(options) == "table" and options.name then
    if self.get_item and self:get_item(options.name) then
      if self.remove_item then
        pcall(self.remove_item, self, options.name)
      else
        return -- Já existe, ignora assert
      end
    end
  end

  if orig_statusview_add_item then
    return orig_statusview_add_item(self, options, ...)
  end
end

-- ── Hook Soberano de Zoom do Terminal via Ctrl + Wheel ───────────────────────
local orig_rootview_on_mouse_wheel = RootView.on_mouse_wheel
function RootView:on_mouse_wheel(y, x, ...)
  -- Se a tecla Ctrl estiver pressionada durante o scroll do mouse
  if keymap and keymap.modkeys and (keymap.modkeys["ctrl"] or keymap.modkeys["control"]) then
    local my = (self.mouse and self.mouse.y) or 0
    local win_h = (self.size and self.size.y) or 800
    local shelf = rawget(_G, "_DOXOADE_SHELF_HUB") or rawget(_G, "_DOXOADE_BOTTOM_SHELF")

    local is_over_shelf = false
    if shelf and shelf.visible and shelf.position and shelf.size then
      if my >= shelf.position.y and my <= (shelf.position.y + shelf.size.y) then
        is_over_shelf = true
      end
    end

    -- Fallback: gaveta aberta e cursor na metade inferior da tela
    if not is_over_shelf and shelf and shelf.visible and my >= (win_h * 0.40) then
      is_over_shelf = true
    end

    if is_over_shelf then
      local mgr = rawget(_G, "_DOXOADE_TERMINAL_SESSION_MGR")
      local term = (mgr and mgr.get_active()) or rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
      if term and term.adjust_font_size then
        if y > 0 then
          term:adjust_font_size(1)
        elseif y < 0 then
          term:adjust_font_size(-1)
        end
        return true
      end
    end
  end

  if orig_rootview_on_mouse_wheel then
    return orig_rootview_on_mouse_wheel(self, y, x, ...)
  end
end
