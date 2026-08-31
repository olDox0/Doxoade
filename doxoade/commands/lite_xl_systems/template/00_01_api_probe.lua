-- doxoade/commands/lite_xl_systems/template/00_01_api_probe.lua
--[[
  🧭 DOXOADE API GUARD — RUNTIME PROBE (Estágio 00.1: Scanner Atômico de Boot)
  - Introspecção hierárquica e resolução dinâmica de submódulos core.*
  - Compatibilidade garantida com o leitor CLI 'api-catalog audit'.
]]
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
  timestamp = os.time(),
  results = {},
  summary = { present = 0, missing = 0, type_mismatch = 0, total = 0 },
}

rawset(_G, "_DOXOADE_API_PROBE", ProbeEngine)

local MODULE_MAP = {
  RootView    = "core.rootview",
  DocView     = "core.docview",
  Doc         = "core.doc",
  Node        = "core.node",
  StatusView  = "core.statusview",
  CommandView = "core.commandview",
  View        = "core.view",
  rencache    = "core.rencache",
}

-- =============================================================================
-- 🔍 RESOLVEDOR HIERÁRQUICO DE SÍMBOLOS E SUBMÓDULOS
-- =============================================================================
function ProbeEngine.resolve_symbol(symbol_path)
  if not symbol_path or symbol_path == "" then return nil, "nil" end

  -- 1. Tenta require direto do símbolo completo
  local ok, mod = pcall(require, symbol_path)
  if ok and mod ~= nil then
    return mod, type(mod)
  end

  -- 2. Tenta resolver dividindo módulo e método (ex: "core.command.add" -> require("core.command")["add"])
  local parts = {}
  for p in symbol_path:gmatch("[^%.]+") do table.insert(parts, p) end

  for split_idx = #parts - 1, 1, -1 do
    local mod_name = table.concat(parts, ".", 1, split_idx)
    local ok_sub, sub_mod = pcall(require, mod_name)
    if ok_sub and sub_mod ~= nil then
      local curr = sub_mod
      for i = split_idx + 1, #parts do
        if type(curr) ~= "table" and type(curr) ~= "userdata" then
          curr = nil
          break
        end
        curr = curr[parts[i]]
        if curr == nil then break end
      end
      if curr ~= nil then
        return curr, type(curr)
      end
    end
  end

  -- 3. Resolução de Classes Globais Mapeadas
  local root_name = parts[1]
  local mapped_name = MODULE_MAP[root_name]
  if mapped_name then
    local ok_cls, cls_mod = pcall(require, mapped_name)
    if ok_cls and cls_mod ~= nil then
      local curr = cls_mod
      for i = 2, #parts do
        if type(curr) ~= "table" and type(curr) ~= "userdata" then
          curr = nil
          break
        end
        curr = curr[parts[i]]
        if curr == nil then break end
      end
      if curr ~= nil then
        return curr, type(curr)
      end
    end
  end

  -- 4. Fallback no _G
  local current = rawget(_G, root_name)
  if current and #parts > 1 then
    for i = 2, #parts do
      if type(current) ~= "table" and type(current) ~= "userdata" then
        return nil, "nil"
      end
      current = current[parts[i]]
      if current == nil then return nil, "nil" end
    end
    return current, type(current)
  end

  return current, type(current)
end

function ProbeEngine.run_probe()
  local catalog_file = probe_dir .. sep .. "catalog.lua"
  local catalog = {}

  local ok_cat, cat_data = pcall(dofile, catalog_file)
  if ok_cat and type(cat_data) == "table" and cat_data.catalog then
    catalog = cat_data.catalog
  else
    catalog = {
      ["core"] = { expected_type = "table", severity = "critical" },
      ["core.command"] = { expected_type = "table", severity = "critical" },
      ["core.command.add"] = { expected_type = "function", severity = "critical" },
      ["core.keymap.add"] = { expected_type = "function", severity = "critical" },
      ["RootView.draw"] = { expected_type = "function", severity = "critical" },
      ["Doc.insert"] = { expected_type = "function", severity = "critical" },
      ["Doc.remove"] = { expected_type = "function", severity = "critical" },
      ["system.mkdir"] = { expected_type = "function", severity = "critical" },
    }
  end

  ProbeEngine.results = {}
  ProbeEngine.summary = { present = 0, missing = 0, type_mismatch = 0, total = 0 }

  for api_id, spec in pairs(catalog) do
    local val, real_type = ProbeEngine.resolve_symbol(api_id)
    local expected = spec.expected_type or "function"
    local status = "present"

    if val == nil or real_type == "nil" then
      status = "missing"
      ProbeEngine.summary.missing = ProbeEngine.summary.missing + 1
    elseif expected ~= "any" and real_type ~= expected then
      status = "type_mismatch"
      ProbeEngine.summary.type_mismatch = ProbeEngine.summary.type_mismatch + 1
    else
      ProbeEngine.summary.present = ProbeEngine.summary.present + 1
    end

    ProbeEngine.summary.total = ProbeEngine.summary.total + 1
    ProbeEngine.results[api_id] = {
      status = status,
      real_type = real_type,
      expected_type = expected,
      severity = spec.severity or "critical",
      is_deprecated = spec.is_deprecated or false,
      fallback = spec.fallback
    }
  end

  pcall(function()
    if system and system.mkdir then
      system.mkdir(doxoade_dir)
      system.mkdir(probe_dir)
    end
    local fj = io.open(probe_out_json, "w")
    if fj then
      fj:write("{\n")
      fj:write(string.format('  "litexl_version": %q,\n', tostring(ProbeEngine.version)))
      fj:write(string.format('  "platform": %q,\n', tostring(ProbeEngine.platform)))
      fj:write(string.format('  "timestamp": %d,\n', os.time()))
      fj:write('  "summary": {\n')
      fj:write(string.format('    "present": %d,\n', ProbeEngine.summary.present))
      fj:write(string.format('    "missing": %d,\n', ProbeEngine.summary.missing))
      fj:write(string.format('    "type_mismatch": %d,\n', ProbeEngine.summary.type_mismatch))
      fj:write(string.format('    "total": %d\n', ProbeEngine.summary.total))
      fj:write('  },\n')
      fj:write('  "capabilities": {\n')
      local entries = {}
      for k, v in pairs(ProbeEngine.results) do
        local entry_str = string.format(
          '    %q: { "status": %q, "real_type": %q, "expected_type": %q, "severity": %q, "is_deprecated": %s }',
          k, v.status, v.real_type, v.expected_type, v.severity, v.is_deprecated and "true" or "false"
        )
        table.insert(entries, entry_str)
      end
      fj:write(table.concat(entries, ",\n"))
      fj:write('\n  },\n')
      fj:write('  "apis": {\n')
      fj:write(table.concat(entries, ",\n"))
      fj:write('\n  }\n}\n')
      fj:flush()
      fj:close()
    end
  end)
end

if core and core.add_thread then
  core.add_thread(function()
    coroutine.yield(0.05)
    ProbeEngine.run_probe()
  end)
else
  pcall(ProbeEngine.run_probe)
end
