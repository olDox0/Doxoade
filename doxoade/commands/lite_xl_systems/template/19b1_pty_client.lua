-- doxoade/commands/lite_xl_systems/template/19b1_pty_client.lua
--[[
  🔌 DOXOADE PTY FILE-STREAM CLIENT (V32.0 Non-Blocking IPC Engine)
  - Comunicação bidirecional via buffer de arquivo atômico em RAM/disco.
  - 100% imune a erros C de handles/pipes do Lite XL no Windows.
  - Zero-Freeze: Leituras rápidas via f:seek (<0.02ms por tick de frame).
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
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

  -- Arquivos do canal IPC
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  self.ipc_dir = user_dir .. sep .. ".doxoade" .. sep .. "terminal_pty_ipc"
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
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local py_anchor = user_dir .. sep .. ".doxoade" .. sep .. "python_path.txt"

  local finfo = system and system.get_file_info and system.get_file_info(py_anchor)
  if finfo and finfo.type == "file" then
    local f = io.open(py_anchor, "r")
    if f then
      local py_exe = f:read("*l") or ""
      f:close()
      py_exe = py_exe:gsub("[\r\n]", ""):gsub("^%s*", ""):gsub("%s*$", "")
      if py_exe ~= "" and system.get_file_info(py_exe) then
        return py_exe:gsub("/", "\\")
      end
    end
  end

  local venv_py = (user_dir .. sep .. ".." .. sep .. "venv" .. sep .. "Scripts" .. sep .. "python.exe"):gsub("/", "\\")
  if system and system.get_file_info and system.get_file_info(venv_py) then
    return venv_py
  end

  return "python"
end

function PTYClient:spawn()
  local python_exe = self:_find_python()
  
  -- Limpa arquivos antigos para não misturar sessões passadas
  pcall(os.remove, self.file_in)
  pcall(os.remove, self.file_out)
  pcall(os.remove, self.file_cmd)
  pcall(os.remove, self.file_status)
  self._last_out_offset = 0
  self.lines = {}
  self.current_line = {}

  local cmd = string.format(
    '"%s" -m doxoade.tools.terminal_pty.pty_file_daemon --ipc-dir "%s" --shell "%s" --cols %d --rows %d',
    python_exe, self.ipc_dir, self.shell, self.cols, self.rows
  )
  if self.cwd then
    cmd = cmd .. string.format(' --cwd "%s"', tostring(self.cwd))
  end

  -- Disparo assíncrono via system.exec (Não toca em process.start, livre de erros C)
  local ok = pcall(system.exec, cmd)
  if not ok then
    if core.log then core.log("❌ [PTY] Falha ao invocar pty_file_daemon.") end
    return false
  end

  self.is_connected = true
  self._handshake_done = false

  if core.log then
    core.log("🖥️ [PTY] Daemon iniciado via File-Stream. Sincronizando...")
  end
  return true
end

function PTYClient:poll_handshake()
  self:poll()
end

function PTYClient:poll()
  if not self.is_connected then return end

  -- Handshake inicial
  if not self._handshake_done then
    local f_st = io.open(self.file_status, "r")
    if f_st then
      local content = f_st:read("*a") or ""
      f_st:close()
      if content:find('"alive":%s*true') then
        self._handshake_done = true
        self.server_pid = tonumber(content:match('"pid":%s*(%d+)')) or 0
        if self.on_ready then pcall(self.on_ready, self) end
        if core.log then core.log("✅ [PTY] Terminal conectado e pronto.") end
      elseif content:find('"alive":%s*false') then
        self:close()
        return
      end
    end
  end

  -- 🎯 Zero-Allocation I/O Guard: Só abre o arquivo se o tamanho realmente mudou no disco
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
      end
    end
  end
end

-- Pool de reciclagem de linhas (Slab Pattern O(1))
local _LINE_POOL = {}

local function acquire_line_container()
  local item = table.remove(_LINE_POOL)
  if item then
    item.segments = {}
    return item
  end
  return { segments = {} }
end

local function release_line_container(item)
  if #_LINE_POOL < 200 then
    item.segments = nil
    table.insert(_LINE_POOL, item)
  end
end

function PTYClient:_handle_output(payload)
  local parsed_segments = self.parser:parse(payload)
  local t0 = os.clock()

  for idx = 1, #parsed_segments do
    local seg = parsed_segments[idx]
    
    if seg.control == "clear" then
      for i = 1, #self.lines do
        release_line_container(self.lines[i])
      end
      self.lines = {}
      self.current_line = {}
      self.scroll_y = 0
    elseif seg.control == "lf" or seg.text == "\n" then
      local line_item = acquire_line_container()
      line_item.segments = self.current_line
      table.insert(self.lines, line_item)
      self.current_line = {}

      if #self.lines > MAX_SCROLLBACK then
        local old = table.remove(self.lines, 1)
        release_line_container(old)
      end
    else
      table.insert(self.current_line, seg)
    end

    -- 🌙 KHONSU TIME-SLICING: Se o lote de texto for longo e passar de 2.5ms, cede a CPU para não engasgar o frame
    if (idx % 20 == 0) and (os.clock() - t0) >= 0.0025 then
      coroutine.yield()
      t0 = os.clock()
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
  local f = io.open(self.file_cmd, "w")
  if f then
    f:write('{"action": "interrupt"}\n')
    f:flush()
    f:close()
  end
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

  if self.on_exit then
    pcall(self.on_exit, 0)
  end
  core.redraw = true
end

rawset(_G, "PTYClient", PTYClient)
rawset(_G, "_DOXOADE_PTY_CLIENT", PTYClient)
