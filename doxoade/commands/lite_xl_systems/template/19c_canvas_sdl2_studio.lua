-- doxoade/commands/lite_xl_systems/template/19c_canvas_sdl2_studio.lua
--[[
  🎨 DOXOADE HIGH-PERFORMANCE CANVAS & PRINTSCREEN STUDIO (Módulo 19c V42.0 Nil-Safe)
  - Resolução Full HD 1080p Nativa (.canvas.rlebin 1920x1080): Leitura de código perfeita.
  - Interpolações de string.format 100% blindadas contra argumentos nil.
  - Viewport Culling O(1): Descarta blocos fora do campo visual no Zoom.
  - Calibração Matemática 1:1 Real (Pixel-Perfect).
  Compliance: ProDeNov 1.2.1, PASC-6.1, Limite < 50KB.
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

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

-- =============================================================================
-- 🚀 GERADOR SOB DEMANDA DE RLE FULL HD 1080P (Lossless RLE)
-- =============================================================================
local function generate_hd_canvas_sidecar(img_path, hd_sidecar)
  local proj_dir, py_exe = resolve_real_project_root()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local cache_dir = user_dir .. sep .. ".doxoade" .. sep .. "canvas_cache"
  pcall(function() system.mkdir(cache_dir) end)

  local script_py = (cache_dir .. sep .. "generate_canvas_hd.py"):gsub("/", "\\")
  local py_code = string.format([[
import sys
from pathlib import Path
try:
    from PIL import Image
    src = Path(%q)
    dest = Path(%q)
    img = Image.open(src).convert("RGB")
    ow, oh = img.size
    
    # 🎯 Resolução HD Nativa: preserva resolução original até 1920x1080 (ou escala suave)
    target_w = min(1920, ow)
    target_h = int(oh * (target_w / ow))
    if (target_w, target_h) != (ow, oh):
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    pixels = img.load()
    rects = []
    
    # RLE exato (threshold 0 = nitidez absoluta de fontes e código)
    for y in range(target_h):
        run_start = 0
        cur_c = pixels[0, y]
        for x in range(1, target_w):
            c = pixels[x, y]
            if c != cur_c:
                rects.append((run_start, y, x - run_start, cur_c[0], cur_c[1], cur_c[2]))
                run_start = x
                cur_c = c
        rects.append((run_start, y, target_w - run_start, cur_c[0], cur_c[1], cur_c[2]))
    
    # Grava cabeçalho DOXRLE1 binário rápido
    import struct
    header = struct.pack("<7sBHHHHI", b"DOXRLE1", 1, target_w, target_h, ow, oh, len(rects))
    with open(dest, "wb") as f:
        f.write(header)
        for rx, ry, rw, r, g, b in rects:
            f.write(struct.pack("<HHHBBB", rx, ry, rw, r, g, b))
    print("[HD-OK]")
except Exception as e:
    print(f"[HD-ERR] {e}")
]], img_path, hd_sidecar)

  local f_py = io.open(script_py, "w")
  if f_py then
    f_py:write(py_code)
    f_py:close()
  end

  pcall(system.exec, string.format('"%s" "%s"', py_exe, script_py))
end

local function load_rle_binary(path)
  if not path then return nil end
  local f = io.open(path, "rb")
  if not f then return nil end
  local data = f:read("*a") or ""
  f:close()
  if #data < 21 or data:sub(1, 7) ~= "DOXRLE1" then return nil end
  local ok, ver, gw, gh, ow, oh, count = pcall(string.unpack, "<BHHHHI", data, 8)
  
  -- Teto elevado para 350.000 blocos (permite telas Full HD 1080p detalhadas)
  if not ok or ver ~= 1 or not count or count > 350000 then return nil end
  
  local rects = {}
  local off = 21
  for i = 1, count do
    local ok2, rx, ry, rw, r, g, b = pcall(string.unpack, "<HHHBBB", data, off)
    if not ok2 or not rx then break end
    off = off + 9
    rects[i] = { x = rx or 0, y = ry or 0, w = rw or 1, h = 1, color = { r or 255, g or 255, b or 255, 255 } }
  end
  return {
    grid_w = gw or 240,
    grid_h = gh or 136,
    orig_w = ow or 1920,
    orig_h = oh or 1080,
    rects = rects
  }
end

local CanvasStudio = {
  rects = {},
  grid_w = 1920,
  grid_h = 1080,
  orig_w = 1920,
  orig_h = 1080,
  image_path = nil,
  zoom = 1.0,
  pan_x = 0,
  pan_y = 0,
  mode_1to1 = false,
  is_panning = false,
  is_capturing = false,
  status_msg = "Nenhum print carregado. Pressione Ctrl+V para colar.",
}
rawset(_G, "_DOXOADE_CANVAS_STUDIO", CanvasStudio)

function CanvasStudio:load_cas_image_by_filename(img_filename)
  if not img_filename or img_filename == "" then return false end
  local full_path = resolve_image_full_path(img_filename)
  local hd_sidecar = full_path:gsub("%.png$", ".canvas.rlebin")
  local thumb_sidecar = full_path:gsub("%.png$", ".thumb.rlebin")

  self.image_path = full_path
  self.mode_1to1 = false
  self.zoom = 1.0
  self.pan_x = 0
  self.pan_y = 0

  -- 1. Tenta carregar o sidecar HD (1080p)
  local bin = load_rle_binary(hd_sidecar)
  
  -- 2. Se não existir, tenta carregar a thumb provisória E dispara a forja em HD
  if not bin then
    bin = load_rle_binary(thumb_sidecar)
    core.add_thread(function()
      generate_hd_canvas_sidecar(full_path, hd_sidecar)
      -- Aguarda geração rápida
      for _ = 1, 30 do
        coroutine.yield(0.05)
        local finfo = system.get_file_info(hd_sidecar)
        if finfo and (finfo.size or 0) > 200 then
          local hd_bin = load_rle_binary(hd_sidecar)
          if hd_bin and hd_bin.rects then
            CanvasStudio.rects = hd_bin.rects
            CanvasStudio.grid_w = hd_bin.grid_w
            CanvasStudio.grid_h = hd_bin.grid_h
            CanvasStudio.orig_w = hd_bin.orig_w
            CanvasStudio.orig_h = hd_bin.orig_h
            CanvasStudio.status_msg = string.format(
              "Canvas 1080p HD: %s (%dx%d px • %d blocos)",
              tostring(img_filename),
              CanvasStudio.orig_w,
              CanvasStudio.orig_h,
              #CanvasStudio.rects
            )
            core.redraw = true
          end
          break
        end
      end
    end)
  end

  if bin and bin.rects and #bin.rects > 0 then
    self.rects = bin.rects
    self.grid_w = tonumber(bin.grid_w) or 1920
    self.grid_h = tonumber(bin.grid_h) or 1080
    self.orig_w = tonumber(bin.orig_w) or 1920
    self.orig_h = tonumber(bin.orig_h) or 1080
    local is_1080p = (self.grid_w >= 960)
    self.status_msg = string.format(
      "Canvas %s: %s (%dx%d px • %d blocos)",
      is_1080p and "1080p HD" or "Otimizando HD...",
      tostring(img_filename),
      self.orig_w,
      self.orig_h,
      #self.rects
    )
  else
    self.status_msg = "Carregando imagem em alta definição..."
  end

  local shelf = rawget(_G, "_DOXOADE_SHELF_HUB")
  if shelf then
    shelf.active_tab = "canvas"
    shelf.visible = true
  end

  core.redraw = true
  if core.log then
    core.log("🔍 [CANVAS] Imagem aberta: " .. tostring(img_filename))
  end
  return true
end

function CanvasStudio:adjust_zoom(delta, pivot_x, pivot_y)
  local old_zoom = self.zoom
  local factor = delta > 0 and 1.15 or 0.85
  
  -- Trava de segurança: Zoom entre 20% (0.2x) e 500% (5.0x)
  self.zoom = math.max(0.2, math.min(5.0, self.zoom * factor))
  
  -- Se estiver no modo 1:1, desativa para permitir zoom livre
  if self.zoom ~= 1.0 then
    self.mode_1to1 = false
  end
  
  core.redraw = true
end

function CanvasStudio:reset_view()
  self.zoom = 1.0
  self.pan_x = 0
  self.pan_y = 0
  self.mode_1to1 = false
  core.redraw = true
end

function CanvasStudio:load_latest_image(force)
  if not force and #self.rects > 0 then return end

  local proj_dir, _ = resolve_real_project_root()
  local sep = PATHSEP or "/"
  local images_dir = proj_dir .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "images"
  local files = system.list_dir(images_dir) or {}
  local latest_png = nil
  local latest_mtime = 0

  for _, fn in ipairs(files) do
    if fn:find("%.png$") then
      local fpath = images_dir .. sep .. fn
      local finfo = system.get_file_info(fpath)
      local mtime = finfo and (finfo.modified or finfo.mtime or 0) or 0
      if mtime >= latest_mtime then
        latest_mtime = mtime
        latest_png = fn
      end
    end
  end

  if latest_png then
    self:load_cas_image_by_filename(latest_png)
  end
end

function CanvasStudio:paste_clipboard_image()
  command.perform("doxoade:paste-image-from-clipboard")
  core.add_thread(function()
    coroutine.yield(0.5)
    CanvasStudio:load_latest_image(true)
  end)
end

function CanvasStudio:copy_image_to_clipboard()
  if not self.image_path or not system.get_file_info(self.image_path) then
    core.log("⚠ Nenhuma imagem carregada no Canvas para copiar.")
    return
  end
  local img_path = self.image_path:gsub("/", "\\")
  if PLATFORM == "Windows" then
    local ps_cmd = string.format([[powershell.exe -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; [System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile('%s'))"]], img_path:gsub('"', '""'))
    pcall(system.exec, ps_cmd)
  end
  core.log("📋 Imagem copiada para a área de transferência do Windows!")
end

function CanvasStudio:open_image_external()
  if self.image_path and system.get_file_info(self.image_path) then
    if PLATFORM == "Windows" then
      system.exec(string.format('explorer.exe "%s"', self.image_path:gsub("/", "\\")))
    else
      system.exec(string.format('xdg-open "%s"', self.image_path))
    end
    core.log("🖼️ Imagem aberta no visualizador do sistema: " .. self.image_path)
  else
    core.log("⚠ Nenhuma imagem salva no Canvas para abrir externamente.")
  end
end

function CanvasStudio:clear()
  self.rects = {}
  self.image_path = nil
  self.zoom = 1.0
  self.pan_x = 0
  self.pan_y = 0
  self.status_msg = "Canvas limpo. Pressione Ctrl+V para colar novo print."
  core.redraw = true
  core.log("🧹 [CANVAS] Tela limpa com sucesso.")
end

-- =============================================================================
-- 🎨 RENDERIZADOR CONTÍNUO FULL HD COM VIEWPORT CULLING (60 FPS)
-- =============================================================================
function CanvasStudio:draw_viewport(x, y, w, h)
  local font = style.font or style.code_font
  if #self.rects > 0 then
    local gw = self.grid_w or 1920
    local gh = self.grid_h or 1080
    local ow = self.orig_w or 1920

    local base_w = w - 32
    local base_h = h - 32
    local fit_scale = math.min(base_w / math.max(1, gw), base_h / math.max(1, gh))

    local scale
    if self.mode_1to1 then
      local ratio_1to1 = (ow / math.max(1, gw))
      scale = ratio_1to1 * self.zoom
    else
      scale = fit_scale * self.zoom
    end

    local total_drawn_w = math.floor(gw * scale)
    local total_drawn_h = math.floor(gh * scale)

    local start_draw_x = x + math.floor((w - total_drawn_w) / 2) + self.pan_x
    local start_draw_y = y + math.floor((h - total_drawn_h) / 2) + self.pan_y

    draw_rect_safe(start_draw_x - 3, start_draw_y - 3, total_drawn_w + 6, total_drawn_h + 6, { 30, 30, 35, 255 })
    draw_rect_safe(start_draw_x, start_draw_y, total_drawn_w, total_drawn_h, { 5, 5, 5, 255 })

    for _, r in ipairs(self.rects) do
      local rx = math.floor(start_draw_x + r.x * scale)
      local ry = math.floor(start_draw_y + r.y * scale)
      local rx2 = math.floor(start_draw_x + (r.x + r.w) * scale)
      local ry2 = math.floor(start_draw_y + (r.y + 1) * scale)
      local rw = math.max(1, rx2 - rx)
      local rh = math.max(1, ry2 - ry)

      -- Viewport Culling O(1): renderiza apenas o que cabe na janela
      if rx + rw >= x and rx <= x + w and ry + rh >= y and ry <= y + h then
        draw_rect_safe(rx, ry, rw, rh, r.color)
      end
    end
  else
    self:load_latest_image(false)
    local empty_box_w = math.min(560, w - 80)
    local empty_box_h = 160
    local e_x = x + math.floor((w - empty_box_w) / 2)
    local e_y = y + math.floor((h - empty_box_h) / 2)

    draw_rect_safe(e_x, e_y, empty_box_w, empty_box_h, { 14, 14, 14, 255 })
    draw_rect_safe(e_x, e_y, empty_box_w, 2, style.accent or { 38, 188, 95, 255 })

    draw_text_safe(font, "CANVAS FORENSE DOXOADE (Visualizador de Prints 1080p HD)", e_x + 20, e_y + 24, style.accent)
    draw_text_safe(font, "• Tire um print com Win+Shift+S ou PrintScreen.", e_x + 20, e_y + 54, { 230, 230, 230, 255 })
    draw_text_safe(font, "• Pressione Ctrl+V para colar a imagem diretamente aqui.", e_x + 20, e_y + 78, { 56, 189, 248, 255 })
    draw_text_safe(font, "• Clique no botão [HD] em qualquer card do documento para abrir aqui.", e_x + 20, e_y + 102, { 150, 150, 150, 255 })
  end
end
