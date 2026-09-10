-- doxoade/commands/lite_xl_systems/template/10_forensic_engine.lua
--[[
  🦅 DOXOADE FORENSIC ENGINE & HIGH-RESOLUTION CHRONOS PROFILER (V3.1)
  - Medição de Boot Real (Exporta boot_telemetry.json com tempo e RAM reais por template).
  - Decomposição de Frame: Medição por componente gráfico (Abas, Editor, Gutter, Shelf).
  - Rastreamento Ativo de Corrotinas: Identificador blindado contra nil e registry limpo.
  - Monitoramento da taxa de alocação de memória do GC (KB/s).
  Compliance: ProDeNov 1.2.1, PASC-6.
]]
local core = require "core"
local config = require "core.config"
local RootView = require "core.rootview"
local command = require "core.command"
local Node = require "core.node"
local DocView = require "core.docview"

local user_dir = USERDIR or "."
local sep = PATHSEP or "/"
local diag_dir = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics"
pcall(function() system.mkdir(diag_dir) end)

local telemetry_json_path = diag_dir .. sep .. "profiler_telemetry.json"
local boot_json_path = diag_dir .. sep .. "boot_telemetry.json"
local report_path = diag_dir .. sep .. "forensic_report.txt"

-- =============================================================================
-- 📊 REGISTRY CENTRAL DO CHRONOS PROFILER
-- =============================================================================
local Profiler = {
  frame_count = 0,
  total_draw_ms = 0.0,
  current_fps = 60.0,
  last_fps_calc = os.clock(),
  last_draw_time = os.clock(),
  frame_spikes = {},
  cmd_frequencies = {},
  thread_bottlenecks = {},
  thread_stats = {}, -- [id] = { total_ms, calls, max_ms }
  subsystems = {
    tabs_ms = 0.0,
    body_ms = 0.0,
    gutter_ms = 0.0,
  },
  gc_memory_kb = collectgarbage("count"),
  gc_prev_kb = collectgarbage("count"),
  gc_growth_rate_kbs = 0.0,
  boot_timestamp = os.date("%Y-%m-%d %H:%M:%S"),
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
  for i = 1, select("#", ...) do args[i] = tostring(args[i]) end
  return table.concat(args, " ")
end

-- =============================================================================
-- 🩺 SONDAS FORENSES DE ERRO E PROJETO
-- =============================================================================
local original_core_error = core.error
function core.error(...)
  local msg = safe_error_message(...)
  local tb = debug.traceback("", 2)
  local culprit = "core"
  local culprit_file = "unknown"
  local culprit_line = 0

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

  if ok then return res else error(res) end
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
        "[%s] CULPRIT: %s | FILE: %s:%d\nMSG: %s\nTRACE: %s\n\n",
        tostring(err.time or "??"), tostring(err.culprit or "unknown"),
        tostring(err.file or "unknown"), tonumber(err.line) or 0,
        tostring(err.msg or ""), tostring(err.trace or "")
      ))
    end
  end
  f:close()
end

-- =============================================================================
-- 🚀 EXPORTADOR DO BOOT REAL (boot_telemetry.json)
-- =============================================================================
local function export_boot_telemetry()
  local report = rawget(_G, "_DOXOADE_BOOT_REPORT")
  if not report or not report.modules or #report.modules == 0 then return end

  local entries = {}
  local total_ms = 0.0
  local total_kb = 0.0

  for _, mod in ipairs(report.modules) do
    total_ms = total_ms + (mod.time_ms or 0)
    total_kb = total_kb + (mod.mem_kb or 0)
    local err_part = mod.error and string.format(', "error": %q', tostring(mod.error)) or ''
    table.insert(entries, string.format(
      '    { "name": %q, "status": %q, "time_ms": %.2f, "mem_kb": %.2f%s }',
      mod.name, mod.status, mod.time_ms or 0, mod.mem_kb or 0, err_part
    ))
  end

  local f = io.open(boot_json_path, "w")
  if f then
    f:write("{\n")
    f:write(string.format('  "timestamp": %q,\n', os.date("%Y-%m-%d %H:%M:%S")))
    f:write(string.format('  "total_modules": %d,\n', report.total or #report.modules))
    f:write(string.format('  "passed_modules": %d,\n', report.passed or 0))
    f:write(string.format('  "failed_modules": %d,\n', report.failed or 0))
    f:write(string.format('  "total_boot_ms": %.2f,\n', total_ms))
    f:write(string.format('  "total_boot_kb": %.2f,\n', total_kb))
    f:write('  "modules": [\n' .. table.concat(entries, ",\n") .. '\n  ]\n}\n')
    f:flush()
    f:close()
  end
end

-- =============================================================================
-- 👁️ DECOMPOSIÇÃO DE FRAME E SUBSISTEMAS GRÁFICOS
-- =============================================================================
local original_draw_tabs = Node.draw_tabs
if original_draw_tabs then
  Node.draw_tabs = function(self, ...)
    local t0 = os.clock()
    local res = original_draw_tabs(self, ...)
    Profiler.subsystems.tabs_ms = Profiler.subsystems.tabs_ms + ((os.clock() - t0) * 1000)
    return res
  end
end

local original_draw_line_body = DocView.draw_line_body
if original_draw_line_body then
  DocView.draw_line_body = function(self, ...)
    local t0 = os.clock()
    local res = original_draw_line_body(self, ...)
    Profiler.subsystems.body_ms = Profiler.subsystems.body_ms + ((os.clock() - t0) * 1000)
    return res
  end
end

local original_draw_line_gutter = DocView.draw_line_gutter
if original_draw_line_gutter then
  DocView.draw_line_gutter = function(self, ...)
    local t0 = os.clock()
    local res = original_draw_line_gutter(self, ...)
    Profiler.subsystems.gutter_ms = Profiler.subsystems.gutter_ms + ((os.clock() - t0) * 1000)
    return res
  end
end

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

  -- Registra spike apenas se passou do orçamento E respeitando intervalo mínimo de 1.0s
  local now_clock = os.clock()
  if elapsed_ms > frame_budget_ms and (now_clock - (Profiler._last_spike_record or 0)) >= 1.0 then
    Profiler._last_spike_record = now_clock
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
-- 🧵 MONITOR DE CORROTINAS (IDENTIFICADOR 100% BLINDADO CONTRA NIL)
-- =============================================================================
local function extract_safe_thread_id(fn, target)
  if target then return tostring(target) end
  local fn_str = tostring(fn)
  local hex_addr = fn_str:match("0x(%x+)") or fn_str:match("(%x%x%x%x+)")
  if hex_addr then
    return "worker_" .. hex_addr
  end
  return "worker_" .. tostring(math.random(1000, 9999))
end

local original_add_thread = core.add_thread
function core.add_thread(fn, target)
  -- 🛡️ Identificador blindado: NUNCA concatena nil
  local thread_id = extract_safe_thread_id(fn, target)
  Profiler.thread_stats[thread_id] = Profiler.thread_stats[thread_id] or { total_ms = 0.0, calls = 0, max_ms = 0.0 }

  local wrapped_fn = function()
    local co_t0 = os.clock()
    local ok, err = xpcall(fn, debug.traceback)
    local co_elapsed = (os.clock() - co_t0) * 1000

    local st = Profiler.thread_stats[thread_id]
    if st then
      st.total_ms = st.total_ms + co_elapsed
      st.calls = st.calls + 1
      if co_elapsed > st.max_ms then st.max_ms = co_elapsed end
    end

    if not ok then
      local err_msg = tostring(err or "Erro em corrotina")
      if core.error then
        core.error(string.format("👻 [THREAD CRASH] %s: %s", thread_id, err_msg))
      end
      return
    end

    if co_elapsed > 10.0 and #Profiler.thread_bottlenecks < 20 then
      table.insert(Profiler.thread_bottlenecks, {
        coroutine_id = thread_id,
        duration_ms = tonumber(string.format("%.2f", co_elapsed)),
        status = "BLOCKING",
        time = os.date("%H:%M:%S")
      })
    end
  end

  -- Se target for string de telemetria interna, passa nil para o Lite XL usar table.insert
  local pass_target = (type(target) == "string") and nil or target
  return original_add_thread(wrapped_fn, pass_target)
end

-- =============================================================================
-- 📤 EXPORTADOR CONTÍNUO DE TELEMETRIA (profiler_telemetry.json)
-- =============================================================================
local function export_profiler_telemetry()
  local now = os.clock()
  local dt = now - (Profiler.last_fps_calc or now)
  local is_idle = (now - (Profiler.last_draw_time or 0)) > 1.2
  local fc = math.max(1, Profiler.frame_count)

  local avg_draw_latency = math.floor((Profiler.total_draw_ms / fc) * 100) / 100
  local calculated_fps = (dt > 0 and Profiler.frame_count > 0)
    and math.min(config.fps or 60.0, math.floor((Profiler.frame_count / dt) * 10) / 10)
    or (config.fps or 60.0)

  local cur_gc = collectgarbage("count")
  local gc_diff = cur_gc - Profiler.gc_prev_kb
  Profiler.gc_growth_rate_kbs = (dt > 0) and math.max(0, math.floor((gc_diff / dt) * 10) / 10) or 0.0
  Profiler.gc_prev_kb = cur_gc
  Profiler.gc_memory_kb = math.floor(cur_gc * 10) / 10

  local avg_tabs = math.floor((Profiler.subsystems.tabs_ms / fc) * 100) / 100
  local avg_body = math.floor((Profiler.subsystems.body_ms / fc) * 100) / 100
  local avg_gutter = math.floor((Profiler.subsystems.gutter_ms / fc) * 100) / 100

  Profiler.current_fps = calculated_fps
  Profiler.frame_count = 0
  Profiler.total_draw_ms = 0.0
  Profiler.last_fps_calc = now
  Profiler.subsystems.tabs_ms = 0.0
  Profiler.subsystems.body_ms = 0.0
  Profiler.subsystems.gutter_ms = 0.0

  local json_parts = {
    "{\n",
    string.format('  "timestamp": %q,\n', os.date("%Y-%m-%d %H:%M:%S")),
    string.format('  "is_idle": %s,\n', is_idle and "true" or "false"),
    string.format('  "avg_draw_latency_ms": %.2f,\n', avg_draw_latency),
    string.format('  "active_fps": %.1f,\n', calculated_fps),
    string.format('  "target_fps": %d,\n', config.fps or 60),
    string.format('  "gc_memory_kb": %.1f,\n', Profiler.gc_memory_kb),
    string.format('  "gc_growth_rate_kbs": %.1f,\n', Profiler.gc_growth_rate_kbs),
    '  "subsystems": {\n',
    string.format('    "tabs_avg_ms": %.2f,\n', avg_tabs),
    string.format('    "doc_body_avg_ms": %.2f,\n', avg_body),
    string.format('    "gutter_avg_ms": %.2f\n', avg_gutter),
    '  },\n',
    '  "active_threads": {\n',
  }

  local th_entries = {}
  for tid, st in pairs(Profiler.thread_stats) do
    table.insert(th_entries, string.format(
      '    %q: { "total_ms": %.2f, "calls": %d, "max_ms": %.2f }',
      tid, st.total_ms, st.calls, st.max_ms
    ))
  end
  json_parts[#json_parts + 1] = table.concat(th_entries, ",\n")
  json_parts[#json_parts + 1] = '\n  },\n  "frame_spikes": [\n'

  for idx, sp in ipairs(Profiler.frame_spikes) do
    json_parts[#json_parts + 1] = string.format(
      '    { "timestamp": %q, "duration_ms": %.2f, "active_file": %q, "is_spike": true }%s\n',
      sp.timestamp, sp.duration_ms, sp.active_file, (idx < #Profiler.frame_spikes and "," or "")
    )
  end
  json_parts[#json_parts + 1] = '  ]\n}\n'

  pcall(function()
    local f = io.open(telemetry_json_path, "w")
    if f then
      f:write(table.concat(json_parts))
      f:flush()
      f:close()
    end
  end)
end

-- =============================================================================
-- 🚀 CICLO DE VIDA E THREADS DE FUNDO
-- =============================================================================
--[[core.add_thread(function()
  coroutine.yield(0.2)
  pcall(export_boot_telemetry)
  pcall(export_profiler_telemetry)
end)

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

core.add_thread(function()
  while true do
    coroutine.yield(2.5)
    pcall(export_profiler_telemetry)
  end
end)]]
