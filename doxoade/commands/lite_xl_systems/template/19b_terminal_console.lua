-- doxoade/commands/lite_xl_systems/template/19b_terminal_console.lua
--[[
  🖥️ DOXOADE TERMINAL REAL ENGINE — SOBERANO & MULTI-SESSÃO (V39.0)
  - Zero falhas de boot: sintaxe estrita validada.
  - Resolução de projeto limpa: extrai o nome real da pasta pai e ignora /venv.
  - Multi-Sessões concorrentes via SessionManager isolado.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"

local TerminalEngine = {}
TerminalEngine.__index = TerminalEngine

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
          local root = pdir:match("^(.*)[/\\]%.?venv$") or pdir:match("^(.*)[/\\]env$")
          if root then pdir = root end
          local norm = (system.absolute_path(pdir) or pdir):gsub("\\", "/")
          if not norm:find("%.config") and not norm:find("test_deploy") and not norm:find("sandbox") then
            return norm
          end
        end
      end
    end
  end

  if core.project_directories and #core.project_directories > 0 then
    for _, p in ipairs(core.project_directories) do
      local p_str = tostring(type(p) == "table" and (p.path or p.name) or p)
      local norm = (system.absolute_path(p_str) or p_str):gsub("\\", "/")
      if not norm:find("%.config") and not norm:find("test_deploy") and not norm:find("sandbox") then
        return norm
      end
    end
  end

  if core.project_dir then
    local norm = (system.absolute_path(core.project_dir) or core.project_dir):gsub("\\", "/")
    if not norm:find("%.config") and not norm:find("test_deploy") and not norm:find("sandbox") then
      return norm
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

local _next_session_id = 1

function TerminalEngine.new(opts)
  opts = opts or {}
  local self = setmetatable({}, TerminalEngine)
  self.id = opts.id or ("term_" .. _next_session_id)
  _next_session_id = _next_session_id + 1

  self.name = opts.name or nil
  self.shell = opts.shell or detect_default_shell()
  self.custom_cwd = opts.cwd or nil
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
  self._font_size = 14
  self._last_view_w = 0
  self._last_view_h = 0
  self._cols = 120
  self._rows = 30
  self._auto_scroll = true
  self._last_line_count = 0
  self._status_msg = "Pronto."

  self:load_project_history()
  return self
end

function TerminalEngine:get_font()
  return self._font or style.code_font or style.font
end

function TerminalEngine:set_font(font)
  self._font = font
  if font and font.get_size then
    self._font_size = font:get_size()
  end
end

function TerminalEngine:adjust_font_size(delta)
  local base_font = self:get_font()
  local cur_size = self._font_size or (base_font and base_font:get_size() or 14)
  local new_size = math.max(9, math.min(32, cur_size + delta))
  if new_size == cur_size then return end

  self._font_size = new_size

  if base_font and base_font.copy then
    self._font = base_font:copy(new_size)
  elseif renderer and renderer.font and renderer.font.load then
    local path = (base_font and base_font.path) or (DATADIR .. "/fonts/monospace.ttf")
    local ok, loaded = pcall(renderer.font.load, path, new_size)
    if ok and loaded then self._font = loaded end
  end

  if self._last_view_w > 0 and self._last_view_h > 0 then
    self:update_viewport(self._last_view_w, self._last_view_h)
  end
  core.redraw = true
end

function TerminalEngine:reset_font_size()
  self._font = nil
  self._font_size = (style.code_font and style.code_font:get_size()) or 14
  if self._last_view_w > 0 and self._last_view_h > 0 then
    self:update_viewport(self._last_view_w, self._last_view_h)
  end
  core.redraw = true
end

function TerminalEngine:get_cwd()
  local target = self.custom_cwd or get_active_project_dir()
  return (system.absolute_path(target) or target):gsub("\\", "/")
end

function TerminalEngine:get_display_name()
  if self.name and self.name ~= "" then return self.name end
  local p = self:get_cwd()
  local root = p:match("^(.*)[/\\]%.?venv$") or p:match("^(.*)[/\\]env$")
  if root then p = root end
  local folder = p:match("[^/\\\\]+$") or p
  return folder
end

function TerminalEngine:set_target_dir(dir_path)
  if not dir_path or dir_path == "" then return end
  self.custom_cwd = (system.absolute_path(dir_path) or dir_path):gsub("\\", "/")
  self.name = nil
  if self._running then
    self:stop()
    self.lines = {}
    self.scroll_y = 0
    self:start()
  end
end

function TerminalEngine:short_shell_label()
  return shell_short_name(self.shell)
end

function TerminalEngine:_shell_list()
  if is_windows() then
    return { "cmd", "powershell", "pwsh" }
  end
  return { "auto", "bash", "zsh", "sh" }
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

function TerminalEngine:ensure_started()
  if not self._running then self:start() end
end

function TerminalEngine:start()
  if self._running then return true end

  local PTYClient = rawget(_G, "_DOXOADE_PTY_CLIENT")
  if not PTYClient then
    self._status_msg = "PTYClient ausente."
    return false
  end

  if self._client then
    self._client:close()
    self._client = nil
  end

  self._client = PTYClient.new({
    id = self.id, -- 🎯 Garante IPC exclusivo por aba
    shell = self.shell,
    cols = self._cols,
    rows = self._rows,
    cwd = self:get_cwd(),
    debug = false,
  })

  local engine = self
  self._client.on_ready = function()
    engine._status_msg = "Conectado: " .. engine:get_cwd()
    engine.is_executing = false
    core.redraw = true
  end
  self._client.on_output = function()
    engine.lines = engine._client.lines or {}
    engine:_evaluate_prompt_state()
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
    self._status_msg = "Falha ao iniciar PTY."
    return false
  end

  self._running = true
  self.is_executing = false
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

function TerminalEngine:_evaluate_prompt_state()
  local last_text = ""

  if self._client and self._client.current_line and #self._client.current_line > 0 then
    for _, seg in ipairs(self._client.current_line) do
      last_text = last_text .. (seg.text or "")
    end
  end

  if last_text == "" and self.lines and #self.lines > 0 then
    for i = #self.lines, math.max(1, #self.lines - 3), -1 do
      local line_item = self.lines[i]
      if line_item and line_item.segments and #line_item.segments > 0 then
        local line_str = ""
        for _, seg in ipairs(line_item.segments) do
          line_str = line_str .. (seg.text or "")
        end
        if line_str:find("%S") then
          last_text = line_str
          break
        end
      end
    end
  end

  local clean = last_text:gsub("%s+$", "")
  if clean:find(">$") or clean:find("%$$") or clean:find("#$") then
    if self.is_executing then
      self.is_executing = false
      core.redraw = true
    end

    -- Elimina linhas residuais sem texto
    while #self.lines > 0 do
      local last = self.lines[#self.lines]
      local has_text = false
      if last and last.segments then
        for _, s in ipairs(last.segments) do
          if s.text and s.text:find("%S") then
            has_text = true
            break
          end
        end
      end
      if not has_text then
        table.remove(self.lines)
      else
        break
      end
    end
  end
end

function TerminalEngine:_start_poller()
  if not core.add_thread then return end
  local engine = self
  core.add_thread(function()
    local idle_count = 0
    while engine._running do
      local had_output = engine:tick()
      if had_output then
        idle_count = 0
        coroutine.yield(0.005)
      else
        idle_count = idle_count + 1
        local nap = idle_count > 4 and 0.03 or 0.01
        coroutine.yield(nap)
      end
    end
  end, engine)
end

function TerminalEngine:tick()
  if not self._client then return false end
  local changed = false

  if not self._client._handshake_done then
    if self._client.poll_handshake then
      changed = self._client:poll_handshake()
    else
      changed = self._client:poll()
    end
  else
    changed = self._client:poll()
  end

  if self._client.lines then
    self.lines = self._client.lines
  end

  if #self.lines ~= self._last_line_count then
    self._last_line_count = #self.lines
    self:_evaluate_prompt_state()
    core.redraw = true
    return true
  end

  return changed
end

function TerminalEngine:_line_height()
  local font = self:get_font()
  return (font and font:get_height() or 14) + 2
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

function TerminalEngine:update_viewport(view_w, view_h)
  if view_w <= 0 or view_h <= 0 then return end
  self._last_view_w = view_w
  self._last_view_h = view_h

  local font = self:get_font()
  local char_w = math.max(1, font:get_width(" "))
  local line_h = self:_line_height()

  local useful_h = math.max(line_h * 2, view_h - 54)
  local useful_w = math.max(char_w * 10, view_w - 24)

  local cols = math.max(20, math.floor(useful_w / char_w))
  local rows = math.max(4, math.floor(useful_h / line_h))

  if cols ~= self._cols or rows ~= self._rows then
    self._cols = cols
    self._rows = rows
    if self._client and self._client.is_connected then
      self._client:send_resize(cols, rows)
    end
  end

  if self._auto_scroll then self:scroll_to_bottom() end
end

function TerminalEngine:scroll_to_bottom()
  local line_h = self:_line_height()
  local useful_h = math.max(line_h * 2, (self._last_view_h or 300) - 54)
  local count = self:get_effective_content_lines()
  local total_h = math.max(1, count) * line_h

  if total_h <= useful_h then
    self.scroll_y = 0
  else
    self.scroll_y = total_h - useful_h
  end
  core.redraw = true
end

function TerminalEngine:scroll_by(delta)
  local line_h = self:_line_height()
  local useful_h = math.max(line_h * 2, (self._last_view_h or 300) - 54)
  local count = self:get_effective_content_lines()
  local content_h = math.max(1, count) * line_h
  local max_scroll = math.max(0, content_h - useful_h)

  self.scroll_y = math.max(0, math.min(max_scroll, self.scroll_y - delta))
  self._auto_scroll = (self.scroll_y >= max_scroll - 4)
  core.redraw = true
end

function TerminalEngine:send_text(text)
  if not self._client or not self._running then return end
  if text and text ~= "" then
    self._client:send_input(text)
    self._auto_scroll = true
    self:tick()
  end
end

function TerminalEngine:send_key(seq)
  self:send_text(seq)
end

function TerminalEngine:execute_command(cmd)
  cmd = (cmd or self.input_text or ""):gsub("[\r\n]", "")
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

  if not self.is_executing and clean_cmd ~= "" and #clean_cmd > 2 then
    self:save_command_to_history(cmd)
  end

  if cmd ~= "" then
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
    self.is_executing = false
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
  if self._client then self._client:clear_screen() end
  self.lines = {}
  self.scroll_y = 0
  self.input_text = ""
  self.input_cursor = 1
  self._all_selected = false
  self.suggestions = {}
  core.redraw = true
end

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
  local trimmed = before:gsub("%s*[^%s]+%s*$", "")
  self.input_text = trimmed .. after
  self.input_cursor = #trimmed + 1
  core.redraw = true
end

function TerminalEngine:load_project_history()
  self.history = {}
  local dox_dir = self:get_cwd() .. "/.doxoade"
  pcall(function() system.mkdir(dox_dir) end)
  local f = io.open(dox_dir .. "/terminal_history.txt", "r")
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
  local dox_dir = self:get_cwd() .. "/.doxoade"
  pcall(function() system.mkdir(dox_dir) end)
  local f = io.open(dox_dir .. "/terminal_history.txt", "a")
  if f then
    f:write(cmd_str .. "\n")
    f:close()
  end
end

function TerminalEngine:launch_external_terminal(as_admin)
  local proj = self:get_cwd()
  local sep = PATHSEP or "/"
  local _, venv_base = detect_project_venv(proj)
  local venv_act = (venv_base or proj) .. sep .. "venv" .. sep .. "Scripts" .. sep .. "activate.bat"
  local has_venv = system.get_file_info(venv_act) ~= nil
  local act_cmd = has_venv and string.format(' && "%s"', venv_act) or ""

  if PLATFORM == "Windows" then
    if as_admin then
      local ps_inner = string.format("cd /d '%s'%s", proj, act_cmd)
      local cmd = string.format('powershell.exe -NoProfile -Command "Start-Process cmd.exe -ArgumentList \'/k %s\' -Verb RunAs"', ps_inner)
      pcall(system.exec, cmd)
    else
      local has_wt = false
      local localapp = os.getenv("LOCALAPPDATA")
      if localapp then
        local wt_exe = localapp .. "\\Microsoft\\WindowsApps\\wt.exe"
        has_wt = system.get_file_info(wt_exe) ~= nil
      end

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

function TerminalEngine:launch_real_terminal(admin)
  return self:launch_external_terminal(admin)
end

-- =============================================================================
-- 🏛️ GERENCIADOR DE SESSÕES MULTI-TERMINAL
-- =============================================================================
local SessionManager = {
  sessions = {},
  active_index = 1,
}

function SessionManager.get_active()
  if #SessionManager.sessions == 0 then
    local initial = TerminalEngine.new()
    table.insert(SessionManager.sessions, initial)
    SessionManager.active_index = 1
  end
  return SessionManager.sessions[SessionManager.active_index] or SessionManager.sessions[1]
end

function SessionManager.new_session(opts)
  opts = opts or {}
  if not opts.cwd and core.project_directories and #core.project_directories > 0 then
    for _, p in ipairs(core.project_directories) do
      local p_path = (system.absolute_path(type(p) == "table" and (p.path or p.name) or p) or ""):gsub("\\", "/")
      if not p_path:find("test_deploy") and not p_path:find("sandbox") then
        local already_has = false
        for _, s in ipairs(SessionManager.sessions) do
          if s:get_cwd():lower() == p_path:lower() then already_has = true; break end
        end
        if not already_has then
          opts.cwd = p_path
          break
        end
      end
    end
  end

  local s = TerminalEngine.new(opts)
  table.insert(SessionManager.sessions, s)
  SessionManager.active_index = #SessionManager.sessions
  s:ensure_started()
  core.redraw = true
  if core.log then
    core.log(string.format("🚀 [TERMINAL] Nova sessão: %s", s:get_display_name()))
  end
  return s
end

function SessionManager.switch_session(idx)
  if idx >= 1 and idx <= #SessionManager.sessions then
    SessionManager.active_index = idx
    local active = SessionManager.get_active()
    active:ensure_started()
    core.redraw = true
  end
end

function SessionManager.next_session()
  if #SessionManager.sessions > 1 then
    local next_i = (SessionManager.active_index % #SessionManager.sessions) + 1
    SessionManager.switch_session(next_i)
  end
end

function SessionManager.prev_session()
  if #SessionManager.sessions > 1 then
    local prev_i = ((SessionManager.active_index - 2 + #SessionManager.sessions) % #SessionManager.sessions) + 1
    SessionManager.switch_session(prev_i)
  end
end

function SessionManager.close_session(idx)
  idx = idx or SessionManager.active_index
  if #SessionManager.sessions <= 1 then
    local cur = SessionManager.get_active()
    cur:clear_screen()
    return
  end
  if idx >= 1 and idx <= #SessionManager.sessions then
    local cur = table.remove(SessionManager.sessions, idx)
    cur:stop()
    SessionManager.active_index = math.max(1, math.min(SessionManager.active_index, #SessionManager.sessions))
    local active = SessionManager.get_active()
    active:ensure_started()
    core.redraw = true
  end
end

function SessionManager.close_active()
  SessionManager.close_session(SessionManager.active_index)
end

function SessionManager.get_or_create_for_project(proj_path)
  if not proj_path or proj_path == "" then return SessionManager.get_active() end
  local norm_target = (system.absolute_path(proj_path) or proj_path):gsub("\\", "/")

  for i, s in ipairs(SessionManager.sessions) do
    if s:get_cwd():lower() == norm_target:lower() then
      SessionManager.switch_session(i)
      return s
    end
  end

  return SessionManager.new_session({ cwd = norm_target })
end

function SessionManager.list_sessions()
  local list = {}
  for i, s in ipairs(SessionManager.sessions) do
    table.insert(list, {
      index = i,
      id = s.id,
      name = s:get_display_name(),
      cwd = s:get_cwd(),
      shell = s:short_shell_label(),
      is_active = (i == SessionManager.active_index),
      is_executing = s.is_executing,
    })
  end
  return list
end

-- ── Histórico Cíclico e Persistente do Terminal ──────────────────────────────
function TerminalEngine:history_prev()
  if not self.history or #self.history == 0 then return end
  
  -- Se está na posição inicial (fora do histórico), salva o rascunho atual
  if self.history_idx > #self.history then
    self._draft_input = self.input_text
  end

  if self.history_idx > 1 then
    self.history_idx = self.history_idx - 1
    self.input_text = self.history[self.history_idx] or ""
    self.input_cursor = #self.input_text + 1
    self._all_selected = false
    self.input_sel_from = nil
    core.redraw = true
  end
end

function TerminalEngine:history_next()
  if not self.history or #self.history == 0 then return end

  if self.history_idx < #self.history then
    self.history_idx = self.history_idx + 1
    self.input_text = self.history[self.history_idx] or ""
    self.input_cursor = #self.input_text + 1
  else
    self.history_idx = #self.history + 1
    self.input_text = self._draft_input or ""
    self.input_cursor = #self.input_text + 1
  end
  self._all_selected = false
  self.input_sel_from = nil
  core.redraw = true
end

-- ── Salto de Palavras no Input (Ctrl + Setas) ─────────────────────────────────
function TerminalEngine:move_word_left()
  local pos = self.input_cursor - 1
  if pos <= 1 then
    self.input_cursor = 1
    core.redraw = true
    return
  end
  local before = self.input_text:sub(1, pos)
  local new_pos = before:match("^.*()[%s_%-/\\][^%s_%-/\\]") or 1
  self.input_cursor = math.max(1, new_pos)
  self._all_selected = false
  self.input_sel_from = nil
  core.redraw = true
end

function TerminalEngine:move_word_right()
  local pos = self.input_cursor
  local len = #self.input_text
  if pos >= len + 1 then return end
  local after = self.input_text:sub(pos)
  local rel = after:match("^[^%s_%-/\\]*[%s_%-/\\]+()") or (len - pos + 2)
  self.input_cursor = math.min(len + 1, pos + rel - 1)
  self._all_selected = false
  self.input_sel_from = nil
  core.redraw = true
end

rawset(_G, "_DOXOADE_TERMINAL_SESSION_MGR", SessionManager)

local terminal_proxy = setmetatable({}, {
  __index = function(_, k)
    local active = SessionManager.get_active()
    local v = active[k]
    if type(v) == "function" then
      return function(_, ...)
        return v(active, ...)
      end
    end
    return v
  end,
  __newindex = function(_, k, v)
    local active = SessionManager.get_active()
    active[k] = v
  end
})

rawset(_G, "_DOXOADE_TERMINAL_ENGINE", terminal_proxy)
rawset(_G, "TerminalRealEngine", TerminalEngine)

command.add(nil, {
  ["doxoade:terminal-launch-real"] = function()
    local term = SessionManager.get_active()
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
  ["doxoade:terminal-set-dir"] = function(dir)
    SessionManager.get_or_create_for_project(dir)
    command.perform("doxoade:terminal-launch-real")
  end,
  ["doxoade:terminal-new-tab"] = function()
    SessionManager.new_session()
    command.perform("doxoade:terminal-launch-real")
  end,
  ["doxoade:terminal-close-tab"] = function()
    SessionManager.close_active()
  end,
  ["doxoade:terminal-next-tab"] = function()
    SessionManager.next_session()
  end,
  ["doxoade:terminal-prev-tab"] = function()
    SessionManager.prev_session()
  end,
  ["doxoade:terminal-zoom-in"] = function()
    local term = SessionManager.get_active()
    if term then term:adjust_font_size(1) end
  end,
  ["doxoade:terminal-zoom-out"] = function()
    local term = SessionManager.get_active()
    if term then term:adjust_font_size(-1) end
  end,
  ["doxoade:terminal-zoom-reset"] = function()
    local term = SessionManager.get_active()
    if term then term:reset_font_size() end
  end,
  ["doxoade:terminal-send-interrupt"] = function()
    local term = SessionManager.get_active()
    if term then term:send_interrupt() end
  end,
  ["doxoade:terminal-launch-external"] = function()
    local term = SessionManager.get_active()
    if term then term:launch_external_terminal(false) end
  end,
  ["doxoade:terminal-launch-admin"] = function()
    local term = SessionManager.get_active()
    if term then term:launch_external_terminal(true) end
  end,
  ["doxoade:terminal-launch-admin-venv"] = function()
    command.perform("doxoade:terminal-launch-admin")
  end,
})

keymap.add {
  ["ctrl+alt+t"]       = "doxoade:terminal-launch-real",
  ["ctrl+alt+shift+t"] = "doxoade:terminal-launch-admin",
  ["ctrl+shift+t"]     = "doxoade:terminal-new-tab",
  ["ctrl+tab"]         = "doxoade:terminal-next-tab",
  ["ctrl+="]           = "doxoade:terminal-zoom-in",
  ["ctrl+-"]           = "doxoade:terminal-zoom-out",
  ["ctrl+0"]           = "doxoade:terminal-zoom-reset",
}

return terminal_proxy
