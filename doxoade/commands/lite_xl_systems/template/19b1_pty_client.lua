-- doxoade/commands/lite_xl_systems/template/19b1_pty_client.lua
--[[
  ⚡ DOXOADE PTY FILE-STREAM CLIENT (V33.0 Fast-Throughput Engine)
  - Latência zero: sem yields artificiais durante o parsing de buffers.
  - Leitura em bloco atômico via f:read com I/O instantâneo.
]]
local core = require "core"

local AnsiParser = rawget(_G, "AnsiParser") or rawget(_G, "_DOXOADE_ANSI_PARSER")
if not AnsiParser then
  AnsiParser = {
    new = function()
      return {
        parse = function(self, data)
          return { { text = tostring(data or ""), style = { fg = { 229, 229, 229, 255 }, bg = nil } } }
        end,
        reset_style = function(self) end
      }
    end
  }
end

local PTYClient = {}
PTYClient.__index = PTYClient
local MAX_SCROLLBACK = 5000

function PTYClient.new(config)
  local cfg = config or {}
  local self = setmetatable({}, PTYClient)

  self.id = cfg.id or "default"
  self.shell = cfg.shell or "cmd"
  self.cols = cfg.cols or 120
  self.rows = cfg.rows or 30
  self.cwd = cfg.cwd or nil
  self.debug = cfg.debug or false

  self.is_connected = false
  self._handshake_done = false
  self.server_pid = 0

  self.lines = {}
  self.current_line = {}
  self.scroll_y = 0
  self.parser = AnsiParser.new()

  -- 🎯 CANAL IPC EXCLUSIVO POR SESSÃO (Zero colisão entre abas)
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  self.ipc_dir = user_dir .. sep .. ".doxoade" .. sep .. "terminal_pty_ipc_" .. tostring(self.id)
  pcall(function() system.mkdir(self.ipc_dir) end)

  self.file_in = self.ipc_dir .. sep .. "pty_in.bin"
  self.file_out = self.ipc_dir .. sep .. "pty_out.bin"
  self.file_cmd = self.ipc_dir .. sep .. "pty_cmd.json"
  self.file_status = self.ipc_dir .. sep .. "pty_status.json"

  self._last_out_offset = 0

  self.on_output = nil
  self.on_exit = nil
  self.on_ready = nil

  return self
end

function PTYClient:_find_python()
  local sep = PATHSEP or "/"
  local user_dir = USERDIR or "."

  -- 1. Varre venvs dentro de todos os projetos abertos no Lite XL
  local check_dirs = {}
  if self.cwd then table.insert(check_dirs, self.cwd) end
  if core.project_directories then
    for _, d in ipairs(core.project_directories) do
      local p = type(d) == "table" and (d.path or d.name) or d
      table.insert(check_dirs, p)
    end
  end
  if core.project_dir then table.insert(check_dirs, core.project_dir) end

  for _, dir in ipairs(check_dirs) do
    local p_str = tostring(dir)
    local v1 = (p_str .. sep .. "venv" .. sep .. "Scripts" .. sep .. "python.exe"):gsub("/", "\\")
    if system and system.get_file_info and system.get_file_info(v1) then return v1 end
    local v2 = (p_str .. sep .. ".venv" .. sep .. "Scripts" .. sep .. "python.exe"):gsub("/", "\\")
    if system and system.get_file_info and system.get_file_info(v2) then return v2 end
  end

  -- 2. Variável de ambiente VIRTUAL_ENV do Windows
  local venv_env = os.getenv("VIRTUAL_ENV")
  if venv_env and venv_env ~= "" then
    local py = (venv_env .. sep .. "Scripts" .. sep .. "python.exe"):gsub("/", "\\")
    if system and system.get_file_info and system.get_file_info(py) then return py end
  end

  -- 3. Âncoras locais (apenas se o arquivo existir fisicamente no bluebaby)
  local home_dir = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
  local anchors = {
    user_dir .. sep .. ".doxoade" .. sep .. "python_path.txt",
    home_dir .. sep .. ".doxoade" .. sep .. "python_path.txt",
  }
  for _, ap in ipairs(anchors) do
    local f = io.open(ap, "r")
    if f then
      local py = (f:read("*l") or ""):gsub("[\r\n]", ""):gsub("^%s*", ""):gsub("%s*$", "")
      f:close()
      if py ~= "" and system.get_file_info and system.get_file_info(py) then
        return py:gsub("/", "\\")
      end
    end
  end

  -- 4. Instalações padrão do Python no Windows 11 (AppData)
  local local_app = os.getenv("LOCALAPPDATA")
  if local_app then
    for _, ver in ipairs({ "Python312", "Python311", "Python310" }) do
      local py_std = (local_app .. [[\Programs\Python\]] .. ver .. [[\python.exe]])
      if system and system.get_file_info and system.get_file_info(py_std) then
        return py_std
      end
    end
  end

  return "python"
end

function PTYClient:spawn()
  local python_exe = self:_find_python()

  pcall(os.remove, self.file_in)
  pcall(os.remove, self.file_out)
  pcall(os.remove, self.file_cmd)
  pcall(os.remove, self.file_status)
  self._last_out_offset = 0
  self.lines = {}
  self.current_line = {}

  local target_cwd = self.cwd and (system.absolute_path(self.cwd) or self.cwd):gsub("/", "\\") or ""
  
  -- 🎯 Resolve a raiz do DoxOADE para injetar no PYTHONPATH
  local root_proj = target_cwd ~= "" and target_cwd or (core.project_dir or ".")
  local abs_root = (system.absolute_path(root_proj) or root_proj):gsub("/", "\\")

  -- Injeção atômica de PYTHONPATH para o bluebaby sempre encontrar o módulo doxoade
  local cmd = string.format(
    'cmd /c "set PYTHONPATH=%s;%%PYTHONPATH%% && start /b \"\" \"%s\" -m doxoade.tools.terminal_pty.pty_file_daemon --ipc-dir \"%s\" --shell \"%s\" --cols %d --rows %d',
    abs_root, python_exe, self.ipc_dir, self.shell, self.cols, self.rows
  )
  if target_cwd ~= "" then
    cmd = cmd .. string.format(' --cwd \"%s\""', target_cwd)
  else
    cmd = cmd .. '"'
  end

  local ok = pcall(system.exec, cmd)
  if not ok then
    if core.log then core.log("❌ [PTY] Falha ao invocar pty_file_daemon.") end
    return false
  end

  self.is_connected = true
  self._handshake_done = false
  return true
end

function PTYClient:poll()
  if not self.is_connected then return false end

  -- Handshake
  if not self._handshake_done then
    local f_st = io.open(self.file_status, "r")
    if f_st then
      local content = f_st:read("*a") or ""
      f_st:close()
      if content:find('"alive":%s*true') then
        self._handshake_done = true
        self.server_pid = tonumber(content:match('"pid":%s*(%d+)')) or 0
        if self.on_ready then pcall(self.on_ready, self) end
        core.redraw = true
        return true
      elseif content:find('"alive":%s*false') then
        local err_msg = content:match('"error"%s*:%s*"([^"]+)"') or "Falha no backend PTY"
        if core.log then core.log("❌ [PTY Bluebaby] " .. err_msg) end
        self:close()
        return false
      end
    end
  end

  local finfo = system.get_file_info(self.file_out)
  local cur_size = finfo and (finfo.size or 0) or 0

  if cur_size > self._last_out_offset then
    local f = io.open(self.file_out, "rb")
    if f then
      f:seek("set", self._last_out_offset)
      local new_data = f:read(cur_size - self._last_out_offset)
      self._last_out_offset = cur_size
      f:close()
      if new_data and new_data ~= "" then
        self:_handle_output(new_data)
        return true
      end
    end
  end
  return false
end

function PTYClient:_handle_output(payload)
  local parsed_segments = self.parser:parse(payload)

  for idx = 1, #parsed_segments do
    local seg = parsed_segments[idx]

    if seg.control == "clear" then
      self.lines = {}
      self.current_line = {}
      self.scroll_y = 0
    elseif seg.control == "lf" or seg.text == "\n" then
      table.insert(self.lines, { segments = self.current_line })
      self.current_line = {}
      if #self.lines > MAX_SCROLLBACK then
        table.remove(self.lines, 1)
      end
    else
      table.insert(self.current_line, seg)
    end
  end

  if self.on_output then
    pcall(self.on_output, self)
  end
  core.redraw = true
end

function PTYClient:send_input(text)
  if not text or text == "" then return end
  local f = io.open(self.file_in, "ab")
  if f then
    f:write(text)
    f:flush()
    f:close()
  end
end

function PTYClient:send_resize(cols, rows)
  self.cols = cols or 120
  self.rows = rows or 30
  local f = io.open(self.file_cmd, "w")
  if f then
    f:write(string.format('{"action": "resize", "cols": %d, "rows": %d}\n', self.cols, self.rows))
    f:flush()
    f:close()
  end
end

function PTYClient:send_interrupt()
  -- 1. Sinal estruturado no pty_cmd.json
  local f = io.open(self.file_cmd, "w")
  if f then
    f:write('{"action": "interrupt"}\n')
    f:flush()
    f:close()
  end
  -- 2. Injeção direta de byte \x03 (ETX / Ctrl+C) no stdin
  self:send_input("\x03\r\n")
end

function PTYClient:clear_screen()
  self.lines = {}
  self.current_line = {}
  self.scroll_y = 0
  if self.parser and self.parser.reset_style then
    self.parser:reset_style()
  end
  core.redraw = true
end

function PTYClient:poll_handshake()
  return self:poll()
end

function PTYClient:close()
  if self.is_connected then
    local f = io.open(self.file_cmd, "w")
    if f then
      f:write('{"action": "shutdown"}\n')
      f:flush()
      f:close()
    end
  end
  self.is_connected = false
  self._handshake_done = false
  if self.on_exit then pcall(self.on_exit, 0) end
  core.redraw = true
end

rawset(_G, "PTYClient", PTYClient)
rawset(_G, "_DOXOADE_PTY_CLIENT", PTYClient)
return PTYClient
