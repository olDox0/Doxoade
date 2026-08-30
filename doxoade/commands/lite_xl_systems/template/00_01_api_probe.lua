-- doxoade/commands/lite_xl_systems/template/00_01_api_probe.lua
-- =============================================================================
-- 🧭 DOXOADE API GUARD — RUNTIME PROBE (ASYNC & ZERO-BOOT OVERHEAD)
-- =============================================================================
local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)
local system = rawget(_G, "system") or (pcall(require, "system") and require("system") or nil)

local user_dir = USERDIR or "."
local sep = PATHSEP or "/"
local doxoade_dir = (user_dir .. sep .. ".doxoade"):gsub("[/\\]", sep)
local probe_dir = (doxoade_dir .. sep .. "api_guard"):gsub("[/\\]", sep)
local probe_out_json = probe_dir .. sep .. "runtime_probe.json"

local ProbeEngine = {
  version = rawget(_G, "VERSION") or "unknown",
  platform = rawget(_G, "PLATFORM") or "unknown",
  timestamp = os.date("%Y-%m-%d %H:%M:%S"),
  results = {},
  total_probed = 0,
  present_count = 0,
  missing_count = 0,
  deprecated_count = 0,
}

-- 1. Estado Global Imediato (Consumível instantaneamente pelo 00_02_api_guard)
rawset(_G, "_DOXOADE_API_PROBE", ProbeEngine)

-- Cache direto dos módulos raiz para evitar chamadas de require repetidas
local ROOT_MODULES = {
  core = core,
  system = system,
  renderer = rawget(_G, "renderer"),
  rencache = rawget(_G, "rencache"),
}

function ProbeEngine.resolve_symbol(symbol_path)
  if not symbol_path or symbol_path == "" then return nil end

  local dot_idx = symbol_path:find("%.")
  local root_name = dot_idx and symbol_path:sub(1, dot_idx - 1) or symbol_path
  local rest = dot_idx and symbol_path:sub(dot_idx + 1) or nil

  local current = ROOT_MODULES[root_name] or rawget(_G, root_name)
  if not current and pcall(require, root_name) then
    current = require(root_name)
    ROOT_MODULES[root_name] = current
  end

  if not current or not rest then
    return current
  end

  for part in rest:gmatch("[^%.]+") do
    if type(current) ~= "table" and type(current) ~= "userdata" then
      return nil
    end
    current = current[part]
    if current == nil then return nil end
  end

  return current
end

function ProbeEngine.probe_api(entry)
  local sym = ProbeEngine.resolve_symbol(entry.id)
  local real_type = type(sym)
  local is_present = (sym ~= nil)
  local status = is_present and "present" or "missing"

  if is_present and entry.is_deprecated then
    status = "deprecated"
  end

  ProbeEngine.total_probed = ProbeEngine.total_probed + 1
  if status == "present" then
    ProbeEngine.present_count = ProbeEngine.present_count + 1
  elseif status == "missing" then
    ProbeEngine.missing_count = ProbeEngine.missing_count + 1
  elseif status == "deprecated" then
    ProbeEngine.deprecated_count = ProbeEngine.deprecated_count + 1
  end

  ProbeEngine.results[entry.id] = {
    status = status,
    real_type = real_type,
    expected_type = entry.expected_type or "function",
    severity = entry.severity or "critical",
    safe_to_patch = entry.safe_to_patch or false,
    fallback = entry.fallback,
  }
end

function ProbeEngine.run_probe()
  local catalog_file = probe_dir .. sep .. "catalog.lua"
  local ok, cat_data = pcall(dofile, catalog_file)
  if not ok or type(cat_data) ~= "table" or not cat_data.catalog then
    return
  end

  for api_id, entry in pairs(cat_data.catalog) do
    entry.id = api_id
    ProbeEngine.probe_api(entry)
  end

  -- Grava o JSON de auditoria de forma atômica
  pcall(function()
    system.mkdir(doxoade_dir)
    system.mkdir(probe_dir)
    local f = io.open(probe_out_json, "w")
    if f then
      local parts = {}
      for id, r in pairs(ProbeEngine.results) do
        table.insert(parts, string.format('    %q: { "status": %q, "real_type": %q, "expected": %q }',
          id, r.status, r.real_type, r.expected_type))
      end
      f:write("{\n  \"version\": \"" .. ProbeEngine.version .. "\",\n  \"apis\": {\n" .. table.concat(parts, ",\n") .. "\n  }\n}\n")
      f:close()
    end
  end)
end

-- 2. Execução Diferida Assíncrona (Libera o boot imediatamente)
if core and core.add_thread then
  core.add_thread(function()
    coroutine.yield(0.05)
    ProbeEngine.run_probe()
  end)
else
  -- Fallback imediato caso não haja event loop (ex: shadow harness)
  pcall(ProbeEngine.run_probe)
end
