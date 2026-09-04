-- doxoade/commands/lite_xl_systems/template/10_forensic_engine.lua
--[[
  🦅 DOXOADE FORENSIC ENGINE & LIVE TELEMETRY (CHRONOS V2)
  - Medição de Frame Spikes (>16.6ms) no pipeline gráfico.
  - Contador de Frequência de Comandos (100x vs 2x).
  - Telemetria de Memória GC e Exportação Contínua de profiler_telemetry.json.
]]
local core = require "core"
local config = require "core.config"
local RootView = require "core.rootview"
local command = require "core.command"

local user_dir = USERDIR or "."
local sep = PATHSEP or "/"
local diag_dir = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics"
pcall(function() system.mkdir(diag_dir) end)

local telemetry_json_path = diag_dir .. sep .. "profiler_telemetry.json"
local report_path = diag_dir .. sep .. "forensic_report.txt"

-- =============================================================================
-- 1. ESTRUTURA GLOBAL DO PROFILER (CHRONOS)
-- =============================================================================
local Profiler = {
  frame_count = 0,
  current_fps = 60.0,
  last_fps_calc = os.clock(),
  frame_spikes = {},       -- Histórico dos últimos 20 spikes (>16.6ms)
  cmd_frequencies = {},    -- Mapa de frequências: [cmd_name] = count
  thread_bottlenecks = {}, -- Histórico de threads demoradas
  gc_memory_kb = collectgarbage("count"),
  boot_timestamp = os.date("%Y-%m-%d %H:%M:%S"),
  total_boot_time_ms = 0.0,
}

rawset(_G, "_DOXOADE_PROFILER", Profiler)



local forensic_data = {
    errors = {},
    performance = {},
    env_plugins = {}
}

rawset(_G, "_DOXOADE_FORENSIC_DATA", forensic_data)
rawset(_G, "forensic_data", forensic_data)

local function safe_error_message(...)
  local args = { ... }

  for i = 1, select("#", ...) do
    args[i] = tostring(args[i])
  end

  return table.concat(args, " ")
end

local original_core_error = core.error

function core.error(...)
  local msg = safe_error_message(...)
  local tb = debug.traceback("", 2)

  local culprit = "core"
  local culprit_file = "unknown"
  local culprit_line = 0

  -- Parsing resiliente do traceback para localizar o arquivo causador fora do core
  for line in tb:gmatch("[^\r\n]+") do
    if not line:match("core[/\\]init%.lua") and
       not line:match("10_forensic_engine%.lua") and
       not line:match("%[C%]:") and
       not line:match("%[string") then
      local file, ln = line:match("(.-):(%d+):")
      if file and not file:match("core[/\\]") then
        culprit_file = file
        culprit_line = tonumber(ln) or 0
        culprit = file:match("plugins[/\\](.-)[/\\]") or
                  file:match("plugins[/\\](.-)%.lua") or "user_config"
        break
      end
    end
  end

  pcall(function()
    table.insert(forensic_data.errors, {
      msg = msg,
      culprit = culprit,
      file = culprit_file,
      line = culprit_line,
      trace = tb,
      time = os.date("%H:%M:%S"),
    })
  end)

  if original_core_error then
    return original_core_error(...)
  end
end

local original_add_dir = core.add_project_directory

function core.add_project_directory(path, ...)
  local start = os.clock()

  local ok, res
  if original_add_dir then
    ok, res = pcall(original_add_dir, path, ...)
  else
    ok = false
    res = "original core.add_project_directory is nil"
  end

  local elapsed = os.clock() - start

  pcall(function()
    table.insert(forensic_data.performance, {
      action = "index_project",
      target = tostring(path),
      duration = string.format("%.3f", elapsed),
      status = elapsed > 1.5 and "BOTTLENECK" or "OK",
      time = os.date("%H:%M:%S"),
    })
  end)

  if ok then
    return res
  else
    error(res)
  end
end

local function write_forensic_report()
  local f = io.open(report_path, "w")
  if not f then return end

  f:write("=== DOXOADE FORENSIC REPORT ===\n")
  f:write(string.format("Generated: %s\n\n", os.date("%Y-%m-%d %H:%M:%S")))

  if #forensic_data.errors == 0 then
    f:write("No errors captured.\n")
  else
    for _, err in ipairs(forensic_data.errors) do
      f:write(string.format(
        "[%s] CULPRIT: %s | FILE: %s:%d\n",
        tostring(err.time or "??"),
        tostring(err.culprit or "unknown"),
        tostring(err.file or "unknown"),
        tonumber(err.line) or 0
      ))
      f:write(string.format("MSG: %s\n", tostring(err.msg or "")))
      f:write(string.format("TRACE: %s\n\n", tostring(err.trace or "")))
    end
  end

  f:write("\n")

  if #forensic_data.performance == 0 then
    f:write("No performance events.\n")
  else
    for _, perf in ipairs(forensic_data.performance) do
      f:write(string.format(
        "[%s] ACTION: %s | TARGET: %s | DURATION: %ss | STATUS: %s\n",
        perf.time,
        perf.action,
        perf.target,
        perf.duration,
        perf.status
      ))
    end
  end

  f:write("\n")
  f:write("Platform: " .. tostring(PLATFORM or "Unknown") .. "\n")
  f:write("Plugins: " .. table.concat(forensic_data.env_plugins, ", ") .. "\n")

  f:close()
end

core.add_thread(function()
  coroutine.yield(3.0)

  pcall(function()
    if core.plugins then
      for name, _ in pairs(core.plugins) do
        table.insert(forensic_data.env_plugins, name)
      end
    end

    write_forensic_report()
  end)
end)

-- =============================================================================
-- 2. HOOK GRÁFICO INTELIGENTE (Render Latency & Active Frame Measurement)
-- =============================================================================
local original_rootview_draw = RootView.draw
function RootView:draw(...)
  local t0 = os.clock()
  original_rootview_draw(self, ...)
  local elapsed_ms = (os.clock() - t0) * 1000

  Profiler.frame_count = Profiler.frame_count + 1
  Profiler.total_draw_ms = (Profiler.total_draw_ms or 0) + elapsed_ms
  Profiler.last_draw_time = os.clock()

  local target_fps = config.fps or 60
  local frame_budget_ms = (1000.0 / target_fps) * 1.15

  if elapsed_ms > frame_budget_ms then
    local active_name = (core.active_view and core.active_view.get_name and core.active_view:get_name()) or "workspace"
    table.insert(Profiler.frame_spikes, {
      timestamp = os.date("%H:%M:%S"),
      duration_ms = math.floor(elapsed_ms * 100) / 100,
      active_file = active_name,
      is_spike = true
    })
    if #Profiler.frame_spikes > 20 then
      table.remove(Profiler.frame_spikes, 1)
    end
  end
end

-- =============================================================================
-- 3. RASTREADOR DE FREQUÊNCIA DE COMANDOS (100x vs 2x)
-- =============================================================================
if command and command.perform then
  local original_command_perform = command.perform
  command.perform = function(cmd_name, ...)
    local name = tostring(cmd_name or "unknown")
    Profiler.cmd_frequencies[name] = (Profiler.cmd_frequencies[name] or 0) + 1
    return original_command_perform(cmd_name, ...)
  end
end

-- =============================================================================
-- 2. MONITORAMENTO DE CORROTINAS (DETECTOR DE THREADS BLOQUEANTES)
-- =============================================================================
local original_add_thread = core.add_thread
function core.add_thread(fn, target)
  local wrapped_fn = function()
    local co_t0 = os.clock()
    fn()
    local co_elapsed = (os.clock() - co_t0) * 1000
    if co_elapsed > 5.0 and #Profiler.thread_bottlenecks < 20 then
      table.insert(Profiler.thread_bottlenecks, {
        coroutine_id = tostring(target or "anonymous_thread"),
        duration_ms = tonumber(string.format("%.2f", co_elapsed)),
        status = "BLOCKING",
        time = os.date("%H:%M:%S")
      })
    end
  end
  return original_add_thread(wrapped_fn, target)
end

-- =============================================================================
-- 4. EXPORTAÇÃO INTELIGENTE (Separa Active Draw de Idle Sleep)
-- =============================================================================
local function export_profiler_telemetry()
  local now = os.clock()
  local is_idle = (now - (Profiler.last_draw_time or 0)) > 1.2

  local avg_draw_latency = 0.0
  local active_fps = 60.0

  if Profiler.frame_count > 0 and Profiler.total_draw_ms then
    avg_draw_latency = math.floor((Profiler.total_draw_ms / Profiler.frame_count) * 100) / 100
    if avg_draw_latency > 0 then
      active_fps = math.min(60.0, math.floor((1000.0 / avg_draw_latency) * 10) / 10)
    end
  end

  Profiler.frame_count = 0
  Profiler.total_draw_ms = 0
  Profiler.gc_memory_kb = math.floor(collectgarbage("count") * 10) / 10

  local json_parts = {
    "{\n",
    string.format('  "timestamp": %q,\n', os.date("%Y-%m-%d %H:%M:%S")),
    string.format('  "is_idle": %s,\n', is_idle and "true" or "false"),
    string.format('  "avg_draw_latency_ms": %.2f,\n', avg_draw_latency),
    string.format('  "active_fps": %.1f,\n', is_idle and (config.fps or 60.0) or active_fps),
    string.format('  "target_fps": %d,\n', config.fps or 60),
    string.format('  "gc_memory_kb": %.1f,\n', Profiler.gc_memory_kb),
    '  "frame_spikes": [\n'
  }

  for idx, sp in ipairs(Profiler.frame_spikes) do
    json_parts[#json_parts + 1] = string.format(
      '    { "timestamp": %q, "duration_ms": %.2f, "active_file": %q, "is_spike": true }%s\n',
      sp.timestamp, sp.duration_ms, sp.active_file, (idx < #Profiler.frame_spikes and "," or "")
    )
  end
  json_parts[#json_parts + 1] = '  ],\n  "command_frequencies": {\n'

  local cmd_entries = {}
  for k, v in pairs(Profiler.cmd_frequencies) do
    cmd_entries[#cmd_entries + 1] = string.format('    %q: %d', k, v)
  end
  json_parts[#json_parts + 1] = table.concat(cmd_entries, ",\n")
  json_parts[#json_parts + 1] = '\n  }\n}\n'

  pcall(function()
    local f = io.open(telemetry_json_path, "w")
    if f then
      f:write(table.concat(json_parts))
      f:flush()
      f:close()
    end
  end)
end

-- Thread de exportação periódica
if core.add_thread then
  core.add_thread(function()
    while true do
      coroutine.yield(2.5)
      export_profiler_telemetry()
    end
  end)
end

-- Exporta telemetria 3 segundos após o boot e periodicamente
core.add_thread(function()
  coroutine.yield(3.0)
  export_profiler_telemetry()
end)
