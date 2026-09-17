-- doxoade/commands/lite_xl_systems/template/19b_terminal_console.lua
--[[
  🖥️ DOXOADE TERMINAL REAL ENGINE — INTEGRAÇÃO LITE XL (V25.0 PTY Nativo).
  Reforma definitiva do terminal embutido conectada ao PTYClient (Fase 1 & 2).
  Responsabilidades:
    • Conectar ao _DOXOADE_PTY_CLIENT via pipes binários
    • Polling contínuo de output em corrotina fatiada (Zero-Freeze)
    • Redimensionamento automático ao redimensionar a janela (resize)
    • Histórico de comandos persistente (.doxoade/terminal_history.txt)
    • Roteamento de comandos de prompt, teclado, Ctrl+C e clipboard
    • Suporte a múltiplos shells (CMD / PowerShell / PWSH / Bash)
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"

local TerminalRealEngine = {}
TerminalRealEngine.__index = TerminalRealEngine

local function is_windows()
  return package.config:sub(1, 1) == "\\"
end

local function detect_default_shell()
  local env_shell = os.getenv("DOX_TERMINAL_SHELL")
  if env_shell and env_shell ~= "" then return env_shell end
  if is_windows() then return "cmd" end
  return os.getenv("SHELL") or "/bin/sh"
end

local function shell_short_name(shell)
  if not shell then return "SHELL" end
  local s = shell:gsub(".*/", ""):gsub("%.exe$", ""):lower()
  if s == "cmd" then return "CMD" end
  if s == "powershell" then return "PS" end
  if s == "pwsh" then return "PW7" end
  if s == "bash" then return "BASH" end
  if s == "zsh" then return "ZSH" end
  if s == "sh" then return "SH" end
  return s:upper()
end

local function get_active_project_dir()
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
          return (system.absolute_path(pdir) or pdir):gsub("\\", "/")
        end
      end
    end
  end
  if core.project_directories and #core.project_directories > 0 then
    for _, p in ipairs(core.project_directories) do
      local p_str = tostring(type(p) == "table" and (p.path or p.name) or p)
      if not p_str:find("test_deploy") and not p_str:find("sandbox") then
        return (system.absolute_path(p_str) or p_str):gsub("\\", "/")
      end
    end
  end
  return (system.absolute_path(".") or "."):gsub("\\", "/")
end

local function detect_project_venv(proj_dir)
  local sep = PATHSEP or "/"
  local candidates = {
    proj_dir .. sep .. "venv",
    proj_dir .. sep .. "doxoade" .. sep .. "venv",
    proj_dir .. sep .. ".venv",
    proj_dir .. sep .. "doxoade" .. sep .. ".venv",
    proj_dir .. sep .. "env",
    proj_dir .. sep .. ".env"
  }
  for _, vpath in ipairs(candidates) do
    local info = system.get_file_info(vpath)
    if info and info.type == "dir" then
      local scripts = is_windows() and (vpath .. sep .. "Scripts") or (vpath .. sep .. "bin")
      if system.get_file_info(scripts) then return scripts, vpath end
    end
  end
  return nil, nil
end

function TerminalRealEngine.new(opts)
  opts = opts or {}
  local self = setmetatable({}, TerminalRealEngine)
  self.shell = opts.shell or detect_default_shell()
  self.is_real_pty = true
  self.lines = {}
  self.scroll_y = 0
  
  -- Prompt e controle de input (utilizado pelo 19d)
  self.input_text = ""
  self.input_cursor = 1
  self._all_selected = false
  self.history = {}
  self.history_idx = 1
  self.suggestions = {}
  self.suggestion_idx = 1
  self.is_executing = false
  self.is_selecting_text = false
  self.sel_start_line = nil
  self.sel_end_line = nil

  self._client = nil
  self._running = false
  self._font = nil
  self._last_view_w = 0
  self._last_view_h = 0
  self._cols = 120
  self._rows = 30
  self._auto_scroll = true
  self._last_line_count = 0
  self._status_msg = "Inicializando..."

  self:load_project_history()
  return self
end

function TerminalRealEngine:get_font()
  return self._font or style.font
end

function TerminalRealEngine:set_font(font)
  self._font = font
end

function TerminalRealEngine:get_cwd()
  local proj = get_active_project_dir()
  return (system.absolute_path(proj) or proj):gsub("\\", "/")
end

function TerminalRealEngine:short_shell_label()
  return shell_short_name(self.shell)
end

function TerminalRealEngine:ensure_started()
  if not self._running then
    self:start()
  end
end

local TerminalEngine = {}
TerminalEngine.__index = TerminalEngine
local TerminalRealEngine = TerminalEngine

-- [manter funções auxiliares: is_windows, detect_default_shell, shell_short_name, etc.]

function TerminalEngine.new(opts)
  opts = opts or {}
  local self = setmetatable({}, TerminalEngine)
  self.shell = opts.shell or detect_default_shell()
  self.is_real_pty = true
  self.lines = {}
  self.scroll_y = 0

  self.input_text = ""
  self.input_cursor = 1
  self._all_selected = false
  self.history = {}
  self.history_idx = 1
  self.suggestions = {}
  self.suggestion_idx = 1
  self.is_executing = false
  self.is_selecting_text = false
  self.sel_start_line = nil
  self.sel_end_line = nil

  self._client = nil
  self._running = false
  self._font = nil
  self._last_view_w = 0
  self._last_view_h = 0
  self._cols = 120
  self._rows = 30
  self._auto_scroll = true
  self._last_line_count = 0
  self._status_msg = "Inicializando..."

  self:load_project_history()
  return self
end

function TerminalEngine:get_font()
  return self._font or style.font
end

function TerminalEngine:set_font(font)
  self._font = font
end

function TerminalEngine:get_cwd()
  local proj = get_active_project_dir()
  return (system.absolute_path(proj) or proj):gsub("\\", "/")
end

function TerminalEngine:short_shell_label()
  return shell_short_name(self.shell)
end

function TerminalEngine:ensure_started()
  if not self._running then
    self:start()
  end
end

function TerminalEngine:start()
  if self._running then return true end

  if self._spawn_attempted then
    self._status_msg = "Falha ao iniciar PTY. Verifique o Python/venv."
    return false
  end

  local PTYClient = rawget(_G, "_DOXOADE_PTY_CLIENT")
  if not PTYClient then
    self._status_msg = "PTYClient ausente."
    self._spawn_attempted = true
    return false
  end

  self._spawn_attempted = true

  self._client = PTYClient.new({
    shell = self.shell,
    cols = self._cols,
    rows = self._rows,
    cwd = self:get_cwd(),
    debug = false,
  })

  local engine = self
  self._client.on_ready = function()
    engine._status_msg = "PTY pronto."
    core.redraw = true
  end
  self._client.on_output = function()
    engine.lines = engine._client.lines or {}
    if engine._auto_scroll then engine:scroll_to_bottom() end
    core.redraw = true
  end
  self._client.on_exit = function(code)
    engine.is_executing = false
    engine._status_msg = string.format("Shell encerrou (%s)", tostring(code or 0))
    core.redraw = true
  end

  local ok = self._client:spawn()
  if not ok then
    self._status_msg = "Falha ao iniciar PTY. Verifique o Python/venv."
    return false
  end

  self._running = true
  self.is_executing = true
  self._status_msg = "Conectado."
  self:_start_poller()
  return true
end

function TerminalEngine:stop()
  self._running = false
  if self._client then
    self._client:close()
    self._client = nil
  end
  self.is_executing = false
end

function TerminalEngine:set_shell(shell)
  if not shell or shell == self.shell then return end
  self.shell = shell
  if self._running then
    self:stop()
    self.lines = {}
    self.scroll_y = 0
    self:start()
  end
end

function TerminalEngine:_shell_list()
  if is_windows() then
    return { "cmd", "powershell", "pwsh" }
  end
  return { "auto", "bash", "zsh", "sh" }
end

function TerminalEngine:cycle_shell()
  local list = self:_shell_list()
  local current = self.shell
  for i, item in ipairs(list) do
    if item == current then
      local next_item = list[(i % #list) + 1]
      self:set_shell(next_item)
      if core.log then
        core.log(string.format("🖥️ [TERMINAL] Shell alterado para: %s", next_item))
      end
      return
    end
  end
  self:set_shell(list[1])
end

function TerminalEngine:_start_poller()
  if not core.add_thread then return end
  local engine = self
  core.add_thread(function()
    local idle_ticks = 0
    while engine._running do
      local prev_count = #engine.lines
      engine:tick()

      -- Se a contagem de linhas não mudou, entra em sono reativo imediatamente
      if #engine.lines == prev_count then
        idle_ticks = idle_ticks + 1
        local sleep_sec = idle_ticks > 2 and 0.20 or 0.05
        coroutine.yield(sleep_sec)
      else
        idle_ticks = 0
        coroutine.yield(0.02)
      end
    end
  end, engine)
end

function TerminalEngine:_line_height()
  local font = (self.get_font and self:get_font()) or style.font
  return (font and font:get_height() or 14) + 2
end
TerminalRealEngine._line_height = TerminalEngine._line_height

function TerminalEngine:tick()
  if not self._client then return end
  if not self._client._handshake_done then
    self._client:poll_handshake()
  else
    self._client:poll()
  end
  
  if self._client.lines then
    self.lines = self._client.lines
  end
  
  -- Heurística de Prompt: se a linha atual ou a última linha for um prompt do shell, libera o status
  local cur_line = self._client.current_line
  if cur_line and #cur_line > 0 then
    local last_seg = cur_line[#cur_line]
    local text = last_seg and last_seg.text or ""
    if text:find(">$") or text:find("%$ $") or text:find("# $") then
      if self.is_executing then
        self.is_executing = false
        core.redraw = true
      end
    end
  end

  local count = #self.lines
  if count ~= self._last_line_count then
    self._last_line_count = count
    core.redraw = true
  end
end

function TerminalEngine:get_effective_content_lines()
  local last_idx = 0
  for i = #self.lines, 1, -1 do
    local item = self.lines[i]
    if item and item.segments and #item.segments > 0 then
      local has_text = false
      for _, seg in ipairs(item.segments) do
        if seg.text and seg.text:find("%S") then
          has_text = true
          break
        end
      end
      if has_text then
        last_idx = i
        break
      end
    end
  end

  -- Se houver a linha ativa do prompt, conta como a última linha
  local cur_line = self._client and self._client.current_line
  if cur_line and #cur_line > 0 then
    for _, seg in ipairs(cur_line) do
      if seg.text and seg.text:find("%S") then
        last_idx = last_idx + 1
        break
      end
    end
  end

  return math.max(1, last_idx)
end
TerminalRealEngine.get_effective_content_lines = TerminalEngine.get_effective_content_lines

function TerminalEngine:update_viewport(view_w, view_h)
  if view_w <= 0 or view_h <= 0 then return end
  self._last_view_w = view_w
  self._last_view_h = view_h
  local font = (self.get_font and self:get_font()) or style.font
  local char_w = math.max(1, font:get_width("M"))
  local line_h = (font and font:get_height() or 14) + 2
  local cols = math.max(20, math.floor((view_w - 28) / char_w))
  local rows = math.max(5, math.floor((view_h - 12) / line_h))
  if cols ~= self._cols or rows ~= self._rows then
    self._cols = cols
    self._rows = rows
    if self._client and self._client.is_connected then
      self._client:send_resize(cols, rows)
    end
  end
  if self._auto_scroll then
    self:scroll_to_bottom()
  end
end

function TerminalEngine:scroll_to_bottom()
  local font = (self.get_font and self:get_font()) or style.font
  local line_h = (font and font:get_height() or 14) + 2
  
  -- Encontra o índice da última linha com conteúdo real
  local last_line_idx = 0
  for i = #self.lines, 1, -1 do
    local item = self.lines[i]
    if item and item.segments and #item.segments > 0 then
      for _, seg in ipairs(item.segments) do
        if seg.text and seg.text:find("%S") then
          last_line_idx = i
          break
        end
      end
      if last_line_idx > 0 then break end
    end
  end

  -- Se a linha corrente tiver texto/prompt, soma +1
  local cur_line = self._client and self._client.current_line
  if cur_line and #cur_line > 0 then
    for _, seg in ipairs(cur_line) do
      if seg.text and seg.text:find("%S") then
        last_line_idx = last_line_idx + 1
        break
      end
    end
  end

  local total_h = math.max(1, last_line_idx) * line_h
  local visible_h = math.max(1, (self._last_view_h or 300))
  
  -- Se o texto cabe na tela, scroll_y é 0 (topo)
  -- Se o texto excede a tela, trava a última linha na borda inferior útil
  if total_h <= visible_h then
    self.scroll_y = 0
  else
    self.scroll_y = total_h - visible_h + line_h
  end
  
  core.redraw = true
end
TerminalRealEngine.scroll_to_bottom = TerminalEngine.scroll_to_bottom

function TerminalEngine:scroll_by(delta)
  local line_h = self:_line_height()
  local content_h = #self.lines * line_h
  local max_scroll = math.max(0, content_h - self._last_view_h + line_h)
  self.scroll_y = math.max(0, math.min(max_scroll, self.scroll_y - delta))
  self._auto_scroll = (self.scroll_y >= max_scroll - 4)
end

function TerminalEngine:send_text(text)
  if not self._client or not self._running then return end
  if text and text ~= "" then
    self._client:send_input(text)
    self._auto_scroll = true
  end
end

function TerminalEngine:send_key(seq)
  self:send_text(seq)
end

function TerminalEngine:execute_command(cmd)
  cmd = (cmd or self.input_text or ""):gsub("[\r\n]", "")
  
  -- Interceptação nativa de limpeza de tela (cls no Windows e clear no Linux)
  local clean_cmd = cmd:gsub("^%s+", ""):gsub("%s+$", ""):lower()
  if clean_cmd == "cls" or clean_cmd == "clear" then
    self:clear_screen()
    self:save_command_to_history(cmd)
    self:send_text("\r\n")
    self.input_text = ""
    self.input_cursor = 1
    self._all_selected = false
    self.is_executing = false
    core.redraw = true
    return
  end

  if cmd ~= "" then
    self:save_command_to_history(cmd)
    self:send_text(cmd .. "\r\n")
  else
    self:send_text("\r\n")
  end
  self.input_text = ""
  self.input_cursor = 1
  self._all_selected = false
  self.is_executing = true
  core.redraw = true
end

function TerminalEngine:send_interrupt()
  if self._client then
    self._client:send_interrupt()
    self._status_msg = "Ctrl+C enviado."
    core.redraw = true
  end
end

function TerminalEngine:handle_tab_completion()
  if #self.suggestions > 0 then
    self.input_text = self.suggestions[self.suggestion_idx]
    self.input_cursor = #self.input_text + 1
    self:update_suggestions()
  else
    self:send_key("\t")
  end
  core.redraw = true
  return true
end

function TerminalEngine:update_suggestions()
  self.suggestions = {}
  self.suggestion_idx = 1
  local current = self.input_text
  if not current or current == "" then return end

  local commands = {
    "doxoade", "doxoade check", "doxoade regret", "doxoade run",
    "doxoade backup", "doxoade diff", "doxoade image", "doxoade image sync",
    "doxoade doxly", "doxoade doxly check-templates", "doxoade doxly deploy test",
    "doxoade doxly deploy production", "doxoade doxly log -m test",
    "pytest", "python", "git status", "git diff", "git log -n 5", "cls", "clear"
  }

  for _, cmd in ipairs(commands) do
    if cmd:sub(1, #current):lower() == current:lower() and #cmd > #current then
      table.insert(self.suggestions, cmd)
    end
  end
end

function TerminalEngine:clear_screen()
  if self._client then
    self._client:clear_screen()
  end
  self.lines = {}
  self.scroll_y = 0
  self.input_text = ""
  self.input_cursor = 1
  self._all_selected = false
  self.suggestions = {}
  core.redraw = true
end

-- ✅ CONTRATO RESTAURADO: Init Welcome (compatibilidade com versões anteriores)
function TerminalEngine:init_welcome()
  self:clear_screen()
end

function TerminalEngine:copy_output()
  local parts = {}
  local start_l = 1
  local end_l = #self.lines
  if self.sel_start_line and self.sel_end_line then
    start_l = math.max(1, math.min(self.sel_start_line, self.sel_end_line))
    end_l = math.min(#self.lines, math.max(self.sel_start_line, self.sel_end_line))
  end

  for i = start_l, end_l do
    local item = self.lines[i]
    if item then
      local line_text = ""
      for _, seg in ipairs(item.segments or {}) do
        line_text = line_text .. (seg.text or "")
      end
      table.insert(parts, line_text)
    end
  end

  local text_to_copy = table.concat(parts, "\n")
  if text_to_copy ~= "" and system and system.set_clipboard then
    system.set_clipboard(text_to_copy)
    if core.log then
      core.log(string.format("📋 %d linha(s) do terminal copiadas.", #parts))
    end
  end
end

function TerminalEngine:paste_clipboard()
  local clip = (system and system.get_clipboard and system.get_clipboard()) or ""
  if clip ~= "" then
    clip = clip:gsub("[\r\n]+", " ")
    self:send_text(clip)
  end
end

-- [manter histórico: get_history_file_path, load_project_history, save_command_to_history]

-- ✅ CONTRATO RESTAURADO: launch_real_terminal delegado para launch_external_terminal
function TerminalEngine:launch_real_terminal(admin)
  return self:launch_external_terminal(admin)
end

-- =============================================================================
-- 📜 HISTÓRICO PERSISTENTE DE COMANDOS
-- =============================================================================
local function get_history_file_path()
  local proj = get_active_project_dir()
  local sep = PATHSEP or "/"
  local dox_dir = proj .. sep .. ".doxoade"
  pcall(function() system.mkdir(dox_dir) end)
  return dox_dir .. sep .. "terminal_history.txt"
end

function TerminalRealEngine:load_project_history()
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

function TerminalRealEngine:save_command_to_history(cmd_str)
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

-- =============================================================================
-- 🚀 LANÇADOR DE TERMINAL EXTERNO (FALLBACK SEGURO DO SO)
-- =============================================================================
function TerminalEngine:launch_external_terminal(as_admin)
  local proj = self:get_cwd()
  local sep = PATHSEP or "/"
  local venv_act = proj .. sep .. "venv" .. sep .. "Scripts" .. sep .. "activate.bat"
  local has_venv = system.get_file_info(venv_act) ~= nil
  local act_cmd = has_venv and string.format(' && "%s"', venv_act) or ""

  if PLATFORM == "Windows" then
    if as_admin then
      -- Elevação UAC segura
      local ps_inner = string.format("cd /d '%s'%s", proj, act_cmd)
      local cmd = string.format('powershell.exe -NoProfile -Command "Start-Process cmd.exe -ArgumentList \'/k %s\' -Verb RunAs"', ps_inner)
      pcall(system.exec, cmd)
    else
      -- 1. Verifica se wt.exe (Windows Terminal) existe de verdade no disco
      local has_wt = false
      local localapp = os.getenv("LOCALAPPDATA")
      if localapp then
        local wt_exe = localapp .. "\\Microsoft\\WindowsApps\\wt.exe"
        has_wt = system.get_file_info(wt_exe) ~= nil
      end

      -- 2. Tenta wt.exe; se não houver, fallback transparente para o cmd.exe clássico
      if has_wt then
        local wt_cmd = string.format('wt.exe -d "%s" cmd.exe /k "cd /d %s%s"', proj, proj, act_cmd)
        pcall(system.exec, wt_cmd)
      else
        local standard_cmd = string.format('start "Doxoade Terminal" cmd.exe /k "cd /d %s%s"', proj, act_cmd)
        pcall(system.exec, standard_cmd)
      end
    end
    if core.log then
      core.log(string.format("🖥️ Terminal Externo lançado (%s): %s", as_admin and "Admin" or "Normal", proj))
    end
  else
    pcall(system.exec, string.format('x-terminal-emulator -e "bash -c \'cd %s && exec bash\'" &', proj))
  end
end

-- Métodos ergonômicos de edição de linha (Ctrl+A, Ctrl+W, etc.)
function TerminalEngine:select_all_or_home()
  if self._all_selected then
    self._all_selected = false
    self.input_cursor = 1
  else
    self._all_selected = true
    self.input_cursor = #self.input_text + 1
  end
  core.redraw = true
end

function TerminalEngine:delete_word_backwards()
  if self._all_selected or self.input_text == "" then
    self.input_text = ""
    self.input_cursor = 1
    self._all_selected = false
    core.redraw = true
    return
  end
  local pos = self.input_cursor - 1
  if pos <= 0 then return end
  local before = self.input_text:sub(1, pos)
  local after = self.input_text:sub(pos + 1)
  -- Remove espaços seguidos da palavra anterior
  local trimmed = before:gsub("%s*[^%s]+%s*$", "")
  self.input_text = trimmed .. after
  self.input_cursor = #trimmed + 1
  core.redraw = true
end

-- =============================================================================
-- ⌨️ INSTANCIAÇÃO E COMANDOS GLOBAIS SOBERANOS
-- =============================================================================
local global_terminal = TerminalRealEngine.new()
rawset(_G, "_DOXOADE_TERMINAL_ENGINE", global_terminal)

command.add(nil, {
  ["doxoade:terminal-launch-real"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term:ensure_started() end
    local shelf = rawget(_G, "_DOXOADE_SHELF_HUB")
    if shelf then
      shelf.active_tab = "terminal"
      shelf.visible = true
      core.redraw = true
    end
  end,
  ["doxoade:open-real-terminal"] = function()
    command.perform("doxoade:terminal-launch-real")
  end,
  ["doxoade:terminal-launch-external"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term:launch_external_terminal(false) end
  end,
  ["doxoade:terminal-launch-admin"] = function()
    local term = rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term then term:launch_external_terminal(true) end
  end,
  ["doxoade:terminal-launch-admin-venv"] = function()
    command.perform("doxoade:terminal-launch-admin")
  end,
})

keymap.add {
  ["ctrl+alt+t"]       = "doxoade:terminal-launch-real",
  ["ctrl+alt+shift+t"] = "doxoade:terminal-launch-admin",
}

return global_terminal
