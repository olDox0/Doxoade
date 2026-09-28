-- doxoade/commands/lite_xl_systems/template/00_00_flow_shadow.lua
--[[
  🧭 DOXOADE SHADOW FLOW — Flight Recorder de Ações & Caixa-Preta Forense (V1.1 Strict-Safe)
  - Ring Buffer contínuo de 64 acionamentos em RAM O(1).
  - Rastreia a cadeia causal: Input -> Foco -> Comandos -> Queda.
  - Grava automaticamente a fita de acionamentos no crash (flow_blackbox.txt).
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)
local command = rawget(_G, "command") or (pcall(require, "core.command") and require("core.command") or nil)

local _RING_SIZE = 64
local _ring = {}
local _head = 1
local _total_logged = 0

-- Inicializa o anel com tabelas vazias pré-alocadas (Zero GC thrashing no hotpath)
for i = 1, _RING_SIZE do
  _ring[i] = { ts = 0, cat = "", act = "", ctx = "" }
end

local function flow_mark(cat, act, ctx)
  local node = _ring[_head]
  node.ts = os.clock()
  node.cat = tostring(cat or "SYS")
  node.act = tostring(act or "")
  node.ctx = tostring(ctx or "")
  _head = (_head % _RING_SIZE) + 1
  _total_logged = _total_logged + 1
end

rawset(_G, "doxoade_flow_mark", flow_mark)

-- Função para exportar a fita de acionamento em caso de falha
local function flow_dump_trail(limit)
  limit = limit or 25
  local count = math.min(_total_logged, _RING_SIZE)
  local start_idx = _head - count
  if start_idx <= 0 then start_idx = start_idx + _RING_SIZE end

  local lines = {
    "═══════════════════════════════════════════════════════════════════════════",
    "🧭 DOXOADE SHADOW FLOW — ÚLTIMA TRAJETÓRIA DE ACIONAMENTO ANTES DO CRASH:",
    "═══════════════════════════════════════════════════════════════════════════"
  }

  local collected = {}
  for i = 1, count do
    local idx = ((start_idx + i - 2) % _RING_SIZE) + 1
    table.insert(collected, _ring[idx])
  end

  local start_print = math.max(1, #collected - limit + 1)
  for i = start_print, #collected do
    local entry = collected[i]
    local step_no = i - #collected
    local line_str = string.format("  [%3d] [%-6s] %-28s | %s", step_no, entry.cat, entry.act, entry.ctx)
    table.insert(lines, line_str)
  end
  table.insert(lines, "═══════════════════════════════════════════════════════════════════════════\n")
  return table.concat(lines, "\n")
end

rawset(_G, "doxoade_flow_dump", flow_dump_trail)

-- Gravação síncrona de emergência no disco
local function save_blackbox_to_disk(err_msg, tb)
  pcall(function()
    local user_dir = USERDIR or "."
    local sep = PATHSEP or "/"
    local diag_dir = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics"
    if system and system.mkdir then pcall(system.mkdir, diag_dir) end

    local trail = flow_dump_trail(25)
    local f = io.open(diag_dir .. sep .. "flow_blackbox.txt", "w")
    if f then
      f:write(trail)
      if err_msg then f:write("\n[ERRO FATAL]:\n" .. tostring(err_msg) .. "\n") end
      if tb then f:write("\n[STACK TRACE]:\n" .. tostring(tb) .. "\n") end
      f:flush()
      f:close()
    end
  end)
end

-- 1. Hook no Despachante de Comandos (com detecção de avalanche)
if command and command.perform then
  local orig_perform = command.perform
  local last_cmd = ""
  local last_time = 0
  local cascade_count = 0

  command.perform = function(cmd_name, ...)
    local now = os.clock()
    if cmd_name == last_cmd and (now - last_time) < 0.05 then
      cascade_count = cascade_count + 1
      if cascade_count == 8 then
        flow_mark("WARN", "CASCADE_LOOP", cmd_name .. " x" .. cascade_count)
      end
    else
      cascade_count = 1
      last_cmd = cmd_name
      last_time = now
    end

    flow_mark("CMD", cmd_name, "")
    return orig_perform(cmd_name, ...)
  end
end

-- 2. Hook de Foco de Janelas / Views
if core and core.set_active_view then
  local orig_set_active_view = core.set_active_view
  core.set_active_view = function(view)
    local vname = "UnknownView"
    if view and view.get_name then
      local ok, n = pcall(view.get_name, view)
      if ok and n then vname = n end
    elseif view and view.doc and view.doc.filename then
      vname = "Doc:" .. (view.doc.filename:match("[^/\\]+$") or view.doc.filename)
    end
    flow_mark("FOCUS", vname, "")
    return orig_set_active_view(view)
  end
end

-- 3. Hook em core.error
if core and core.error then
  local orig_core_error = core.error
  core.error = function(...)
    local msg = table.concat({...}, " ")
    flow_mark("ERROR", "core.error", msg:sub(1, 60))
    save_blackbox_to_disk(msg, debug.traceback("", 2))
    return orig_core_error(...)
  end
end

-- 4. Hook no Manipulador de Queda Fatal do Lite XL (core.on_error)
if core then
  local orig_on_error = core.on_error
  core.on_error = function(err)
    flow_mark("CRASH", "FATAL_ABORT", tostring(err):sub(1, 60))
    save_blackbox_to_disk(err, debug.traceback("", 2))
    if orig_on_error then return orig_on_error(err) end
  end
end

-- Limpa resíduos de crash de sessões anteriores no boot
pcall(function()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local old_blackbox = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics" .. sep .. "flow_blackbox.txt"
  if system and system.get_file_info(old_blackbox) then
    os.remove(old_blackbox)
  end
end)

flow_mark("BOOT", "flow_shadow_init", "Flight Recorder Armado")

