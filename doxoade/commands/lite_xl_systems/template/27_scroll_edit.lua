-- doxoade/commands/lite_xl_systems/template/27_scroll_edit.lua
-- 🖱️ SCROLL EDIT V3 — Middle click (padrão) + wheel rotation opcional
if rawget(_G, "_DOXOADE_SCROLL_EDIT_LOADED") then return end
rawset(_G, "_DOXOADE_SCROLL_EDIT_LOADED", true)

local core     = require "core"
local config   = require "core.config"
local keymap   = require "core.keymap"
local RootView = require "core.rootview"

-- ═══════════════════════════════════════════════════════════════
-- CONFIG (default: middle click, per user request)
-- ═══════════════════════════════════════════════════════════════
config.doxoade_scroll_edit_trigger     = config.doxoade_scroll_edit_trigger or "click"
--   "click"  → só o botão do meio (default)
--   "wheel"  → só rotação da rodinha (modo V2)
--   "both"   → ambos funcionam
config.doxoade_scroll_edit_mode        = config.doxoade_scroll_edit_mode or "dynamic"
--   "off"     → desativa tudo
--   "safe"    → clique sempre funciona; wheel exige Ctrl
--   "dynamic" → clique + wheel (sem exigir Ctrl)
config.doxoade_scroll_edit_cooldown_ms = config.doxoade_scroll_edit_cooldown_ms or 600
config.doxoade_scroll_edit_paste_window_ms = config.doxoade_scroll_edit_paste_window_ms or 6000
config.doxoade_scroll_edit_min_sel_chars   = config.doxoade_scroll_edit_min_sel_chars or 3
config.doxoade_scroll_edit_max_sel_lines   = config.doxoade_scroll_edit_max_sel_lines or 100
config.doxoade_scroll_edit_debug           = config.doxoade_scroll_edit_debug or false

-- ═══════════════════════════════════════════════════════════════
-- HELPERS
-- ═══════════════════════════════════════════════════════════════
local _last_action_time = 0
local _last_cut_time = 0

local function _ctrl_held()
  if not (keymap and keymap.modkeys) then return false end
  local mk = keymap.modkeys
  if type(mk) ~= "table" then return false end
  return mk["ctrl"] == true or mk["control"] == true
end

local function _clipboard()
  if not (system and system.get_clipboard) then return "" end
  local ok, txt = pcall(system.get_clipboard)
  return (ok and tostring(txt or "")) or ""
end

local function _set_clipboard(txt)
  if not (system and system.set_clipboard) then return false end
  return pcall(system.set_clipboard, txt)
end

local function _get_selection(doc)
  if not doc or type(doc.has_selection) ~= "function" then return nil end
  local ok1, has = pcall(doc.has_selection, doc)
  if not ok1 or not has then return nil end
  local ok2, l1, c1, l2, c2 = pcall(doc.get_selection, doc, true)
  if not ok2 or not l1 or not c1 or not l2 or not c2 then return nil end
  local ok3, txt = pcall(doc.get_text, doc, l1, c1, l2, c2)
  if not ok3 or not txt then return nil end
  if #txt < (config.doxoade_scroll_edit_min_sel_chars or 3) then return nil end
  return { text = txt, l1 = l1, c1 = c1, l2 = l2, c2 = c2,
           lines = (l2 - l1 + 1) }
end

local function _cut(doc, sel)
  if not _set_clipboard(sel.text) then return false end
  local ok = pcall(function()
    doc:remove(sel.l1, sel.c1, sel.l2, sel.c2)
    doc:set_selection(sel.l1, sel.c1, sel.l1, sel.c1)
  end)
  if not ok then return false end
  _last_cut_time = os.clock()
  if core.log then
    core.log(string.format("✂️ [SCROLL] Recortado: %d chars, %d linhas",
      #sel.text, sel.lines))
  end
  core.redraw = true
  return true
end

local function _paste(doc, text)
  if #text == 0 then return false end
  local ok, l, c = pcall(doc.get_selection, doc, true)
  if not ok or not l or not c then return false end
  if doc.has_selection and doc:has_selection() then
    pcall(doc.set_selection, doc, l, c, l, c)
  end
  if not pcall(doc.insert, doc, l, c, text) then return false end
  local nl, nc = l, c
  for i = 1, #text do
    if text:sub(i, i) == "\n" then nl = nl + 1; nc = 1
    else nc = nc + 1 end
  end
  pcall(doc.set_selection, doc, nl, nc, nl, nc)
  if core.log then
    core.log(string.format("📋 [SCROLL] Colado: %d chars", #text))
  end
  core.redraw = true
  return true
end

-- ═══════════════════════════════════════════════════════════════
-- CORE LOGIC (shared)
-- ═══════════════════════════════════════════════════════════════
local function _handle_action(doc)
  local now = os.clock()
  local cd = (config.doxoade_scroll_edit_cooldown_ms or 600) / 1000
  if (now - _last_action_time) < cd then
    if config.doxoade_scroll_edit_debug and core.log then
      core.log("[SCROLL] cooldown ativo")
    end
    return false
  end

  local sel = _get_selection(doc)
  if sel then
    local max_lines = config.doxoade_scroll_edit_max_sel_lines or 100
    if max_lines > 0 and sel.lines > max_lines then
      if config.doxoade_scroll_edit_debug and core.log then
        core.log(string.format("[SCROLL] seleção grande (%d > %d), delegando",
          sel.lines, max_lines))
      end
      return false
    end
    _last_action_time = now
    return _cut(doc, sel)
  end

  local win = (config.doxoade_scroll_edit_paste_window_ms or 6000) / 1000
  if (now - _last_cut_time) < win then
    local txt = _clipboard()
    if #txt > 0 then
      _last_action_time = now
      if _paste(doc, txt) then
        _last_cut_time = 0
        return true
      end
    end
  end

  if config.doxoade_scroll_edit_debug and core.log then
    core.log(string.format(
      "[SCROLL] no action (ctrl=%s, cut_age=%.1fs)",
      tostring(_ctrl_held()), now - _last_cut_time))
  end
  return false
end

-- ═══════════════════════════════════════════════════════════════
-- HOOK: Middle click (trigger = "click" ou "both")
-- ═══════════════════════════════════════════════════════════════
local _orig_pressed = RootView.on_mouse_pressed
RootView.on_mouse_pressed = function(self, button, x, y, clicks)
  local trigger = config.doxoade_scroll_edit_trigger or "click"
  local mode    = config.doxoade_scroll_edit_mode or "dynamic"

  if trigger ~= "click" and trigger ~= "both" then
    return _orig_pressed(self, button, x, y, clicks)
  end
  if mode == "off" then
    return _orig_pressed(self, button, x, y, clicks)
  end

  -- Middle button detection (Lite XL: "middle"; SDL2: 2 ou 3)
  local is_middle = (button == "middle") or (button == 2) or (button == 3)
  if not is_middle then
    return _orig_pressed(self, button, x, y, clicks)
  end

  local view = core.active_view
  local doc = view and view.doc
  if not doc then
    return _orig_pressed(self, button, x, y, clicks)
  end

  if _handle_action(doc) then
    return true   -- consome: evita auto-scroll nativo do middle click
  end
  return _orig_pressed(self, button, x, y, clicks)
end

-- ═══════════════════════════════════════════════════════════════
-- HOOK: Wheel rotation (trigger = "wheel" ou "both")
-- ═══════════════════════════════════════════════════════════════
local _orig_wheel = RootView.on_mouse_wheel
RootView.on_mouse_wheel = function(self, y, x, ...)
  local trigger = config.doxoade_scroll_edit_trigger or "click"
  local mode    = config.doxoade_scroll_edit_mode or "dynamic"

  if trigger ~= "wheel" and trigger ~= "both" then
    return _orig_wheel(self, y, x, ...)
  end
  if mode == "off" then
    return _orig_wheel(self, y, x, ...)
  end
  if mode == "safe" and not _ctrl_held() then
    return _orig_wheel(self, y, x, ...)
  end

  local view = core.active_view
  local doc = view and view.doc
  if not doc then
    return _orig_wheel(self, y, x, ...)
  end

  if _handle_action(doc) then return true end
  return _orig_wheel(self, y, x, ...)
end

core.log(string.format(
  "🖱️ [SCROLL EDIT V3] Trigger='%s' mode='%s' (cooldown %dms, paste %ds)",
  config.doxoade_scroll_edit_trigger,
  config.doxoade_scroll_edit_mode,
  config.doxoade_scroll_edit_cooldown_ms,
  config.doxoade_scroll_edit_paste_window_ms / 1000))
