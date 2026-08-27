-- doxoade/commands/lite_xl_systems/template/10_forensic_engine.lua
-- =============================================================================
-- 10. FORENSIC ENGINE (HARDENED)
-- =============================================================================

local core = require "core"
local config = require "core.config"

local diag_dir = USERDIR .. PATHSEP .. ".doxoade" .. PATHSEP .. "diagnostics"

pcall(function()
  system.mkdir(diag_dir)
end)

local report_path = diag_dir .. PATHSEP .. "forensic_report.txt"

local forensic_data = {
  errors = {},
  performance = {},
  env_plugins = {},
  start_time = os.time(),
}

-- Hotfix de compatibilidade:
-- Se algum código antigo referenciar forensic_data como global,
-- evitamos "cannot get undefined variable" enquanto a causa raiz é removida.
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
