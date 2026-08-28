-- doxoade/commands/lite_xl_systems/template/00_01_api_probe.lua
-- =============================================================================
-- DOXOADE API GUARD — RUNTIME PROBE (Estágio 00.1: Scanner Atômico de Boot)
-- =============================================================================

local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or {})
local system = rawget(_G, "system") or (pcall(require, "system") and require("system") or {})

local user_dir = USERDIR or "."
local sep = PATHSEP or "/"
local doxoade_dir = (user_dir .. sep .. ".doxoade"):gsub("\\", "/")
local probe_dir = (doxoade_dir .. sep .. "api_guard"):gsub("\\", "/")

-- Garante pastas universalmente
pcall(function() system.mkdir(doxoade_dir) end)
pcall(function() system.mkdir(probe_dir) end)

local probe_out_json = probe_dir .. sep .. "runtime_probe.json"

local ProbeEngine = {
  version = rawget(_G, "VERSION") or "unknown",
  platform = rawget(_G, "PLATFORM") or "unknown",
  timestamp = os.time(),
  results = {},
  summary = { present = 0, missing = 0, type_mismatch = 0, total = 0 }
}

local CLASS_MODULE_MAP = {
  RootView = "core.rootview",
  DocView = "core.docview",
  Doc = "core.doc",
  Node = "core.node",
  StatusView = "core.statusview",
  CommandView = "core.commandview",
  View = "core.view",
}

-- Mapeamento inteligente de raízes e módulos
local MODULE_MAP = {
  core = "core",
  common = "core.common",
  config = "core.config",
  style = "core.style",
  command = "core.command",
  keymap = "core.keymap",
  syntax = "core.syntax",
  RootView = "core.rootview",
  DocView = "core.docview",
  Doc = "core.doc",
  Node = "core.node",
  StatusView = "core.statusview",
  CommandView = "core.commandview",
  View = "core.view",
}

function ProbeEngine.resolve_symbol(symbol_path)
  if not symbol_path or symbol_path == "" then return nil, "nil" end

  local parts = {}
  for part in symbol_path:gmatch("[^%.]+") do
    table.insert(parts, part)
  end

  local root_name = parts[1]
  local current = rawget(_G, root_name)

  -- 1. Se for módulo core (ex: core.log, core.open_doc, core.command.add)
  if root_name == "core" then
    local ok, core_mod = pcall(require, "core")
    if ok and type(core_mod) == "table" then
      current = core_mod
      table.remove(parts, 1) -- Consome 'core'

      -- Se o próximo for um submódulo que precisa de require (ex: core.command)
      if #parts > 0 and current[parts[1]] == nil then
        local sub_name = "core." .. parts[1]
        local ok_sub, sub_mod = pcall(require, sub_name)
        if ok_sub then
          current = sub_mod
          table.remove(parts, 1)
        end
      end
    end
  -- 2. Se for uma classe/módulo mapeado (ex: RootView, DocView, rencache)
  elseif current == nil and MODULE_MAP[root_name] then
    local ok, mod = pcall(require, MODULE_MAP[root_name])
    if ok then
      current = mod
      table.remove(parts, 1)
    end
  -- 3. Tenta require genérico
  elseif current == nil then
    local ok, mod = pcall(require, root_name)
    if ok then
      current = mod
      table.remove(parts, 1)
    end
  else
    table.remove(parts, 1)
  end

  if current == nil then return nil, "nil" end

  -- Navega pelas propriedades restantes da tabela
  for _, part in ipairs(parts) do
    if type(current) == "table" or type(current) == "userdata" then
      local ok, val = pcall(function() return current[part] end)
      if ok and val ~= nil then
        current = val
      else
        return nil, "nil"
      end
    else
      return nil, type(current)
    end
  end

  return current, type(current)
end

function ProbeEngine.run_probe()
  local catalog_path = probe_dir .. sep .. "catalog.lua"
  local catalog = {}

  local ok_cat, cat_data = pcall(dofile, catalog_path)
  if ok_cat and type(cat_data) == "table" and cat_data.catalog then
    catalog = cat_data.catalog
  else
    catalog = {
      ["core"] = { expected_type = "table", severity = "critical" },
      ["core.command.add"] = { expected_type = "function", severity = "critical" },
      ["core.keymap.add"] = { expected_type = "function", severity = "critical" },
      ["RootView.draw"] = { expected_type = "function", severity = "critical" },
      ["RootView.on_text_input"] = { expected_type = "function", severity = "warning", is_deprecated = true },
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
      severity = spec.severity or "warning",
      is_deprecated = spec.is_deprecated or false,
      fallback = spec.fallback
    }
  end

  pcall(function()
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
      fj:write("\n  }\n}\n")
      fj:flush()
      fj:close()
    end
  end)
end

ProbeEngine.run_probe()
rawset(_G, "_DOXOADE_API_PROBE", ProbeEngine)
