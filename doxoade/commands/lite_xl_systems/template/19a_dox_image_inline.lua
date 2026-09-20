-- doxoade/commands/lite_xl_systems/template/19a_dox_image_inline.lua
--[[
🖼️ DOXOADE INLINE IMAGE CARDS (V64.0 Non-Invasive + Toggle Arrow)
Arquitetura Não-Invasiva: Hooks que preservam 100% da funcionalidade nativa.
Seta de Colapso (▶/▼) para expandir/recolher imagens sem quebrar o scroll.
Compliance: ProDeNov 1.2.1, PASC-6.1.
]]
local core = require "core"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local DocView = require "core.docview"
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

-- =============================================================================
-- CONFIGURAÇÕES E ESTADO
-- =============================================================================
local CARD_HEIGHT = 190
local CARD_MARGIN_X = 8
local TOGGLE_ARROW_SIZE = 18  -- Seta maior e mais clicável
local _image_meta_cache = {}
local _meta_order = {}
local MAX_META_CACHE = 64
local _card_interactive_regions = {}
local _collapsed_images = {}  -- Estado de colapso por linha: { [line_idx] = true/false }

-- =============================================================================
-- 🛡️ POLYFILLS DE RENDERIZAÇÃO SEGURA (Blindados contra tipos incorretos)
-- =============================================================================
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
  if type(color) ~= "table" then
    color = { 255, 255, 255, 255 }
  end
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

-- 👇 NOVAS FUNÇÕES (Adicionar aqui) 👇
local function safe_push_clip_rect(x, y, w, h)
  if core.push_clip_rect then
    pcall(core.push_clip_rect, x, y, w, h)
  end
end

local function safe_pop_clip_rect()
  if core.pop_clip_rect then
    pcall(core.pop_clip_rect)
  end
end
-- 👆 FIM DAS NOVAS FUNÇÕES 👆

-- =============================================================================
-- 🔄 TOGGLE (EXPANDIR/COLAPSAR)
-- =============================================================================
local function is_image_collapsed(line_idx)
  return _collapsed_images[line_idx] == true
end

local function toggle_image_collapse(line_idx)
  _collapsed_images[line_idx] = not _collapsed_images[line_idx]
  core.redraw = true
end

-- =============================================================================
-- 🔽 RENDERIZAÇÃO DA SETA TOGGLE (Fixa na linha do código)
-- =============================================================================
local function draw_toggle_arrow(view, line_idx, line_y, line_h, is_collapsed)
  local font = view:get_font()
  local gw = (view.get_gutter_width and view:get_gutter_width()) or 40
  
  -- Posicionamento: logo após o gutter, centralizado verticalmente na linha
  local arrow_x = view.position.x + gw + 2
  local arrow_y = line_y + math.floor((line_h - TOGGLE_ARROW_SIZE) / 2)
  
  -- Fundo do botão (área clicável visível)
  draw_rect_safe(arrow_x, arrow_y, TOGGLE_ARROW_SIZE, TOGGLE_ARROW_SIZE, { 50, 50, 55, 255 })
  
  -- Borda sutil para destacar
  draw_rect_safe(arrow_x, arrow_y, TOGGLE_ARROW_SIZE, 1, { 80, 80, 85, 255 })
  draw_rect_safe(arrow_x, arrow_y + TOGGLE_ARROW_SIZE - 1, TOGGLE_ARROW_SIZE, 1, { 80, 80, 85, 255 })
  
  -- Símbolo da seta (centralizado no botão)
  local arrow_symbol = is_collapsed and "▶" or "▼"
  local arrow_color = { 255, 255, 255, 255 }
  local text_x = arrow_x + math.floor((TOGGLE_ARROW_SIZE - font:get_width(arrow_symbol)) / 2)
  local text_y = arrow_y + 2
  draw_text_safe(font, arrow_symbol, text_x, text_y, arrow_color)
  
  -- Registrar região clicável
  _card_interactive_regions["toggle_" .. line_idx] = {
    type = "toggle",
    line_idx = line_idx,
    x = arrow_x,
    y = arrow_y,
    w = TOGGLE_ARROW_SIZE,
    h = TOGGLE_ARROW_SIZE,
  }
end

-- =============================================================================
-- RESOLUÇÃO DE PROJETO E PYTHON
-- =============================================================================
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
        local pdir = py_exe:match("^(.+)[/\\]Scripts[/\\]") or py_exe:match("^(.+)[/\\]bin[/\\]") or py_exe:match("^(.+)[/\\]")
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

-- =============================================================================
-- EXTRAÇÃO DE INFO DE IMAGEM
-- =============================================================================
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

-- =============================================================================
-- CACHE DE METADADOS
-- =============================================================================
local function load_rle_binary(path)
  local f = io.open(path, "rb")
  if not f then return nil end
  local data = f:read("*a") or ""
  f:close()
  if #data < 21 or data:sub(1, 7) ~= "DOXRLE1" then return nil end
  local ok, ver, gw, gh, ow, oh, count = pcall(string.unpack, "<BHHHHI", data, 8)
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
    filename = filename, loaded = false,
    width = 1920, height = 1080,
    grid_w = 240, grid_h = 136, rects = {}
  }
  if bin and bin.rects and #bin.rects > 0 then
    meta.width = bin.orig_w; meta.height = bin.orig_h
    meta.grid_w = bin.grid_w; meta.grid_h = bin.grid_h
    meta.rects = bin.rects; meta.loaded = true
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

local function invalidate_image_cache(filename)
  if filename then
    _image_meta_cache[filename] = nil
    for i, fn in ipairs(_meta_order) do
      if fn == filename then table.remove(_meta_order, i); break end
    end
  end
end

-- =============================================================================
-- TOGGLE (EXPANDIR/COLAPSAR)
-- =============================================================================
local function is_image_collapsed(line_idx)
  return _collapsed_images[line_idx] == true
end

local function toggle_image_collapse(line_idx)
  _collapsed_images[line_idx] = not _collapsed_images[line_idx]
  core.redraw = true
end

-- =============================================================================
-- DETECÇÃO RÁPIDA: documento tem imagens?
-- =============================================================================
local function doc_has_any_images(doc)
  if not doc or not doc.lines then return false end
  for _, line in ipairs(doc.lines) do
    if extract_dox_image_info(line) then return true end
  end
  return false
end

-- =============================================================================
-- RENDERIZAÇÃO DA SETA TOGGLE (fixa na linha do código)
-- =============================================================================
local function draw_toggle_arrow(view, line_idx, line_y, line_h, is_collapsed)
  local font = view:get_font()
  local gw = (view.get_gutter_width and view:get_gutter_width()) or 40
  
  -- Posicionamento: alinhado à esquerda do gutter, centralizado verticalmente
  --local arrow_x = view.position.x + 2  -- Margem esquerda pequena
  local arrow_x = view.position.x + gw - 10
  local arrow_y = line_y + math.floor((line_h - TOGGLE_ARROW_SIZE) + 8)
  
  -- Fundo do botão (área clicável visível)
  draw_rect_safe(arrow_x, arrow_y, TOGGLE_ARROW_SIZE, TOGGLE_ARROW_SIZE, { 50, 50, 55, 255 })
  
  -- Borda sutil para destacar
  -- draw_rect_safe(arrow_x, arrow_y, TOGGLE_ARROW_SIZE, 1, { 38, 188, 95, 255 })
  -- draw_rect_safe(arrow_x, arrow_y + TOGGLE_ARROW_SIZE - 1, TOGGLE_ARROW_SIZE, 1, { 38, 188, 95, 255 })
  
  -- Símbolo da seta (centralizado no botão)
  local arrow_symbol = is_collapsed and "▶" or "▼"
  local arrow_color = { 38, 188, 95, 255 }
  local text_x = arrow_x + math.floor((TOGGLE_ARROW_SIZE - font:get_width(arrow_symbol)) / 2)
  local text_y = arrow_y + 0.5
  draw_text_safe(font, arrow_symbol, text_x, text_y, arrow_color)
  
  -- Registrar região clicável
  _card_interactive_regions["toggle_" .. line_idx] = {
    type = "toggle",
    line_idx = line_idx,
    x = arrow_x,
    y = arrow_y,
    w = TOGGLE_ARROW_SIZE,
    h = TOGGLE_ARROW_SIZE,
  }
end

-- =============================================================================
-- RENDERIZAÇÃO DO CARD DE IMAGEM (overlay flutuante)
-- =============================================================================
local function draw_image_card(view, line_idx, info, x, y, line_h)
  if is_image_collapsed(line_idx) then return end
  
  local info_fn = (info and info.filename) or "image.png"
  local meta = load_image_meta(info_fn)
  local font = view:get_font()
  local gw = (view.get_gutter_width and view:get_gutter_width()) or 40
  local max_available_w = view.size.x - gw - 28
  local card_w = math.max(260, math.min(max_available_w, 540))
  local card_h = CARD_HEIGHT
  local card_x = view.position.x + gw + CARD_MARGIN_X
  local card_y = y + line_h + 2  -- Logo abaixo da linha do código
  
  -- Fundo do card
  draw_rect_safe(card_x - 1, card_y - 1, card_w + 2, card_h + 2, { 30, 30, 32, 255 })
  draw_rect_safe(card_x, card_y, card_w, card_h, style.background2 or { 24, 24, 27, 255 })
  draw_rect_safe(card_x, card_y, 3, card_h, style.accent or { 38, 188, 95, 255 })
  
  -- Header
  local disp_w = tonumber(meta and meta.width) or 1920
  local disp_h = tonumber(meta and meta.height) or 1080
  local header_text = string.format("[IMG] %s (%dx%d)", tostring(info_fn), disp_w, disp_h)
  draw_text_safe(font, header_text, card_x + 10, card_y + 8, style.accent or { 38, 188, 95, 255 })
  
  -- Botões
  local btn_copy_x = card_x + card_w - 120
  local btn_hd_x = card_x + card_w - 54
  local btn_y = card_y + 4
  local btn_h = 18
  
  draw_rect_safe(btn_copy_x, btn_y, 60, btn_h, { 40, 40, 45, 255 })
  draw_text_safe(font, "[Copiar]", btn_copy_x + 4, btn_y + 1, { 220, 220, 220, 255 })
  draw_rect_safe(btn_hd_x, btn_y, 48, btn_h, { 40, 40, 45, 255 })
  draw_text_safe(font, "[HD]", btn_hd_x + 7, btn_y + 1, { 56, 189, 248, 255 })
  
  -- Regiões interativas
  _card_interactive_regions[info.filename] = {
    btn_copy = { x = btn_copy_x, y = btn_y, w = 30, h = btn_h, filename = info.filename },
    btn_hd = { x = btn_hd_x, y = btn_y, w = 48, h = btn_h, filename = info.filename },
  }
  
  -- Thumbnail box
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
    
    safe_push_clip_rect(thumb_box_x, thumb_box_y, thumb_box_w, thumb_box_h)
    for _, r in ipairs(meta.rects) do
      local rx = offset_x + (r.x * scale)
      local ry = offset_y + (r.y * scale)
      local rw = math.max(1, r.w * scale)
      local rh = math.max(1, (r.h or 1) * scale)
      draw_rect_safe(rx, ry, rw, rh, r.color)
    end
    safe_pop_clip_rect()
  else
    draw_text_safe(font, "Carregando preview...", thumb_box_x + 10, thumb_box_y + 20, style.dim)
  end
end

-- =============================================================================
-- HOOK NÃO-INVASIVO NO DOCVIEW:DRAW (ZERO BLACKOUT)
-- =============================================================================
if not rawget(_G, "_DOXOADE_IMAGE_INLINE_V63_HOOKED") then
  rawset(_G, "_DOXOADE_IMAGE_INLINE_V63_HOOKED", true)
  
  local original_docview_draw = DocView.draw
  function DocView:draw(...)
    -- 1. Chama o draw original PRIMEIRO (preserva 100% da renderização nativa)
    original_docview_draw(self, ...)
    
    -- 2. Só desenha overlays se houver imagens no documento
    if not self.doc or not doc_has_any_images(self.doc) then return end
    
    -- Limpa regiões interativas antigas
    _card_interactive_regions = {}
    
    local line_h = self:get_line_height()
    local font = self:get_font()
    local gw = (self.get_gutter_width and self:get_gutter_width()) or 40
    local view_top = self.position.y
    local view_bottom = self.position.y + self.size.y
    local text_x = self.position.x + gw + 8
    
    -- Calcula range visível (usando o método nativo)
    local min_line, max_line
    if self.get_visible_line_range then
      min_line, max_line = self:get_visible_line_range()
    else
      min_line = 1
      max_line = #self.doc.lines
    end
    
    -- Desenha setas e cards sobre o conteúdo já renderizado
    for line_idx = min_line, max_line do
      local text = self.doc.lines[line_idx]
      local info = extract_dox_image_info(text)
      if info then
        -- Posição Y nativa da linha (via método do Lite XL)
        local line_x, line_y = self:get_line_screen_position(line_idx, 1)
        
        -- Só desenha se estiver na área visível
        if line_y + line_h + CARD_HEIGHT >= view_top and line_y <= view_bottom then
          -- Desenha seta toggle (sempre visível)
          local is_collapsed = is_image_collapsed(line_idx)
          draw_toggle_arrow(self, line_idx, line_y, line_h, is_collapsed)
          
          -- Desenha card apenas se EXPANDIDA
          if not is_collapsed then
            draw_image_card(self, line_idx, info, text_x, line_y, line_h)
          end
        end
      end
    end
  end
end

-- =============================================================================
-- INTERCEPTAÇÃO DE CLIQUE (Toggle + Botões)
-- =============================================================================
local original_on_mouse_pressed = DocView.on_mouse_pressed
function DocView:on_mouse_pressed(button, px, py, clicks)
  if button == "left" or button == 1 then
    -- Verifica clique em setas de toggle
    for key, region in pairs(_card_interactive_regions) do
      if region.type == "toggle" then
        if px >= region.x and px <= region.x + region.w and
           py >= region.y and py <= region.y + region.h then
          toggle_image_collapse(region.line_idx)
          return true
        end
      end
    end
    
    -- Verifica clique em botões de card
    for _, region in pairs(_card_interactive_regions) do
      if region.btn_copy and px >= region.btn_copy.x and px <= region.btn_copy.x + region.btn_copy.w and
         py >= region.btn_copy.y and py <= region.btn_copy.y + region.btn_copy.h then
        local img_path = resolve_image_full_path(region.btn_copy.filename):gsub("/", "\\")
        
        -- Copia a IMAGEM REAL para o clipboard do Windows
        if PLATFORM == "Windows" then
          local ps_cmd = string.format(
            [[powershell.exe -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; [System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile('%s'))"]],
            img_path:gsub("'", "''")
          )
          pcall(system.exec, ps_cmd)
        end
        
        -- Também copia o texto da tag como fallback
        if system.set_clipboard then
          system.set_clipboard(string.format("[DOX-IMG: %s]", region.btn_copy.filename))
        end
        
        core.log(" [IMAGE] Imagem copiada para o clipboard: " .. region.btn_copy.filename)
        return true
      end
      
      if region.btn_hd and px >= region.btn_hd.x and px <= region.btn_hd.x + region.btn_hd.w and
         py >= region.btn_hd.y and py <= region.btn_hd.y + region.btn_hd.h then
        local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
        if canvas and canvas.load_cas_image_by_filename then
          canvas:load_cas_image_by_filename(region.btn_hd.filename)
          local shelf = rawget(_G, "_DOXOADE_SHELF_HUB")
          if shelf then
            shelf.active_tab = "canvas"
            shelf.visible = true
          end
        end
        core.redraw = true
        return true
      end
    end
  end
  return original_on_mouse_pressed and original_on_mouse_pressed(self, button, px, py, clicks)
end

-- =============================================================================
-- SISTEMA DE PASTE
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
  
  local py_code = [[
import sys, os, time, json, platform, struct, datetime
from io import BytesIO
from pathlib import Path

def get_image_from_clipboard():
    try:
        from PIL import ImageGrab, Image
        for _ in range(4):
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image): return img
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
    if len(sys.argv) < 3: sys.exit(1)
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
            "status": "SUCCESS", "filename": fn, "full_path": str(dest_png),
            "tag": f"[DOX-IMG: {fn} | {orig_w}x{orig_h} | {date_str}]",
            "width": orig_w, "height": orig_h
        }
        out_p.write_text(json.dumps(payload), encoding="utf-8")
    except Exception as e:
        out_p.write_text(json.dumps({"status": "ERROR", "error": str(e)}), encoding="utf-8")

if __name__ == "__main__":
    main()
]]
  
  local f_bridge = io.open(bridge_py, "w")
  if f_bridge then f_bridge:write(py_code); f_bridge:close() end
  
  local direct_cmd = string.format('"%s" "%s" "%s" "%s"',
    py_exe:gsub("/", "\\"), bridge_py:gsub("/", "\\"),
    out_json:gsub("/", "\\"), proj_dir:gsub("/", "\\")
  )
  
  core.add_thread(function()
    pcall(system.exec, direct_cmd)
    for _ = 1, 75 do
      coroutine.yield(0.04)
      local finfo = system.get_file_info(out_json)
      if finfo and (finfo.size or 0) > 0 then break end
    end
    local f = io.open(out_json, "r")
    if f then
      local raw = f:read("*a") or ""; f:close()
      local tag = raw:match('"tag"%s*:%s*"([^"]+)"')
      local filename = raw:match('"filename"%s*:%s*"([^"]+)"')
      local status = raw:match('"status"%s*:%s*"([^"]+)"')
      if status == "SUCCESS" and tag and filename then
        invalidate_image_cache(filename)
        local l1, c1 = doc:get_selection(true)
        doc:insert(l1, c1, tag .. "\n")
        core.redraw = true
        local canvas = rawget(_G, "_DOXOADE_CANVAS_STUDIO")
        if canvas and canvas.load_cas_image_by_filename then
          canvas:load_cas_image_by_filename(filename)
        end
        core.log("🖼️ [PASTE] Imagem salva: " .. filename)
        if on_complete_callback then on_complete_callback(true) end
      else
        local err = raw:match('"error"%s*:%s*"([^"]+)"') or "Nenhuma imagem encontrada."
        if on_complete_callback then on_complete_callback(false, err)
        else core.log(" [PASTE] " .. err) end
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
      if not success then command.perform("doc:paste") end
    end)
  end
})

keymap.add {
  ["ctrl+shift+v"] = "doxoade:paste-image-from-clipboard",
  ["ctrl+alt+v"]   = "doxoade:paste-image-from-clipboard",
}
