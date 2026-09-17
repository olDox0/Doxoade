-- doxoade/commands/lite_xl_systems/template/10_forensic_engine.lua
--[[
  🦅 DOXOADE CHRONOS V3 — DEEP PROFILER, TIME-SERIES & FORENSIC TELEMETRY
  - Time-Series Engine: Ring Buffer temporal de 120 amostras (2 minutos deslizantes).
  - Decomposição do Loop Principal: core.step (Lógica/IPC) vs RootView:draw (Render/SDL2).
  - Percentis de Frame: Cálculo dinâmico de P50, P95, P99 e Jitter a cada 1s.
  - Medição Líquida de CPU e Alocação (KB) por Corrotina.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local config = require "core.config"
local RootView = require "core.rootview"
local command = require "core.command"
local keymap = require "core.keymap"
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
-- ⏱️ ESTRUTURA CENTRAL DO CHRONOS V3
-- =============================================================================
local TIMESERIES_MAX = 120
local _timeseries_ring = {}
local _timeseries_head = 1
local _timeseries_count = 0

-- =============================================================================
-- 📈 SLAB PRE-ALLOCATED RING BUFFER (Pilar 3)
-- =============================================================================
local function push_timeseries_sample(sample_data)
  local node = _timeseries_ring[_timeseries_head]
  if not node then
    node = {}
    _timeseries_ring[_timeseries_head] = node
  end

  -- Atualiza os campos no mesmo nó de memória (zero alocação de tabela)
  node.ts = sample_data.ts
  node.fps = sample_data.fps
  node.frame_ms = sample_data.frame_ms
  node.p95_ms = sample_data.p95_ms
  node.p99_ms = sample_data.p99_ms
  node.step_logic_ms = sample_data.step_logic_ms
  node.draw_ms = sample_data.draw_ms
  node.gc_kb = sample_data.gc_kb
  node.alloc_kbs = sample_data.alloc_kbs
--  node.top_thread = sample_data.top_thread
--  node.top_cpu = sample_data.top_thread_ms
  node.top_thread = sample_data.top_thread or "none"
  node.top_thread_ms = sample_data.top_thread_ms or sample_data.top_cpu or 0.0
  node.top_cpu = node.top_thread_ms

  _timeseries_head = (_timeseries_head % TIMESERIES_MAX) + 1
  if _timeseries_count < TIMESERIES_MAX then
    _timeseries_count = _timeseries_count + 1
  end
end

local function get_ordered_timeseries()
  local list = {}
  local start_idx = _timeseries_head - _timeseries_count
  if start_idx <= 0 then start_idx = start_idx + TIMESERIES_MAX end
  for i = 1, _timeseries_count do
    local idx = ((start_idx + i - 2) % TIMESERIES_MAX) + 1
    if _timeseries_ring[idx] then
      table.insert(list, _timeseries_ring[idx])
    end
  end
  return list
end

local Profiler = {
  frame_count = 0,
  total_draw_ms = 0.0,
  current_fps = 60.0,
  last_fps_calc = os.clock(),
  last_draw_time = os.clock(),
  last_sample_clock = os.clock(),
  frame_samples_1s = {},
  percentiles = { p50 = 0.0, p95 = 0.0, p99 = 0.0, min_ms = 0.0, max_ms = 0.0, jitter_ms = 0.0 },
  cycle = {
    step_total_ms = 0.0,
    step_logic_ms = 0.0,
    last_draw_ms = 0.0,
    avg_step_logic_ms = 0.0,
    avg_draw_ms = 0.0,
  },
  frame_spikes = {},
  cmd_frequencies = {},
  thread_bottlenecks = {},
  thread_stats = {},
  subsystems = {
    tabs_ms = 0.0,
    body_ms = 0.0,
    gutter_ms = 0.0,
    rencache_ms = 0.0,
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

-- =============================================================================
-- 📊 CÁLCULO ESTATÍSTICO DE PERCENTIS (P50, P95, P99)
-- =============================================================================
local function calculate_percentiles(samples)
  local n = #samples
  if n == 0 then return 0, 0, 0, 0, 0, 0 end
  table.sort(samples)
  local min_ms = samples[1]
  local max_ms = samples[n]
  local sum = 0
  for i = 1, n do sum = sum + samples[i] end
  local avg_ms = math.floor((sum / n) * 100) / 100

  local idx_50 = math.max(1, math.floor(n * 0.50))
  local idx_95 = math.max(1, math.floor(n * 0.95))
  local idx_99 = math.max(1, math.floor(n * 0.99))

  local p50 = math.floor(samples[idx_50] * 100) / 100
  local p95 = math.floor(samples[idx_95] * 100) / 100
  local p99 = math.floor(samples[idx_99] * 100) / 100
  local jitter = math.floor((p99 - p50) * 100) / 100

  return p50, p95, p99, min_ms, max_ms, avg_ms, jitter
end

-- =============================================================================
-- 📜 HOOKS DE CAPTURA FORENSE DE ERROS
-- =============================================================================
local function safe_error_message(...)
  local args = { ... }
  for i = 1, select("#", ...) do args[i] = tostring(args[i]) end
  return table.concat(args, " ")
end

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

-- =============================================================================
-- 🎨 SONDAS DE SUBSISTEMAS GRÁFICOS (Abas, DocView, Gutter)
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

-- =============================================================================
-- 🖼️ SONDAS DO LOOP PRINCIPAL (RootView:draw & core.step)
-- =============================================================================
local original_rootview_draw = RootView.draw
function RootView:draw(...)
  local t0 = os.clock()
  original_rootview_draw(self, ...)
  local t_draw_total = (os.clock() - t0) * 1000

  Profiler.cycle.last_draw_ms = t_draw_total
  local measured = Profiler.subsystems.tabs_ms + Profiler.subsystems.body_ms + Profiler.subsystems.gutter_ms
  Profiler.subsystems.rencache_ms = math.max(0, t_draw_total - measured)

  Profiler.frame_count = Profiler.frame_count + 1
  Profiler.total_draw_ms = (Profiler.total_draw_ms or 0) + t_draw_total
  Profiler.last_draw_time = os.clock()

  -- Amostra instantânea para o cálculo de percentis
  table.insert(Profiler.frame_samples_1s, t_draw_total)

  local target_fps = config.fps or 60
  local frame_budget_ms = (1000.0 / target_fps) * 1.15
  local now_clock = os.clock()

  if t_draw_total > frame_budget_ms and (now_clock - (Profiler._last_spike_record or 0)) >= 1.0 then
    Profiler._last_spike_record = now_clock
    local active_name = (core.active_view and core.active_view.get_name and core.active_view:get_name()) or "workspace"
    table.insert(Profiler.frame_spikes, {
      timestamp = os.date("%H:%M:%S"),
      duration_ms = math.floor(t_draw_total * 100) / 100,
      active_file = active_name,
      is_spike = true
    })
    if #Profiler.frame_spikes > 20 then
      table.remove(Profiler.frame_spikes, 1)
    end
  end
end

local original_core_step = core.step
if original_core_step then
  core.step = function(...)
    local t0 = os.clock()
    local ret = original_core_step(...)
    local t_step_total = (os.clock() - t0) * 1000

    Profiler.cycle.step_total_ms = t_step_total
    local draw_ms = Profiler.cycle.last_draw_ms or 0
    local logic_ms = math.max(0, t_step_total - draw_ms)
    Profiler.cycle.step_logic_ms = logic_ms

    -- Médias móveis amortecidas (EMA 0.1)
    Profiler.cycle.avg_step_logic_ms = (Profiler.cycle.avg_step_logic_ms * 0.9) + (logic_ms * 0.1)
    Profiler.cycle.avg_draw_ms = (Profiler.cycle.avg_draw_ms * 0.9) + (draw_ms * 0.1)

    return ret
  end
end

-- =============================================================================
-- 🧵 MONITOR LÍQUIDO DE CORROTINAS (Zero Sleep Overhead + Alocação KB)
-- =============================================================================
local function extract_safe_thread_id(fn, target)
  if target then
    if type(target) == "string" then return target end
    if type(target) == "table" then
      if target.class and target.class.name then return tostring(target.class.name) end
      if target.get_name and pcall(target.get_name, target) then
        local ok, n = pcall(target.get_name, target)
        if ok and n then return tostring(n) end
      end
    end
  end
  local info = debug.getinfo(fn, "Sl")
  if info and info.short_src then
    local fname = info.short_src:match("[^/\\]+$") or info.short_src
    return string.format("%s:L%d", fname, info.linedefined or 0)
  end
  return "thread_" .. tostring(fn):sub(-6)
end

local original_add_thread = core.add_thread
function core.add_thread(fn, target)
  local thread_id = extract_safe_thread_id(fn, target)
  local st = Profiler.thread_stats[thread_id] or {
    id = thread_id,
    calls = 0,
    total_cpu_ms = 0.0,
    peak_cpu_ms = 0.0,
    last_cpu_snapshot = 0.0,
    total_alloc_kb = 0.0,
  }
  Profiler.thread_stats[thread_id] = st

  return original_add_thread(function(...)
    local co = coroutine.create(fn)
    local args = { ... }

    while coroutine.status(co) ~= "dead" do
      local t0 = os.clock()
      local mem0 = collectgarbage("count")

      -- Executa apenas a fatia ativa da corrotina
      local results = { coroutine.resume(co, table.unpack(args)) }
      local elapsed_ms = (os.clock() - t0) * 1000
      local alloc_kb = math.max(0, collectgarbage("count") - mem0)

      st.calls = st.calls + 1
      st.total_cpu_ms = st.total_cpu_ms + elapsed_ms
      st.total_alloc_kb = st.total_alloc_kb + alloc_kb

      if elapsed_ms > st.peak_cpu_ms then
        st.peak_cpu_ms = math.floor(elapsed_ms * 100) / 100
      end

      local ok = results[1]
      if not ok then
        local err = results[2]
        if core and core.error then
          core.error(string.format("👻 [THREAD CRASH:%s] %s", thread_id, tostring(err)))
        end
        break
      end

      -- Cede a CPU sem computar o tempo adormecido no cronômetro da corrotina
      args = { coroutine.yield(table.unpack(results, 2)) }
    end
  end, target)
end

-- =============================================================================
-- 💾 EXPORTAÇÃO JSON DA TELEMETRIA COMPLETA (Chronos V3)
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

local function export_profiler_telemetry()
  local ordered_ts = get_ordered_timeseries()
  local ts_json = {}
  for _, s in ipairs(ordered_ts) do
    table.insert(ts_json, string.format(
      '    { "ts": %d, "fps": %.1f, "frame_ms": %.2f, "p95": %.2f, "step_ms": %.2f, "draw_ms": %.2f, "gc_kb": %.1f, "alloc_kbs": %.1f, "top_thread": %q, "top_cpu": %.2f }',
      s.ts or 0,
      s.fps or 60.0,
      s.frame_ms or 0.0,
      s.p95_ms or 0.0,
      s.step_logic_ms or 0.0,
      s.draw_ms or 0.0,
      s.gc_kb or 0.0,
      s.alloc_kbs or 0.0,
      tostring(s.top_thread or "none"),
      tonumber(s.top_thread_ms or s.top_cpu or 0.0) or 0.0 -- 👈 Blindado com fallback numérico!
    ))
  end

  local thread_entries = {}
  for tid, st in pairs(Profiler.thread_stats) do
    table.insert(thread_entries, string.format(
      '    { "id": %q, "calls": %d, "cpu_ms": %.2f, "peak_ms": %.2f, "alloc_kb": %.1f }',
      st.id, st.calls, st.total_cpu_ms, st.peak_cpu_ms, st.total_alloc_kb or 0.0
    ))
  end

  local spike_entries = {}
  for _, sp in ipairs(Profiler.frame_spikes) do
    table.insert(spike_entries, string.format(
      '    { "time": %q, "duration_ms": %.2f, "active_file": %q }',
      sp.timestamp, sp.duration_ms, sp.active_file or "nil"
    ))
  end

  local f = io.open(telemetry_json_path, "w")
  if f then
    f:write("{\n")
    f:write(string.format('  "timestamp": %q,\n', os.date("%Y-%m-%d %H:%M:%S")))
    f:write(string.format('  "fps": %.1f,\n', Profiler.current_fps or 60.0))
    f:write(string.format('  "frame_ms": %.2f,\n', Profiler.percentiles.max_ms or 0.0))
    f:write('  "cycle": {\n')
    f:write(string.format('    "step_logic_ms": %.2f,\n', Profiler.cycle.avg_step_logic_ms or 0.0))
    f:write(string.format('    "draw_ms": %.2f,\n', Profiler.cycle.avg_draw_ms or 0.0))
    f:write(string.format('    "step_total_ms": %.2f\n', Profiler.cycle.step_total_ms or 0.0))
    f:write('  },\n')
    f:write('  "percentiles": {\n')
    f:write(string.format('    "p50": %.2f,\n', Profiler.percentiles.p50 or 0.0))
    f:write(string.format('    "p95": %.2f,\n', Profiler.percentiles.p95 or 0.0))
    f:write(string.format('    "p99": %.2f,\n', Profiler.percentiles.p99 or 0.0))
    f:write(string.format('    "min_ms": %.2f,\n', Profiler.percentiles.min_ms or 0.0))
    f:write(string.format('    "max_ms": %.2f,\n', Profiler.percentiles.max_ms or 0.0))
    f:write(string.format('    "jitter_ms": %.2f\n', Profiler.percentiles.jitter_ms or 0.0))
    f:write('  },\n')
    f:write('  "subsystems": {\n')
    f:write(string.format('    "tabs_ms": %.2f,\n', Profiler.subsystems.tabs_ms or 0.0))
    f:write(string.format('    "body_ms": %.2f,\n', Profiler.subsystems.body_ms or 0.0))
    f:write(string.format('    "gutter_ms": %.2f,\n', Profiler.subsystems.gutter_ms or 0.0))
    f:write(string.format('    "rencache_ms": %.2f\n', Profiler.subsystems.rencache_ms or 0.0))
    f:write('  },\n')
    f:write('  "gc": {\n')
    f:write(string.format('    "memory_kb": %.1f,\n', Profiler.gc_memory_kb or 0.0))
    f:write(string.format('    "growth_rate_kbs": %.1f\n', Profiler.gc_growth_rate_kbs or 0.0))
    f:write('  },\n')
    f:write('  "threads": [\n' .. table.concat(thread_entries, ",\n") .. '\n  ],\n')
    f:write('  "frame_spikes": [\n' .. table.concat(spike_entries, ",\n") .. '\n  ],\n')
    f:write('  "timeseries": [\n' .. table.concat(ts_json, ",\n") .. '\n  ]\n')
    f:write("}\n")
    f:flush()
    f:close()
  end
end

-- =============================================================================
-- 🌙 CORROTINA AMOSTRADORA 1HZ (Gera Histórico Temporal)
-- =============================================================================
core.add_thread(function()
  coroutine.yield(1.0)
  export_boot_telemetry()

  local flush_timer = 0
  while true do
    coroutine.yield(1.0)
    flush_timer = flush_timer + 1

    local now_clock = os.clock()
    local gc_now = collectgarbage("count")
    local dt = now_clock - (Profiler.last_sample_clock or now_clock)
    if dt <= 0 then dt = 1.0 end

    -- Taxa real de crescimento do heap amortecida
    local alloc_delta = math.max(0, gc_now - (Profiler.gc_prev_kb or gc_now))
    Profiler.gc_growth_rate_kbs = math.floor((alloc_delta / dt) * 10) / 10
    Profiler.gc_prev_kb = gc_now
    Profiler.gc_memory_kb = gc_now
    Profiler.last_sample_clock = now_clock

    local frames_in_1s = #Profiler.frame_samples_1s
    Profiler.current_fps = math.min(60.0, frames_in_1s)

    local p50, p95, p99, min_ms, max_ms, avg_ms, jitter = calculate_percentiles(Profiler.frame_samples_1s)
    Profiler.percentiles = {
      p50 = p50, p95 = p95, p99 = p99,
      min_ms = min_ms, max_ms = max_ms,
      avg_ms = avg_ms, jitter_ms = jitter
    }
    Profiler.frame_samples_1s = {}

    -- Identifica maior consumidor daquele ciclo
    local top_thread_id = "none"
    local top_thread_cpu = 0.0
    for tid, st in pairs(Profiler.thread_stats) do
      local delta_cpu = (st.total_cpu_ms or 0) - (st.last_cpu_snapshot or 0)
      st.last_cpu_snapshot = st.total_cpu_ms or 0
      if delta_cpu > top_thread_cpu then
        top_thread_cpu = delta_cpu
        top_thread_id = tid
      end
    end

    push_timeseries_sample({
      ts = os.time(),
      fps = Profiler.current_fps,
      frame_ms = avg_ms,
      p95_ms = p95,
      p99_ms = p99,
      step_logic_ms = math.floor((Profiler.cycle.avg_step_logic_ms or 0) * 100) / 100,
      draw_ms = math.floor((Profiler.cycle.avg_draw_ms or 0) * 100) / 100,
      gc_kb = math.floor(gc_now * 10) / 10,
      alloc_kbs = Profiler.gc_growth_rate_kbs,
      top_thread = top_thread_id,
      top_thread_ms = math.floor(top_thread_cpu * 100) / 100,
    })

    Profiler.subsystems.tabs_ms = 0.0
    Profiler.subsystems.body_ms = 0.0
    Profiler.subsystems.gutter_ms = 0.0
    Profiler.subsystems.rencache_ms = 0.0

    -- Exporta para o disco a cada 2 segundos para cortar I/O e alocações pela metade
    if flush_timer >= 2 then
      flush_timer = 0
      export_profiler_telemetry()
    end
  end
end)

if core.log then
  core.log("🦅 [CHRONOS V3] Telemetria temporal e Ring Buffer de 120s ativos.")
end
