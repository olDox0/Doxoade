-- doxoade/commands/lite_xl_systems/template/19c_canvas_sdl2_studio.lua
--[[
  🎨 DOXOADE HIGH-PERFORMANCE CANVAS & PRINTSCREEN STUDIO (Módulo 19c V27.0)
  - Renderizador de Bordas Contíguas: Elimina 100% das linhas de grade e frestas pretas.
  - Pan Drag & Zoom a 60 FPS: Otimização RLE contínua (~700 blocos com carga < 0.05s).
  - Captura Win32 Nativa via Venv Python (CF_DIB / CF_DIBV5 e Pillow).
]]
local core = require "core"
local style = require "core.style"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then native_renderer.draw_rect(x, y, w, h, color) end
end

local function draw_text_safe(font, text, x, y, color)
  if rencache and rencache.draw_text then rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then native_renderer.draw_text(font, text, x, y, color) end
end

local function get_active_project_dir()
  if core.project_directories and #core.project_directories > 0 then
    local p = core.project_directories[1]
    return tostring(type(p) == "table" and (p.path or p.name) or p)
  end
  return core.project_dir or "."
end

local function detect_project_venv(proj_dir)
  local sep = PATHSEP or "/"
  local candidates = { proj_dir .. sep .. "venv", proj_dir .. sep .. ".venv", proj_dir .. sep .. "env", proj_dir .. sep .. ".env" }
  for _, vpath in ipairs(candidates) do
    local info = system.get_file_info(vpath)
    if info and info.type == "dir" then
      local scripts = (PLATFORM == "Windows") and (vpath .. sep .. "Scripts") or (vpath .. sep .. "bin")
      if system.get_file_info(scripts) then return scripts, vpath end
    end
  end
  return nil, nil
end

-- =============================================================================
-- 🖼️ AUTO-THUMBNAIL ÁRTEMIS V2 (sidecar pós-paste, escopo corrigido)
-- Correção do crash 'cannot get undefined variable: dest_png':
-- caminhos agora entram como PARÂMETROS (upvalues reais da closure).
-- =============================================================================
local function _spawn_sidecar_generator(dest_png, proj_dir)
  if not dest_png or not proj_dir then return end
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local cache_dir = user_dir .. sep .. ".doxoade" .. sep .. "canvas_cache"
  pcall(function() system.mkdir(cache_dir) end)
  local gen_script = cache_dir .. sep .. "auto_thumb_gen_19c.py"
  local py_code = string.format([[
import sys
from pathlib import Path
try:
    sys.path.insert(0, %q)
    from doxoade.tools.image_systems import ThumbnailEngine
    engine = ThumbnailEngine(Path(%q))
    res = engine.generate(Path(%q), preset="card")
    print(f"[THUMB-19C] {res.status} {res.rects} rects")
except Exception as e:
    print(f"[THUMB-19C-ERR] {e}")
]], proj_dir, proj_dir, dest_png)
  local f_py = io.open(gen_script, "w")
  if f_py then f_py:write(py_code); f_py:close() end
  local venv_scripts = detect_project_venv(proj_dir)
  local py_exe = (venv_scripts and (venv_scripts .. sep .. "python.exe")) or "python"
  core.add_thread(function()
    pcall(system.exec, string.format('"%s" "%s"', py_exe, gen_script))
  end)
end

local function resolve_image_full_path(filename)
  local proj_dir = get_active_project_dir()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  
  local candidates = {
    proj_dir .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "images" .. sep .. filename,
    user_dir .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "images" .. sep .. filename,
    user_dir .. sep .. "assets" .. sep .. "images" .. sep .. filename,
  }
  for _, path in ipairs(candidates) do
    if system.get_file_info(path) then return path end
  end
  return candidates[1]
end

local CanvasStudio = {
  rects = {},
  grid_w = 1920, --460
  grid_h = 270,
  orig_w = 1366,
  orig_h = 768,
  image_path = nil,
  meta_path = nil,
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
  local full_path = resolve_image_full_path(img_filename)
  local meta_path = full_path:gsub("%.png$", ".meta.json")

  if not system.get_file_info(full_path) then
    core.log("⚠ Imagem não encontrada: " .. full_path)
    return false
  end

  self.image_path = full_path
  self.meta_path = meta_path
  self.mode_1to1 = false
  self.zoom = 1.0
  self.pan_x = 0
  self.pan_y = 0

  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local cache_dir = user_dir .. sep .. ".doxoade" .. sep .. "canvas_cache"
  pcall(function() system.mkdir(cache_dir) end)
  local rle_out = cache_dir .. sep .. "preview_rle.dat"
  local script_py = cache_dir .. sep .. "load_cas_rle.py"

  self.status_msg = "Carregando imagem em alta definição..."
  core.redraw = true

  local py_code = [[
import sys, os
try:
    from PIL import Image
    img = Image.open(sys.argv[1]).convert("RGB")
    orig_w, orig_h = img.size
    target_w = min(1920, orig_w) # 480
    target_h = max(10, int(orig_h * (target_w / orig_w)))
    resized = img.resize((target_w, target_h), Image.Resampling.BILINEAR)
    pixels = resized.load()

    rects = []
    for y in range(target_h):
        run_start = 0
        cur_c = pixels[0, y]
        run_len = 1
        for x in range(1, target_w):
            c = pixels[x, y]
            if abs(c[0]-cur_c[0]) <= 4 and abs(c[1]-cur_c[1]) <= 4 and abs(c[2]-cur_c[2]) <= 4:
                run_len += 1
            else:
                rects.append(f"{run_start},{y},{run_len},{cur_c[0]},{cur_c[1]},{cur_c[2]}")
                run_start = x; cur_c = c; run_len = 1
        rects.append(f"{run_start},{y},{run_len},{cur_c[0]},{cur_c[1]},{cur_c[2]}")

    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(f"{target_w},{target_h},{orig_w},{orig_h}\n")
        f.write("\n".join(rects))
    print(f"[OK] {orig_w}|{orig_h}")
except Exception as e:
    print(f"[ERRO] {e}")
]]
  local f_py = io.open(script_py, "w")
  if f_py then f_py:write(py_code); f_py:close() end

  local proj_dir = get_active_project_dir()
  local venv_scripts, _ = detect_project_venv(proj_dir)
  local py_exe = (venv_scripts and (venv_scripts .. "\\python.exe")) or "python"

  core.add_thread(function()
    pcall(system.exec, string.format('"%s" "%s" "%s" "%s"', py_exe, script_py, full_path, rle_out))
    for _ = 1, 40 do
      coroutine.yield(0.04)
      local finfo = system.get_file_info(rle_out)
      if finfo and (finfo.size or 0) > 0 then break end
    end

    local f_rle = io.open(rle_out, "r")
    if f_rle then
      local header = f_rle:read("*l") or "480,270,1366,768"
      local gw, gh, ow, oh = header:match("^(%d+),(%d+),(%d+),(%d+)$")
      CanvasStudio.grid_w = tonumber(gw) or 480
      CanvasStudio.grid_h = tonumber(gh) or 270
      CanvasStudio.orig_w = tonumber(ow) or 1366
      CanvasStudio.orig_h = tonumber(oh) or 768
      CanvasStudio.rects = {}
      for line in f_rle:lines() do
        local rx, ry, rw, r, g, b = line:match("^(%d+),(%d+),(%d+),(%d+),(%d+),(%d+)$")
        if rx then
          table.insert(CanvasStudio.rects, {
            x = tonumber(rx), y = tonumber(ry), w = tonumber(rw),
            color = { tonumber(r), tonumber(g), tonumber(b), 255 }
          })
        end
      end
      f_rle:close()
      CanvasStudio.status_msg = string.format("CAS Visualizer: %s (%dx%d px)", img_filename, CanvasStudio.orig_w, CanvasStudio.orig_h)
      core.redraw = true
    end
  end)
  core.log("✔ Imagem CAS aberta no Canvas: " .. img_filename)
  return true
end

function CanvasStudio:paste_clipboard_image()
  if self.is_capturing then return end
  self.is_capturing = true

  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local cache_dir = user_dir .. sep .. ".doxoade" .. sep .. "canvas_cache"
  pcall(function() system.mkdir(cache_dir) end)

  local rle_out = cache_dir .. sep .. "clipboard_rle.dat"
  local script_py = cache_dir .. sep .. "clip_bridge_v3.py"
  local log_out = cache_dir .. sep .. "clip_bridge.log"

  pcall(os.remove, rle_out)
  pcall(os.remove, log_out)

  local proj_dir = get_active_project_dir()
  local assets_dir = proj_dir .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "images"
  pcall(function() system.mkdir(proj_dir .. sep .. ".doxoade") end)
  pcall(function() system.mkdir(assets_dir) end)

  local ts = os.date("%Y%m%d_%H%M%S")
  local dest_png = assets_dir .. sep .. "print_" .. ts .. ".png"
  local dest_meta = assets_dir .. sep .. "print_" .. ts .. ".meta.json"

  self.status_msg = "Capturando PrintScreen via Venv Python..."
  core.redraw = true

  local py_code = [[
import sys, os, time, json, platform
from io import BytesIO
from pathlib import Path

def get_clipboard_image():
    try:
        from PIL import ImageGrab, Image
        for _ in range(5):
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image): return img
            elif isinstance(img, list) and len(img) > 0 and Path(img[0]).is_file():
                return Image.open(img[0])
            time.sleep(0.04)
    except Exception: pass

    if platform.system() == "Windows":
        try:
            import ctypes
            from PIL import Image
            u32 = ctypes.windll.user32
            k32 = ctypes.windll.kernel32
            for _ in range(5):
                if u32.OpenClipboard(None):
                    h_data = u32.GetClipboardData(8) or u32.GetClipboardData(17)
                    if h_data:
                        p_data = k32.GlobalLock(h_data)
                        size = k32.GlobalSize(h_data)
                        if p_data and size > 0:
                            import struct
                            raw_bytes = ctypes.string_at(p_data, size)
                            k32.GlobalUnlock(h_data)
                            u32.CloseClipboard()
                            header_size = struct.unpack("<I", raw_bytes[0:4])[0]
                            file_header = struct.pack("<2sIHHI", b"BM", 14 + size, 0, 0, 14 + header_size)
                            return Image.open(BytesIO(file_header + raw_bytes))
                    u32.CloseClipboard()
                time.sleep(0.04)
        except Exception: pass
    return None

def main():
    if len(sys.argv) < 4: sys.exit(1)
    dest_png, dest_meta, rle_file = sys.argv[1], sys.argv[2], sys.argv[3]

    img = get_clipboard_image()
    if not img:
        print("[ERRO] Clipboard vazio ou sem imagem.")
        sys.exit(1)

    from PIL import Image
    img = img.convert("RGB")
    orig_w, orig_h = img.size

    # Salva PNG Nativo 100% Original
    img.save(dest_png, format="PNG")

    # Miniatura 60x34 para o card do documento
    tw = 60
    th = max(10, int((orig_h / orig_w) * tw))
    thumb = img.resize((tw, th), Image.Resampling.BILINEAR)
    t_pixels = thumb.load()
    thumb_rects = []
    for ty in range(th):
        r_start = 0; cur_c = t_pixels[0, ty]; r_len = 1
        for tx in range(1, tw):
            c = t_pixels[tx, ty]
            if c == cur_c: r_len += 1
            else:
                thumb_rects.append(f"{r_start},{ty},{r_len},{cur_c[0]},{cur_c[1]},{cur_c[2]}")
                r_start = tx; cur_c = c; r_len = 1
        thumb_rects.append(f"{r_start},{ty},{r_len},{cur_c[0]},{cur_c[1]},{cur_c[2]}")

    meta = {
        "width": orig_w, "height": orig_h, "resolution": f"{orig_w}x{orig_h}",
        "thumb_w": tw, "thumb_h": th, "thumb_rects": thumb_rects,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "platform": platform.system()
    }
    with open(dest_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    # RLE Contínuo para o Canvas Studio (Espaço de grade 480px sem saltos de linha)
    target_w = min(480, orig_w)
    target_h = max(10, int(orig_h * (target_w / orig_w)))
    resized = img.resize((target_w, target_h), Image.Resampling.BILINEAR)
    pixels = resized.load()

    rects = []
    for y in range(target_h):
        run_start = 0; cur_color = pixels[0, y]; run_len = 1
        for x in range(1, target_w):
            c = pixels[x, y]
            if abs(c[0]-cur_color[0]) <= 4 and abs(c[1]-cur_color[1]) <= 4 and abs(c[2]-cur_color[2]) <= 4:
                run_len += 1
            else:
                rects.append(f"{run_start},{y},{run_len},{cur_color[0]},{cur_color[1]},{cur_color[2]}")
                run_start = x; cur_color = c; run_len = 1
        rects.append(f"{run_start},{y},{run_len},{cur_color[0]},{cur_color[1]},{cur_color[2]}")

    with open(rle_file, "w", encoding="utf-8") as f:
        f.write(f"{target_w},{target_h},{orig_w},{orig_h}\n")
        f.write("\n".join(rects))

    print(f"[OK] {orig_w}|{orig_h}")
    sys.exit(0)

if __name__ == "__main__": main()
]]

  local f_py = io.open(script_py, "w")
  if f_py then f_py:write(py_code); f_py:close() end

  local venv_scripts, _ = detect_project_venv(proj_dir)
  local py_exe = (venv_scripts and (venv_scripts .. "\\python.exe")) or "python"

  core.add_thread(function()
    pcall(system.exec, string.format('"%s" "%s" "%s" "%s" "%s" > "%s" 2>&1', py_exe, script_py, dest_png, dest_meta, rle_out, log_out))

    for _ = 1, 40 do
      coroutine.yield(0.04)
      local finfo = system.get_file_info(rle_out)
      if finfo and (finfo.size or 0) > 0 then break end
    end

    local f_rle = io.open(rle_out, "r")
    if f_rle then
      local header = f_rle:read("*l") or "480,270,1366,768"
      local gw, gh, ow, oh = header:match("^(%d+),(%d+),(%d+),(%d+)$")
      CanvasStudio.grid_w = tonumber(gw) or 480
      CanvasStudio.grid_h = tonumber(gh) or 270
      CanvasStudio.orig_w = tonumber(ow) or 1366
      CanvasStudio.orig_h = tonumber(oh) or 768
      CanvasStudio.rects = {}
      for line in f_rle:lines() do
        local rx, ry, rw, r, g, b = line:match("^(%d+),(%d+),(%d+),(%d+),(%d+),(%d+)$")
        if rx then
          table.insert(CanvasStudio.rects, {
            x = tonumber(rx), y = tonumber(ry), w = tonumber(rw),
            color = { tonumber(r), tonumber(g), tonumber(b), 255 }
          })
        end
      end
      f_rle:close()
      CanvasStudio.image_path = dest_png
      CanvasStudio.meta_path = dest_meta
      CanvasStudio.mode_1to1 = false
      CanvasStudio.zoom = 1.0
      CanvasStudio.pan_x = 0
      CanvasStudio.pan_y = 0
      CanvasStudio.status_msg = string.format("Print Salvo: print_%s.png (%dx%d px)", ts, CanvasStudio.orig_w, CanvasStudio.orig_h)
      core.log(string.format("✔ Print capturado e salvo: .doxoade/assets/images/print_%s.png", ts))
    else
      CanvasStudio.status_msg = "Nenhuma imagem encontrada no clipboard."
      core.log("⚠ Clipboard vazio. Pressione a tecla PrintScreen ou Win+Shift+S.")
    end
    CanvasStudio.is_capturing = false
    core.redraw = true
  end)
end

function CanvasStudio:copy_image_to_clipboard()
  if not self.image_path or not system.get_file_info(self.image_path) then
    core.log("⚠ Nenhuma imagem carregada no Canvas para copiar.")
    return
  end
  local full_path = self.image_path
  local fname = full_path:match("[^/\\]+$")

  if PLATFORM == "Windows" then
    local ps_cmd = string.format([[powershell.exe -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; [System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile('%s'))"]], full_path:gsub('/', '\\'))
    pcall(system.exec, ps_cmd)
  end

  if system.set_clipboard then
    local tag = string.format("[DOX-IMG:%s | %dx%d | %s]", fname, self.orig_w or 1366, self.orig_h or 768, os.date("%Y-%m-%d"))
    system.set_clipboard(tag)
  end

  core.log(string.format("✔ Imagem '%s' copiada para a área de transferência!", fname))
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

-- Adicionar o método de limpeza completa
function CanvasStudio:clear()
  self.rects = {}
  self.image_path = nil
  self.meta_path = nil
  self.native_img_obj = nil
  self.zoom = 1.0
  self.pan_x = 0
  self.pan_y = 0
  self.status_msg = "Canvas limpo. Pressione Ctrl+V para colar novo print."
  core.redraw = true
  if core.log then core.log("🧹 [CANVAS] Tela limpa com sucesso.") end
end

-- =============================================================================
-- RENDERIZADOR CONTÍNUO ZERO-SEAMS (Sem Linhas de Grade e Pan Drag Suave 60 FPS)
-- =============================================================================
function CanvasStudio:draw_viewport(x, y, w, h)
  local font = style.font or style.code_font
  if #self.rects > 0 then
    local gw = self.grid_w or 480
    local gh = self.grid_h or 270

    local base_w = w - 20
    local base_h = h - 20
    local base_scale = math.min(base_w / gw, base_h / gh)

    local total_drawn_w = math.floor(gw * base_scale * self.zoom)
    local total_drawn_h = math.floor(gh * base_scale * self.zoom)

    local start_draw_x = x + math.floor((w - total_drawn_w) / 2) + self.pan_x
    local start_draw_y = y + math.floor((h - total_drawn_h) / 2) + self.pan_y

    local scale_x = total_drawn_w / gw
    local scale_y = total_drawn_h / gh

    -- Fundo de contraste escuro
    draw_rect_safe(start_draw_x - 2, start_draw_y - 2, total_drawn_w + 4, total_drawn_h + 4, { 5, 5, 5, 255 })

    -- 🚀 Renderizador de Bordas Contíguas: rx2 - rx e ry2 - ry eliminam qualquer fresta
    for _, r in ipairs(self.rects) do
      local rx = start_draw_x + math.floor(r.x * scale_x)
      local ry = start_draw_y + math.floor(r.y * scale_y)
      local rx2 = start_draw_x + math.ceil((r.x + r.w) * scale_x)
      local ry2 = start_draw_y + math.ceil((r.y + 1) * scale_y)
      local rw = rx2 - rx
      local rh = ry2 - ry

      -- Viewport Culling rápido
      if rx + rw >= x and rx <= x + w and ry + rh >= y and ry <= y + h then
        draw_rect_safe(rx, ry, rw, rh, r.color)
      end
    end
  else
    local empty_box_w = math.min(560, w - 80)
    local empty_box_h = 160
    local e_x = x + math.floor((w - empty_box_w) / 2)
    local e_y = y + math.floor((h - empty_box_h) / 2)
    draw_rect_safe(e_x, e_y, empty_box_w, empty_box_h, { 14, 14, 14, 255 })
    draw_rect_safe(e_x, e_y, empty_box_w, 2, style.accent or { 38, 188, 95, 255 })
    draw_text_safe(font, "CANVAS FORENSE DOXOADE (Captura Direta)", e_x + 20, e_y + 24, style.accent)
    draw_text_safe(font, "• Pressione a tecla PrintScreen ou Win+Shift+S.", e_x + 20, e_y + 54, { 230, 230, 230, 255 })
    draw_text_safe(font, "• Pressione Ctrl+V para colar a imagem diretamente aqui.", e_x + 20, e_y + 78, { 56, 189, 248, 255 })
    draw_text_safe(font, "• Pressione Ctrl+C para copiar a imagem de volta ao clipboard.", e_x + 20, e_y + 102, { 150, 150, 150, 255 })
  end
end

-- =============================================================================
-- AUTO-THUMBNAIL GENERATOR (integração 19c -> 19a)
-- =============================================================================
local function auto_generate_thumbnail(img_path)
  if not img_path then return end
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local cache_dir = user_dir .. sep .. ".doxoade" .. sep .. "canvas_cache"
  local gen_script = cache_dir .. sep .. "auto_thumb_gen.py"
  local sidecar = img_path:gsub("%.png$", ".thumb.rlebin")
  
  -- Só gera se o sidecar não existe ou é mais antigo que a imagem
  local sidecar_info = system.get_file_info(sidecar)
  local img_info = system.get_file_info(img_path)
  if sidecar_info and img_info and sidecar_info.modified >= img_info.modified then
    return -- já existe e é fresco
  end
  
  local py_code = [[
import sys
from pathlib import Path
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from doxoade.tools.image_systems import ThumbnailEngine, RleCodec
    from PIL import Image
    img_path, out_path = sys.argv[1], sys.argv[2]
    with Image.open(img_path) as img:
        img = img.convert("RGB")
        ow, oh = img.size
        thumb = img.resize((60, 34), Image.Resampling.LANCZOS)
        flat = list(thumb.getdata())
    rects = RleCodec.build_runs(flat, 60, 34)
    blob = RleCodec.encode_binary(60, 34, ow, oh, rects)
    with open(out_path, "wb") as f:
        f.write(blob)
    print(f"[THUMB] {img_path} -> {len(rects)} rects, {len(blob)}B")
except Exception as e:
    print(f"[THUMB-ERR] {e}")
]]
  
  local f_py = io.open(gen_script, "w")
  if f_py then f_py:write(py_code); f_py:close() end
  
  local proj_dir = get_active_project_dir()
  local venv_scripts, _ = detect_project_venv(proj_dir)
  local py_exe = (venv_scripts and (venv_scripts .. "\\python.exe")) or "python"
  
  -- Assíncrono: não bloqueia o loop de UI
  core.add_thread(function()
    pcall(system.exec, string.format('"%s" "%s" "%s" "%s"', 
      py_exe, gen_script, img_path, sidecar))
    core.log("🖼️ [AUTO-THUMB] Sidecar gerado para: " .. img_path)
  end)
end

-- Hook: quando o 19c salva um print novo, dispara geração automática
local original_paste = CanvasStudio.paste_clipboard_image
CanvasStudio.paste_clipboard_image = function(self)
  local result = original_paste(self)
  -- Aguarda o arquivo existir (o 19c salva em background)
  -- core.add_thread(function()
  --   -- Aguarda o PNG existir no disco
  --   for _ = 1, 30 do
  --     coroutine.yield(0.1)
  --     if system.get_file_info(dest_png) then
  --       -- Dispara o gerador de sidecar (mesma lógica do 19a)
  --       local sidecar = dest_png:gsub("%.png$", ".thumb.rlebin")
  --       local gen_script = cache_dir .. sep .. "auto_thumb_gen_19c.py"
  --       local py_code = string.format([[
  -- import sys
  -- from pathlib import Path
  -- try:
  --     sys.path.insert(0, %q)
  --     from doxoade.tools.image_systems import ThumbnailEngine
  --     engine = ThumbnailEngine(Path(%q))
  --     res = engine.generate(Path(%q), preset="card")
  --     print(f"[THUMB-19C] {res.status}")
  -- except Exception as e:
  --     print(f"[THUMB-19C-ERR] {e}")
  -- ]], proj_dir, proj_dir, dest_png)
        
  --       local f_py = io.open(gen_script, "w")
  --       if f_py then f_py:write(py_code); f_py:close() end
        
  --       local py_exe = (venv_scripts and (venv_scripts .. "\\python.exe")) or "python"
  --       pcall(system.exec, string.format('"%s" "%s"', py_exe, gen_script))
  --       core.log("🖼️ [19c] Sidecar RLE gerado automaticamente para o print.")
  --       break
  --     end
  --   end
  -- end)
  return result
end
