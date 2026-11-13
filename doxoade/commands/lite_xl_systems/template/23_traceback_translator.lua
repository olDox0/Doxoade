-- doxoade/commands/lite_xl_systems/template/23_traceback_translator.lua
--[[
  🩺 DOXOADE TRACEBACK TRANSLATOR (V1.0 — Anúbis)
  ----------------------------------------------------------------------------
  Enriquece tracebacks do Lite XL com:
    1. Source Map: qual template original gerou a linha no init.lua unificado.
    2. Variáveis locais no momento do erro (debug.getlocal).
    3. Comando ativo (via command.perform hook).
    4. Blame de plugin (core vs doxoade vs plugins/*).

  Saída: .doxoade/diagnostics/traceback_translations.ndjson
]]

local core = require "core"
local command = require "core.command"

local user_dir = USERDIR or "."
local sep = PATHSEP or "/"
local diag_dir = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics"
local trans_file = diag_dir .. sep .. "traceback_translations.ndjson"

pcall(function() if system and system.mkdir then system.mkdir(diag_dir) end end)

-- ── Source Map (preenchido pelo Khonsu Gate) ──────────────────────────────
local _source_map = rawget(_G, "_DOXOADE_SOURCE_MAP") or {}

local function resolve_source(line_no)
  if not _source_map or not _source_map.resolve then return nil end
  local ok, resolved = pcall(_source_map.resolve, line_no)
  if ok and resolved then return resolved end
  return nil
end

-- ── Rastrear último comando executado ─────────────────────────────────────
local _last_cmd = ""
local _last_cmd_time = 0
if command and command.perform then
  local _orig_perform = command.perform
  command.perform = function(cmd_name, ...)
    _last_cmd = cmd_name
    _last_cmd_time = os.clock()
    return _orig_perform(cmd_name, ...)
  end
end

-- ── Capturar variáveis locais no nível do erro ────────────────────────────
local function capture_locals(level)
  local vars = {}
  if not debug or not debug.getlocal then return vars end
  local i = 1
  while true do
    local ok, name, value = pcall(debug.getlocal, level, i)
    if not ok or not name then break end
    if type(value) ~= "function" and type(value) ~= "table" then
      vars[name] = tostring(value)
    elseif type(value) == "table" then
      vars[name] = "<table>"
    end
    i = i + 1
    if i > 20 then break end
  end
  return vars
end

-- ── Blame de plugin ──────────────────────────────────────────────────────
local function classify_blame(traceback)
  if not traceback then return "unknown" end
  if traceback:find("plugins[/\\]") then
    return "plugin:" .. (traceback:match("plugins[/\\]([^/:]+)") or "unknown")
  elseif traceback:find("doxoade[/\\]") or traceback:find("template[/\\]") then
    return "doxoade"
  elseif traceback:find("core[/\\]") then
    return "core"
  elseif traceback:find("%[C%]:") then
    return "C_native"
  end
  return "unknown"
end

-- ── JSON helper ───────────────────────────────────────────────────────────
local function json_escape(s)
  if not s then return "" end
  return tostring(s):gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"):gsub("\r", "\\r"):gsub("\t", "\\t")
end

-- ── Hook no core.error ────────────────────────────────────────────────────
local _orig_core_error = core.error
core.error = function(...)
  local msg = table.concat({...}, " ")
  local tb = debug.traceback("", 2) or ""
  
  -- Extrai linha e arquivo do traceback
  local file, line = nil, nil
  local m = tb:match("([^%s]+):(%d+):")
  if m then
    file = tb:match("([^%s]+):%d+:") or nil
    line = tonumber(tb:match(":%s*(%d+):") or "0")
  end
  
  -- Source map
  local resolved = nil
  if line and line > 0 then
    resolved = resolve_source(line)
  end
  
  -- Variáveis locais
  local vars = {}
  pcall(function() vars = capture_locals(2) end)
  
  -- Blame
  local blame = classify_blame(tb)
  
  -- Comando ativo
  local active_cmd = _last_cmd
  if (os.clock() - _last_cmd_time) > 2.0 then
    active_cmd = "(stale)"
  end
  
  -- Payload NDJSON
  local payload = {
    ts = os.time(),
    ts_iso = os.date("%Y-%m-%d %H:%M:%S"),
    error = msg,
    traceback_head = tb:sub(1, 500),
    blame = blame,
    active_command = active_cmd,
    source_map = resolved and {
      template = resolved.name,
      original_line = resolved.line or (line - (resolved.start_line or line) + 1),
      unified_line = line,
    } or nil,
    variables = vars,
  }
  
  -- Append NDJSON
  pcall(function()
    local f = io.open(trans_file, "a")
    if f then
      local json = string.format(
        '{"ts":%d,"ts_iso":"%s","error":"%s","blame":"%s","active_command":"%s","source_map":%s,"variables":%s}\n',
        payload.ts, payload.ts_iso,
        json_escape(payload.error),
        json_escape(payload.blame),
        json_escape(payload.active_command),
        payload.source_map and string.format('{"template":"%s","original_line":%d,"unified_line":%d}',
          json_escape(payload.source_map.template),
          payload.source_map.original_line,
          payload.source_map.unified_line) or "null",
        (function()
          local parts = {}
          for k, v in pairs(payload.variables) do
            table.insert(parts, string.format('"%s":"%s"', json_escape(k), json_escape(v)))
          end
          return "{" .. table.concat(parts, ",") .. "}"
        end)()
      )
      f:write(json)
      f:flush()
      f:close()
    end
  end)
  
  return _orig_core_error(...)
end

if core.log then
  core.log("🩺 [TRACEBACK] Tradutor V1.0 ativo. Saída: " .. trans_file)
end
