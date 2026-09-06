-- doxoade/commands/lite_xl_systems/template/19_bottom_shelf_canvas.lua
--[[
  🖥️ DOXOADE BLACK CONSOLE TERMINAL & PRO STUDIO (V14.0 Performance Edition)
  - Zoom do Terminal com Ctrl+MouseWheel (Fonte escalável de 8px a 24px).
  - Seleção de Texto Isolada no Terminal (Mouse Drag + Ctrl+C exclusivo).
  - Zero Lag de Digitação (Cache de arquivos para Autocomplete sem I/O repetitivo).
  - Quebra de Linhas Longas (Word-Wrap Inteligente) e Cores Vivas do Pantheon.
  - Canvas 1:1 Nativo SDL2 com Metadados Forenses e SHA-256.
]]
local core = require "core"
local RootView = require "core.rootview"
local command = require "core.command"
local keymap = require "core.keymap"
local style = require "core.style"
local config = require "core.config"

-- =============================================================================
-- 1. POLYFILLS DE RENDERIZAÇÃO
-- =============================================================================
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

local function draw_text_safe(font, text, x, y, color)
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

-- =============================================================================
-- 2. TABELA DE CORES ANSI E COLORIZADOR SEMÂNTICO SOBERANO
-- =============================================================================
local ANSI_PALETTE = {
  [30] = { 20, 20, 20, 255 }, [31] = { 239, 68, 68, 255 }, [32] = { 34, 197, 94, 255 },
  [33] = { 234, 179, 8, 255 }, [34] = { 59, 130, 246, 255 }, [35] = { 168, 85, 247, 255 },
  [36] = { 6, 182, 212, 255 }, [37] = { 230, 230, 230, 255 },
  [90] = { 115, 115, 115, 255 }, [91] = { 248, 113, 113, 255 }, [92] = { 74, 222, 128, 255 },
  [93] = { 250, 204, 21, 255 }, [94] = { 96, 165, 250, 255 }, [95] = { 192, 132, 252, 255 },
  [96] = { 34, 211, 238, 255 }, [97] = { 255, 255, 255, 255 },
}

local PANTHEON_CMD_COLORS = {
  ["audit"]        = { 248, 113, 113, 255 }, -- Vermelho Ma'at
  ["typhon"]       = { 251, 191, 36, 255 },  -- Amarelo Caos
  ["check"]        = { 52, 211, 153, 255 },  -- Verde Sanidade
  ["vulcan"]       = { 251, 146, 60, 255 },  -- Laranja Metalurgia
  ["hades"]        = { 239, 68, 68, 255 },   -- Vermelho Persistência
  ["doxly"]        = { 56, 189, 248, 255 },  -- Ciano IDE
  ["deploy"]       = { 129, 140, 248, 255 }, -- Índigo Pipeline
}

local function semantic_fallback_colorize(raw_line)
  local segs = {}
  local default_text_col = { 230, 230, 230, 255 }

  if raw_line:find("^%[INFO%]") or raw_line:find("✔") or raw_line:find("%[PASS%]") or raw_line:find("%[HERMES%-LOGGER%]") then
    local tag, rest = raw_line:match("^(%b[])(.*)$")
    if tag then
      table.insert(segs, { text = tag, fg = { 52, 211, 153, 255 } })
      table.insert(segs, { text = rest, fg = default_text_col })
      return segs
    end
  elseif raw_line:find("^%[ERROR%]") or raw_line:find("✖") or raw_line:find("%[FAIL%]") or raw_line:find("Error:") or raw_line:find("Falha") then
    table.insert(segs, { text = raw_line, fg = { 248, 113, 113, 255 } })
    return segs
  elseif raw_line:find("^%[WARN%]") or raw_line:find("⚠") or raw_line:find("Warning:") then
    table.insert(segs, { text = raw_line, fg = { 251, 191, 36, 255 } })
    return segs
  end

  local cmd_name, cmd_desc = raw_line:match("^%s+([%w%-_]+)%s%s+(.*)$")
  if cmd_name and cmd_desc and not raw_line:find(":") then
    local cmd_col = PANTHEON_CMD_COLORS[cmd_name:lower()] or { 56, 189, 248, 255 }
    table.insert(segs, { text = "  " .. cmd_name, fg = cmd_col })
    table.insert(segs, { text = "  " .. cmd_desc, fg = { 210, 215, 230, 255 } })
    return segs
  end

  local opt_name, opt_desc = raw_line:match("^%s+(%-%-[%w%-_]+)%s%s+(.*)$")
  if opt_name and opt_desc then
    table.insert(segs, { text = "  " .. opt_name, fg = { 251, 191, 36, 255 } })
    table.insert(segs, { text = "  " .. opt_desc, fg = { 210, 215, 230, 255 } })
    return segs
  end

  if raw_line:find("^%s*[%w%s]+:%s*$") then
    table.insert(segs, { text = raw_line, fg = { 168, 85, 247, 255 } })
    return segs
  end

  table.insert(segs, { text = raw_line, fg = default_text_col })
  return segs
end

local function parse_ansi_segments(raw_line, default_fg)
  default_fg = default_fg or { 230, 230, 230, 255 }
  if not raw_line or raw_line == "" then
    return { { text = "", fg = default_fg } }
  end

  if not raw_line:find("\x1b%[") then
    return semantic_fallback_colorize(raw_line)
  end

  local segments = {}
  local current_fg = default_fg
  local current_bg = nil
  local pos = 1
  local len = #raw_line

  while pos <= len do
    local esc_start, esc_end, params_str = raw_line:find("\x1b%[([%d;]*)m", pos)
    if not esc_start then
      local text_part = raw_line:sub(pos):gsub("\r", "")
      if text_part ~= "" then
        table.insert(segments, { text = text_part, fg = current_fg, bg = current_bg })
      end
      break
    end

    if esc_start > pos then
      local text_part = raw_line:sub(pos, esc_start - 1):gsub("\r", "")
      if text_part ~= "" then
        table.insert(segments, { text = text_part, fg = current_fg, bg = current_bg })
      end
    end

    local params = {}
    for p in params_str:gmatch("%d+") do table.insert(params, tonumber(p)) end
    if #params == 0 then params = { 0 } end

    local i = 1
    while i <= #params do
      local code = params[i]
      if code == 0 then
        current_fg = default_fg; current_bg = nil
      elseif code >= 30 and code <= 37 then
        current_fg = ANSI_PALETTE[code] or default_fg
      elseif code >= 90 and code <= 97 then
        current_fg = ANSI_PALETTE[code] or default_fg
      elseif code >= 40 and code <= 47 then
        current_bg = ANSI_PALETTE[code - 10]
      elseif code >= 100 and code <= 107 then
        current_bg = ANSI_PALETTE[code - 60]
      elseif code == 39 then current_fg = default_fg
      elseif code == 49 then current_bg = nil
      elseif code == 38 and params[i+1] == 2 and params[i+2] and params[i+3] and params[i+4] then
        current_fg = { params[i+2], params[i+3], params[i+4], 255 }
        i = i + 4
      elseif code == 48 and params[i+1] == 2 and params[i+2] and params[i+3] and params[i+4] then
        current_bg = { params[i+2], params[i+3], params[i+4], 255 }
        i = i + 4
      end
      i = i + 1
    end
    pos = esc_end + 1
  end
  return segments
end

-- =============================================================================
-- 3. UTILITÁRIOS DE PROJETO E VENV
-- =============================================================================
local function get_active_project_dir()
  if core.project_directories and #core.project_directories > 0 then
    local p = core.project_directories[1]
    local path = type(p) == "table" and (p.path or p.name) or p
    return (system.absolute_path(path) or path):gsub("[/\\]+$", "")
  end
  return core.project_dir or "."
end

local function detect_project_venv(proj_dir)
  local sep = PATHSEP or "\\"
  local candidates = {
    proj_dir .. sep .. "venv",
    proj_dir .. sep .. ".venv",
  }
  for _, venv_dir in ipairs(candidates) do
    local scripts_dir = venv_dir .. sep .. (PLATFORM == "Windows" and "Scripts" or "bin")
    local info = system.get_file_info(scripts_dir)
    if info and info.type == "dir" then
      return scripts_dir, venv_dir
    end
  end
  return nil, nil
end

local DOXOADE_AUTOCOMPLETE_COMMANDS = {
  "doxoade", "doxoade doxly", "doxoade doxly deploy test", "doxoade doxly deploy sandbox",
  "doxoade doxly deploy production", "doxoade doxly log -m test", "doxoade doxly log -m sandbox",
  "doxoade diff", "doxoade venv", "doxoade venv --admin", "doxoade test", "doxoade check",
  "python", "pip list", "pip install", "pytest", "git status", "git diff", "git log",
  "cls", "admin", "help", "dir", "ls"
}

-- =============================================================================
-- 4. ESTADO DO PAINEL FLUTUANTE INDEPENDENTE
-- =============================================================================
local FloatingPanel = {
  visible = false,
  is_maximized = false,
  header_height = 30,
  active_mode = "terminal",
  hovered_tab = nil,
  hovered_btn = nil,
  hovered_close = false,
  is_executing = false,
  scroll_y = 0,
  scroll_to_y = 0,

  -- Terminal State & Zoom
  input_text = "",
  input_cursor = 1,
  history = {},
  history_idx = 0,
  terminal_lines = {},
  suggestions = {},
  suggestion_idx = 1,
  term_font_size = 14,
  term_font = nil,

  -- Seleção de Texto Isolada no Terminal
  is_selecting_text = false,
  sel_start_line = nil,
  sel_end_line = nil,

  -- Cache de Arquivos para Autocomplete Rápido (Zero Lag de Digitação)
  cached_project_files = {},
  last_file_cache_time = 0,

  -- Canvas Native SDL2 State
  canvas_rects = {},
  canvas_grid_w = 0,
  canvas_grid_h = 0,
  canvas_image_path = nil,
  canvas_meta_path = nil,
  canvas_meta = {},
  canvas_zoom = 1.0,
  canvas_pan_x = 0,
  canvas_pan_y = 0,
  canvas_mode_1to1 = false,
  is_panning = false,
  image_status_msg = "Nenhum print carregado. Pressione Ctrl+V para colar um PrintScreen.",

  tabs = {
    { id = "terminal", label = "Terminal (Venv)" },
    { id = "canvas",   label = "Imagem / Canvas" },
    { id = "output",   label = "Saida" },
  },

  action_buttons = {}
}

rawset(_G, "_DOXOADE_FLOATING_PANEL", FloatingPanel)

function FloatingPanel:get_terminal_font()
  if not self.term_font or self.term_font:get_size() ~= self.term_font_size then
    local base = style.code_font or style.font
    if base and base.copy then
      self.term_font = base:copy(self.term_font_size)
    else
      self.term_font = base
    end
  end
  return self.term_font or style.font
end

local function get_history_file_path()
  local proj = get_active_project_dir()
  local sep = PATHSEP or "\\"
  local dox_dir = proj .. sep .. ".doxoade"
  pcall(function() system.mkdir(dox_dir) end)
  return dox_dir .. sep .. "terminal_history.txt"
end

function FloatingPanel:load_project_history()
  self.history = {}
  local h_path = get_history_file_path()
  local f = io.open(h_path, "r")
  if f then
    for line in f:lines() do
      local clean = line:gsub("[\r\n]+", "")
      if clean ~= "" then table.insert(self.history, clean) end
    end
    f:close()
  end
  self.history_idx = #self.history + 1
end

function FloatingPanel:save_command_to_history(cmd_str)
  if not cmd_str or cmd_str == "" then return end
  if self.history[#self.history] == cmd_str then return end

  table.insert(self.history, cmd_str)
  self.history_idx = #self.history + 1

  local h_path = get_history_file_path()
  local f = io.open(h_path, "a")
  if f then
    f:write(cmd_str .. "\n")
    f:close()
  end
end

function FloatingPanel:init_welcome()
  local proj = get_active_project_dir()
  local _, venv_root = detect_project_venv(proj)
  local venv_status = venv_root and ("\x1b[32mATIVO (" .. venv_root .. ")\x1b[0m") or "\x1b[33mNAO ENCONTRADO (Execute: doxoade venv)\x1b[0m"

  local banner_lines = {
    "\x1b[90m================================================================================\x1b[0m",
    "  \x1b[38;2;0;108;255mDOXOADE\x1b[0m \x1b[38;2;38;188;95mCONSOLE STUDIO\x1b[0m \x1b[90m(V14.0 Pro)\x1b[0m",
    "  \x1b[36mProjeto\x1b[0m : \x1b[37m" .. proj .. "\x1b[0m",
    "  \x1b[36mVenv   \x1b[0m : " .. venv_status,
    "  \x1b[90mAtalhos: TAB (Completar) | Ctrl+MouseWheel (Zoom) | Arraste Mouse (Selecionar) | Esc\x1b[0m",
    "\x1b[90m================================================================================\x1b[0m",
    ""
  }

  self.terminal_lines = {}
  for _, line in ipairs(banner_lines) do
    table.insert(self.terminal_lines, { segments = parse_ansi_segments(line) })
  end
  self:load_project_history()
end

FloatingPanel:init_welcome()

-- =============================================================================
-- 5. CÓPIA INTEGRAL OU DE TEXTO SELECIONADO
-- =============================================================================
function FloatingPanel:copy_terminal_output()
  local buffer = {}
  local start_l = 1
  local end_l = #self.terminal_lines

  -- Se o usuário arrastou e selecionou linhas específicas
  if self.sel_start_line and self.sel_end_line then
    start_l = math.max(1, math.min(self.sel_start_line, self.sel_end_line))
    end_l = math.min(#self.terminal_lines, math.max(self.sel_start_line, self.sel_end_line))
  end

  for i = start_l, end_l do
    local line = self.terminal_lines[i]
    if line then
      local line_parts = {}
      for _, seg in ipairs(line.segments or {}) do
        table.insert(line_parts, seg.text or "")
      end
      table.insert(buffer, table.concat(line_parts))
    end
  end

  local full_text = table.concat(buffer, "\n")
  if system.set_clipboard then
    system.set_clipboard(full_text)
  end
  core.log(string.format("✔ %d linha(s) copiadas para o clipboard!", #buffer))
end

-- =============================================================================
-- 6. MOTOR DO CANVAS 1:1 NATIVO SDL2
-- =============================================================================
function FloatingPanel:paste_clipboard_image()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "\\"
  local cache_dir = user_dir .. sep .. ".doxoade" .. sep .. "canvas_cache"
  pcall(function() system.mkdir(cache_dir) end)

  local dest_png = cache_dir .. sep .. "pasted_image.png"
  local dest_meta = cache_dir .. sep .. "pasted_image.meta.json"
  local script_py = cache_dir .. sep .. "clip_bridge_sdl2.py"
  local log_out = cache_dir .. sep .. "clip_bridge_sdl2.log"
  local rle_out = cache_dir .. sep .. "preview_rle.dat"

  pcall(os.remove, dest_png)
  pcall(os.remove, dest_meta)
  pcall(os.remove, log_out)
  pcall(os.remove, rle_out)

  local py_code = [[
import sys, os, time, json, hashlib, datetime, platform, getpass
from pathlib import Path
from io import BytesIO

def get_clipboard_image():
    try:
        from PIL import ImageGrab, Image
        for _ in range(5):
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image): return img
            elif isinstance(img, list) and len(img) > 0:
                p = Path(img[0])
                if p.is_file(): return Image.open(p)
            time.sleep(0.08)
    except Exception: pass

    try:
        import ctypes
        from PIL import Image
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        for _ in range(5):
            if user32.OpenClipboard(None):
                CF_DIB = 8; CF_DIBV5 = 17
                h_data = user32.GetClipboardData(CF_DIB) or user32.GetClipboardData(CF_DIBV5)
                if h_data:
                    p_data = kernel32.GlobalLock(h_data)
                    size = kernel32.GlobalSize(h_data)
                    if p_data and size > 0:
                        import struct
                        raw_bytes = ctypes.string_at(p_data, size)
                        kernel32.GlobalUnlock(h_data)
                        user32.CloseClipboard()
                        header_size = struct.unpack("<I", raw_bytes[0:4])[0]
                        file_header = struct.pack("<2sIHHI", b"BM", 14 + size, 0, 0, 14 + header_size)
                        return Image.open(BytesIO(file_header + raw_bytes))
                user32.CloseClipboard()
            time.sleep(0.08)
    except Exception: pass
    return None

def generate_native_rle_rects(img):
    from PIL import Image
    img = img.convert("RGB")
    orig_w, orig_h = img.size
    target_w, target_h = orig_w, orig_h
    if target_w > 2560:
        scale = 2560 / target_w
        target_w = 2560
        target_h = int(target_h * scale)
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    pixels = img.load()
    rects = []
    for y in range(target_h):
        run_start_x = 0
        cur_color = pixels[0, y]
        run_len = 1
        for x in range(1, target_w):
            c = pixels[x, y]
            if c == cur_color:
                run_len += 1
            else:
                rects.append(f"{run_start_x},{y},{run_len},{cur_color[0]},{cur_color[1]},{cur_color[2]}")
                run_start_x = x; cur_color = c; run_len = 1
        rects.append(f"{run_start_x},{y},{run_len},{cur_color[0]},{cur_color[1]},{cur_color[2]}")
    return rects, target_w, target_h

def main():
    if len(sys.argv) < 4: sys.exit(1)
    dest_png, dest_meta, rle_file = sys.argv[1], sys.argv[2], sys.argv[3]
    proj_dir = sys.argv[4] if len(sys.argv) > 4 else "."

    img = get_clipboard_image()
    if not img:
        print("[ERRO] Clipboard nao continha imagem.")
        sys.exit(1)

    buf = BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    sha256 = hashlib.sha256(png_bytes).hexdigest()

    now = datetime.datetime.now()
    meta = {
        "timestamp_iso": now.isoformat(),
        "timestamp_human": now.strftime("%Y-%m-%d %H:%M:%S"),
        "project_dir": proj_dir,
        "platform": f"{platform.system()} {platform.release()}",
        "user": getpass.getuser(),
        "width": img.size[0],
        "height": img.size[1],
        "resolution": f"{img.size[0]}x{img.size[1]}",
        "sha256": sha256,
        "size_bytes": len(png_bytes),
        "size_kb": round(len(png_bytes) / 1024, 2),
    }

    from PIL.PngImagePlugin import PngInfo
    png_info = PngInfo()
    for k, v in meta.items(): png_info.add_text(f"doxoade_{k}", str(v))
    img.save(dest_png, format="PNG", pnginfo=png_info)

    with open(dest_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    rects, gw, gh = generate_native_rle_rects(img)
    with open(rle_file, "w", encoding="utf-8") as f:
        f.write(f"{gw},{gh}\n")
        f.write("\n".join(rects))

    print(f"[OK] {img.size[0]}|{img.size[1]}|{meta['size_bytes']}|{sha256[:8]}|{len(rects)}")
    sys.exit(0)

if __name__ == "__main__": main()
]]

  local f_py = io.open(script_py, "w")
  if f_py then f_py:write(py_code); f_py:close() end

  self.image_status_msg = "Capturando printscreen nativo 1:1..."
  core.redraw = true

  local proj = get_active_project_dir()
  local venv_scripts, venv_dir = detect_project_venv(proj)
  local py_exe = (venv_scripts and (venv_scripts .. "\\python.exe")) or "python"

  core.add_thread(function()
    local cmd
    if PLATFORM == "Windows" then
      cmd = string.format('cmd.exe /c ""%s" "%s" "%s" "%s" "%s" "%s" > "%s" 2>&1"',
        py_exe, script_py, dest_png, dest_meta, rle_out, proj, log_out)
    else
      cmd = string.format('python3 "%s" "%s" "%s" "%s" "%s" > "%s" 2>&1',
        script_py, dest_png, dest_meta, rle_out, proj, log_out)
    end

    pcall(system.exec, cmd)

    for _ = 1, 50 do
      coroutine.yield(0.05)
      local finfo = system.get_file_info(rle_out)
      if finfo and (finfo.size or 0) > 0 then break end
    end

    local f_log = io.open(log_out, "r")
    local log_content = f_log and f_log:read("*a") or ""
    if f_log then f_log:close() end

    local w, h, size_bytes, hash_prefix, rect_count = log_content:match("%[OK%] (%d+)|(%d+)|(%d+)|([%w_]+)|(%d+)")

    if w and h then
      local f_rle = io.open(rle_out, "r")
      if f_rle then
        local header = f_rle:read("*l") or "1366,768"
        local gw, gh = header:match("^(%d+),(%d+)$")
        FloatingPanel.canvas_grid_w = tonumber(gw) or 1366
        FloatingPanel.canvas_grid_h = tonumber(gh) or 768

        FloatingPanel.canvas_rects = {}
        for line in f_rle:lines() do
          local rx, ry, rw, r, g, b = line:match("^(%d+),(%d+),(%d+),(%d+),(%d+),(%d+)$")
          if rx then
            table.insert(FloatingPanel.canvas_rects, {
              x = tonumber(rx), y = tonumber(ry), w = tonumber(rw),
              color = { tonumber(r), tonumber(g), tonumber(b), 255 }
            })
          end
        end
        f_rle:close()

        FloatingPanel.canvas_image_path = dest_png
        FloatingPanel.canvas_meta_path = dest_meta
        FloatingPanel.canvas_zoom = 1.0
        FloatingPanel.canvas_pan_x = 0
        FloatingPanel.canvas_pan_y = 0
        FloatingPanel.canvas_mode_1to1 = false

        FloatingPanel.image_status_msg = string.format("Nativo 1:1 SDL2: %dx%d px (%.1f KB) | SHA256: %s... | %s blocos",
          tonumber(w), tonumber(h), tonumber(size_bytes) / 1024, hash_prefix, rect_count)
        core.log(string.format("✔ Imagem 1:1 Renderizada no SDL2 (%dx%d px | %s blocos)!", tonumber(w), tonumber(h), rect_count))
      end
    else
      FloatingPanel.image_status_msg = "Falha: Clipboard nao continha imagem."
      core.log("⚠ Nenhuma imagem encontrada no clipboard.")
    end
    core.redraw = true
  end)
end

function FloatingPanel:save_canvas_image_to_project()
  if not self.canvas_image_path or #self.canvas_rects == 0 then
    core.log("⚠ Nenhum print carregado no Canvas para salvar.")
    return
  end

  local proj = get_active_project_dir()
  local timestamp = os.date("%Y%m%d_%H%M%S")
  local default_name = "assets/screenshot_" .. timestamp .. ".png"

  core.command_view:enter("Salvar imagem no projeto como (ex: assets/print.png)", {
    text = default_name,
    submit = function(target_rel_path)
      if not target_rel_path or target_rel_path:match("^%s*$") then return end
      local sep = PATHSEP or "\\"
      local full_target_png = proj .. sep .. target_rel_path:gsub("[/\\]", sep)
      local full_target_meta = full_target_png:gsub("%.png$", "") .. ".meta.json"

      local dir = full_target_png:match("^(.*)[/\\]")
      if dir and system.mkdir then pcall(system.mkdir, dir) end

      local f_in = io.open(FloatingPanel.canvas_image_path, "rb")
      if f_in then
        local data = f_in:read("*a")
        f_in:close()
        local f_out = io.open(full_target_png, "wb")
        if f_out then
          f_out:write(data)
          f_out:close()

          if FloatingPanel.canvas_meta_path and system.get_file_info(FloatingPanel.canvas_meta_path) then
            local f_m_in = io.open(FloatingPanel.canvas_meta_path, "r")
            if f_m_in then
              local m_data = f_m_in:read("*a")
              f_m_in:close()
              local f_m_out = io.open(full_target_meta, "w")
              if f_m_out then f_m_out:write(m_data); f_m_out:close() end
            end
          end

          FloatingPanel.image_status_msg = "Salvo: " .. target_rel_path .. " (+ meta.json)"
          core.log(string.format("✔ Imagem 1:1 e Metadados Forenses salvos em: %s", target_rel_path))
          core.redraw = true
          return
        end
      end
      core.error("Falha ao gravar arquivo em: " .. full_target_png)
    end
  })
end

function FloatingPanel:open_image_external()
  if self.canvas_image_path and system.get_file_info(self.canvas_image_path) then
    if PLATFORM == "Windows" then
      system.exec(string.format('explorer.exe "%s"', self.canvas_image_path:gsub("/", "\\")))
    else
      system.exec(string.format('xdg-open "%s"', self.canvas_image_path))
    end
    core.log("🖼️ Imagem aberta no visualizador do sistema.")
  end
end

-- =============================================================================
-- 7. AUTOCOMPLETE RÁPIDO COM CACHE EM MEMÓRIA (ZERO LAG DE DIGITAÇÃO)
-- =============================================================================
function FloatingPanel:update_suggestions()
  self.suggestions = {}
  self.suggestion_idx = 1
  local current = self.input_text:sub(1, self.input_cursor - 1)
  if current == "" or current:match("^%s+$") then return end

  for _, candidate in ipairs(DOXOADE_AUTOCOMPLETE_COMMANDS) do
    if candidate:sub(1, #current):lower() == current:lower() and #candidate > #current then
      table.insert(self.suggestions, candidate)
    end
  end

  local last_token = current:match("([^%s]+)$") or ""
  if #last_token > 0 then
    local now = os.clock()
    -- Revalida o cache de arquivos apenas a cada 3 segundos
    if now - self.last_file_cache_time > 3.0 then
      local proj = get_active_project_dir()
      self.cached_project_files = system.list_dir(proj) or {}
      self.last_file_cache_time = now
    end

    for _, fn in ipairs(self.cached_project_files) do
      if fn:sub(1, #last_token):lower() == last_token:lower() and #fn > #last_token then
        local before = current:sub(1, #current - #last_token)
        table.insert(self.suggestions, before .. fn)
      end
    end
  end
end

function FloatingPanel:handle_tab_completion()
  if #self.suggestions == 0 then self:update_suggestions() end
  if #self.suggestions > 0 then
    local chosen = self.suggestions[self.suggestion_idx]
    if chosen then
      self.input_text = chosen .. " "
      self.input_cursor = #self.input_text + 1
      self.suggestion_idx = (self.suggestion_idx % #self.suggestions) + 1
      self:update_suggestions()
      core.redraw = true
    end
  end
end

function FloatingPanel:execute_command(raw_cmd)
  if not raw_cmd or raw_cmd:match("^%s*$") then return end
  local cmd_str = raw_cmd:gsub("^%s*", ""):gsub("%s*$", "")

  self:save_command_to_history(cmd_str)
  self.suggestions = {}
  self.sel_start_line = nil
  self.sel_end_line = nil

  local proj = get_active_project_dir()

  if cmd_str == "cls" or cmd_str == "clear" then
    self.terminal_lines = {}; self.input_text = ""; self.input_cursor = 1; core.redraw = true; return
  elseif cmd_str == "admin" then
    command.perform("doxoade:terminal-launch-admin-venv"); self.input_text = ""; self.input_cursor = 1; core.redraw = true; return
  elseif cmd_str == "help" then
    local help_msg = {
      "\x1b[32m(venv) > help\x1b[0m",
      "  \x1b[36mcls / clear \x1b[0m : Limpa a tela do terminal",
      "  \x1b[36madmin       \x1b[0m : Abre terminal com permissoes de Administrador",
      "  \x1b[36mAlt + Enter \x1b[0m : Alterna entre Centralizado e Tela Cheia",
      "  \x1b[36mCtrl+Shift+C\x1b[0m : Copia a saida ou selecao do terminal",
    }
    for _, l in ipairs(help_msg) do
      table.insert(self.terminal_lines, { segments = parse_ansi_segments(l) })
    end
    self.input_text = ""; self.input_cursor = 1; core.redraw = true; return
  end

  local prompt_line = "\x1b[38;2;38;188;95m(venv)\x1b[0m \x1b[36m" .. proj .. "\x1b[0m\x1b[90m>\x1b[0m \x1b[37m" .. cmd_str .. "\x1b[0m"
  table.insert(self.terminal_lines, { segments = parse_ansi_segments(prompt_line) })

  self.input_text = ""; self.input_cursor = 1; self.is_executing = true; core.redraw = true

  local venv_scripts, venv_dir = detect_project_venv(proj)
  local safe_venv_root = venv_dir or ""
  local safe_scripts = venv_scripts or ""

  core.add_thread(function()
    local user_dir = USERDIR or "."
    local sep = PATHSEP or "\\"
    local out_tmp = user_dir .. sep .. ".doxoade" .. sep .. "terminal_stream.tmp"
    local run_cmd
    pcall(os.remove, out_tmp)

    if PLATFORM == "Windows" then
      if safe_scripts ~= "" then
        run_cmd = string.format('cmd.exe /c "set "PATH=%s;%%PATH%%" & set "VIRTUAL_ENV=%s" & set "CLICOLOR_FORCE=1" & set "FORCE_COLOR=1" & set "PYTHONUNBUFFERED=1" & set "TERM=xterm-256color" & cd /d "%s" & %s > "%s" 2>&1 & echo:__DOXOADE_EOF__ >> "%s""',
          safe_scripts, safe_venv_root, proj, cmd_str, out_tmp, out_tmp)
      else
        run_cmd = string.format('cmd.exe /c "set "CLICOLOR_FORCE=1" & set "FORCE_COLOR=1" & set "PYTHONUNBUFFERED=1" & set "TERM=xterm-256color" & cd /d "%s" & %s > "%s" 2>&1 & echo:__DOXOADE_EOF__ >> "%s""',
          proj, cmd_str, out_tmp, out_tmp)
      end
    else
      if safe_scripts ~= "" then
        run_cmd = string.format('sh -c "export PATH=\'%s:$PATH\'; export VIRTUAL_ENV=\'%s\'; export CLICOLOR_FORCE=1; export FORCE_COLOR=1; export PYTHONUNBUFFERED=1; export TERM=xterm-256color; cd \'%s\'; %s > \'%s\' 2>&1; echo \'__DOXOADE_EOF__\' >> \'%s\'"',
          safe_scripts, safe_venv_root, proj, cmd_str, out_tmp, out_tmp)
      else
        run_cmd = string.format('sh -c "export CLICOLOR_FORCE=1; export FORCE_COLOR=1; export PYTHONUNBUFFERED=1; export TERM=xterm-256color; cd \'%s\'; %s > \'%s\' 2>&1; echo \'__DOXOADE_EOF__\' >> \'%s\'"',
          proj, cmd_str, out_tmp, out_tmp)
      end
    end

    pcall(system.exec, run_cmd)

    local last_pos = 0
    local is_done = false
    local attempts = 0

    while not is_done and attempts < 400 do
      coroutine.yield(0.02)
      attempts = attempts + 1

      local f = io.open(out_tmp, "r")
      if f then
        f:seek("set", last_pos)
        for line in f:lines() do
          if line:find("__DOXOADE_EOF__") then
            is_done = true
            break
          else
            table.insert(FloatingPanel.terminal_lines, { segments = parse_ansi_segments(line) })
          end
        end
        last_pos = f:seek()
        f:close()

        local font = FloatingPanel:get_terminal_font()
        local line_h = font:get_height() + 2
        FloatingPanel.scroll_to_y = math.max(0, (#FloatingPanel.terminal_lines * line_h) - 300)
        core.redraw = true
      end
    end

    pcall(os.remove, out_tmp)
    FloatingPanel.is_executing = false
    core.redraw = true
  end)
end

-- =============================================================================
-- 8. RENDERIZAÇÃO: PURE BLACK CONSOLE RGB(0,0,0) COM SELEÇÃO & ZOOM
-- =============================================================================
function FloatingPanel:draw()
  if not self.visible then return end

  local font = self:get_terminal_font()
  local screen_w = core.root_view.size.x
  local screen_h = core.root_view.size.y

  draw_rect_safe(0, 0, screen_w, screen_h, { 0, 0, 0, 180 })

  local x, y, w, h
  if self.is_maximized then
    x, y, w, h = 8, 8, screen_w - 16, screen_h - 16
  else
    w = math.min(screen_w - 24, math.max(850, math.floor(screen_w * 0.88)))
    h = math.min(screen_h - 24, math.max(540, math.floor(screen_h * 0.84)))
    x = math.floor((screen_w - w) / 2)
    y = math.floor((screen_h - h) / 2)
  end

  self.card_rect = { x = x, y = y, w = w, h = h }

  draw_rect_safe(x - 6, y - 6, w + 12, h + 12, { 0, 0, 0, 120 })
  draw_rect_safe(x, y, w, h, { 0, 0, 0, 255 })
  draw_rect_safe(x, y, w, 2, style.accent or { 38, 188, 95, 255 })

  draw_rect_safe(x, y + 2, w, self.header_height, { 16, 16, 16, 255 })
  draw_rect_safe(x, y + self.header_height + 1, w, 1, { 35, 35, 35, 255 })

  -- Abas do Header
  local tab_x = x + 12
  for i, tab in ipairs(self.tabs) do
    local is_active = (self.active_mode == tab.id)
    local is_hovered = (self.hovered_tab == i)
    local tab_w = font:get_width(tab.label) + 18
    local tab_h = self.header_height - 6

    if is_active then
      draw_rect_safe(tab_x, y + 4, tab_w, tab_h, { 0, 0, 0, 255 })
      draw_rect_safe(tab_x, y + 4, tab_w, 2, style.accent or { 38, 188, 95, 255 })
    elseif is_hovered then
      draw_rect_safe(tab_x, y + 4, tab_w, tab_h, { 30, 30, 30, 255 })
    end

    local text_color = is_active and (style.accent or { 38, 188, 95, 255 }) or { 150, 150, 150, 255 }
    draw_text_safe(font, tab.label, tab_x + 9, y + 7, text_color)
    tab.rect = { x = tab_x, y = y + 4, w = tab_w, h = tab_h }
    tab_x = tab_x + tab_w + 6
  end

  -- Botões de Ação
  local dynamic_buttons = {}
  if self.active_mode == "terminal" then
    dynamic_buttons = {
      { id = "admin",    label = "[> Admin Venv]", action = function() command.perform("doxoade:terminal-launch-admin-venv") end },
      { id = "copy",     label = "[Copiar]",       action = function() FloatingPanel:copy_terminal_output() end },
      { id = "maximize", label = self.is_maximized and "[Restaurar]" or "[Tela Cheia]", action = function() command.perform("doxoade:bottom-shelf-toggle-maximize") end },
      { id = "clear",    label = "[Limpar]",       action = function() FloatingPanel.terminal_lines = {}; core.redraw = true end },
    }
  elseif self.active_mode == "canvas" then
    dynamic_buttons = {
      { id = "paste_img", label = "[Colar Print (Ctrl+V)]", action = function() FloatingPanel:paste_clipboard_image() end },
      { id = "mode_1to1", label = self.canvas_mode_1to1 and "[Ajustar ao Quadro]" or "[1:1 Real]", action = function()
          FloatingPanel.canvas_mode_1to1 = not FloatingPanel.canvas_mode_1to1
          FloatingPanel.canvas_zoom = 1.0
          FloatingPanel.canvas_pan_x = 0
          FloatingPanel.canvas_pan_y = 0
          core.redraw = true
        end
      },
      { id = "save_img",  label = "[Salvar no Projeto]",    action = function() FloatingPanel:save_canvas_image_to_project() end },
      { id = "open_ext",  label = "[Abrir Externo]",        action = function() FloatingPanel:open_image_external() end },
      { id = "clear_img", label = "[Limpar]",               action = function() FloatingPanel.canvas_rects = {}; FloatingPanel.image_status_msg = "Canvas limpo."; core.redraw = true end },
    }
  else
    dynamic_buttons = {
      { id = "clear", label = "[Limpar]", action = function() core.redraw = true end }
    }
  end

  self.action_buttons = dynamic_buttons

  local btn_x = tab_x + 16
  for i, btn in ipairs(self.action_buttons) do
    local bw = font:get_width(btn.label) + 12
    local bh = self.header_height - 8
    local is_hovered = (self.hovered_btn == i)

    if btn_x + bw < x + w - 30 then
      if is_hovered then
        draw_rect_safe(btn_x, y + 5, bw, bh, { 35, 35, 35, 255 })
      end
      draw_text_safe(font, btn.label, btn_x + 6, y + 7, is_hovered and (style.accent or { 38, 188, 95, 255 }) or { 56, 189, 248, 255 })
      btn.rect = { x = btn_x, y = y + 5, w = bw, h = bh }
      btn_x = btn_x + bw + 6
    end
  end

  -- Botão Fechar [X]
  local close_w = 22
  local close_x = x + w - close_w - 10
  local close_y = y + 4
  if self.hovered_close then
    draw_rect_safe(close_x, close_y, close_w, self.header_height - 6, { 200, 50, 50, 200 })
  end
  draw_text_safe(font, "[X]", close_x + 2, close_y + 3, self.hovered_close and { 255, 255, 255, 255 } or { 150, 150, 150, 255 })
  self.close_rect = { x = close_x, y = close_y, w = close_w, h = self.header_height - 6 }

  -- 5. Área de Conteúdo
  local is_term = (self.active_mode == "terminal")
  local sug_h = (is_term and #self.suggestions > 0) and 24 or 0
  local bottom_bar_h = is_term and 30 or 26
  local canvas_y = y + self.header_height + 2
  local canvas_h = h - self.header_height - bottom_bar_h - sug_h

  core.push_clip_rect(x + 2, canvas_y, w - 4, canvas_h)

  -- Renderizador SDL2
  if self.active_mode == "canvas" then
    FloatingPanel.canvas_viewport_rect = { x = x + 2, y = canvas_y, w = w - 4, h = canvas_h }

    if #self.canvas_rects > 0 then
      local gw = self.canvas_grid_w or 1366
      local gh = self.canvas_grid_h or 768

      local pixel_size
      if self.canvas_mode_1to1 then
        pixel_size = 1.0 * self.canvas_zoom
      else
        local base_pixel_scale = math.min((w - 40) / gw, (canvas_h - 40) / gh)
        pixel_size = base_pixel_scale * self.canvas_zoom
      end

      local total_drawn_w = math.floor(gw * pixel_size)
      local total_drawn_h = math.floor(gh * pixel_size)
      local start_draw_x = x + math.floor((w - total_drawn_w) / 2) + self.canvas_pan_x
      local start_draw_y = canvas_y + math.floor((canvas_h - total_drawn_h) / 2) + self.canvas_pan_y

      draw_rect_safe(start_draw_x - 2, start_draw_y - 2, total_drawn_w + 4, total_drawn_h + 4, { 5, 5, 5, 255 })

      for _, r in ipairs(self.canvas_rects) do
        local rx = start_draw_x + math.floor(r.x * pixel_size)
        local ry = start_draw_y + math.floor(r.y * pixel_size)
        local rw = math.max(1, math.ceil(r.w * pixel_size))
        local rh = math.max(1, math.ceil(pixel_size))

        if rx + rw >= x and rx <= x + w and ry + rh >= canvas_y and ry <= canvas_y + canvas_h then
          draw_rect_safe(rx, ry, rw, rh, r.color)
        end
      end
    else
      local empty_box_w = math.min(560, w - 80)
      local empty_box_h = 160
      local e_x = x + math.floor((w - empty_box_w) / 2)
      local e_y = canvas_y + math.floor((canvas_h - empty_box_h) / 2)

      draw_rect_safe(e_x, e_y, empty_box_w, empty_box_h, { 14, 14, 14, 255 })
      draw_rect_safe(e_x, e_y, empty_box_w, 2, style.accent or { 38, 188, 95, 255 })

      draw_text_safe(font, "CANVAS FORENSE SDL2 (1:1 Native Resolution)", e_x + 20, e_y + 24, style.accent)
      draw_text_safe(font, "• Tire um print com Win+Shift+S ou PrintScreen.", e_x + 20, e_y + 54, { 230, 230, 230, 255 })
      draw_text_safe(font, "• Pressione Ctrl+V para renderizar os pixels reais do print.", e_x + 20, e_y + 78, { 56, 189, 248, 255 })
      draw_text_safe(font, "• Clique em [1:1 Real] para ver os pixels originais da tela.", e_x + 20, e_y + 102, { 150, 150, 150, 255 })
    end

  elseif self.active_mode == "terminal" then
    local line_h = font:get_height() + 2
    local cur_y = canvas_y + 6 - self.scroll_y
    local max_line_w = w - 28

    -- Determina intervalo de seleção para realce visual
    local min_sel = self.sel_start_line and self.sel_end_line and math.min(self.sel_start_line, self.sel_end_line)
    local max_sel = self.sel_start_line and self.sel_end_line and math.max(self.sel_start_line, self.sel_end_line)

    for line_idx, item in ipairs(self.terminal_lines) do
      if cur_y + line_h > canvas_y and cur_y < canvas_y + canvas_h then
        -- 🎨 Realce de Linha Selecionada
        if min_sel and max_sel and line_idx >= min_sel and line_idx <= max_sel then
          draw_rect_safe(x + 8, cur_y - 1, w - 16, line_h, { 56, 189, 248, 45 })
        end

        local seg_x = x + 14
        for _, seg in ipairs(item.segments or {}) do
          if seg.bg then
            local seg_w = font:get_width(seg.text)
            draw_rect_safe(seg_x, cur_y, seg_w, line_h, seg.bg)
          end
          draw_text_safe(font, seg.text, seg_x, cur_y, seg.fg)
          seg_x = seg_x + font:get_width(seg.text)
        end
      end
      cur_y = cur_y + line_h
    end
  else
    draw_text_safe(font, "Buffer de saida pronto.", x + 14, canvas_y + 16, { 230, 230, 230, 255 })
  end

  core.pop_clip_rect()

  -- 6. Rodapé do Canvas ou Prompt do Terminal
  if self.active_mode == "canvas" then
    local info_y = y + h - 26
    draw_rect_safe(x + 1, info_y, w - 2, 25, { 12, 12, 12, 255 })
    draw_rect_safe(x + 1, info_y, w - 2, 1, { 35, 35, 35, 255 })
    local mode_str = self.canvas_mode_1to1 and "1:1 Real" or "Ajustado"
    local zoom_label = string.format("[%s | Zoom: %d%%] ", mode_str, math.floor(self.canvas_zoom * 100))
    draw_text_safe(font, zoom_label, x + 14, info_y + 5, style.accent)
    draw_text_safe(font, self.image_status_msg, x + 14 + font:get_width(zoom_label), info_y + 5, { 150, 150, 150, 255 })

  elseif self.active_mode == "terminal" then
    if #self.suggestions > 0 then
      local sug_y = y + h - 56
      draw_rect_safe(x + 1, sug_y, w - 2, 24, { 16, 16, 16, 255 })
      draw_rect_safe(x + 1, sug_y, w - 2, 1, { 35, 35, 35, 255 })

      local sx = x + 14
      for idx, sug in ipairs(self.suggestions) do
        if sx > x + w - 80 then break end
        local is_cur = (idx == self.suggestion_idx)
        local chip_text = is_cur and ("[Tab: " .. sug .. "]") or (" " .. sug .. " ")
        local chip_w = font:get_width(chip_text) + 8

        if is_cur then
          draw_rect_safe(sx, sug_y + 2, chip_w, 20, { 35, 35, 35, 255 })
          draw_rect_safe(sx, sug_y + 2, chip_w, 1, style.accent or { 38, 188, 95, 255 })
        end
        draw_text_safe(font, chip_text, sx + 4, sug_y + 4, is_cur and (style.accent or { 38, 188, 95, 255 }) or { 150, 150, 150, 255 })
        sx = sx + chip_w + 6
      end
    end

    local input_y = y + h - 30
    draw_rect_safe(x + 1, input_y, w - 2, 29, { 10, 10, 10, 255 })
    draw_rect_safe(x + 1, input_y, w - 2, 1, style.accent or { 38, 188, 95, 255 })

    local tag_venv = self.is_executing and "[RODANDO]" or "[VENV]"
    local tag_col = self.is_executing and { 251, 191, 36, 255 } or { 34, 197, 94, 255 }
    local tag_w = font:get_width(tag_venv .. " ")
    draw_text_safe(font, tag_venv .. " ", x + 14, input_y + 6, tag_col)

    local prompt_symbol = "$ "
    local prompt_w = font:get_width(prompt_symbol)
    draw_text_safe(font, prompt_symbol, x + 14 + tag_w, input_y + 6, style.accent or { 38, 188, 95, 255 })

    local text_x = x + 14 + tag_w + prompt_w
    draw_text_safe(font, self.input_text, text_x, input_y + 6, { 245, 245, 245, 255 })

    if #self.suggestions > 0 and self.input_cursor > #self.input_text then
      local top_sug = self.suggestions[self.suggestion_idx]
      if top_sug and #top_sug > #self.input_text then
        local ghost_tail = top_sug:sub(#self.input_text + 1)
        draw_text_safe(font, ghost_tail, text_x + font:get_width(self.input_text), input_y + 6, { 100, 100, 100, 180 })
      end
    end

    local cursor_x = text_x + font:get_width(self.input_text:sub(1, self.input_cursor - 1))
    if (os.clock() % 1.0) < 0.5 then
      draw_rect_safe(cursor_x, input_y + 6, 8, font:get_height(), style.accent or { 38, 188, 95, 255 })
    end
  end
end

-- =============================================================================
-- 9. EVENTOS DE MOUSE, SELEÇÃO DE TEXTO ISOLADA & ZOOM (Ctrl+Wheel)
-- =============================================================================
local original_rootview_draw = RootView.draw
function RootView:draw(...)
  original_rootview_draw(self, ...)
  if FloatingPanel.visible then FloatingPanel:draw() end
end

local original_rootview_on_mouse_moved = RootView.on_mouse_moved
function RootView:on_mouse_moved(x, y, dx, dy)
  if FloatingPanel.visible then
    local r = FloatingPanel.card_rect
    FloatingPanel.hovered_tab = nil
    FloatingPanel.hovered_btn = nil
    FloatingPanel.hovered_close = false

    -- Arraste de Seleção de Texto dentro do Terminal
    if FloatingPanel.is_selecting_text and FloatingPanel.active_mode == "terminal" then
      local font = FloatingPanel:get_terminal_font()
      local line_h = font:get_height() + 2
      local canvas_y = r.y + FloatingPanel.header_height + 2
      local rel_y = y - canvas_y + FloatingPanel.scroll_y
      local line_no = math.floor(rel_y / line_h) + 1
      FloatingPanel.sel_end_line = math.max(1, math.min(#FloatingPanel.terminal_lines, line_no))
      core.redraw = true
      return
    end

    if FloatingPanel.is_panning and FloatingPanel.active_mode == "canvas" then
      FloatingPanel.canvas_pan_x = FloatingPanel.canvas_pan_x + dx
      FloatingPanel.canvas_pan_y = FloatingPanel.canvas_pan_y + dy
      core.redraw = true
      return
    end

    if r and x >= r.x and x <= r.x + r.w and y >= r.y and y <= r.y + r.h then
      for i, tab in ipairs(FloatingPanel.tabs or {}) do
        if tab.rect and x >= tab.rect.x and x <= tab.rect.x + tab.rect.w and
           y >= tab.rect.y and y <= tab.rect.y + tab.rect.h then
          FloatingPanel.hovered_tab = i; core.redraw = true; return
        end
      end

      for i, btn in ipairs(FloatingPanel.action_buttons or {}) do
        if btn.rect and x >= btn.rect.x and x <= btn.rect.x + btn.rect.w and
           y >= btn.rect.y and y <= btn.rect.y + btn.rect.h then
          FloatingPanel.hovered_btn = i; core.redraw = true; return
        end
      end

      if FloatingPanel.close_rect and x >= FloatingPanel.close_rect.x and x <= FloatingPanel.close_rect.x + FloatingPanel.close_rect.w and
         y >= FloatingPanel.close_rect.y and y <= FloatingPanel.close_rect.y + FloatingPanel.close_rect.h then
        FloatingPanel.hovered_close = true
        core.redraw = true
        return
      end
    end
    core.redraw = true
    return
  end
  return original_rootview_on_mouse_moved(self, x, y, dx, dy)
end

local original_rootview_on_mouse_pressed = RootView.on_mouse_pressed
function RootView:on_mouse_pressed(button, x, y, clicks)
  if FloatingPanel.visible then
    local r = FloatingPanel.card_rect
    if r and (x < r.x or x > r.x + r.w or y < r.y or y > r.y + r.h) then
      FloatingPanel.visible = false; core.redraw = true; return true
    end

    if FloatingPanel.hovered_tab then
      local tab = FloatingPanel.tabs[FloatingPanel.hovered_tab]
      if tab then FloatingPanel.active_mode = tab.id; core.redraw = true; return true end
    end

    if FloatingPanel.hovered_btn then
      local btn = FloatingPanel.action_buttons[FloatingPanel.hovered_btn]
      if btn and btn.action then btn.action(); return true end
    end

    if FloatingPanel.hovered_close then
      FloatingPanel.visible = false
      core.redraw = true
      return true
    end

    -- Inicia Seleção de Linhas de Texto no Terminal
    if FloatingPanel.active_mode == "terminal" and (button == "left" or button == 1) then
      local font = FloatingPanel:get_terminal_font()
      local line_h = font:get_height() + 2
      local canvas_y = r.y + FloatingPanel.header_height + 2
      local rel_y = y - canvas_y + FloatingPanel.scroll_y
      local line_no = math.floor(rel_y / line_h) + 1

      if y < r.y + r.h - 30 then
        FloatingPanel.is_selecting_text = true
        FloatingPanel.sel_start_line = math.max(1, math.min(#FloatingPanel.terminal_lines, line_no))
        FloatingPanel.sel_end_line = FloatingPanel.sel_start_line
        core.redraw = true
        return true
      end
    end

    if FloatingPanel.active_mode == "canvas" and (button == "left" or button == 1) then
      local vr = FloatingPanel.canvas_viewport_rect
      if vr and x >= vr.x and x <= vr.x + vr.w and y >= vr.y and y <= vr.y + vr.h then
        FloatingPanel.is_panning = true
        return true
      end
    end

    core.redraw = true
    return true
  end
  return original_rootview_on_mouse_pressed(self, button, x, y, clicks)
end

local original_rootview_on_mouse_released = RootView.on_mouse_released
function RootView:on_mouse_released(button, x, y)
  if FloatingPanel.visible then
    if FloatingPanel.is_selecting_text then
      FloatingPanel.is_selecting_text = false
      core.redraw = true
      return true
    end
    if FloatingPanel.is_panning then
      FloatingPanel.is_panning = false
      core.redraw = true
      return true
    end
  end
  if original_rootview_on_mouse_released then
    return original_rootview_on_mouse_released(self, button, x, y)
  end
end

local original_rootview_on_mouse_wheel = RootView.on_mouse_wheel
function RootView:on_mouse_wheel(delta)
  if FloatingPanel.visible then
    local is_ctrl = (keymap.modkeys and (keymap.modkeys["ctrl"] or keymap.modkeys["cmd"])) or false

    -- 🔍 Zoom no Terminal com Ctrl + Roda do Mouse (Uso seguro de keymap.modkeys)
    if FloatingPanel.active_mode == "terminal" and is_ctrl then
      if delta > 0 then
        FloatingPanel.term_font_size = math.min(26, FloatingPanel.term_font_size + 1)
      else
        FloatingPanel.term_font_size = math.max(8, FloatingPanel.term_font_size - 1)
      end
      FloatingPanel.term_font = nil
      core.redraw = true
      return true
    end

    if FloatingPanel.active_mode == "canvas" then
      if delta > 0 then
        FloatingPanel.canvas_zoom = math.min(6.0, FloatingPanel.canvas_zoom * 1.2)
      else
        FloatingPanel.canvas_zoom = math.max(0.1, FloatingPanel.canvas_zoom * 0.8)
      end
      core.redraw = true
      return true
    elseif FloatingPanel.active_mode == "terminal" then
      FloatingPanel.scroll_y = math.max(0, FloatingPanel.scroll_y - (delta * 30))
      core.redraw = true
      return true
    end
    return true
  end
  return original_rootview_on_mouse_wheel(self, delta)
end

local original_rootview_on_text_input = RootView.on_text_input
function RootView:on_text_input(text)
  if FloatingPanel.visible and FloatingPanel.active_mode == "terminal" and text then
    FloatingPanel.input_text = FloatingPanel.input_text:sub(1, FloatingPanel.input_cursor - 1) .. text .. FloatingPanel.input_text:sub(FloatingPanel.input_cursor)
    FloatingPanel.input_cursor = FloatingPanel.input_cursor + #text
    FloatingPanel:update_suggestions()
    core.redraw = true
    return true
  end
  return original_rootview_on_text_input(self, text)
end

-- =============================================================================
-- 10. COMANDOS E KEYMAPS
-- =============================================================================
local function is_floating_panel_active()
  return FloatingPanel.visible
end

local function is_floating_terminal_active()
  return FloatingPanel.visible and FloatingPanel.active_mode == "terminal"
end

command.add(nil, {
  ["doxoade:toggle-bottom-shelf"] = function()
    FloatingPanel.visible = not FloatingPanel.visible
    core.redraw = true
    core.log(FloatingPanel.visible and "🖥️ Terminal Console aberto." or "🖥️ Terminal Console recolhido.")
  end,

  ["doxoade:bottom-shelf-toggle-maximize"] = function()
    if FloatingPanel.visible then
      FloatingPanel.is_maximized = not FloatingPanel.is_maximized
      core.redraw = true
      core.log(FloatingPanel.is_maximized and "🖥️ Console em Tela Cheia." or "🖥️ Console Centralizado.")
    end
  end,

  ["doxoade:terminal-launch-admin-venv"] = function()
    local proj = get_active_project_dir()
    core.log("⚡ Elevando privilegios de Administrador no projeto: " .. proj)
    if PLATFORM == "Windows" then
      system.exec(string.format('doxoade venv --admin --title "DOXOADE_ADMIN_%s"', proj:match("([^/\\]+)$") or "PROJ"))
    else
      system.exec("doxoade venv")
    end
  end
})

command.add(is_floating_panel_active, {
  ["bottom-shelf:paste-action"] = function()
    if FloatingPanel.active_mode == "canvas" then
      FloatingPanel:paste_clipboard_image()
    elseif FloatingPanel.active_mode == "terminal" then
      local clip = (system.get_clipboard and system.get_clipboard()) or ""
      if clip and clip ~= "" then
        clip = clip:gsub("[\r\n]+", " ")
        FloatingPanel.input_text = FloatingPanel.input_text:sub(1, FloatingPanel.input_cursor - 1) .. clip .. FloatingPanel.input_text:sub(FloatingPanel.input_cursor)
        FloatingPanel.input_cursor = FloatingPanel.input_cursor + #clip
        FloatingPanel:update_suggestions()
        core.redraw = true
      end
    end
  end,

  ["bottom-shelf:close"] = function()
    FloatingPanel.visible = false
    core.redraw = true
  end,
})

command.add(is_floating_terminal_active, {
  ["bottom-shelf:submit"] = function()
    if not FloatingPanel.is_executing then
      FloatingPanel:execute_command(FloatingPanel.input_text)
    end
    return true -- 🛡️ Consome o evento para não disparar doc:newline ou treeview
  end,

  ["bottom-shelf:tab-complete"] = function()
    FloatingPanel:handle_tab_completion()
    return true
  end,

  ["bottom-shelf:backspace"] = function()
    if FloatingPanel.input_cursor > 1 then
      FloatingPanel.input_text = FloatingPanel.input_text:sub(1, FloatingPanel.input_cursor - 2) .. FloatingPanel.input_text:sub(FloatingPanel.input_cursor)
      FloatingPanel.input_cursor = FloatingPanel.input_cursor - 1
      FloatingPanel:update_suggestions()
      core.redraw = true
    end
    return true
  end,

  ["bottom-shelf:delete"] = function()
    if FloatingPanel.input_cursor <= #FloatingPanel.input_text then
      FloatingPanel.input_text = FloatingPanel.input_text:sub(1, FloatingPanel.input_cursor - 1) .. FloatingPanel.input_text:sub(FloatingPanel.input_cursor + 1)
      FloatingPanel:update_suggestions()
      core.redraw = true
    end
    return true
  end,

  ["bottom-shelf:previous-char"] = function()
    FloatingPanel.input_cursor = math.max(1, FloatingPanel.input_cursor - 1)
    core.redraw = true
    return true
  end,

  ["bottom-shelf:next-char"] = function()
    FloatingPanel.input_cursor = math.min(#FloatingPanel.input_text + 1, FloatingPanel.input_cursor + 1)
    core.redraw = true
    return true
  end,

  ["bottom-shelf:start-of-line"] = function()
    FloatingPanel.input_cursor = 1
    core.redraw = true
    return true
  end,

  ["bottom-shelf:end-of-line"] = function()
    FloatingPanel.input_cursor = #FloatingPanel.input_text + 1
    core.redraw = true
    return true
  end,

  ["bottom-shelf:history-prev"] = function()
    if #FloatingPanel.history > 0 and FloatingPanel.history_idx > 1 then
      FloatingPanel.history_idx = FloatingPanel.history_idx - 1
      FloatingPanel.input_text = FloatingPanel.history[FloatingPanel.history_idx] or ""
      FloatingPanel.input_cursor = #FloatingPanel.input_text + 1
      FloatingPanel:update_suggestions()
      core.redraw = true
    end
    return true
  end,

  ["bottom-shelf:history-next"] = function()
    if FloatingPanel.history_idx < #FloatingPanel.history then
      FloatingPanel.history_idx = FloatingPanel.history_idx + 1
      FloatingPanel.input_text = FloatingPanel.history[FloatingPanel.history_idx] or ""
      FloatingPanel.input_cursor = #FloatingPanel.input_text + 1
      FloatingPanel:update_suggestions()
      core.redraw = true
    elseif FloatingPanel.history_idx == #FloatingPanel.history then
      FloatingPanel.history_idx = #FloatingPanel.history + 1
      FloatingPanel.input_text = ""
      FloatingPanel.input_cursor = 1
      FloatingPanel.suggestions = {}
      core.redraw = true
    end
    return true
  end,

  ["bottom-shelf:copy-all"] = function()
    FloatingPanel:copy_terminal_output()
    return true
  end,
})

keymap.add {
  ["ctrl+`"]        = "doxoade:toggle-bottom-shelf",
  ["alt+return"]    = "doxoade:bottom-shelf-toggle-maximize",
  ["escape"]        = "bottom-shelf:close",
  ["ctrl+v"]        = "bottom-shelf:paste-action",
  ["return"]        = "bottom-shelf:submit",
  ["keypad enter"]  = "bottom-shelf:submit",
  ["tab"]           = "bottom-shelf:tab-complete",
  ["backspace"]     = "bottom-shelf:backspace",
  ["delete"]        = "bottom-shelf:delete",
  ["left"]          = "bottom-shelf:previous-char",
  ["right"]         = "bottom-shelf:next-char",
  ["home"]          = "bottom-shelf:start-of-line",
  ["end"]           = "bottom-shelf:end-of-line",
  ["up"]            = "bottom-shelf:history-prev",
  ["down"]          = "bottom-shelf:history-next",
  ["ctrl+shift+c"]  = "bottom-shelf:copy-all",
}
