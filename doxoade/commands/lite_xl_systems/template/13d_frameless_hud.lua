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
local CommandView = require "core.commandview"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

-- ─── BLINDAGEM CONTRA O "ENTER FANTASMA" DO LITE XL ─────────────────────────
local _last_cmd_view_close = 0

local orig_hide = CommandView.hide
if orig_hide then
  function CommandView:hide()
    _last_cmd_view_close = os.clock()
    return orig_hide(self)
  end
end

local orig_submit = CommandView.submit
if orig_submit then
  function CommandView:submit(text)
    _last_cmd_view_close = os.clock()
    return orig_submit(self, text)
  end
end

local orig_command_perform = command.perform
command.perform = function(name, ...)
  if name == "doc:newline" or name == "doc:new-line" then
    if (os.clock() - _last_cmd_view_close) < 0.2 then
      return -- Engole o Enter Fantasma!
    end
  end
  return orig_command_perform(name, ...)
end
-- ────────────────────────────────────────────────────────────────────────────

-- ─── WINDOW TITLE: Doxly - <modo> - PID <pid> ────────────────────────────
core.add_thread(function()
  coroutine.yield(0.2)
  local sep = PATHSEP or "/"
  local mode = (os.getenv("DOXOADE_DEPLOY_MODE") or "production"):lower()

  local MODE_LABELS = {
    production = "produção",
    test       = "teste",
    staging    = "staging",
    sandbox    = "sandbox",
  }
  local mode_label = MODE_LABELS[mode] or mode

  local pid = "?"
  local pid_file = (USERDIR or ".") .. sep .. "." .. mode .. ".pid"
  local f = io.open(pid_file, "r")
  if f then
    local raw = f:read("*l") or ""
    f:close()
    raw = raw:gsub("%s+", "")
    if raw ~= "" and tonumber(raw) then
      pid = raw
    end
  end

  if system and system.set_window_title then
    local title = string.format("Doxly - %s - PID %s", mode_label, pid)
    system.set_window_title(title)
    if core.log then
      core.log("🪟 [HUD] Título da janela definido: " .. title)
    end
  end
end)

-- ── 1. RENDERIZADORES SEGUROS ─────────────────────────────────────────────────
local function draw_rect_safe(x, y, w, h, c)
  if type(c) ~= "table" or not c[1] or not c[2] or not c[3] then 
    c = { 128, 128, 128, 255 } 
  end
  if not c[4] then c[4] = 255 end

  if rencache and rencache.draw_rect then rencache.draw_rect(x, y, w, h, c)
  elseif native_renderer and native_renderer.draw_rect then native_renderer.draw_rect(x, y, w, h, c) end
end

local function draw_text_safe(font, text, x, y, c)
  if not font or not text or text == "" then return end
  if type(c) ~= "table" or not c[1] or not c[2] or not c[3] then 
    c = { 255, 255, 255, 255 } 
  end
  if not c[4] then c[4] = 255 end

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
    table.insert(rects, { tonumber(rx) or 0, tonumber(ry) or 0, tonumber(rw) or 1, tonumber(r) or 255, tonumber(g) or 255, tonumber(b) or 255 })
  end

  local icon_obj = { w = tonumber(w) or 16, h = tonumber(h) or 16, rects = rects }
  _ICON_CACHE[name] = icon_obj
  return icon_obj
end

local function draw_rle_icon(name, x, y, tint_color)
  local icon = load_rle_icon(name)
  if not icon or not icon.rects then return false end
  for _, rc in ipairs(icon.rects) do
    local c = tint_color or { rc[4], rc[5], rc[6], 255 }
    draw_rect_safe((tonumber(x) or 0) + rc[1], (tonumber(y) or 0) + rc[2], rc[3], 1, c)
  end
  return true
end

-- ── 3. ESTADOS E DESCRIÇÕES PARA AS LEGENDAS (TOOLTIPS) ──────────────────────
local _state = {
  t = 0,
  leap_active = false,
  leap_mode = "idle",
  sl_on = false,
  layout_mode = "auto",
  hovered = nil,
  custom_toast_msg = nil,
  custom_toast_timeout = 0,
  custom_toast_color = { 56, 189, 248, 255 },
  canonical = {
    loaded_at = 0,
    promotion_pending = false,
    staging_exists = false,
    test_exists = false,
    canonical_size = 0,
    staging_size = 0,
    staging_is_aot = false,
  },
  promote_pulse_t = 0,
  hovered_env = nil,
  ctx_menu = nil,
  ctx_menu_rects = {},
}

local DESCRIPTIONS = {
  check       = { title = "Auditoria Ma'at", sub = "Clique para executar análise de integridade" },
  notes       = { title = "Notas e Agenda P2P", sub = "Clique para abrir o painel de notas" },
  search      = { title = "Docs Hub & Busca Global", sub = "Clique para localizar no projeto" },
  term        = { title = "Terminal / Console", sub = "Clique para abrir o prompt inferior" },
  leap        = { title = "Leap KVM", sub = "Clique para alternar serviço Host/Cliente" },
  scroll      = { title = "Scroll Lock", sub = "Se vermelho, desative a tecla no teclado" },
  indent      = { title = "Indentação", sub = "Clique para alternar 2 / 4 / OFF" },
  sel         = { title = "Seleção ativa no documento", sub = "" },
  layout      = { title = "Alternador de Escada", sub = "1L → 2L → 3L (Alt+T cicla)" },
  env_prod    = { title = "Ambiente PRODUCTION", sub = "Clique = abrir · Direito = menu" },
  env_test    = { title = "Ambiente TEST", sub = "Clique = abrir · Direito = menu" },
  env_stg     = { title = "Ambiente STAGING", sub = "Clique = abrir · Direito = menu" },
  promote     = { title = "⚡ Promover staging → test+prod", sub = "Clique = promote · Direito = menu" },
  promote_ok  = { title = "Canonical em sincronia", sub = "Sem promoção pendente" },
  env_canon   = { title = "🏛️ Ambiente CANONICAL", sub = "Clique = abrir ~/.config/lite-xl (sem redeploy) · Direito = menu" },
}

-- ═══════════════════════════════════════════════════════════════
-- MOTOR DE CORES DO TOAST (INFERÊNCIA DE SEVERIDADE)
-- ═══════════════════════════════════════════════════════════════
local function infer_toast_color(msg, explicit_color)
  if explicit_color and type(explicit_color) == "table" and explicit_color[1] and explicit_color[2] and explicit_color[3] then
    return { tonumber(explicit_color[1]) or 0, tonumber(explicit_color[2]) or 0, tonumber(explicit_color[3]) or 0, tonumber(explicit_color[4]) or 255 }
  end

  local text = ""
  if type(msg) == "table" then
    text = tostring(msg.text or "table"):lower()
  else
    text = tostring(msg):lower()
  end
  
  if text:find("error") or text:find("crash") or text:find("fail") or text:find("exception") or 
     text:find("ghost") or text:find("phanto") or text:find("erro") then
    return { 239, 68, 68, 255 }
  elseif text:find("warn") or text:find("aviso") or text:find("wip") or text:find("slow") or 
         text:find("atraso") or text:find("limite") then
    return { 245, 158, 11, 255 }
  elseif text:find("✔") or text:find("success") or text:find("ok") or text:find("done") or 
         text:find("concluído") or text:find("restored") then
    return { 52, 211, 153, 255 }
  elseif text:find("diag") or text:find("key-raw") or text:find("trigger") or 
         text:find("plugin_command") or text:find("watchdog") then
    return { 168, 85, 247, 255 }
  end
  
  return { 56, 189, 248, 255 }
end

local function _safe_time()
  return os.time()
end

-- Bloqueia o toast nativo do Lite XL no topo
local orig_show_message = StatusView.show_message
if orig_show_message then
  function StatusView:show_message(text, color, duration)
    -- O nosso toast é controlado via core.log, então ignoramos o nativo.
  end
end

-- ✅ INTERCEPTAÇÃO DIRETA DO CORE.LOG (Para capturar as mensagens do Doxoade)
local orig_core_log = core.log
core.log = function(...)
  local args = { ... }
  local msg = ""
  if type(args[1]) == "string" then
    local ok, formatted = pcall(string.format, ...)
    msg = ok and formatted or table.concat(args, " ")
  else
    msg = table.concat(args, " ")
  end

  local is_noisy = msg:find("%[KEY-RAW%]") or 
                   msg:find("%[PLUGIN_COMMAND%]") or 
                   msg:find("%[TRIGGER%]") or 
                   msg:find("%[CMD%]")

  if not is_noisy and msg ~= "" and not msg:match("^%s*$") then
    _state.custom_toast_msg = msg
    _state.custom_toast_color = infer_toast_color(msg)
    _state.custom_toast_timeout = _safe_time() + 3.5
    core.redraw = true
  end

  return orig_core_log(...)
end

local function _toast(msg, color, duration)
  _state.custom_toast_msg = tostring(msg)
  _state.custom_toast_color = infer_toast_color(msg, color)
  local dur = tonumber(duration) or 3.0
  _state.custom_toast_timeout = _safe_time() + dur
  core.redraw = true
end

-- FASE 3 — Leitura do status canonical
local _STATUS_TTL = 3.0
local function _read_canonical_status()
  local now = os.clock()
  if (now - _state.canonical.loaded_at) < _STATUS_TTL then return end
  _state.canonical.loaded_at = now
  local sep = PATHSEP or "/"
  local user_dir = USERDIR or "."
  local path = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics" .. sep .. "canonical_status.json"
  local f = io.open(path, "r")
  if not f then return end
  local raw = f:read("*a") or ""
  f:close()
  if raw == "" then return end

  local c = _state.canonical
  c.promotion_pending = raw:find('"promotion_pending"%s*:%s*true') ~= nil
  c.staging_exists = raw:find('"staging"%s*:%s*{[^}]-"exists"%s*:%s*true') ~= nil
  c.test_exists = raw:find('"test"%s*:%s*{[^}]-"exists"%s*:%s*true') ~= nil
  c.staging_is_aot = raw:find('"staging"%s*:%s*{[^}]-"is_aot"%s*:%s*true') ~= nil
  local csize = raw:match('"canonical"%s*:%s*{[^}]-"size"%s*:%s*(%d+)')
  if csize then c.canonical_size = tonumber(csize) or 0 end
  local ssize = raw:match('"staging"%s*:%s*{[^}]-"size"%s*:%s*(%d+)')
  if ssize then c.staging_size = tonumber(ssize) or 0 end
end

local function refresh_states()
  local now = os.clock()
  if now - _state.t < 1.0 then return end
  _state.t = now

  local home = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
  local lf = io.open(home .. (PATHSEP or "/") .. ".doxoade" .. (PATHSEP or "/") .. "leap_state.json", "r")
  if lf then
    local c = lf:read("*a") or ""; lf:close()
    _state.leap_active = c:find('"active":%s*true') ~= nil
    _state.leap_mode = c:match('"mode":%s*"([^"]+)"') or "idle"
  else
    _state.leap_active = false
  end

  local tmp = os.getenv("TEMP") or os.getenv("TMP") or "."
  local sf = io.open(tmp .. (PATHSEP or "/") .. "doxoade_scroll_lock.txt", "r")
  if sf then
    local l = sf:read("*l") or ""; sf:close()
    _state.sl_on = (l == "1")
  else
    _state.sl_on = false
  end
end

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

local function get_tier_count(total_w, total_h)
  if _state.layout_mode == "triple" then return 3 end
  if _state.layout_mode == "dual"   then return 2 end
  if _state.layout_mode == "single" then return 1 end
  if (total_h > total_w) or (total_w < 820) then return 3 end
  if total_w < 1080 then return 2 end
  return 1
end

local function toggle_rows_mode()
  if _state.layout_mode == "auto" then
    _state.layout_mode = "triple"
    core.log("📐 [TOOLBAR] Modo Forçado: 3 Andares (Escada Tripla).")
  elseif _state.layout_mode == "triple" then
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

keymap.add { ["alt+t"] = "doxoade:toggle-toolbar-layout" }

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

  if doc and doc.has_selection and doc:has_selection() then
    local l1, c1, l2, c2 = doc:get_selection(true)
    local sel_txt = (l2 > l1) and string.format("%dL", l2 - l1 + 1) or string.format("%dC", math.abs(c2 - c1))
    add("sel", "indent", "SEL", sel_txt, { 25, 45, 60, 255 }, { 56, 189, 248, 255 }, nil)
  end

  local ion = (config.draw_indent_guides ~= false)
  local isz = (doc and doc.indent_size) or config.indent_size or 4
  local ind_lbl = ion and tostring(isz) or "OFF"
  local ind_fg = ion and { 110, 231, 183, 255 } or { 120, 120, 128, 255 }
  add("indent", "indent", "IN", ind_lbl, { 20, 40, 30, 255 }, ind_fg, toggle_indent_action)

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

  add("notes", "note", "N", "NOTAS", { 45, 30, 60, 255 }, { 216, 180, 254, 255 }, open_notes_action)

  local s_txt, s_col = "BUSCA", { 147, 197, 253, 255 }
  local st = rawget(_G, "_DOXOADE_SEARCH_STATE")
  if st and st.is_searching then s_txt, s_col = "…", { 234, 179, 8, 255 } end
  local search_cmd = (command.map and command.map["doxoade:open-search-docs-hub"]) and "doxoade:open-search-docs-hub" or "doxoade:execute-pot-search"
  add("search", "search", "Q", s_txt, { 30, 50, 70, 255 }, s_col, search_cmd)

  add("term", "term", ">_", "CLI", { 25, 45, 60, 255 }, { 56, 189, 248, 255 }, "doxoade:toggle-bottom-shelf")

  local leap_fg = _state.leap_active and { 110, 231, 183, 255 } or { 120, 120, 128, 255 }
  local leap_lbl = _state.leap_active and (_state.leap_mode == "host" and "HST" or "CLI") or "OFF"
  local leap_cmd = (command.map and command.map["doxoade:leap-toggle"]) and "doxoade:leap-toggle" or "doxoade:toggle-leap-service"
  add("leap", "leap", "<>", leap_lbl, { 20, 45, 35, 255 }, leap_fg, leap_cmd)

  local sl_fg = _state.sl_on and { 239, 68, 68, 255 } or { 120, 120, 128, 255 }
  add("scroll", "lock", "SL", "SL", { 35, 30, 35, 255 }, sl_fg, function()
    core.log("💡 Dica: Pressione Scroll Lock no teclado físico para alternar.")
  end)

  _read_canonical_status()
  local c = _state.canonical

  add("env_prod", "term", "P", "PROD", { 20, 40, 30, 255 }, { 110, 231, 183, 255 }, "doxoade:launch-production")
  add("env_test", "term", "T", "TEST", { 30, 30, 45, 255 }, { 180, 180, 220, 255 }, "doxoade:launch-test")

  if c.staging_exists then
    local stg_bg = c.staging_is_aot and { 45, 30, 20, 255 } or { 30, 40, 40, 255 }
    local stg_fg = c.staging_is_aot and { 245, 158, 11, 255 } or { 100, 200, 200, 255 }
    add("env_stg", "term", "S", "STG", stg_bg, stg_fg, "doxoade:launch-staging")
  end

  add("env_canon", "term", "C", "CANON", { 32, 32, 42, 255 }, { 220, 220, 240, 255 }, "doxoade:launch-canonical")

  if c.promotion_pending then
    _state.promote_pulse_t = ((tonumber(_state.promote_pulse_t) or 0) + 0.05) % (math.pi * 2)
    local pulse = 0.5 + 0.5 * math.sin(_state.promote_pulse_t * 4)
    local bg = { math.floor(60 + 20 * pulse), math.floor(45 + 15 * pulse), math.floor(20 + 10 * pulse), 255 }
    local fg = { 255, 200, 80, 255 }
    add("promote", "check", "⚡", "PROMOTE", bg, fg, "doxoade:do-promote")
  else
    add("promote_ok", "check", "OK", "SYNC", { 20, 50, 35, 255 }, { 52, 211, 153, 255 }, nil)
  end

  return chips
end

local orig_statusview_update = StatusView.update
local ROW_H = 22

function StatusView:update(...)
  if orig_statusview_update then orig_statusview_update(self, ...) end
  local root_w = core.root_view and core.root_view.size.x or 1200
  local root_h = core.root_view and core.root_view.size.y or 800
  local tiers = get_tier_count(tonumber(root_w) or 1200, tonumber(root_h) or 800)
  self.size.y = tiers * ROW_H
end

local _active_rects = {}

function StatusView:draw(...)
  local font = style.font
  local total_w = tonumber(self.size.x) or 1200
  local total_h = tonumber(self.size.y) or 22
  local tiers = math.floor(total_h / ROW_H + 0.5)
  if tiers < 1 then tiers = 1 end
  local pos_x, pos_y = tonumber(self.position.x) or 0, tonumber(self.position.y) or 0
  _active_rects = {}

  draw_rect_safe(pos_x, pos_y, total_w, total_h, style.background2 or { 24, 24, 28, 255 })
  draw_rect_safe(pos_x, pos_y, total_w, 1, style.line_number or { 45, 45, 50, 255 })

  local row_y = {}
  for i = 1, tiers do row_y[i] = pos_y + (i - 1) * ROW_H + 2 end

  local chips = build_action_chips(tiers >= 2, total_w)
  local chip_rows = (tiers >= 2) and (tiers - 1) or 1
  local chip_entries = {}
  for _, chip in ipairs(chips) do
    local label_w = (chip.text:find(" ") and (tonumber(font:get_width(chip.label)) or 0) + 6) or 0
    table.insert(chip_entries, { chip = chip, w = 16 + label_w + 12 })
  end

  local rows_chips = {}
  for i = 1, chip_rows do rows_chips[i] = {} end
  local cur_row, cur_x = 1, pos_x + 6
  local max_x = pos_x + total_w - 90
  for _, entry in ipairs(chip_entries) do
    if cur_x + entry.w > max_x and cur_row < chip_rows then
      cur_row = cur_row + 1
      cur_x = pos_x + 6
    end
    table.insert(rows_chips[cur_row], entry)
    cur_x = cur_x + entry.w + 4
  end

  local STAIRCASE_INDENT = (tiers >= 3) and 10 or 0
  for row_idx, row_chips in ipairs(rows_chips) do
    local x_cursor = pos_x + 6 + (row_idx - 1) * STAIRCASE_INDENT
    local y = row_y[row_idx]
    for _, entry in ipairs(row_chips) do
      local chip, chip_w, chip_h = entry.chip, entry.w, ROW_H - 4
      local is_hover = (_state.hovered == chip.id)
      local bg = is_hover and { (tonumber(chip.bg[1]) or 0)+20, (tonumber(chip.bg[2]) or 0)+20, (tonumber(chip.bg[3]) or 0)+20, 255 } or chip.bg
      draw_rect_safe(x_cursor, y, chip_w, chip_h, bg)
      draw_rect_safe(x_cursor, y, chip_w, 1, is_hover and (style.accent or {56,189,248,255}) or {chip.bg[1]+30, chip.bg[2]+30, chip.bg[3]+30, 255})

      local icon_ok = draw_rle_icon(chip.icon, x_cursor + 5, y + math.floor((chip_h-16)/2), chip.fg)
      if not icon_ok then
        draw_text_safe(font, chip.ascii, x_cursor + 5, y + math.floor((chip_h - (tonumber(font:get_height()) or 14))/2), chip.fg)
      end
      if chip.text:find(" ") then
        draw_text_safe(font, chip.label, x_cursor + 24, y + math.floor((chip_h - (tonumber(font:get_height()) or 14))/2), chip.fg)
      end

      table.insert(_active_rects, { id = chip.id, x = x_cursor, y = y, w = chip_w, h = chip_h, cmd = chip.cmd })
      x_cursor = x_cursor + chip_w + 4
    end
  end

  local badge = tostring(tiers) .. "L"
  if _state.layout_mode == "auto" then badge = badge .. "·A" end
  local bw = (tonumber(font:get_width(badge)) or 0) + 12
  local bx = pos_x + total_w - bw - 6
  local hov = (_state.hovered == "layout")
  draw_rect_safe(bx, row_y[1], bw, ROW_H - 4, hov and { 50, 50, 65, 255 } or { 35, 35, 45, 255 })
  draw_text_safe(font, badge, bx + 6, row_y[1] + 2, { 180, 180, 200, 255 })
  table.insert(_active_rects, { id = "layout", x = bx, y = row_y[1], w = bw, h = ROW_H - 4, cmd = toggle_rows_mode })

  local doc_y = row_y[tiers]
  local av = core.active_view
  local doc = av and av.doc
  if doc then
    local raw = doc.filename or (doc.get_name and doc:get_name()) or "Sem Título"
    local rel = get_relative_project_path(raw)
    local display = (tiers >= 2) and rel or (raw:match("[^/\\\\]+$") or raw)
    if doc.is_dirty and doc:is_dirty() then display = display .. " *" end

    if tiers >= 2 then
      draw_rle_icon("note", pos_x + 8, doc_y + 1, style.accent or { 110, 231, 183, 255 })
      local ty = doc_y + math.floor((ROW_H - (tonumber(font:get_height()) or 14))/2)
      local dc = (doc.is_dirty and doc:is_dirty()) and { 234, 179, 8, 255 } or (style.text or {220,220,220,255})
      draw_text_safe(font, display, pos_x + 28, ty, dc)
    end

    local info = {}
    if doc.get_selection then
      local l1,c1,l2,c2 = doc:get_selection(true)
      local tot = (doc.lines and #doc.lines) or 1
      table.insert(info, string.format("Ln %d/%d, Col %d", l1, tot, c1))
    end
    local tsz = (doc.indent_size) or config.indent_size or 4
    local ttype = config.tab_type or "soft"
    table.insert(info, (ttype == "hard") and ("tabs: "..tsz) or ("spaces: "..tsz))
    table.insert(info, (doc.crlf == true) and "CRLF" or "LF")
    table.insert(info, (doc.encoding or "UTF-8"):upper())
    if doc.syntax and doc.syntax.name then table.insert(info, doc.syntax.name) end

    if #info > 0 then
      local str = table.concat(info, "  |  ")
      local ix = pos_x + total_w - (tonumber(font:get_width(str)) or 0) - 10
      local ty = doc_y + math.floor((ROW_H - (tonumber(font:get_height()) or 14))/2)
      draw_text_safe(font, str, ix, ty, style.dim or {150,150,160,255})
    end
  end
end

local function draw_tooltip()
  if not _state.hovered then return end
  local entry = DESCRIPTIONS[_state.hovered]
  if not entry then return end

  local font = style.font
  local title = entry.title or ""
  local sub   = entry.sub   or ""

  local tw = math.max((tonumber(font:get_width(title)) or 0), (tonumber(font:get_width(sub)) or 0)) + 20
  local th = (tonumber(font:get_height()) or 14) + (sub ~= "" and (tonumber(font:get_height()) or 14) + 4 or 0) + 12

  local sv = core.status_view
  if not sv then return end

  local target_btn = nil
  for _, b in ipairs(_active_rects) do
    if b.id == _state.hovered then target_btn = b; break end
  end

  local tx = target_btn and (tonumber(target_btn.x) or 10) or 10
  local ty = (tonumber(sv.position.y) or 0) - th - 6
  local max_x = (tonumber(core.root_view.size.x) or 1200) - tw - 6
  tx = math.max(6, math.min(tx, max_x))

  draw_rect_safe(tx - 2, ty - 2, tw + 4, th + 4, { 6, 6, 8, 220 })
  draw_rect_safe(tx, ty, tw, th, { 24, 24, 30, 250 })
  draw_rect_safe(tx, ty, 3, th, style.accent or { 56, 189, 248, 255 })
  draw_rect_safe(tx, ty, tw, 1, style.accent or { 56, 189, 248, 255 })

  draw_text_safe(font, title, tx + 10, ty + 6, { 255, 255, 255, 255 })
  if sub ~= "" then
    draw_text_safe(font, sub, tx + 10, ty + 6 + (tonumber(font:get_height()) or 14) + 2, { 180, 180, 190, 255 })
  end
end

local function draw_log_toast()
  local sv = core.status_view
  if not sv or not sv.visible then return end

  local msg = _state.custom_toast_msg
  local now = _safe_time()
  local timeout = tonumber(_state.custom_toast_timeout) or 0

  if not msg or (timeout > 0 and now > timeout) then
    _state.custom_toast_msg = nil
    return
  end

  local text = tostring(msg)
  if text == "" or text:match("^%s*$") then return end

  local font = style.code_font or style.font
  local th = (tonumber(font:get_height()) or 14) + 6
  local tw = math.min((tonumber(font:get_width(text)) or 0) + 24, (tonumber(core.root_view.size.x) or 1200) - 24)

  local tx = (tonumber(sv.position.x) or 0) + 8
  local ty = (tonumber(sv.position.y) or 0) - th - 45

  local col = _state.custom_toast_color or { 56, 189, 248, 255 }

  draw_rect_safe(tx - 1, ty - 1, tw + 2, th + 2, { 10, 10, 14, 180 })
  draw_rect_safe(tx, ty, tw, th, { 15, 15, 20, 240 })
  
  draw_rect_safe(tx, ty, 3, th, col)
  draw_rect_safe(tx, ty, tw, 1, { tonumber(col[1]) or 56, tonumber(col[2]) or 189, tonumber(col[3]) or 248, 100 })

  local text_col = { tonumber(col[1]) or 255, tonumber(col[2]) or 255, tonumber(col[3]) or 255, 255 }
  draw_text_safe(font, text, tx + 10, ty + math.floor((th - (tonumber(font:get_height()) or 14)) / 2), text_col)
end

local _last_click_t = 0

local function handle_action_click(x, y)
  local now = os.clock()
  if now - _last_click_t < 0.20 then return true end
  local nx, ny = tonumber(x) or 0, tonumber(y) or 0

  for _, btn in ipairs(_active_rects) do
    if nx >= (tonumber(btn.x) or 0) and nx <= (tonumber(btn.x) or 0) + (tonumber(btn.w) or 0) and 
       ny >= (tonumber(btn.y) or 0) and ny <= (tonumber(btn.y) or 0) + (tonumber(btn.h) or 0) then
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

local MENU_ITEM_H = 22
local MENU_PAD = 6
local MENU_W = 200

local function _open_env_context_menu(env_id, x, y)
  local env_name = env_id:gsub("env_", "")
  local items = {}
  if env_name == "prod" then
    table.insert(items, { text = "🚀 Redeploy PRODUCTION",  cmd = "doxoade:launch-production" })
    table.insert(items, { text = "⚡ Promote staging → prod", cmd = "doxoade:do-promote" })
    table.insert(items, { text = "💾 Rollback canonical", cmd = "doxoade:rollback-canonical" })
    table.insert(items, { text = "📁 Ver backups",        cmd = "doxoade:list-backups" })
    table.insert(items, { text = "📊 Diff vs staging",    cmd = "doxoade:diff-canonical" })
  elseif env_name == "test" then
    table.insert(items, { text = "🧪 Redeploy TEST", cmd = "doxoade:launch-test" })
  elseif env_name == "stg" then
    table.insert(items, { text = "🎯 Redeploy STAGING", cmd = "doxoade:launch-staging" })
    table.insert(items, { text = "⚡ Promover → test+prod", cmd = "doxoade:do-promote" })
  elseif env_name == "canon" then
    table.insert(items, { text = "🏛️ Abrir Canonical (sem redeploy)", cmd = "doxoade:launch-canonical" })
    table.insert(items, { text = "💾 Rollback canonical", cmd = "doxoade:rollback-canonical" })
    table.insert(items, { text = "📁 Listar backups", cmd = "doxoade:list-backups" })
    table.insert(items, { text = "📊 Diff staging ↔ canonical", cmd = "doxoade:diff-canonical" })
  end
  local menu_h = #items * MENU_ITEM_H + MENU_PAD * 2
  local sw = tonumber(core.root_view and core.root_view.size.x) or 1200
  local sh = tonumber(core.root_view and core.root_view.size.y) or 800
  _state.ctx_menu = {
    x = math.min(tonumber(x) or 0, sw - MENU_W - 8),
    y = math.min(tonumber(y) or 0, sh - menu_h - 8),
    w = MENU_W, h = menu_h, items = items, hovered_idx = nil,
  }
  _state.ctx_menu_rects = {}
  core.redraw = true
end

local function _open_promote_context_menu(x, y)
  local items = {
    { text = "⚡ Promover staging → test+prod", cmd = "doxoade:do-promote" },
    { text = "📊 Ver diff staging",             cmd = "doxoade:diff-canonical" },
    { text = "🔄 Redeploy staging",             cmd = "doxoade:redeploy-staging" },
  }
  local menu_h = #items * MENU_ITEM_H + MENU_PAD * 2
  local sw = tonumber(core.root_view and core.root_view.size.x) or 1200
  local sh = tonumber(core.root_view and core.root_view.size.y) or 800
  _state.ctx_menu = {
    x = math.min(tonumber(x) or 0, sw - MENU_W - 8),
    y = math.min(tonumber(y) or 0, sh - menu_h - 8),
    w = MENU_W, h = menu_h, items = items, hovered_idx = nil,
  }
  _state.ctx_menu_rects = {}
  core.redraw = true
end

local function _draw_context_menu()
  local m = _state.ctx_menu
  if not m then return end
  local mx = tonumber(m.x) or 0
  local my = tonumber(m.y) or 0
  local mw = tonumber(m.w) or 0
  local mh = tonumber(m.h) or 0
  draw_rect_safe(mx - 1, my - 1, mw + 2, mh + 2, { 10, 10, 12, 230 })
  draw_rect_safe(mx, my, mw, mh, { 28, 28, 34, 250 })
  draw_rect_safe(mx, my, mw, 1, style.accent or { 56, 189, 248, 255 })
  _state.ctx_menu_rects = {}
  local font = style.font
  local cy = my + MENU_PAD
  for i, item in ipairs(m.items) do
    local is_hov = (m.hovered_idx == i)
    if is_hov then
      draw_rect_safe(mx + 1, cy, mw - 2, MENU_ITEM_H, { 45, 45, 55, 255 })
    end
    draw_text_safe(font, item.text, mx + 10, cy + 4, is_hov and { 255, 255, 255, 255 } or { 220, 220, 220, 255 })
    table.insert(_state.ctx_menu_rects, { x = mx, y = cy, w = mw, h = MENU_ITEM_H, item = item, idx = i })
    cy = cy + MENU_ITEM_H
  end
end

local orig_rootview_draw = RootView.draw
function RootView:draw(...)
  orig_rootview_draw(self, ...)
  pcall(draw_tooltip)
  pcall(draw_log_toast)
  pcall(_draw_context_menu)
end

local orig_rootview_on_mouse_moved = RootView.on_mouse_moved
function RootView:on_mouse_moved(px, py, ...)
  local old_h = _state.hovered
  _state.hovered = nil
  local npx = tonumber(px) or 0
  local npy = tonumber(py) or 0

  if _state.ctx_menu then
    local m = _state.ctx_menu
    m.hovered_idx = nil
    for _, r in ipairs(_state.ctx_menu_rects) do
      if npx >= (tonumber(r.x) or 0) and npx <= (tonumber(r.x) or 0) + (tonumber(r.w) or 0) and 
         npy >= (tonumber(r.y) or 0) and npy <= (tonumber(r.y) or 0) + (tonumber(r.h) or 0) then
        m.hovered_idx = r.idx
        break
      end
    end
    core.redraw = true
  end

  for _, b in ipairs(_active_rects) do
    if npx >= (tonumber(b.x) or 0) and npx <= (tonumber(b.x) or 0) + (tonumber(b.w) or 0) and 
       npy >= (tonumber(b.y) or 0) and npy <= (tonumber(b.y) or 0) + (tonumber(b.h) or 0) then
      _state.hovered = b.id
      break
    end
  end

  if _state.hovered ~= old_h then core.redraw = true end

  if orig_rootview_on_mouse_moved then return orig_rootview_on_mouse_moved(self, px, py, ...) end
end

local orig_rootview_on_mouse_pressed = RootView.on_mouse_pressed
function RootView:on_mouse_pressed(button, x, y, clicks)
  local nx = tonumber(x) or 0
  local ny = tonumber(y) or 0

  if _state.ctx_menu and (button == "left" or button == 1) then
    for _, r in ipairs(_state.ctx_menu_rects) do
      if nx >= (tonumber(r.x) or 0) and nx <= (tonumber(r.x) or 0) + (tonumber(r.w) or 0) and 
         ny >= (tonumber(r.y) or 0) and ny <= (tonumber(r.y) or 0) + (tonumber(r.h) or 0) then
        local cmd = r.item.cmd
        _state.ctx_menu = nil
        _state.ctx_menu_rects = {}
        core.redraw = true
        if cmd then
          _toast("▶ " .. r.item.text, { 56, 189, 248, 255 })
          command.perform(cmd)
        end
        return true
      end
    end
  end

  if button == "right" or button == 2 then
    for _, b in ipairs(_active_rects) do
      if nx >= (tonumber(b.x) or 0) and nx <= (tonumber(b.x) or 0) + (tonumber(b.w) or 0) and 
         ny >= (tonumber(b.y) or 0) and ny <= (tonumber(b.y) or 0) + (tonumber(b.h) or 0) then
        if b.id == "env_prod" or b.id == "env_test" or b.id == "env_stg" or b.id == "env_canon" then
          _open_env_context_menu(b.id, nx, ny)
          return true
        elseif b.id == "promote" then
          _open_promote_context_menu(nx, ny)
          return true
        end
      end
    end
    if _state.ctx_menu then
      _state.ctx_menu = nil
      _state.ctx_menu_rects = {}
      core.redraw = true
      return true
    end
  end

  if button == "left" and handle_action_click(nx, ny) then return true end
  if orig_rootview_on_mouse_pressed then return orig_rootview_on_mouse_pressed(self, button, x, y, clicks) end
end

pcall(function()
  if core.status_view and core.status_view.remove_item then
    core.status_view:remove_item("doxoade:indent_status")
  end
end)

local orig_statusview_add_item = StatusView.add_item
function StatusView:add_item(options, ...)
  if type(options) == "function" then
    local extra = { ... }
    options = {
      predicate = options, name = extra[1], alignment = extra[2],
      get_item = extra[3], command = extra[4], position = extra[5]
    }
  end
  if type(options) == "table" and options.name then
    if self.get_item and self:get_item(options.name) then
      if self.remove_item then pcall(self.remove_item, self, options.name)
      else return end
    end
  end
  if orig_statusview_add_item then return orig_statusview_add_item(self, options, ...) end
end

local orig_rootview_on_mouse_wheel = RootView.on_mouse_wheel
function RootView:on_mouse_wheel(y, x, ...)
  if keymap and keymap.modkeys and (keymap.modkeys["ctrl"] or keymap.modkeys["control"]) then
    local my = (self.mouse and tonumber(self.mouse.y)) or 0
    local win_h = (self.size and tonumber(self.size.y)) or 800
    local shelf = rawget(_G, "_DOXOADE_SHELF_HUB") or rawget(_G, "_DOXOADE_BOTTOM_SHELF")
    local is_over_shelf = false
    if shelf and shelf.visible and shelf.position and shelf.size then
      local s_y = tonumber(shelf.position.y) or 0
      local s_h = tonumber(shelf.size.y) or 0
      if my >= s_y and my <= (s_y + s_h) then
        is_over_shelf = true
      end
    end
    if is_over_shelf then
      local mgr = rawget(_G, "_DOXOADE_TERMINAL_SESSION_MGR")
      local term = (mgr and mgr.get_active()) or rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
      if term and term.adjust_font_size then
        local ny = tonumber(y) or 0
        if ny > 0 then term:adjust_font_size(1)
        elseif ny < 0 then term:adjust_font_size(-1) end
        return true
      end
    end
  end
  if orig_rootview_on_mouse_wheel then return orig_rootview_on_mouse_wheel(self, y, x, ...) end
end

-- ═══════════════════════════════════════════════════════════════
-- FASE 3 — Comandos do HUD e Execução Assíncrona
-- ═══════════════════════════════════════════════════════════════

local function get_project_root()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local py_anchor = user_dir .. sep .. ".doxoade" .. sep .. "python_path.txt"
  local f = io.open(py_anchor, "r")
  if f then
    local py_exe = f:read("*l") or ""
    f:close()
    py_exe = py_exe:gsub("[\r\n]", "")
    local root = py_exe:match("^(.*)[/\\]venv[/\\]Scripts[/\\]python%.exe$")
    if root then return root end
    root = py_exe:match("^(.*)[/\\]%.venv[/\\]Scripts[/\\]python%.exe$")
    if root then return root end
    root = py_exe:match("^(.*)[/\\]venv[/\\]bin[/\\]python$")
    if root then return root end
  end
  return core.project_dir or "."
end

local function _run_async(cmd)
  local root = get_project_root()
  local args = cmd:gsub("^doxoade%s+", "")
  local full_cmd = string.format('start "" /b cmd /c "cd /d \\"%s\\" && doxoade %s"', root, args)
  local ok = pcall(system.exec, full_cmd)
  if not ok then
    _toast("⚠ Falha ao executar comando. Rode manualmente no terminal.", { 239, 68, 68, 255 })
  end
end

command.add(nil, {
  ["doxoade:launch-production"] = function()
    _toast("🏛️ Redeploy PRODUCTION (recompila + lança)...", { 110, 231, 183, 255 })
    _run_async("doxoade doxly deploy production -f --legacy-direct")
  end,
  ["doxoade:launch-test"] = function()
    _toast("🧪 Redeploy TEST (recompila + lança)...", { 180, 180, 220, 255 })
    _run_async("doxoade doxly deploy test -f")
  end,
  ["doxoade:launch-staging"] = function()
    _toast("🎯 Redeploy STAGING (recompila + lança)...", { 100, 200, 200, 255 })
    _run_async("doxoade doxly deploy staging -f --launch-test")
  end,
  ["doxoade:launch-canonical"] = function()
    _toast("🏛️ Abrindo CANONICAL (sem redeploy)...", { 220, 220, 240, 255 })
    _run_async("doxoade lite-xl canonical")
  end,
  ["doxoade:do-promote"] = function()
    _toast("⚡ Promovendo staging → test+prod...", { 255, 200, 80, 255 })
    _run_async("doxoade doxly deploy promote -f")
    core.add_thread(function()
      coroutine.yield(2.0)
      _state.canonical.loaded_at = 0
      core.redraw = true
    end)
  end,
  ["doxoade:rollback-canonical"] = function()
    _toast("💾 Rollback canonical solicitado...", { 200, 100, 100, 255 })
    _run_async("doxoade doxly deploy restore -m production")
  end,
  ["doxoade:list-backups"] = function()
    _toast("📁 Abrindo lista de backups no terminal...", { 180, 180, 220, 255 })
    _run_async("start cmd /k doxoade doxly deploy restore --list -m production")
  end,
  ["doxoade:diff-canonical"] = function()
    _toast("📊 Gerando diff staging↔canonical...", { 56, 189, 248, 255 })
    _run_async("start cmd /k doxoade doxly deploy status")
  end,
  ["doxoade:redeploy-test"] = function()
    _toast("🔄 Redeploy TEST...", { 180, 180, 220, 255 })
    _run_async("doxoade doxly deploy test -f")
  end,
  ["doxoade:redeploy-staging"] = function()
    _toast("🔄 Redeploy STAGING...", { 100, 200, 200, 255 })
    _run_async("doxoade doxly deploy staging -f --launch-test")
  end,
})
