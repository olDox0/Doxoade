-- doxoade/commands/lite_xl_systems/template/13d_frameless_hud.lua
--[[
  🎛️ DOXOADE TOOLBAR HUD & FLOATING LOG TOAST (V3.3 Safe-Predicate)
  - Zero overrides em get_items: Extingue o crash em merge_deprecated_items.
  - Ocultação de caminhos e diretórios sob os ícones via item.predicate = false.
  - Floating Log Toast: Mensagens de log flutuam ACIMA da barra em Azul com texto Branco.
  - Chips de status na ala esquerda limpa (Seleção, Indent, Check, Note, Search, Terminal, Leap, Scroll Lock).
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core       = require "core"
local style      = require "core.style"
local config     = require "core.config"
local command    = require "core.command"
local RootView   = require "core.rootview"
local StatusView = require "core.statusview"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

if rawget(_G, "_DOXOADE_TOOLBAR_HUD_V3_LOADED") then return end
rawset(_G, "_DOXOADE_TOOLBAR_HUD_V3_LOADED", true)

local CHIP_PAD = 6
local DARK     = { 30, 30, 34, 255 }
local GREEN    = { 38, 188, 95, 255 }
local BLUE     = { 56, 189, 248, 255 }
local GREY     = { 120, 120, 128, 255 }
local RED      = { 239, 68, 68, 255 }
local YEL      = { 234, 179, 8, 255 }

local hud = { chips = {}, hovered = nil, icons = {} }
rawset(_G, "_DOXOADE_TOOLBAR_HUD", hud)

local DESCRIPTIONS = {
  sel    = "Seleção ativa no documento",
  indent = "Guias de indentação — clique para alternar",
  check  = "Auditoria Ma'at — clique para executar",
  note   = "Sincronização de notas P2P — clique para alternar",
  search = "Docs Hub offline (Consult FTS5)",
  term   = "Terminal / Canvas (Bottom Shelf)",
  leap   = "Leap KVM — clique para alternar Host/Cliente",
  scroll = "Scroll Lock — se vermelho, desative no teclado",
}

local function draw_rect_safe(x, y, w, h, c)
  if rencache and rencache.draw_rect then rencache.draw_rect(x, y, w, h, c)
  elseif native_renderer and native_renderer.draw_rect then native_renderer.draw_rect(x, y, w, h, c) end
end

local function draw_text_safe(font, text, x, y, c)
  if not font or not text or text == "" then return end
  if rencache and rencache.draw_text then rencache.draw_text(font, text, x, y, c)
  elseif native_renderer and native_renderer.draw_text then native_renderer.draw_text(font, text, x, y, c) end
end

local function mix(base, accent, t)
  return {
    math.floor(base[1] + (accent[1] - base[1]) * t),
    math.floor(base[2] + (accent[2] - base[2]) * t),
    math.floor(base[3] + (accent[3] - base[3]) * t),
    255
  }
end

local function looks_like_path(s)
  if not s or s == "" then return false end
  local str = tostring(s):lower()
  if str:find("[/\\]") then return true end
  if str:find("^[a-z]:") then return true end
  if str:find("%.%w+$") and #str > 4 then return true end
  if str:find("projetos") or str:find("doxoade") or str:find("autonomo") then return true end
  return false
end

-- =============================================================================
-- DETECÇÃO DE ESTADOS (LEAP & SCROLL LOCK)
-- =============================================================================
local _leap_cache = { t = 0, active = false, mode = "idle" }
local function leap_state()
  local now = os.clock()
  if now - _leap_cache.t < 1.0 then return _leap_cache end
  _leap_cache.t = now
  local home = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
  local f = io.open(home .. (PATHSEP or "/") .. ".doxoade" .. (PATHSEP or "/") .. "leap_state.json", "r")
  if f then
    local c = f:read("*a") or ""; f:close()
    _leap_cache.active = c:find('"active":%s*true') ~= nil
    _leap_cache.mode = c:match('"mode":%s*"([^"]+)"') or "idle"
  else
    _leap_cache.active = false; _leap_cache.mode = "idle"
  end
  return _leap_cache
end

local _sl_cache = { t = 0, on = false }
local function scroll_state()
  local now = os.clock()
  if now - _sl_cache.t < 1.0 then return _sl_cache.on end
  _sl_cache.t = now
  local tmp = os.getenv("TEMP") or os.getenv("TMP") or "."
  local f = io.open(tmp .. (PATHSEP or "/") .. "doxoade_scroll_lock.txt", "r")
  if f then
    local l = f:read("*l") or ""; f:close()
    _sl_cache.on = (l == "1")
  else
    _sl_cache.on = false
  end
  return _sl_cache.on
end

-- =============================================================================
-- CONSTRUÇÃO E DESENHO DOS CHIPS DO HUD
-- =============================================================================
local function build_chips()
  local chips = {}
  local doc = core.active_view and core.active_view.doc
  if doc and doc.has_selection and doc:has_selection() then
    local l1, c1, l2, c2 = doc:get_selection(true)
    local txt = (l2 > l1) and string.format("%dL", l2 - l1 + 1) or string.format("%dC", math.abs(c2 - c1))
    chips[#chips + 1] = { id = "sel", text = txt, color = BLUE, cmd = nil }
  end

  local ion = (config.draw_indent_guides ~= false)
  local isz = config.indent_size or 4
  if doc and doc.filename and tostring(doc.filename):lower():find("%.lua$") then isz = 2 end
  chips[#chips + 1] = { id = "indent", text = ion and tostring(isz) or "OFF", color = ion and GREEN or GREY, cmd = "doxoade:toggle-indent-guides" }

  local ctxt, ccol = "OK", GREEN
  if rawget(_G, "_DOXOADE_AUDIT_RUNNING") then
    ctxt, ccol = "…", YEL
  else
    local sum = rawget(_G, "_DOXOADE_AUDIT_SUMMARY")
    if sum and type(sum) == "table" then
      local e = tonumber(sum.errors) or 0
      local w = tonumber(sum.warnings) or 0
      if e > 0 then ctxt, ccol = string.format("%dE", e), RED
      elseif w > 0 then ctxt, ccol = string.format("%dW", w), YEL end
    end
  end
  chips[#chips + 1] = { id = "check", text = ctxt, color = ccol, cmd = "doxoade:trigger-active-check" }

  local non = rawget(_G, "_DOXOADE_NOTE_SYNC_ACTIVE") ~= false
  chips[#chips + 1] = { id = "note", text = non and "ON" or "OFF", color = non and GREEN or GREY, cmd = "doxoade:note-status-click" }

  local st = rawget(_G, "_DOXOADE_SEARCH_STATE")
  local stxt, scol = "", BLUE
  if st and st.is_searching then stxt, scol = "…", YEL end
  chips[#chips + 1] = { id = "search", text = stxt ~= "" and stxt or "🔍", color = scol, cmd = "doxoade:open-search-docs-hub" }
  chips[#chips + 1] = { id = "term", text = ">_", color = BLUE, cmd = "doxoade:toggle-bottom-shelf" }

  local lp = leap_state()
  local ltxt, lcol = "OFF", GREY
  if lp.active then
    if lp.mode == "host" then ltxt, lcol = "HST", GREEN else ltxt, lcol = "CLI", BLUE end
  end
  chips[#chips + 1] = { id = "leap", text = ltxt, color = lcol, cmd = "doxoade:leap-toggle" }

  local sl = scroll_state()
  chips[#chips + 1] = { id = "scroll", text = "SL", color = sl and RED or GREY, cmd = function()
    core.log("💡 Dica: Pressione a tecla 'Scroll Lock' no teclado para alternar.")
  end }

  return chips
end

local function draw_chips(status_view)
  local font = style.font or style.code_font
  local h = status_view.size.y
  local cy = status_view.position.y + math.floor((h - 18) / 2)
  local cx = status_view.position.x + 4

  hud.chips = build_chips()
  for _, c in ipairs(hud.chips) do
    local text_w = font:get_width(c.text)
    local w = math.max(18, text_w + CHIP_PAD * 2)
    local is_hover = (hud.hovered == c.id)
    local bg = is_hover and mix(DARK, c.color, 0.45) or mix(DARK, c.color, 0.22)

    draw_rect_safe(cx, cy, w, 18, bg)
    draw_rect_safe(cx, cy, w, 1, c.color)
    draw_rect_safe(cx, cy + 17, w, 1, mix(c.color, {0,0,0,255}, 0.5))

    local tx = cx + math.floor((w - text_w) / 2)
    local ty = cy + math.floor((18 - font:get_height()) / 2)
    draw_text_safe(font, c.text, tx, ty, is_hover and {255,255,255,255} or c.color)

    c.rect = { x = cx, y = cy, w = w, h = 18 }
    cx = cx + w + 3
  end
end

-- =============================================================================
-- LOG TOAST FLUTUANTE (AZUL & BRANCO - 6px ACIMA DA BARRA DE STATUS)
-- =============================================================================
local function draw_log_toast()
  local sv = core.status_view
  if not sv or not sv.visible then return end
  local msg = sv.message
  if not msg then return end

  local now = (system and system.get_time and system.get_time()) or os.clock()
  local timeout = sv.message_timeout or (type(msg) == "table" and msg.time) or 0
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

  local icon_str = "ℹ "
  if text:find("💡") or text:lower():find("dica") then
    icon_str = "💡 "
    text = text:gsub("^[💡ℹ%s]+", "")
  elseif text:find("⚠") or text:lower():find("aviso") then
    icon_str = "⚠️ "
    text = text:gsub("^[⚠️⚠%s]+", "")
  end

  local full_text = icon_str .. text
  local font = style.font or style.code_font
  local text_w = font:get_width(full_text)
  local toast_h = 24
  local screen_w = core.root_view.size.x or 1200
  local toast_w = math.min(text_w + 24, screen_w - 24)

  -- Flutua exatamente 6 pixels ACIMA da barra de status
  local toast_x = sv.position.x + 8
  local toast_y = sv.position.y - toast_h - 6

  -- Sombra suave
  draw_rect_safe(toast_x - 1, toast_y - 1, toast_w + 2, toast_h + 2, { 8, 14, 24, 160 })

  -- Fundo Azul Real vibrante
  draw_rect_safe(toast_x, toast_y, toast_w, toast_h, { 24, 82, 155, 245 })

  -- Borda fina em Sky Blue
  draw_rect_safe(toast_x, toast_y, toast_w, 1, { 56, 189, 248, 255 })
  draw_rect_safe(toast_x, toast_y + toast_h - 1, toast_w, 1, { 56, 189, 248, 160 })
  draw_rect_safe(toast_x, toast_y, 1, toast_h, { 56, 189, 248, 255 })
  draw_rect_safe(toast_x + toast_w - 1, toast_y, 1, toast_h, { 56, 189, 248, 255 })

  -- Texto Branco Puro
  local text_y = toast_y + math.floor((toast_h - font:get_height()) / 2)
  draw_text_safe(font, full_text, toast_x + 10, text_y, { 255, 255, 255, 255 })
end

local function draw_tooltip()
  if not hud.hovered then return end
  local text = DESCRIPTIONS[hud.hovered]
  if not text or text == "" then return end
  local font = style.font or style.code_font
  local tw = font:get_width(text) + 16
  local th = font:get_height() + 8
  local sv = core.status_view
  if not sv then return end

  local target_chip = nil
  for _, c in ipairs(hud.chips or {}) do
    if c.id == hud.hovered then target_chip = c break end
  end

  local tx = target_chip and target_chip.rect and target_chip.rect.x or 10
  local ty = sv.position.y - th - 6
  local max_x = (core.root_view.size.x or 1200) - tw - 6
  tx = math.max(6, math.min(tx, max_x))

  draw_rect_safe(tx - 1, ty - 1, tw + 2, th + 2, { 10, 10, 10, 200 })
  draw_rect_safe(tx, ty, tw, th, { 25, 25, 28, 250 })
  draw_rect_safe(tx, ty, tw, 1, style.accent or { 56, 189, 248, 255 })
  draw_text_safe(font, text, tx + 8, ty + 4, style.text or { 240, 240, 240, 255 })
end

-- =============================================================================
-- HOOKS NO STATUSVIEW & ROOTVIEW (SANEAMENTO E RENDERIZAÇÃO)
-- =============================================================================
-- Suprime a mensagem horizontal no rodapé e desativa caminhos via predicate
local orig_statusview_draw = StatusView.draw
function StatusView:draw(...)
  -- 1. Oculta com segurança itens de diretório/arquivo à esquerda através do predicado
  local items_table = self.items or self.left_items
  if type(items_table) == "table" then
    for _, it in pairs(items_table) do
      if type(it) == "table" and it.alignment == StatusView.Item.LEFT then
        local name = tostring(it.name or ""):lower()
        if name == "doc:file-name" or name == "doc:file-info" or name == "file-info" or name:find("path") or name:find("file") then
          it.predicate = function() return false end
        elseif not it._dox_pred_shielded then
          it._dox_pred_shielded = true
          local orig_p = it.predicate or function() return true end
          it.predicate = function(...)
            if not orig_p(...) then return false end
            local ok, parts = pcall(it.get_item, it)
            if ok and type(parts) == "table" then
              for _, p in ipairs(parts) do
                if type(p) == "string" and looks_like_path(p) then
                  return false
                end
              end
            end
            return true
          end
        end
      end
    end
  end

  -- 2. Intercepta a mensagem crua horizontal na barra de status
  local active_msg = self.message
  self.message = nil

  orig_statusview_draw(self, ...)

  self.message = active_msg -- Restaura para o timer do Lite XL

  -- 3. Desenha os chips segmentados
  draw_chips(self)
end

-- Desenha o Toast flutuante e tooltips sem sofrer corte de viewport
local orig_rootview_draw = RootView.draw
function RootView:draw(...)
  orig_rootview_draw(self, ...)
  pcall(draw_tooltip)
  pcall(draw_log_toast)
end

local orig_mouse_moved = RootView.on_mouse_moved
function RootView:on_mouse_moved(px, py, ...)
  hud.hovered = nil
  for _, c in ipairs(hud.chips or {}) do
    if c.rect and px >= c.rect.x and px <= (c.rect.x + c.rect.w) and py >= c.rect.y and py <= (c.rect.y + c.rect.h) then
      hud.hovered = c.id
      core.redraw = true
      break
    end
  end
  return orig_mouse_moved(self, px, py, ...)
end

local orig_mouse_pressed = RootView.on_mouse_pressed
function RootView:on_mouse_pressed(button, px, py, ...)
  if button == "left" then
    for _, c in ipairs(hud.chips or {}) do
      if c.rect and px >= c.rect.x and px <= (c.rect.x + c.rect.w) and py >= c.rect.y and py <= (c.rect.y + c.rect.h) then
        if type(c.cmd) == "function" then
          c.cmd()
        elseif type(c.cmd) == "string" then
          command.perform(c.cmd)
        end
        return true
      end
    end
  end
  return orig_mouse_pressed(self, button, px, py, ...)
end
