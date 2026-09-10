-- doxoade/commands/lite_xl_systems/template/19b_terminal_console.lua
--[[
  🖥️ DOXOADE PURE-BLACK TERMINAL & VENV CONSOLE (Módulo 19b V20.0)
  - Lançador de Terminal Nativo Real (Windows Terminal wt.exe / PowerShell com Venv).
  - Parser de TrueColor 24-bit (\x1b[38;2;R;G;Bm) e cores ANSI estendidas.
  - Higienizador de \r (Carriage Return) e sequências de controle de cursor.
  - Autocomplete enriquecido com comandos Doxoade, Git e arquivos locais.
  Compliance: ProDeNov 1.2.1, PASC-6.3.
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"

local function get_active_project_dir()
  if core.project_directories and #core.project_directories > 0 then
    local p = core.project_directories[1]
    return tostring(type(p) == "table" and (p.path or p.name) or p)
  end
  return core.project_dir or "."
end

local function detect_project_venv(proj_dir)
  local sep = PATHSEP or "/"
  local candidates = {
    proj_dir .. sep .. "venv",
    proj_dir .. sep .. ".venv",
    proj_dir .. sep .. "env",
    proj_dir .. sep .. ".env"
  }
  for _, vpath in ipairs(candidates) do
    local info = system.get_file_info(vpath)
    if info and info.type == "dir" then
      local scripts = (PLATFORM == "Windows") and (vpath .. sep .. "Scripts") or (vpath .. sep .. "bin")
      if system.get_file_info(scripts) then return scripts, vpath end
    end
  end
  return nil, nil
end

local ANSI_PALETTE = {
  [30] = { 20, 20, 20, 255 },     [31] = { 239, 68, 68, 255 },    [32] = { 34, 197, 94, 255 },
  [33] = { 234, 179, 8, 255 },    [34] = { 59, 130, 246, 255 },   [35] = { 168, 85, 247, 255 },
  [36] = { 6, 182, 212, 255 },    [37] = { 230, 230, 230, 255 },
  [90] = { 115, 115, 115, 255 },  [91] = { 248, 113, 113, 255 },  [92] = { 74, 222, 128, 255 },
  [93] = { 250, 204, 21, 255 },   [94] = { 96, 165, 250, 255 },   [95] = { 192, 132, 252, 255 },
  [96] = { 34, 211, 238, 255 },   [97] = { 255, 255, 255, 255 },
}

local PANTHEON_CMD_COLORS = {
  ["audit"]        = { 248, 113, 113, 255 },
  ["typhon"]       = { 251, 191, 36, 255 },
  ["check"]        = { 52, 211, 153, 255 },
  ["vulcan"]       = { 251, 146, 60, 255 },
  ["hades"]        = { 239, 68, 68, 255 },
  ["doxly"]        = { 56, 189, 248, 255 },
  ["deploy"]       = { 129, 140, 248, 255 },
  ["regret"]       = { 56, 189, 248, 255 },
  ["backup"]       = { 251, 191, 36, 255 },
  ["mk"]           = { 52, 211, 153, 255 },
  ["run"]          = { 56, 189, 248, 255 },
}

local function semantic_fallback_colorize(raw_line)
  local segs = {}
  local default_text_col = { 210, 215, 230, 255 }

  if raw_line:find("^%[INFO%]") or raw_line:find("✔") or raw_line:find("%[PASS%]") or raw_line:find("%[HERMES%-LOGGER%]") then
    local tag, rest = raw_line:match("^(%b[])(.*)$")
    if tag then
      table.insert(segs, { text = tag, fg = { 52, 211, 153, 255 } })
      table.insert(segs, { text = rest, fg = default_text_col })
      return segs
    end
    table.insert(segs, { text = raw_line, fg = { 52, 211, 153, 255 } })
    return segs
  elseif raw_line:find("^%[ERROR%]") or raw_line:find("✖") or raw_line:find("%[FAIL%]") or raw_line:find("Error:") or raw_line:find("Falha") or raw_line:find("Traceback") then
    table.insert(segs, { text = raw_line, fg = { 248, 113, 113, 255 } })
    return segs
  elseif raw_line:find("^%[WARN%]") or raw_line:find("⚠") or raw_line:find("Warning:") then
    table.insert(segs, { text = raw_line, fg = { 251, 191, 36, 255 } })
    return segs
  end

  -- 🛡️ PRESERVAÇÃO INTEGRAL DE ESPAÇOS: Não destrói as colunas originais do Click!
  local leading, cmd_name, spaces, cmd_desc = raw_line:match("^(%s*)([%w%-_]+)(%s%s+)(.*)$")
  if cmd_name and cmd_desc and not raw_line:find(":") then
    local cmd_col = PANTHEON_CMD_COLORS[cmd_name:lower()] or { 56, 189, 248, 255 }
    table.insert(segs, { text = leading .. cmd_name, fg = cmd_col })
    table.insert(segs, { text = spaces .. cmd_desc, fg = default_text_col })
    return segs
  end

  local leading_o, opt_name, spaces_o, opt_desc = raw_line:match("^(%s*)(%-%-[%w%-_]+)(%s%s+)(.*)$")
  if opt_name and opt_desc then
    table.insert(segs, { text = leading_o .. opt_name, fg = { 251, 191, 36, 255 } })
    table.insert(segs, { text = spaces_o .. opt_desc, fg = default_text_col })
    return segs
  end

  table.insert(segs, { text = raw_line, fg = default_text_col })
  return segs
end

-- =============================================================================
-- 🛡️ SANITIZADOR DE TEXTO E MAPA DE CARACTERES UNIVERSAIS
-- =============================================================================
local UNICODE_ASCII_REPLACEMENTS = {
  -- Converte divisores de caixa que viravam a fileira de ▯▯▯▯▯
  ["═"] = "=", ["║"] = "|", ["╔"] = "+", ["╗"] = "+", ["╚"] = "+", ["╝"] = "+",
  ["╠"] = "+", ["╣"] = "+", ["╦"] = "+", ["╩"] = "+", ["╬"] = "+",
  ["─"] = "-", ["│"] = "|", ["┌"] = "+", ["┐"] = "+", ["└"] = "+", ["┘"] = "+",
  ["├"] = "+", ["┤"] = "+", ["┬"] = "+", ["┴"] = "+", ["┼"] = "+",
  -- Converte símbolos especiais
  ["►"] = ">", ["✔"] = "[OK]", ["✖"] = "[X]", ["⚠"] = "[!]",
  ["⚡"] = "*", ["⛶"] = "",
}

local function sanitize_terminal_text(text)
  if not text or text == "" then return "" end

  -- 1. Remove variation selectors (U+FE0F: \xEF\xB8\x8F) que sobram de emojis
  text = text:gsub("\239\184\143", "")

  -- 2. Converte caracteres de caixa (═, ─) e símbolos para ASCII seguro
  for uni_char, ascii_rep in pairs(UNICODE_ASCII_REPLACEMENTS) do
    text = text:gsub(uni_char, ascii_rep)
  end

  -- 3. Remove quaisquer emojis restantes de 4 bytes UTF-8 (como 🔍, 🚀, 🔥)
  text = text:gsub("[\240-\244][\128-\191][\128-\191][\128-\191]", "")

  -- 4. ⚡ EXTERMINA qualquer byte \x1b órfão e caracteres de controle ASCII (1 a 31)
  -- Isso impede que qualquer caractere de escape vire o símbolo de caixa ▯ na tela!
  text = text:gsub("\x1b", "")
  text = text:gsub("[%z\1-\8\11\12\14-\31\127]", "")

  return text
end

-- =============================================================================
-- 🎨 PARSER ANSI BLINDADO CONTRA BYTES RESIDUAIS
-- =============================================================================
local function parse_ansi_segments(raw_line, default_fg)
  default_fg = default_fg or { 230, 230, 230, 255 }
  if not raw_line or raw_line == "" then return { { text = "", fg = default_fg } } end

  -- Preserva apenas o conteúdo após o último \r (spinners / progress bars)
  if raw_line:find("\r") then
    raw_line = raw_line:match("([^\r]+)$") or raw_line
  end

  raw_line = raw_line:gsub("\t", "    ")

  -- Remove sequências de escape de cursor que NÃO são de cor (não terminam em m)
  raw_line = raw_line:gsub("\x1b%[[%?%d;]*[a-ln-zA-LN-Z]", "")
  raw_line = raw_line:gsub("\x1b%([A-Za-z]", "")

  -- Se não houver mais sequências de cores restantes
  if not raw_line:find("\x1b%[") then
    local clean = sanitize_terminal_text(raw_line)
    return semantic_fallback_colorize(clean)
  end

  local segments = {}
  local current_fg = default_fg
  local pos = 1
  local len = #raw_line

  while pos <= len do
    local s, e, code_str = raw_line:find("\x1b%[([%d;]*)m", pos)
    if s then
      if s > pos then
        local chunk = sanitize_terminal_text(raw_line:sub(pos, s - 1))
        if chunk ~= "" then
          table.insert(segments, { text = chunk, fg = current_fg })
        end
      end

      -- Atualiza cor
      if code_str == "" or code_str == "0" then
        current_fg = default_fg
      else
        local tc_r, tc_g, tc_b = code_str:match("38;2;(%d+);(%d+);(%d+)")
        if tc_r and tc_g and tc_b then
          current_fg = { tonumber(tc_r), tonumber(tc_g), tonumber(tc_b), 255 }
        else
          for c in code_str:gmatch("%d+") do
            local n = tonumber(c)
            if ANSI_PALETTE[n] then
              current_fg = ANSI_PALETTE[n]
            end
          end
        end
      end
      pos = e + 1
    else
      local chunk = sanitize_terminal_text(raw_line:sub(pos))
      if chunk ~= "" then
        table.insert(segments, { text = chunk, fg = current_fg })
      end
      break
    end
  end

  return #segments > 0 and segments or { { text = "", fg = default_fg } }
end

local TerminalEngine = {
  lines = {},
  input_text = "",
  input_cursor = 1,
  history = {},
  history_idx = 1,
  is_executing = false,
  scroll_y = 0,
  scroll_to_y = 0,
  term_font_size = 14,
  term_font = nil,
  suggestions = {},
  suggestion_idx = 1,
  is_selecting_text = false,
  sel_start_line = nil,
  sel_end_line = nil,
  cached_project_files = {},
  last_file_cache_time = 0,
}

rawset(_G, "_DOXOADE_TERMINAL_ENGINE", TerminalEngine)

function TerminalEngine:get_font()
  if not self.term_font or self.term_font:get_size() ~= self.term_font_size then
    local base = style.code_font or style.font
    self.term_font = (base and base.copy) and base:copy(self.term_font_size) or base
  end
  return self.term_font or style.font
end

local function get_history_file_path()
  local proj = get_active_project_dir()
  local sep = PATHSEP or "/"
  local dox_dir = proj .. sep .. ".doxoade"
  pcall(function() system.mkdir(dox_dir) end)
  return dox_dir .. sep .. "terminal_history.txt"
end

function TerminalEngine:load_project_history()
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

function TerminalEngine:save_command_to_history(cmd_str)
  if not cmd_str or cmd_str == "" then return end
  if self.history[#self.history] == cmd_str then return end
  table.insert(self.history, cmd_str)
  self.history_idx = #self.history + 1
  local h_path = get_history_file_path()
  local f = io.open(h_path, "a")
  if f then f:write(cmd_str .. "\n"); f:close() end
end

-- =============================================================================
-- 🚀 LANÇADOR DE TERMINAL NATIVO REAL (WINDOWS TERMINAL / POWERSHELL / VENV)
-- =============================================================================
function TerminalEngine:copy_output(force_all)
  local buffer = {}
  local start_l = 1
  local end_l = #self.lines

  -- Se houver seleção com mouse e não for cópia forçada de tudo
  if not force_all and self.sel_start_line and self.sel_end_line and self.sel_start_line ~= self.sel_end_line then
    start_l = math.max(1, math.min(self.sel_start_line, self.sel_end_line))
    end_l = math.min(#self.lines, math.max(self.sel_start_line, self.sel_end_line))
  end

  for i = start_l, end_l do
    local item = self.lines[i]
    if item then
      local l_text = ""
      for _, seg in ipairs(item.segments or {}) do l_text = l_text .. seg.text end
      table.insert(buffer, l_text)
    end
  end

  local text_to_copy = table.concat(buffer, "\n")
  if text_to_copy ~= "" then
    system.set_clipboard(text_to_copy)
    if core.log then
      local count = end_l - start_l + 1
      core.log(string.format("%d linha(s) do terminal copiadas para a área de transferência.", count))
    end
  end
end

function TerminalEngine:launch_real_terminal(admin)
  local proj = get_active_project_dir()
  local _, venv_dir = detect_project_venv(proj)
  local sep = PATHSEP or "/"

  if PLATFORM == "Windows" then
    local act_bat = venv_dir and (venv_dir .. sep .. "Scripts" .. sep .. "activate.bat")
    local has_act_bat = act_bat and system.get_file_info(act_bat)

    -- 1. Tenta o Windows Terminal moderno (wt.exe) se existir
    local local_appdata = os.getenv("LOCALAPPDATA") or ""
    local wt_path = local_appdata .. "\\Microsoft\\WindowsApps\\wt.exe"
    local has_wt = system.get_file_info(wt_path)

    if has_wt then
      local wt_cmd
      if has_act_bat then
        wt_cmd = string.format('start "" "%s" -d "%s" cmd.exe /k ""%s""', wt_path, proj, act_bat)
      else
        wt_cmd = string.format('start "" "%s" -d "%s"', wt_path, proj)
      end
      local ok = pcall(system.exec, wt_cmd)
      if ok then
        if core.log then core.log("[TERMINAL REAL] Windows Terminal aberto em: " .. proj) end
        return true
      end
    end

    -- 2. Fallback Direto para CMD clássico (Robusto no Windows 10 e 11)
    local cmd_cmd
    if has_act_bat then
      cmd_cmd = string.format('start "Doxoade Terminal" cmd.exe /k "cd /d "%s" && "%s""', proj, act_bat)
    else
      cmd_cmd = string.format('start "Doxoade Terminal" cmd.exe /k "cd /d "%s""', proj)
    end
    pcall(system.exec, cmd_cmd)
    if core.log then core.log("[TERMINAL REAL] CMD nativo aberto em: " .. proj) end
    return true
  else
    -- Linux / POSIX
    local posix_cmd = string.format('x-terminal-emulator -e "bash -c \'cd \\"%s\\" && if [ -f \\"venv/bin/activate\\" ]; then source venv/bin/activate; fi; exec bash\'" &', proj)
    pcall(system.exec, posix_cmd)
    return true
  end
end

-- =============================================================================
-- 🧭 MOTOR DE AUTOCOMPLETE ENRIQUECIDO
-- =============================================================================
function TerminalEngine:update_suggestions()
  self.suggestions = {}
  self.suggestion_idx = 1
  local current = self.input_text
  if not current or current == "" then return end

  local commands = {
    -- Atalhos de controle do terminal nativo
    "wt", "term", "terminal", "cmd", "powershell", "cls", "clear", "exit",
    -- Comandos centrais do Doxoade
    "doxoade", "doxoade check", "doxoade mk", "doxoade regret", "doxoade run",
    "doxoade backup", "doxoade diff", "doxoade doctor", "doxoade init", "doxoade debug",
    "doxoade search", "doxoade clean", "doxoade health", "doxoade save", "doxoade git",
    -- Submódulos Doxly
    "doxoade doxly", "doxoade doxly check-templates", "doxoade doxly deploy test",
    "doxoade doxly deploy production", "doxoade doxly deploy sandbox", "doxoade doxly log",
    "doxoade doxly diagnose", "doxoade doxly profile", "doxoade doxly typhon",
    -- Comandos Git frequentes
    "git status", "git diff", "git log --oneline -n5", "git add .", "git commit -m",
    -- Python e pytest
    "pytest", "python", "pip list",
  }

  for _, cmd in ipairs(commands) do
    if cmd:sub(1, #current):lower() == current:lower() and #cmd > #current then
      table.insert(self.suggestions, cmd)
    end
  end

  local last_token = current:match("([^%s]+)$") or ""
  if #last_token > 0 then
    local now = os.clock()
    if now - self.last_file_cache_time > 3.0 then
      self.cached_project_files = system.list_dir(get_active_project_dir()) or {}
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

function TerminalEngine:handle_tab_completion()
  if #self.suggestions > 0 then
    self.input_text = self.suggestions[self.suggestion_idx]
    self.input_cursor = #self.input_text + 1
    self:update_suggestions()
    core.redraw = true
  end
end

function TerminalEngine:clear_screen()
  self.lines = {}
  self.scroll_y = 0
  self.scroll_to_y = 0
  self.input_text = ""
  self.input_cursor = 1
  self.sel_start_line = nil
  self.sel_end_line = nil
  self.suggestions = {}
  self:init_welcome()
  core.redraw = true
end

function TerminalEngine:init_welcome()
  local proj = get_active_project_dir()
  local _, venv_root = detect_project_venv(proj)
  local venv_status = venv_root and ("\x1b[38;2;34;197;94m " .. venv_root:match("[^/\\]+$") .. "\x1b[0m") or "\x1b[38;2;234;179;8m(Nenhum venv local)\x1b[0m"
  local banner_lines = {
    "\x1b[90m================================================================================\x1b[0m",
    "  \x1b[38;2;0;108;255mDOXOADE\x1b[0m \x1b[38;2;38;188;95mCONSOLE STUDIO\x1b[0m \x1b[90m(V20.0 TrueColor)\x1b[0m",
    "  \x1b[36mProjeto\x1b[0m : \x1b[37m" .. proj .. "\x1b[0m",
    "  \x1b[36mVenv   \x1b[0m : " .. venv_status,
    "  \x1b[90mAtalhos: TAB (Completar) | term/wt (Abrir Terminal Real) | cls (Limpar)\x1b[0m",
    "\x1b[90m================================================================================\x1b[0m",
    ""
  }
  for _, line in ipairs(banner_lines) do
    table.insert(self.lines, { segments = parse_ansi_segments(line) })
  end
end

function TerminalEngine:copy_output()
  local buffer = {}
  local start_l = 1
  local end_l = #self.lines
  if self.sel_start_line and self.sel_end_line then
    start_l = math.max(1, math.min(self.sel_start_line, self.sel_end_line))
    end_l = math.min(#self.lines, math.max(self.sel_start_line, self.sel_end_line))
  end
  for i = start_l, end_l do
    local item = self.lines[i]
    if item then
      local l_text = ""
      for _, seg in ipairs(item.segments or {}) do l_text = l_text .. seg.text end
      table.insert(buffer, l_text)
    end
  end
  system.set_clipboard(table.concat(buffer, "\n"))
  if core.log then core.log("Conteúdo do terminal copiado para a área de transferência.") end
end

function TerminalEngine:execute_command(cmd_str)
  local clean = cmd_str:gsub("^%s*", ""):gsub("%s*$", "")
  if clean == "" then return end

  self:save_command_to_history(clean)

  local lower = clean:lower()
  if lower == "cls" or lower == "clear" then
    self:clear_screen()
    return
  end

  if lower == "wt" or lower == "term" or lower == "terminal" or lower == "cmd" or lower == "powershell" then
    table.insert(self.lines, { segments = parse_ansi_segments("\x1b[38;2;38;188;95m⚡ [TERMINAL REAL] Lançando terminal nativo no projeto...\x1b[0m") })
    self:launch_real_terminal()
    core.redraw = true
    return
  end

  -- Timestamp de início sem espaço duplo órfão
  local time_start = os.date("%H:%M:%S")
  local cmd_header = string.format("\x1b[90m[%s]\x1b[0m \x1b[38;2;56;189;248m> %s\x1b[0m", time_start, clean)
  table.insert(self.lines, { segments = parse_ansi_segments(cmd_header) })

  self.input_text = ""
  self.input_cursor = 1
  self.suggestions = {}
  self.is_executing = true
  core.redraw = true

  local proj = get_active_project_dir()
  local sep = PATHSEP or "/"
  local user_dir = USERDIR or "."
  local temp_dir = user_dir .. sep .. ".doxoade" .. sep .. "terminal_temp"
  pcall(function() system.mkdir(temp_dir) end)

  local run_id = os.time() .. "_" .. math.random(1000, 9999)
  local batch_file = temp_dir .. sep .. "run_" .. run_id .. (PLATFORM == "Windows" and ".cmd" or ".sh")
  local out_file = temp_dir .. sep .. "out_" .. run_id .. ".txt"
  local done_file = temp_dir .. sep .. "done_" .. run_id .. ".flag"

  local venv_scripts, _ = detect_project_venv(proj)
  local script_content = ""

  if PLATFORM == "Windows" then
    script_content = "@echo off\r\nchcp 65001 > nul\r\ncd /d \"" .. proj .. "\"\r\n"
    -- 🚀 Força emissão de cores e formatação nativa do Python/Click
    script_content = script_content .. "set FORCE_COLOR=1\r\nset CLICOLOR_FORCE=1\r\nset PYTHONUNBUFFERED=1\r\n"
    if venv_scripts then
      script_content = script_content .. "set PATH=" .. venv_scripts .. ";%PATH%\r\n"
    end
    script_content = script_content .. clean .. " > \"" .. out_file .. "\" 2>&1\r\n"
    script_content = script_content .. "echo 1 > \"" .. done_file .. "\"\r\n"
  else
    script_content = "#!/usr/bin/env bash\ncd \"" .. proj .. "\"\n"
    script_content = script_content .. "export FORCE_COLOR=1\nexport CLICOLOR_FORCE=1\nexport PYTHONUNBUFFERED=1\n"
    if venv_scripts then
      script_content = script_content .. "export PATH=\"" .. venv_scripts .. ":$PATH\"\n"
    end
    script_content = script_content .. clean .. " > \"" .. out_file .. "\" 2>&1\n"
    script_content = script_content .. "echo 1 > \"" .. done_file .. "\"\n"
  end

  local f_batch = io.open(batch_file, "w")
  if f_batch then
    f_batch:write(script_content)
    f_batch:close()
  end

  core.add_thread(function()
    local t0 = os.clock()
    pcall(system.exec, (PLATFORM == "Windows" and ("\"" .. batch_file .. "\"") or ("bash \"" .. batch_file .. "\"")))

    local last_read_pos = 0
    local poll_start = os.clock()

    while os.clock() - poll_start < 120.0 do
      coroutine.yield(0.04)
      local f_out = io.open(out_file, "r")
      if f_out then
        f_out:seek("set", last_read_pos)
        local chunk = f_out:read("*a")
        last_read_pos = f_out:seek()
        f_out:close()

        if chunk and chunk ~= "" then
          for line in chunk:gmatch("[^\r\n]+") do
            -- Ignora linhas vazias ou de resíduos
            table.insert(TerminalEngine.lines, { segments = parse_ansi_segments(line) })
          end
          core.redraw = true
        end
      end

      if system.get_file_info(done_file) then
        local f_final = io.open(out_file, "r")
        if f_final then
          f_final:seek("set", last_read_pos)
          local rest = f_final:read("*a")
          f_final:close()
          if rest and rest ~= "" then
            for line in rest:gmatch("[^\r\n]+") do
              table.insert(TerminalEngine.lines, { segments = parse_ansi_segments(line) })
            end
          end
        end
        break
      end
    end

    local elapsed = os.clock() - t0
    local time_end = os.date("%H:%M:%S")
    local done_msg = string.format("\x1b[90m[%s] [OK] Concluído em %.2fs\x1b[0m", time_end, elapsed)
    table.insert(TerminalEngine.lines, { segments = parse_ansi_segments(done_msg) })

    TerminalEngine.is_executing = false
    pcall(os.remove, batch_file)
    pcall(os.remove, out_file)
    pcall(os.remove, done_file)
    core.redraw = true
  end)
end

-- =============================================================================
-- COMANDOS E KEYMAPS GLOBAIS
-- =============================================================================
command.add(nil, {
  ["doxoade:terminal-launch-real"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term and term.launch_real_terminal then
      term:launch_real_terminal()
    end
  end,
  ["doxoade:open-real-terminal"] = function()
    command.perform("doxoade:terminal-launch-real")
  end,
  ["doxoade:terminal-launch-admin-venv"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term and term.launch_admin_venv then
      term:launch_admin_venv()
    end
  end,
})

keymap.add {
  ["ctrl+shift+t"] = "doxoade:terminal-launch-real",
}
