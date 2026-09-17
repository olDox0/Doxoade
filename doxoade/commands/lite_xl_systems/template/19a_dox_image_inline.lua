-- doxoade/commands/lite_xl_systems/template/19a_dox_image_inline.lua
--[[ WIP - ainda é preciso terminar e corrigir o problema da linha
corrigir: o sistema de imagem precisa deixar a linha e sistemas de identação.
  🖼️ DOXOADE INLINE IMAGE CARDS (V60.0 Full-HD 1080p Native Engine)
  - Ponte de Captura 1080p Nativa (1920x1080 com tol=1 para nitidez total de texto).
  - Gera simultaneamente: PNG original + Card Thumb (240x136) + Canvas HD (1920x1080).
  - Vácuo dinâmico e isolamento perfeito do Gutter.
  Compliance: ProDeNov 1.2.1, PASC-6.1, Limite < 50KB.
]]
local core = require "core"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local DocView = require "core.docview"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local CARD_HEIGHT = 190
local CARD_MARGIN_X = 8
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
  if not font or not text or text == "" then return end
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

local function resolve_real_project_root()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  
  local py_anchor = user_dir .. sep .. ".doxoade" .. sep .. "python_path.txt"
  local finfo = system.get_file_info(py_anchor)
  if finfo and finfo.type == "file" then
    local f = io.open(py_anchor, "r")
    if f then
      local py_exe = f:read("*l") or ""
      f:close()
      if py_exe ~= "" and system.get_file_info(py_exe) then
        local pdir = py_exe:match("^(.*)[/\\]Scripts[/\\]") or py_exe:match("^(.*)[/\\]bin[/\\]") or py_exe:match("^(.*)[/\\]")
        if pdir and system.get_file_info(pdir) then
          return (system.absolute_path(pdir) or pdir):gsub("\\", "/"), py_exe:gsub("/", "\\")
        end
      end
    end
  end

  if core.project_directories and #core.project_directories > 0 then
    for _, p in ipairs(core.project_directories) do
      local p_str = tostring(type(p) == "table" and (p.path or p.name) or p)
      if not p_str:find("test_deploy") and not p_str:find("sandbox") then
        local abs_p = (system.absolute_path(p_str) or p_str):gsub("\\", "/")
        return abs_p, "python"
      end
    end
  end

  local cwd = (system.absolute_path(".") or "."):gsub("\\", "/")
  return cwd, "python"
end

local function detect_project_python()
  local proj_dir, py_anchor_exe = resolve_real_project_root()
  if py_anchor_exe and py_anchor_exe ~= "python" and system.get_file_info(py_anchor_exe) then
    return py_anchor_exe
  end

  local sep = PATHSEP or "/"
  local candidates = {
    proj_dir .. sep .. "venv",
    proj_dir .. sep .. "doxoade" .. sep .. "venv",
    proj_dir .. sep .. ".venv",
    proj_dir .. sep .. "doxoade" .. sep .. ".venv",
    proj_dir .. sep .. "env",
  }
  for _, vpath in ipairs(candidates) do
    local scripts = (PLATFORM == "Windows") and (vpath .. sep .. "Scripts") or (vpath .. sep .. "bin")
    if system.get_file_info(scripts) then
      local exe = scripts .. sep .. "python" .. (PLATFORM == "Windows" and ".exe" or "")
      if system.get_file_info(exe) then return exe:gsub("/", "\\") end
    end
  end
  return "python"
end

local function resolve_image_full_path(filename)
  local proj_dir, _ = resolve_real_project_root()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local candidates = {
    proj_dir .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "images" .. sep .. filename,
    proj_dir .. sep .. "doxoade" .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "images" .. sep .. filename,
    proj_dir .. sep .. "assets" .. sep .. "images" .. sep .. filename,
    user_dir .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "images" .. sep .. filename,
    user_dir .. sep .. "assets" .. sep .. "images" .. sep .. filename,
  }
  for _, path in ipairs(candidates) do
    if system.get_file_info(path) then return path end
  end
  return candidates[1]
end

local function get_safe_gutter_w(view)
  local font = (view and view.get_font and view:get_font()) or style.font
  local total_lines = (view and view.doc and view.doc.lines and #view.doc.lines) or 100
  local digits = #tostring(total_lines)
  local min_w = font:get_width(string.rep("0", math.max(digits, 2))) + 20
  if view and view.get_gutter_width then
    local ok, w = pcall(view.get_gutter_width, view)
    if ok and type(w) == "number" and w > min_w then return w end
  end
  return math.max(34, min_w)
end

local function draw_clean_gutter_number(view, line_idx, pos_x, line_y, gw)
  local font = (view and view.get_font and view:get_font()) or style.font
  local num_str = tostring(line_idx)
  local is_selected = false
  if view.doc and view.doc.get_selection then
    local l1, _, l2, _ = view.doc:get_selection(true)
    is_selected = (line_idx >= l1 and line_idx <= l2)
  end

  local color = is_selected and (style.line_number2 or { 255, 255, 255, 255 }) or (style.line_number or { 140, 140, 145, 255 })
  local num_w = font:get_width(num_str)
  local num_x = pos_x + gw - num_w - 8
  draw_text_safe(font, num_str, num_x, line_y, color)
end

local function extract_dox_image_info(line_text)
  if not line_text or line_text == "" then return nil end
  if not line_text:find("DOX%-IMG") and not line_text:find("%.doxoade/assets/images") and not line_text:find("assets/images") then
    return nil
  end

  local fn, res, dt = line_text:match("%[DOX%-IMG:%s*([%w_%-%.]+%.png)%s*|?%s*([^|%]]*)%s*|?%s*([^%]]*)%]")
  if fn then
    return {
      filename = fn:gsub("^%s*", ""):gsub("%s*$", ""),
      resolution = (res ~= "" and res:gsub("^%s*", ""):gsub("%s*$", "")) or "HD",
      date = (dt ~= "" and dt:gsub("^%s*", ""):gsub("%s*$", "")) or "Recente",
    }
  end

  local md_fn = line_text:match("!%[[^%]]*%]%(.-/([%w_%-%.]+%.png)%)")
  if md_fn then
    return { filename = md_fn, resolution = "HD", date = "Markdown" }
  end
  return nil
end
rawset(_G, "_DOXOADE_EXTRACT_IMAGE_INFO", extract_dox_image_info)

local function load_rle_binary(path)
  local f = io.open(path, "rb")
  if not f then return nil end
  local data = f:read("*a") or ""
  f:close()
  if #data < 21 or data:sub(1, 7) ~= "DOXRLE1" then return nil end
  local ok, ver, gw, gh, ow, oh, count = pcall(string.unpack, "<BHHHHI", data, 8)
  
  -- Sincronizado com o 19c: teto elevado para 350.000 blocos Full HD
  if not ok or ver ~= 1 or not count or count > 350000 then return nil end

  local rects = {}
  local off = 21
  for i = 1, count do
    local ok2, rx, ry, rw, r, g, b = pcall(string.unpack, "<HHHBBB", data, off)
    if not ok2 or not rx then break end
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
    width = 1920,
    height = 1080,
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

local function get_cumulative_image_offset(doc, target_line)
  if not doc or not doc.lines then return 0 end
  local offset = 0
  local limit = math.min(target_line - 1, #doc.lines)
  for l = 1, limit do
    local text = doc.lines[l]
    if text and extract_dox_image_info(text) then
      offset = offset + CARD_HEIGHT
    end
  end
  return offset
end

local function get_absolute_line_screen_y(view, line_idx)
  local lh = view:get_line_height()
  local scroll_y = view.scroll and view.scroll.y or 0
  local extra = get_cumulative_image_offset(view.doc, line_idx)
  return view.position.y + (line_idx - 1) * lh + extra - scroll_y
end

local function doc_has_any_images(doc)
  if not doc or not doc.lines then return false end
  for _, line in ipairs(doc.lines) do
    if extract_dox_image_info(line) then return true end
  end
  return false
end

local function draw_image_card(view, line_idx, info, x, y, line_h)
  local info_fn = (info and info.filename) or "image.png"
  local meta = load_image_meta(info_fn)
  local gw = get_safe_gutter_w(view)
  local max_available_w = view.size.x - gw - 28
  local card_w = math.max(260, math.min(max_available_w, 540))
  local card_h = CARD_HEIGHT
  local card_x = view.position.x + gw + CARD_MARGIN_X
  local card_y = y + line_h + 2

  draw_rect_safe(card_x - 1, card_y - 1, card_w + 2, card_h + 2, { 30, 30, 32, 255 })
  draw_rect_safe(card_x, card_y, card_w, card_h, style.background2 or { 24, 24, 27, 255 })
  draw_rect_safe(card_x, card_y, 3, card_h, style.accent or { 38, 188, 95, 255 })

  local disp_w = tonumber(meta and meta.width) or 1920
  local disp_h = tonumber(meta and meta.height) or 1080
  local header_text = string.format("[IMG] %s (%dx%d)", tostring(info_fn), disp_w, disp_h)
  draw_text_safe(style.font, header_text, card_x + 10, card_y + 8, style.accent or { 38, 188, 95, 255 })

  local btn_copy_x = card_x + card_w - 120
  local btn_hd_x = card_x + card_w - 54
  local btn_y = card_y + 4
  local btn_h = 18

  draw_rect_safe(btn_copy_x, btn_y, 60, btn_h, { 40, 40, 45, 255 })
  draw_text_safe(style.font, "[Copiar]", btn_copy_x + 4, btn_y + 1, { 220, 220, 220, 255 })

  draw_rect_safe(btn_hd_x, btn_y, 48, btn_h, { 40, 40, 45, 255 })
  draw_text_safe(style.font, "[HD]", btn_hd_x + 7, btn_y + 1, { 56, 189, 248, 255 })

  _card_interactive_regions[info.filename] = {
    btn_copy = { x = btn_copy_x, y = btn_y, w = 60, h = btn_h, filename = info.filename },
    btn_hd = { x = btn_hd_x, y = btn_y, w = 48, h = btn_h, filename = info.filename },
  }

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
    draw_text_safe(style.font, "Carregando preview CAS em alta definição...", thumb_box_x + 10, thumb_box_y + 20, style.dim)
  end
end

if not rawget(_G, "_DOXOADE_IMAGE_INLINE_V60_HOOKED") then
  rawset(_G, "_DOXOADE_IMAGE_INLINE_V60_HOOKED", true)

  local original_get_scrollable_size = DocView.get_scrollable_size
  function DocView:get_scrollable_size()
    local w, h = original_get_scrollable_size(self)
    if self.doc and self.doc.lines then
      local extra = get_cumulative_image_offset(self.doc, #self.doc.lines + 1)
      return w, (h or 0) + extra
    end
    return w, h
  end

  local original_get_line_screen_position = DocView.get_line_screen_position
  function DocView:get_line_screen_position(line, col)
    local x, _ = original_get_line_screen_position(self, line, col)
    if self.doc and doc_has_any_images(self.doc) then
      local abs_y = get_absolute_line_screen_y(self, line)
      return x, abs_y
    end
    return original_get_line_screen_position(self, line, col)
  end

  local original_resolve_screen_position = DocView.resolve_screen_position
  function DocView:resolve_screen_position(x, y)
    if not self.doc or not doc_has_any_images(self.doc) then
      return original_resolve_screen_position(self, x, y)
    end

    local lh = self:get_line_height()
    local total_lines = #self.doc.lines
    local target_line = total_lines

    for l = 1, total_lines do
      local line_y = get_absolute_line_screen_y(self, l)
      local text = self.doc.lines[l]
      local has_img = text and extract_dox_image_info(text)
      local span_h = lh + (has_img and CARD_HEIGHT or 0)

      if y < line_y + span_h then
        target_line = l
        break
      end
    end

    local col = 1
    if self.doc.lines[target_line] then
      local line_text = self.doc.lines[target_line]
      local gw = get_safe_gutter_w(self)
      local text_x = self.position.x + gw + 8
      local rel_x = x - text_x
      if rel_x > 0 then
        local font = self:get_font()
        local best_col = 1
        local best_diff = math.abs(rel_x)
        for c = 1, #line_text + 1 do
          local sub_w = font:get_width(line_text:sub(1, c - 1))
          local diff = math.abs(rel_x - sub_w)
          if diff < best_diff then
            best_diff = diff
            best_col = c
          end
        end
        col = best_col
      end
    end

    return target_line, col
  end

  local original_get_visible_line_range = DocView.get_visible_line_range
  function DocView:get_visible_line_range()
    if not self.doc or not doc_has_any_images(self.doc) then
      return original_get_visible_line_range(self)
    end

    local lh = self:get_line_height()
    local total_lines = #self.doc.lines
    local view_top = self.position.y
    local view_bottom = self.position.y + self.size.y

    local min_line = 1
    for l = 1, total_lines do
      local y = get_absolute_line_screen_y(self, l)
      local text = self.doc.lines[l]
      local has_img = text and extract_dox_image_info(text)
      local span_h = lh + (has_img and CARD_HEIGHT or 0)

      if y + span_h >= view_top then
        min_line = l
        break
      end
    end

    local max_line = total_lines
    for l = min_line, total_lines do
      local y = get_absolute_line_screen_y(self, l)
      if y > view_bottom then
        max_line = l
        break
      end
    end

    return min_line, max_line
  end
end

local original_docview_draw = DocView.draw
function DocView:draw(...)
  if not self.doc or not doc_has_any_images(self.doc) then
    return original_docview_draw(self, ...)
  end

  self:draw_background(style.background)

  local line_h = self:get_line_height()
  local min_line, max_line = self:get_visible_line_range()
  local view_top = self.position.y
  local view_bottom = self.position.y + self.size.y
  local pos_x = self.position.x
  local gw = get_safe_gutter_w(self)
  local text_x = pos_x + gw + 8

  core.push_clip_rect(text_x - 4, self.position.y, self.size.x - gw - 4, self.size.y)

  for line_idx = min_line, max_line do
    local line_y = get_absolute_line_screen_y(self, line_idx)
    local text = self.doc.lines[line_idx]
    local info = extract_dox_image_info(text)

    self:draw_line_body(line_idx, text_x, line_y)

    if info and (line_y + line_h + CARD_HEIGHT >= view_top) and (line_y <= view_bottom) then
      draw_image_card(self, line_idx, info, text_x, line_y, line_h)
    end
  end

  core.pop_clip_rect()

  core.push_clip_rect(pos_x, self.position.y, gw, self.size.y)
  draw_rect_safe(pos_x, self.position.y, gw, self.size.y, style.background)
  draw_rect_safe(pos_x + gw - 1, self.position.y, 1, self.size.y, style.divider or { 45, 45, 48, 255 })

  for line_idx = min_line, max_line do
    local line_y = get_absolute_line_screen_y(self, line_idx)
    draw_clean_gutter_number(self, line_idx, pos_x, line_y, gw)
  end

  core.pop_clip_rect()

  if self.draw_scrollbar then pcall(self.draw_scrollbar, self) end
end

local original_on_mouse_pressed = DocView.on_mouse_pressed
function DocView:on_mouse_pressed(button, px, py, clicks)
  if button == "left" or button == 1 then
    for _, region in pairs(_card_interactive_regions) do
      if region.btn_copy and px >= region.btn_copy.x and px <= region.btn_copy.x + region.btn_copy.w and
         py >= region.btn_copy.y and py <= region.btn_copy.y + region.btn_copy.h then
        local img_path = resolve_image_full_path(region.btn_copy.filename):gsub("/", "\\")
        if PLATFORM == "Windows" then
          local ps_cmd = string.format([[powershell.exe -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; [System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile('%s'))"]], img_path:gsub('"', '""'))
          pcall(system.exec, ps_cmd)
        end
        if system.set_clipboard then
          system.set_clipboard(string.format("[DOX-IMG: %s]", region.btn_copy.filename))
        end
        core.log("📋 [IMAGE] Imagem copiada para a área de transferência!")
        return true
      end

      if region.btn_hd and px >= region.btn_hd.x and px <= region.btn_hd.x + region.btn_hd.w and
         py >= region.btn_hd.y and py <= region.btn_hd.y + region.btn_hd.h then
        local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
        if canvas and canvas.load_cas_image_by_filename then
          canvas:load_cas_image_by_filename(region.btn_hd.filename)
        else
          core.log("🔍 [IMAGE] Abrindo imagem: " .. region.btn_hd.filename)
        end
        return true
      end
    end
  end
  return original_on_mouse_pressed and original_on_mouse_pressed(self, button, px, py, clicks)
end

local function format_dox_img_tag(fn, res, dt)
  local safe_fn = tostring(fn or "image.png")
  local safe_res = tostring(res or "HD")
  local safe_dt = tostring(dt or os.date("%Y-%m-%d"))
  return string.format("[DOX-IMG: %s | %s | %s]", safe_fn, safe_res, safe_dt)
end

-- =============================================================================
-- 📋 CAPTURA DIRETA & GERAÇÃO 1080P NATIVA (CARD + CANVAS FULL-HD)
-- =============================================================================
local function execute_paste_image_from_clipboard(on_complete_callback)
  local doc = core.active_view and core.active_view.doc
  if not doc then return end

  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local proj_dir, _ = resolve_real_project_root()
  local cache_dir = user_dir .. sep .. ".doxoade" .. sep .. "canvas_cache"
  pcall(function() system.mkdir(cache_dir) end)

  local out_json = (cache_dir .. sep .. "last_paste.json"):gsub("\\", "/")
  local bridge_py = (cache_dir .. sep .. "standalone_paste_bridge.py"):gsub("\\", "/")
  pcall(os.remove, out_json)

  local py_exe = detect_project_python()

  -- Script Python Autocontido que gera PNG + Card RLE (240px) + Canvas Full HD (1920px com tol=1)
  local py_code = [[
import sys, os, time, json, platform, struct, datetime
from io import BytesIO
from pathlib import Path

def get_image_from_clipboard():
    try:
        from PIL import ImageGrab, Image
        for _ in range(4):
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                return img
            elif isinstance(img, list) and len(img) > 0:
                p = Path(img[0])
                if p.is_file(): return Image.open(p)
            time.sleep(0.05)
    except Exception: pass

    if platform.system() == "Windows":
        try:
            import ctypes
            from PIL import Image
            u32 = ctypes.windll.user32
            k32 = ctypes.windll.kernel32
            for _ in range(4):
                if u32.OpenClipboard(None):
                    h = u32.GetClipboardData(8) or u32.GetClipboardData(17)
                    if h:
                        p_data = k32.GlobalLock(h)
                        size = k32.GlobalSize(h)
                        if p_data and size > 0:
                            raw = ctypes.string_at(p_data, size)
                            k32.GlobalUnlock(h)
                            u32.CloseClipboard()
                            hdr_size = struct.unpack("<I", raw[0:4])[0]
                            bmp_hdr = struct.pack("<2sIHHI", b"BM", 14 + size, 0, 0, 14 + hdr_size)
                            return Image.open(BytesIO(bmp_hdr + raw))
                    u32.CloseClipboard()
                time.sleep(0.05)
        except Exception: pass
    return None

def build_doxrle(img_rgb, target_w, target_h, orig_w, orig_h, tol=1):
    from PIL import Image
    resized = img_rgb.resize((target_w, target_h), Image.Resampling.BILINEAR)
    pixels = resized.load()
    rects = []
    for y in range(target_h):
        r_start = 0; cur_c = pixels[0, y]; r_len = 1
        for x in range(1, target_w):
            c = pixels[x, y]
            if abs(c[0]-cur_c[0]) <= tol and abs(c[1]-cur_c[1]) <= tol and abs(c[2]-cur_c[2]) <= tol:
                r_len += 1
            else:
                rects.append((r_start, y, r_len, cur_c[0], cur_c[1], cur_c[2]))
                r_start = x; cur_c = c; r_len = 1
        rects.append((r_start, y, r_len, cur_c[0], cur_c[1], cur_c[2]))

    header = struct.pack("<7sBHHHHI", b"DOXRLE1", 1, target_w, target_h, orig_w, orig_h, len(rects))
    body = bytearray()
    for rx, ry, rw, r, g, b in rects:
        body.extend(struct.pack("<HHHBBB", rx, ry, rw, r, g, b))
    return header + bytes(body)

def main():
    if len(sys.argv) < 3:
        sys.exit(1)
    out_p = Path(sys.argv[1])
    root = Path(sys.argv[2])
    try:
        from PIL import Image
        img = get_image_from_clipboard()
        if not img:
            out_p.write_text(json.dumps({"status": "EMPTY", "error": "Nenhuma imagem na área de transferência."}), encoding="utf-8")
            sys.exit(0)

        img_rgb = img.convert("RGB")
        orig_w, orig_h = img_rgb.size

        assets_dir = root / ".doxoade" / "assets" / "images"
        assets_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.datetime.now()
        ts = now.strftime("%Y%m%d_%H%M%S")
        date_str = now.strftime("%Y-%m-%d")
        fn = f"print_{ts}.png"
        dest_png = assets_dir / fn
        dest_thumb_rle = assets_dir / f"print_{ts}.thumb.rlebin"
        dest_canvas_rle = assets_dir / f"print_{ts}.canvas.rlebin"

        img_rgb.save(dest_png, format="PNG")

        card_w = min(240, orig_w)
        card_h = max(10, int(orig_h * (card_w / orig_w)))
        dest_thumb_rle.write_bytes(build_doxrle(img_rgb, card_w, card_h, orig_w, orig_h, tol=4))

        hd_w = min(1920, orig_w)
        hd_h = max(10, int(orig_h * (hd_w / orig_w)))
        dest_canvas_rle.write_bytes(build_doxrle(img_rgb, hd_w, hd_h, orig_w, orig_h, tol=1))

        payload = {
            "status": "SUCCESS",
            "filename": fn,
            "full_path": str(dest_png),
            "tag": f"[DOX-IMG: {fn} | {orig_w}x{orig_h} | {date_str}]",
            "width": orig_w,
            "height": orig_h
        }
        out_p.write_text(json.dumps(payload), encoding="utf-8")
    except Exception as e:
        out_p.write_text(json.dumps({"status": "ERROR", "error": str(e)}), encoding="utf-8")

if __name__ == "__main__":
    main()
]]

  local f_bridge = io.open(bridge_py, "w")
  if f_bridge then
    f_bridge:write(py_code)
    f_bridge:close()
  end

  -- Execução passando out_json e proj_dir como argumentos de linha de comando seguros
  local direct_cmd = string.format('"%s" "%s" "%s" "%s"',
    py_exe:gsub("/", "\\"),
    bridge_py:gsub("/", "\\"),
    out_json:gsub("/", "\\"),
    proj_dir:gsub("/", "\\")
  )
  
  core.add_thread(function()
    pcall(system.exec, direct_cmd)
    for _ = 1, 45 do
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
      local status = raw:match('"status"%s*:%s*"([^"]+)"')

      if status == "SUCCESS" and tag and filename then
        local l1, c1 = doc:get_selection(true)
        doc:insert(l1, c1, tag .. "\n")
        core.log("🖼️ [PASTE] Imagem salva e card inserido: " .. filename)

        -- Notifica o Canvas Studio para carregar a nova imagem HD
        local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
        if canvas and canvas.load_cas_image_by_filename then
          canvas:load_cas_image_by_filename(filename)
        end

        core.redraw = true
        if on_complete_callback then on_complete_callback(true) end
      else
        local err = raw:match('"error"%s*:%s*"([^"]+)"') or "Nenhuma imagem encontrada na área de transferência."
        if on_complete_callback then
          on_complete_callback(false, err)
        else
          core.log("⚠ [PASTE] " .. err)
        end
      end
    else
      if on_complete_callback then on_complete_callback(false, "Timeout ao capturar print.") end
    end
  end)
end

command.add("core.docview", {
  ["doxoade:paste-image-from-clipboard"] = function()
    execute_paste_image_from_clipboard()
  end,
  ["doxoade:smart-paste"] = function()
    execute_paste_image_from_clipboard(function(success, err)
      if not success then
        command.perform("doc:paste")
      end
    end)
  end
})

keymap.add {
  ["ctrl+shift+v"] = "doxoade:paste-image-from-clipboard",
  ["ctrl+alt+v"]   = "doxoade:paste-image-from-clipboard",
  --["ctrl+v"]       = "doxoade:smart-paste",
}
