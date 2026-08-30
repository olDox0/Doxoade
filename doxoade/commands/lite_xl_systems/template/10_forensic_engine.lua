-- doxoade/commands/lite_xl_systems/template/10_forensic_engine.lua
-- =============================================================================
-- 10. FORENSIC ENGINE (HARDENED)
-- =============================================================================

local core = require "core"
local config = require "core.config"
local RootView = require "core.rootview"

local diag_dir = USERDIR .. PATHSEP .. ".doxoade" .. PATHSEP .. "diagnostics"
pcall(function() system.mkdir(diag_dir) end)

local telemetry_json_path = diag_dir .. PATHSEP .. "profiler_telemetry.json"

local Profiler = {
  frame_spikes = {},
  thread_bottlenecks = {},
  last_step_time = os.clock(),
  frame_count = 0,
  total_frame_time = 0,
  max_spike_records = 30,
}

-- Hotfix de compatibilidade:
-- Se algum código antigo referenciar forensic_data como global,
-- evitamos "cannot get undefined variable" enquanto a causa raiz é removida.
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
-- 1. MONITORAMENTO DE FRAME BUDGET (DETECTOR DE QUEDA DE FPS)
-- =============================================================================
local original_rootview_draw = RootView.draw
function RootView:draw(...)
  local t0 = os.clock()
  original_rootview_draw(self, ...)
  local elapsed = (os.clock() - t0) * 1000

  Profiler.frame_count = Profiler.frame_count + 1
  Profiler.total_frame_time = Profiler.total_frame_time + elapsed

  -- Registra spike se o frame demorar mais de 16.6ms (< 60 FPS)
  if elapsed > 16.6 and #Profiler.frame_spikes < Profiler.max_spike_records then
    local active_fn = "none"
    local lines = 0
    if core.active_view and core.active_view.doc then
      active_fn = tostring(core.active_view.doc.filename or core.active_view.doc:get_name())
      lines = core.active_view.doc.lines and #core.active_view.doc.lines or 0
    end

    table.insert(Profiler.frame_spikes, {
      timestamp = os.date("%H:%M:%S"),
      duration_ms = tonumber(string.format("%.2f", elapsed)),
      fps = tonumber(string.format("%.1f", 1000 / math.max(elapsed, 1))),
      active_file = active_fn,
      lines_count = lines,
      is_spike = true
    })
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
-- 3. EXPORTAÇÃO ASSÍNCRONA DE TELEMETRIA JSON
-- =============================================================================
local function export_profiler_telemetry()
  local boot_report = rawget(_G, "_DOXOADE_BOOT_REPORT") or { modules = {}, total = 0 }
  local boot_list = {}
  local total_boot_ms = 0

  for name, data in pairs(boot_report.modules or {}) do
    local ms = data.time_ms or 0
    total_boot_ms = total_boot_ms + ms
    table.insert(boot_list, {
      module = name,
      status = data.status or "UNKNOWN",
      time_ms = tonumber(string.format("%.2f", ms)),
      error = data.error
    })
  end

  local avg_fps = 60.0
  if Profiler.frame_count > 0 then
    local avg_duration = Profiler.total_frame_time / Profiler.frame_count
    avg_fps = tonumber(string.format("%.1f", 1000 / math.max(avg_duration, 1)))
  end

  local payload = {
    timestamp = os.date("%Y-%m-%d %H:%M:%S"),
    total_boot_time_ms = tonumber(string.format("%.2f", total_boot_ms)),
    boot_modules = boot_list,
    frame_spikes = Profiler.frame_spikes,
    thread_bottlenecks = Profiler.thread_bottlenecks,
    gc_memory_kb = tonumber(string.format("%.2f", collectgarbage("count"))),
    average_fps = avg_fps
  }

  pcall(function()
    local f = io.open(telemetry_json_path, "w")
    if f then
      -- Serializador JSON simples e rápido
      local function serialize(val)
        local t = type(val)
        if t == "table" then
          local is_arr = (#val > 0)
          local items = {}
          if is_arr then
            for _, v in ipairs(val) do table.insert(items, serialize(v)) end
            return "[" .. table.concat(items, ", ") .. "]"
          else
            for k, v in pairs(val) do table.insert(items, string.format("%q: %s", tostring(k), serialize(v))) end
            return "{" .. table.concat(items, ", ") .. "}"
          end
        elseif t == "string" then
          return string.format("%q", val)
        elseif t == "number" or t == "boolean" then
          return tostring(val)
        else
          return "null"
        end
      end
      f:write(serialize(payload))
      f:close()
    end
  end)
end

-- Exporta telemetria 3 segundos após o boot e periodicamente
core.add_thread(function()
  coroutine.yield(3.0)
  export_profiler_telemetry()
end)
