-- doxoade/commands/lite_xl_systems/template/13d_frameless_hud.lua
--[[
🎛️ DOXOADE TOOLBAR HUD & ICON RUNTIME (V2.0 Toolbar-Nativa)
- Chips com ícones PNG→RLE (DOXRLE1) desenhados DENTRO da StatusView (rodapé).
- Purga: diretório duplicado + badges emoji (tofu) — por nome E por conteúdo.
- Coexistência: ancora à esquerda do cluster nativo direito (spaces/LF/UTF-8).
- Tooltip de info abre ACIMA da toolbar; zero core.log em interações (UX limpa).
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core    = require "core"
local style   = require "core.style"
local config  = require "core.config"
local command = require "core.command"
local RootView   = require "core.rootview"
local StatusView = require "core.statusview"
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

if rawget(_G, "_DOXOADE_TOOLBAR_HUD_V2_LOADED") then return end
rawset(_G, "_DOXOADE_TOOLBAR_HUD_V2_LOADED", true)

local CHIP_PAD  = 6
local DARK      = { 30, 30, 34, 255 }
local GREEN = { 38, 188, 95, 255 }
local BLUE  = { 56, 189, 248, 255 }
local GREY  = { 120, 120, 128, 255 }
local RED   = { 239, 68, 68, 255 }
local YEL   = { 234, 179, 8, 255 }

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

-- ═══════════════ RENDER SAFE ═══════════════
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
    math.floor(base[3] + (accent[3] - base[3]) * t), 255 }
end

-- ═══════════════ ÍCONES RLE (DOXRLE1) ═══════════════
local function icons_dir()
  local home = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
  local sep = PATHSEP or "/"
  return home .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "icons" .. sep
end
local function load_icon(name)
  local hit = hud.icons[name]
  if hit ~= nil then return hit or nil end
  local f = io.open(icons_dir() .. name .. ".icon.rlebin", "rb")
  if not f then hud.icons[name] = false; return nil end
  local data = f:read("*a") or ""; f:close()
  if #data < 21 or data:sub(1, 7) ~= "DOXRLE1" then hud.icons[name] = false; return nil end
  local ok, ver, gw, gh, ow, oh, count = pcall(string.unpack, "<BHHHHI", data, 8)
  if not ok or ver ~= 1 or not count or count > 20000 then hud.icons[name] = false; return nil end
  local rects, off = {}, 21
  for _ = 1, count do
    local ok2, rx, ry, rw, r, g, b = pcall(string.unpack, "<HHHBBB", data, off)
    if not ok2 or not rx then break end
    off = off + 9
    rects[#rects + 1] = { x = rx, y = ry, w = rw, color = { r, g, b, 255 } }
  end
  local icon = { gw = gw, gh = gh, rects = rects }
  hud.icons[name] = icon
  return icon
end
local function draw_icon(icon, x, y, size, tint)
  if not icon then return false end
  local s = size / icon.gw
  for _, r in ipairs(icon.rects) do
    draw_rect_safe(x + r.x * s, y + r.y * s, math.max(1, r.w * s), math.max(1, s), tint or r.color)
  end
  return true
end

-- ═══════════════ LEITORES DE ESTADO (cache 1s) ═══════════════
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
  else _leap_cache.active = false; _leap_cache.mode = "idle" end
  return _leap_cache
end
local _sl_cache = { t = 0, on = false }
local function scroll_state()
  local now = os.clock()
  if now - _sl_cache.t < 1.0 then return _sl_cache.on end
  _sl_cache.t = now
  local tmp = os.getenv("TEMP") or os.getenv("TMP") or "."
  local f = io.open(tmp .. (PATHSEP or "/") .. "doxoade_scroll_lock.txt", "r")
  if f then local l = f:read("*l") or ""; f:close(); _sl_cache.on = (l == "1")
  else _sl_cache.on = false end
  return _sl_cache.on
end

-- ═══════════════ CONSTRUÇÃO DOS CHIPS ═══════════════
local function build_chips()
  local chips = {}
  local doc = core.active_view and core.active_view.doc
  if doc and doc.has_selection and doc:has_selection() then
    local l1, c1, l2, c2 = doc:get_selection(true)
    local txt = (l2 > l1) and string.format("%dL", l2 - l1 + 1) or string.format("%dC", math.abs(c2 - c1))
    chips[#chips + 1] = { id = "sel", icon = nil, text = txt, color = BLUE, cmd = nil }
  end
  local ion = (config.draw_indent_guides ~= false)
  local isz = config.indent_size or 4
  if doc and doc.filename and tostring(doc.filename):lower():find("%.lua$") then isz = 2 end
  chips[#chips + 1] = { id = "indent", icon = "indent", text = ion and tostring(isz) or "OFF",
    color = ion and GREEN or GREY, cmd = "doxoade:toggle-indent-guides" }
  local ctxt, ccol = "OK", GREEN
  if rawget(_G, "_DOXOADE_AUDIT_RUNNING") then ctxt, ccol = "…", YEL
  else
    local sum = rawget(_G, "_DOXOADE_AUDIT_SUMMARY")
    if sum and type(sum) == "table" then
      local e = tonumber(sum.errors) or 0; local w = tonumber(sum.warnings) or 0
      if e > 0 then ctxt, ccol = string.format("%dE", e), RED
      elseif w > 0 then ctxt, ccol = string.format("%dW", w), YEL end
    end
  end
  chips[#chips + 1] = { id = "check", icon = "check", text = ctxt, color = ccol, cmd = "doxoade:trigger-active-check" }
  local non = rawget(_G, "_DOXOADE_NOTE_SYNC_ACTIVE") ~= false
  chips[#chips + 1] = { id = "note", icon = "note", text = non and "ON" or "OFF",
    color = non and GREEN or GREY, cmd = "doxoade:note-status-click" }
  local st = rawget(_G, "_DOXOADE_SEARCH_STATE")
  local stxt, scol = "", BLUE
  if st and st.is_searching then stxt, scol = "…", YEL end
  chips[#chips + 1] = { id = "search", icon = "search", text = stxt, color = scol, cmd = "doxoade:open-search-docs-hub" }
  chips[#chips + 1] = { id = "term", icon = "term", text = "", color = BLUE, cmd = "doxoade:toggle-bottom-shelf" }
  local lp = leap_state()
  local ltxt, lcol = "OFF", GREY
  if lp.active then
    if lp.mode == "host" then ltxt, lcol = "HST", GREEN else ltxt, lcol = "CLI", BLUE end
  end
  chips[#chips + 1] = { id = "leap", icon = "leap", text = ltxt, color = lcol, cmd = "doxoade:leap-toggle" }
  local sl = scroll_state()
  chips[#chips + 1] = { id = "scroll", icon = "lock", text = sl and "SL" or "",
    color = sl and RED or GREEN, cmd = "doxoade:scroll-lock-hint" }
  return chips
end

-- ═══════════════ DESENHO DENTRO DA STATUSVIEW ═══════════════
local function draw_chips(sv)
  if not sv or not sv.position or not sv.size then return end
  local x, y, w, h = sv.position.x, sv.position.y, sv.size.x, sv.size.y
  local font = style.font
  local chip_h = math.max(14, math.min(18, h - 8))
  local icon_size = chip_h - 4

  -- Mede o cluster nativo DIREITO para ancorar o grupo à esquerda dele
  local right_w = 0
  for _, it in ipairs(sv.items or {}) do
    if it.alignment == StatusView.Item.RIGHT and (not it.predicate or it.predicate()) then
      local ok, res = pcall(it.get_item)
      if ok and type(res) == "table" then
        for i = 2, #res, 2 do right_w = right_w + font:get_width(tostring(res[i] or "")) end
      end
    end
  end

  local chips = build_chips()
  hud.chips = chips
  local total = 0
  for _, ch in ipairs(chips) do
    local tw = font:get_width(ch.text or "")
    ch.w = CHIP_PAD + (ch.icon and icon_size + 4 or 0) + tw + CHIP_PAD
    total = total + ch.w
  end

  local group_x = x + w - right_w - total - 12
  if group_x < x + 4 then group_x = x + 4 end
  local cy = y + math.floor((h - chip_h) / 2)
  local cx = group_x

  for i, ch in ipairs(chips) do
    ch.rect = { x = cx, y = cy, w = ch.w, h = chip_h }
    local bg = mix(DARK, ch.color, (hud.hovered == ch.id) and 0.50 or 0.22)
    draw_rect_safe(cx, cy, ch.w, chip_h, bg)
    -- divisória interna de 1px entre segmentos (efeito controle segmentado)
    if i > 1 then draw_rect_safe(cx, cy, 1, chip_h, { 0, 0, 0, 120 }) end
    -- fio de luz no topo e sombra na base do segmento
    draw_rect_safe(cx, cy, ch.w, 1, mix(bg, { 255, 255, 255, 255 }, 0.14))
    draw_rect_safe(cx, cy + chip_h - 1, ch.w, 1, { 0, 0, 0, 90 })

    local ix = cx + CHIP_PAD
    if ch.icon then
      local icon = load_icon(ch.icon)
      if icon then
        draw_icon(icon, ix, cy + math.floor((chip_h - icon_size) / 2), icon_size,
          mix(ch.color, { 255, 255, 255, 255 }, 0.55))
      end
      ix = ix + icon_size + 4
    end
    draw_text_safe(font, ch.text, ix, cy + 2, { 245, 245, 245, 255 })
    cx = cx + ch.w
  end

  -- divisória vertical separando o grupo HUD do cluster nativo (respiração)
  if #chips > 0 then
    draw_rect_safe(group_x - 6, cy - 2, 1, chip_h + 4, { 70, 70, 78, 255 })
  end
end

local orig_sv_draw = StatusView.draw
function StatusView:draw(...)
  orig_sv_draw(self, ...)
  pcall(draw_chips, self)
end

-- ═══════════════ TOOLTIP ACIMA DA TOOLBAR (nunca sobre ela) ═══════════════
local function draw_tooltip()
  if not hud.hovered then return end
  local sv = core.status_view
  if not sv or not sv.position then return end
  local ch = nil
  for _, c in ipairs(hud.chips) do if c.id == hud.hovered then ch = c break end end
  if not ch or not ch.rect then return end
  local text = DESCRIPTIONS[ch.id] or ch.id
  local font = style.font
  local tw = font:get_width(text)
  local bw, bh = tw + 16, 22
  local W = core.root_view.size.x
  local bx = math.max(4, math.min(ch.rect.x, W - bw - 4))
  local by = sv.position.y - bh - 6   -- ⬆️ ACIMA da toolbar
  draw_rect_safe(bx - 1, by - 1, bw + 2, bh + 2, { 0, 0, 0, 200 })
  draw_rect_safe(bx, by, bw, bh, { 22, 22, 26, 255 })
  draw_rect_safe(bx, by, bw, 2, ch.color)
  draw_text_safe(font, text, bx + 8, by + 5, { 235, 235, 235, 255 })
end
local orig_rv_draw = RootView.draw
function RootView:draw(...)
  orig_rv_draw(self, ...)
  pcall(draw_tooltip)
end

-- ═══════════════ MOUSE (somente dentro da StatusView) ═══════════════
local function chip_at(px, py)
  local sv = core.status_view
  if not sv or not sv.position or not sv.size then return nil end
  if py < sv.position.y or py > sv.position.y + sv.size.y then return nil end
  for _, ch in ipairs(hud.chips) do
    if ch.rect and px >= ch.rect.x and px < ch.rect.x + ch.rect.w then return ch end
  end
  return nil
end
local orig_pressed = RootView.on_mouse_pressed
function RootView:on_mouse_pressed(button, x, y, clicks)
  if button == "left" then
    local ch = chip_at(x, y)
    if ch then
      if ch.cmd then command.perform(ch.cmd) end
      return true
    end
  end
  return orig_pressed(self, button, x, y, clicks)
end
local orig_moved = RootView.on_mouse_moved
function RootView:on_mouse_moved(x, y, ...)
  local ch = chip_at(x, y)
  local id = ch and ch.id or nil
  if id ~= hud.hovered then
    hud.hovered = id
    core.redraw = true
  end
  return orig_moved(self, x, y, ...)
end

-- ═══════════════ PURGA DA STATUSVIEW (nome + conteúdo) ═══════════════
local PURGE_NAMES = {
  "doxoade:selection_counter", "doxoade:indent_status", "doxoade:check_status",
  "doxoade:note_status", "doxoade:search_status", "doxoade:bottom_shelf_btn",
  "doxoade:leap_status", "doxoade:scroll_lock_status",
}

local function item_text(it)
  local ok, res = pcall(it.get_item)
  if not ok or type(res) ~= "table" then return "" end
  local out = ""
  for i = 2, #res, 2 do out = out .. tostring(res[i] or "") end
  return out
end

-- 🛡️ Detecta QUALQUER fragmento de caminho (inclusive truncados no meio):
-- precisa ter separador de diretório entre caracteres de palavra e tamanho >= 7.
-- Itens nativos ("spaces: 4", "CRLF", "953 lines", "Ln 1, Col 1", "C/C++") nunca casam.
local function looks_like_path_fragment(txt)
  if not txt or #txt < 7 then return false end
  if txt:find("[%w%)%]]%s*[/\\]%s*[%w%(%.]") then return true end
  return false
end

local function purge_status_bar()
  local sv = core.status_view
  if not sv then return end
  if sv.remove_item then
    for _, nm in ipairs(PURGE_NAMES) do pcall(function() sv:remove_item(nm) end) end
  end
  if sv.items then
    for i = #sv.items, 1, -1 do
      local it = sv.items[i]
      local nm = tostring((it or {}).name or "")
      local kill = false
      for _, p in ipairs(PURGE_NAMES) do if nm == p then kill = true break end end
      if not kill and (nm:find("path") or nm:find("dir") or nm:find("cwd") or nm:find("folder")) then
        kill = true
      end
      if not kill then
        if looks_like_path_fragment(item_text(it)) then kill = true end
      end
      if kill then table.remove(sv.items, i) end
    end
  end
  core.redraw = true
end

core.add_thread(function()
  coroutine.yield(0.40); purge_status_bar()
  coroutine.yield(0.80); purge_status_bar()
  coroutine.yield(1.30); purge_status_bar()
end)

-- ═══════════════ COMANDOS ═══════════════
command.add(nil, {
  ["doxoade:scroll-lock-hint"] = function()
    -- Info via tooltip/log silencioso: NÃO notifica sobre a toolbar
    if core.log then core.log("Scroll Lock: pressione a tecla Scroll Lock no teclado para alternar.") end
  end,
  ["doxoade:hud-reload-icons"] = function()
    hud.icons = {}
    core.redraw = true
  end,
})
