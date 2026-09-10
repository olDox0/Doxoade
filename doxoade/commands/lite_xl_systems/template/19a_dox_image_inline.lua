-- doxoade/commands/lite_xl_systems/template/19a_dox_image_inline.lua
--[[
  🖼️ DOXOADE INLINE IMAGE CARDS (V49.0 Pure Native Gutter & Smart Paste)
  - Numeração 100% Nativa: Zero interferência no Gutter, scroll e cliques do editor.
  - Renderização Limpa: Card acoplado diretamente ao corpo da linha.
  - Proporção 16:9 Letterbox sem esticar a imagem.
  - Botão [Copiar]: Injeta o bitmap direto na área de transferência do Windows.
  - Botão [HD]: Abre no Canvas Studio com pan e zoom a 60 FPS.
  - Ctrl+V Inteligente: Cola texto se houver texto, ou print/imagem se houver imagem.
]]
local core = require "core"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local DocView = require "core.docview"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local CARD_HEIGHT = 180
local CARD_MARGIN_X = 10
local _image_meta_cache = {}
local _meta_order = {}
local MAX_META_CACHE = 64
local _card_interactive_regions = {}

local function draw_rect_safe(x, y, w, h, color)
  if not color or type(color) ~= "table" then color = { 128, 128, 128, 255 } end
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

local function draw_text_safe(font, text, x, y, color)
  if not font or not text then return end
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

-- =============================================================================
-- 🔍 DETECTOR DE TAGS [DOX-IMG]
-- =============================================================================
local function extract_dox_image_info(line_text)
  if not line_text or line_text == "" then return nil end
  if not line_text:find("DOX%-IMG") and not line_text:find("%.doxoade/assets/images") then return nil end

  local fn, res, dt = line_text:match("%[DOX%-IMG:%s*([%w_%-%.]+%.png)%s*|?%s*([^|%]]*)%s*|?%s*([^%]]*)%]")
  if fn then
    return {
      filename = fn:gsub("^%s*", ""):gsub("%s*$", ""),
      resolution = (res ~= "" and res:gsub("^%s*", ""):gsub("%s*$", "")) or "HD",
      date = (dt ~= "" and dt:gsub("^%s*", ""):gsub("%s*$", "")) or "Recente",
    }
  end

  local md_fn = line_text:match("!%[[^%]]*%]%(%.doxoade/assets/images/([%w_%-%.]+%.png)%)")
  if md_fn then
    return { filename = md_fn, resolution = "HD", date = "Markdown" }
  end
  return nil
end
rawset(_G, "_DOXOADE_EXTRACT_IMAGE_INFO", extract_dox_image_info)

local function get_active_project_dir()
  if core.project_directories and #core.project_directories > 0 then
    local p = core.project_directories[1]
    return tostring(type(p) == "table" and (p.path or p.name) or p)
  end
  return core.project_dir or "."
end

local function resolve_image_full_path(filename)
  local proj_dir = get_active_project_dir()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local candidates = {
    proj_dir .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "images" .. sep .. filename,
    proj_dir .. sep .. "doxoade" .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "images" .. sep .. filename,
    user_dir .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "images" .. sep .. filename,
  }
  for _, path in ipairs(candidates) do
    if system.get_file_info(path) then return path end
  end
  return candidates[1]
end

-- =============================================================================
-- 📦 CARREGADOR DOXRLE1 BINÁRIO
-- =============================================================================
local function load_rle_binary(path)
  local f = io.open(path, "rb")
  if not f then return nil end
  local data = f:read("*a") or ""
  f:close()
  if #data < 21 or data:sub(1, 7) ~= "DOXRLE1" then return nil end

  local ok, ver, gw, gh, ow, oh, count = pcall(string.unpack, "<BHHHHI", data, 8)
  if not ok or ver ~= 1 or count > 60000 then return nil end

  local rects = {}
  local off = 21
  for i = 1, count do
    local ok2, rx, ry, rw, r, g, b = pcall(string.unpack, "<HHHBBB", data, off)
    if not ok2 then break end
    off = off + 9
    rects[i] = { x = rx, y = ry, w = rw, h = 1, color = { r, g, b, 255 } }
  end
  return { grid_w = gw, grid_h = gh, orig_w = ow, orig_h = oh, rects = rects }
end

local function load_image_meta(filename)
  local hit = _image_meta_cache[filename]
  if hit then return hit end

  local img_path = resolve_image_full_path(filename)
  local sidecar_path = img_path:gsub("%.png$", ".thumb.rlebin")
  local bin = load_rle_binary(sidecar_path)

  local meta = {
    filename = filename,
    loaded = false,
    width = 1366,
    height = 768,
    grid_w = 240,
    grid_h = 136,
    rects = {}
  }

  if bin and bin.rects and #bin.rects > 0 then
    meta.width = bin.orig_w
    meta.height = bin.orig_h
    meta.grid_w = bin.grid_w
    meta.grid_h = bin.grid_h
    meta.rects = bin.rects
    meta.loaded = true
  end

  if _image_meta_cache[filename] == nil then
    table.insert(_meta_order, filename)
    if #_meta_order > MAX_META_CACHE then
      local old = table.remove(_meta_order, 1)
      _image_meta_cache[old] = nil
    end
  end
  _image_meta_cache[filename] = meta
  return meta
end

-- =============================================================================
-- 🎨 RENDERIZADOR DO CARD ACOPLADO À LINHA
-- =============================================================================
local function draw_image_card(view, line_idx, info, x, y, line_h)
  local meta = load_image_meta(info.filename)
  local card_w = math.min(view.size.x - x - 20, 560)
  if card_w < 200 then card_w = 200 end
  local card_h = CARD_HEIGHT
  local card_x = x + CARD_MARGIN_X
  local card_y = y + line_h + 2

  draw_rect_safe(card_x - 1, card_y - 1, card_w + 2, card_h + 2, { 30, 30, 32, 255 })
  draw_rect_safe(card_x, card_y, card_w, card_h, style.background2 or { 24, 24, 27, 255 })
  draw_rect_safe(card_x, card_y, 3, card_h, style.accent or { 38, 188, 95, 255 })

  -- Cabeçalho
  local header_text = string.format("[IMG] %s (%dx%d)", info.filename, meta.width, meta.height)
  draw_text_safe(style.font, header_text, card_x + 8, card_y + 4, style.accent or { 38, 188, 95, 255 })

  -- Botões de Ação
  local btn_copy_x = card_x + card_w - 122
  local btn_hd_x = card_x + card_w - 56
  local btn_y = card_y + 4
  local btn_h = 18

  draw_rect_safe(btn_copy_x, btn_y, 62, btn_h, { 40, 40, 45, 255 })
  draw_text_safe(style.font, "[Copiar]", btn_copy_x + 5, btn_y + 1, { 220, 220, 220, 255 })

  draw_rect_safe(btn_hd_x, btn_y, 50, btn_h, { 40, 40, 45, 255 })
  draw_text_safe(style.font, "[HD]", btn_hd_x + 8, btn_y + 1, { 56, 189, 248, 255 })

  _card_interactive_regions[info.filename] = {
    btn_copy = { x = btn_copy_x, y = btn_y, w = 62, h = btn_h, filename = info.filename },
    btn_hd = { x = btn_hd_x, y = btn_y, w = 50, h = btn_h, filename = info.filename },
  }

  -- Janela da Imagem (16:9 Letterbox)
  local thumb_box_x = card_x + 8
  local thumb_box_y = card_y + 26
  local thumb_box_w = card_w - 16
  local thumb_box_h = card_h - 32
  draw_rect_safe(thumb_box_x, thumb_box_y, thumb_box_w, thumb_box_h, { 10, 10, 10, 255 })

  if meta.loaded and #meta.rects > 0 then
    local scale = math.min(thumb_box_w / math.max(1, meta.grid_w), thumb_box_h / math.max(1, meta.grid_h))
    local rendered_w = meta.grid_w * scale
    local rendered_h = meta.grid_h * scale
    local offset_x = thumb_box_x + math.floor((thumb_box_w - rendered_w) / 2)
    local offset_y = thumb_box_y + math.floor((thumb_box_h - rendered_h) / 2)

    core.push_clip_rect(thumb_box_x, thumb_box_y, thumb_box_w, thumb_box_h)
    for _, r in ipairs(meta.rects) do
      local rx = offset_x + (r.x * scale)
      local ry = offset_y + (r.y * scale)
      local rw = math.max(1, r.w * scale)
      local rh = math.max(1, (r.h or 1) * scale)
      draw_rect_safe(rx, ry, rw, rh, r.color)
    end
    core.pop_clip_rect()
  else
    draw_text_safe(style.font, "Gerando preview em alta definição...", thumb_box_x + 10, thumb_box_y + 20, style.dim)
  end
end

-- =============================================================================
-- 🖌️ HOOK ÚNICO E NÃO-INVASIVO (APENAS EM DRAW_LINE_BODY)
-- =============================================================================
local original_draw_line_body = DocView.draw_line_body
function DocView:draw_line_body(line_idx, x, y)
  local res = original_draw_line_body(self, line_idx, x, y)
  if self.doc and self.doc.lines and self.doc.lines[line_idx] then
    local text = self.doc.lines[line_idx]
    local info = extract_dox_image_info(text)
    if info then
      local line_h = self:get_line_height()
      draw_image_card(self, line_idx, info, x, y, line_h)
    end
  end
  return res
end

-- =============================================================================
-- 🐍 LOCALIZADOR DO PYTHON ATIVO (ÂNCORA INFALÍVEL)
-- =============================================================================
local function detect_project_python()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local proj_dir = get_active_project_dir()

  local anchor_paths = {
    user_dir .. sep .. ".doxoade" .. sep .. "python_path.txt",
    proj_dir .. sep .. ".doxoade" .. sep .. "python_path.txt",
    proj_dir .. sep .. "doxoade" .. sep .. ".doxoade" .. sep .. "python_path.txt",
  }
  for _, ap in ipairs(anchor_paths) do
    local f = io.open(ap, "r")
    if f then
      local line = f:read("*l") or ""
      f:close()
      line = line:gsub("^%s*", ""):gsub("%s*$", "")
      if line ~= "" and system.get_file_info(line) then
        return line
      end
    end
  end

  local candidates = {
    proj_dir .. sep .. "venv",
    proj_dir .. sep .. "doxoade" .. sep .. "venv",
    proj_dir .. sep .. ".venv",
    proj_dir .. sep .. "doxoade" .. sep .. ".venv",
    proj_dir .. sep .. "env",
    user_dir .. sep .. ".doxoade" .. sep .. "venv",
  }
  for _, vpath in ipairs(candidates) do
    local scripts = (PLATFORM == "Windows") and (vpath .. sep .. "Scripts") or (vpath .. sep .. "bin")
    if system.get_file_info(scripts) then
      local exe = scripts .. sep .. "python" .. (PLATFORM == "Windows" and ".exe" or "")
      if system.get_file_info(exe) then return exe end
    end
  end
  return "python"
end

-- =============================================================================
-- 🖱️ CLIQUE NOS BOTÕES (COPIAR & VER HD)
-- =============================================================================
local original_on_mouse_pressed = DocView.on_mouse_pressed
function DocView:on_mouse_pressed(button, px, py, clicks)
  if button == "left" or button == 1 then
    for _, region in pairs(_card_interactive_regions) do
      if region.btn_copy and px >= region.btn_copy.x and px <= region.btn_copy.x + region.btn_copy.w and
         py >= region.btn_copy.y and py <= region.btn_copy.y + region.btn_copy.h then
        local img_path = resolve_image_full_path(region.btn_copy.filename):gsub("/", "\\")
        local py_exe = detect_project_python()
        local cmd = string.format('"%s" -m doxoade image copy "%s"', py_exe, img_path)
        core.add_thread(function()
          pcall(system.exec, cmd)
          core.log("📋 [IMAGE] Imagem copiada para a área de transferência do Windows!")
        end)
        return true
      end

      if region.btn_hd and px >= region.btn_hd.x and px <= region.btn_hd.x + region.btn_hd.w and
         py >= region.btn_hd.y and py <= region.btn_hd.y + region.btn_hd.h then
        local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
        if canvas and canvas.load_cas_image_by_filename then
          canvas:load_cas_image_by_filename(region.btn_hd.filename)
          command.perform("doxoade:toggle-bottom-shelf")
        else
          core.log("🔍 [IMAGE] Abrindo no visualizador: " .. region.btn_hd.filename)
        end
        return true
      end
    end
  end
  return original_on_mouse_pressed and original_on_mouse_pressed(self, button, px, py, clicks)
end

-- =============================================================================
-- 📋 PONTE DIRETA DE COLAGEM (AUTO-SYS.PATH INJECTION)
-- =============================================================================
local function execute_paste_image_from_clipboard()
  local doc = core.active_view and core.active_view.doc
  if not doc then return end

  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local proj_dir = get_active_project_dir()
  local cache_dir = user_dir .. sep .. ".doxoade" .. sep .. "canvas_cache"
  pcall(function() system.mkdir(cache_dir) end)

  local out_json = (cache_dir .. sep .. "last_paste.json"):gsub("\\", "/")
  local bridge_py = cache_dir .. sep .. "paste_bridge.py"
  pcall(os.remove, out_json)

  local py_exe = detect_project_python()

  local py_code = string.format([[
import sys, os, json
from pathlib import Path
from datetime import datetime

for p in [%q, %q, %q]:
    if p and os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

out_p = Path(%q)
try:
    from doxoade.tools.image_systems.clipboard_grabber import grab_image_hybrid
    from doxoade.tools.image_systems.thumbnail_engine import ThumbnailEngine

    res = grab_image_hybrid()
    if res.get("status") != "SUCCESS":
        out_p.write_text(json.dumps({"status": "EMPTY", "error": res.get("error", "Nenhuma imagem encontrada")}), encoding="utf-8")
        sys.exit(0)

    img = res["image"]
    root = Path(%q)
    assets_dir = root / ".doxoade" / "assets" / "images"
    assets_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%%Y%%m%%d_%%H%%M%%S")
    date_str = datetime.now().strftime("%%Y-%%m-%%d")
    fn = f"print_{ts}.png"
    dest_png = assets_dir / fn
    img.convert("RGB").save(dest_png, format="PNG")

    engine = ThumbnailEngine(root)
    thumb_res = engine.generate(dest_png, preset="card", force=True)

    payload = {
        "status": "SUCCESS",
        "filename": fn,
        "full_path": str(dest_png),
        "tag": f"[DOX-IMG: {fn} | {img.width}x{img.height} | {date_str}]",
        "markdown": f"![{fn}](.doxoade/assets/images/{fn})",
        "width": img.width,
        "height": img.height
    }
    out_p.write_text(json.dumps(payload), encoding="utf-8")
except Exception as e:
    out_p.write_text(json.dumps({"status": "ERROR", "error": str(e)}), encoding="utf-8")
]], proj_dir, (proj_dir .. "/doxoade"), (user_dir .. "/.doxoade"), out_json, proj_dir)

  local f_bridge = io.open(bridge_py, "w")
  if f_bridge then
    f_bridge:write(py_code)
    f_bridge:close()
  end

  local cmd = string.format('"%s" "%s"', py_exe, bridge_py)

  core.add_thread(function()
    pcall(system.exec, cmd)
    for _ = 1, 35 do
      coroutine.yield(0.04)
      local finfo = system.get_file_info(out_json)
      if finfo and (finfo.size or 0) > 0 then break end
    end

    local f = io.open(out_json, "r")
    if f then
      local raw = f:read("*a") or ""
      f:close()
      local tag = raw:match('"tag"%s*:%s*"([^"]+)"')
      local filename = raw:match('"filename"%s*:%s*"([^"]+)"')

      if tag and filename then
        local l1, c1 = doc:get_selection(true)
        doc:insert(l1, c1, tag .. "\n")
        core.log("🖼️ [PASTE] Imagem salva e miniatura inserida: " .. filename)
        core.redraw = true
      else
        local err = raw:match('"error"%s*:%s*"([^"]+)"') or "Nenhuma imagem válida encontrada."
        core.log("⚠ [PASTE] " .. err)
      end
    end
  end)
end

-- =============================================================================
-- 📋 REGISTRO DE COMANDOS & KEYMAPS SMART CTRL+V
-- =============================================================================
command.add("core.docview", {
  ["doxoade:paste-image-from-clipboard"] = function()
    execute_paste_image_from_clipboard()
  end,
  ["doxoade:smart-paste"] = function()
    local text = nil
    if system and system.get_clipboard then
      local ok, clip = pcall(system.get_clipboard)
      if ok and type(clip) == "string" and clip ~= "" then
        text = clip
      end
    end

    if text and text ~= "" then
      command.perform("doc:paste")
    else
      execute_paste_image_from_clipboard()
    end
  end
})

keymap.add {
  ["ctrl+v"]       = "doxoade:smart-paste",
  ["ctrl+shift+v"] = "doxoade:paste-image-from-clipboard",
  ["ctrl+alt+v"]   = "doxoade:paste-image-from-clipboard",
}
