-- doxoade/commands/lite_xl_systems/template/00_phanto_core.lua
--[[
  👻 PHANTO_CRISIS CORE — Err Isolation & Deep Err Capture (V2.1 Strict-Safe)
  - Interceptação de falhas O(1) imune ao strict.lua do Lite XL.
  - Ring Buffer em memória protegendo contra I/O bloqueante no frame.
  - Despejo assíncrono blindado para phanto_crisis.ndjson.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)
local config = rawget(_G, "config") or (pcall(require, "core.config") and require("core.config") or {})
local system = rawget(_G, "system") or (pcall(require, "system") and require("system") or nil)

local user_dir = USERDIR or "."
local sep = PATHSEP or "/"
local diag_dir = user_dir .. sep .. ".doxoade" .. sep .. "diagnostics"
local ndjson_file = "phanto_crisis.ndjson"

local PHANTO_CONFIG = {
  enabled = true,
  max_entries = 100,
  flush_interval_sec = 2.0,
  diag_dir = diag_dir,
  ndjson_file = ndjson_file,
}

local _phanto_ring = {}
local _phanto_head = 1
local _phanto_count = 0
local _phanto_last_flush = os.clock()
local _inside_capture = false

rawset(_G, "_PHANTO_CRISIS_STATE", {
  ring = _phanto_ring,
  config = PHANTO_CONFIG,
  total_captured = 0,
  last_error = nil,
})

local function safe_json_escape(str)
  if not str then return "" end
  return tostring(str):gsub("\\", "\\\\")
                      :gsub('"', '\\"')
                      :gsub("\n", "\\n")
                      :gsub("\r", "\\r")
                      :gsub("\t", "\\t")
end

local function ensure_diag_dir(target_dir)
  if not system or not system.mkdir then return end
  local parts = {}
  for p in tostring(target_dir):gmatch("[^/\\]+") do
    table.insert(parts, p)
  end
  local cur = ""
  for i, p in ipairs(parts) do
    if i == 1 and p:find("^[a-zA-Z]:") then
      cur = p
    else
      cur = (cur == "" and "" or cur .. sep) .. p
      pcall(system.mkdir, cur)
    end
  end
end

local function phanto_shadow_flush()
  if _phanto_count == 0 then return end

  pcall(function()
    ensure_diag_dir(PHANTO_CONFIG.diag_dir)

    local target_path = PHANTO_CONFIG.diag_dir .. sep .. PHANTO_CONFIG.ndjson_file

    -- Rotação se exceder 20MB
    local finfo = system and system.get_file_info and system.get_file_info(target_path)
    if finfo and finfo.size and finfo.size > (20 * 1024 * 1024) then
      pcall(os.remove, target_path .. ".bak")
      pcall(os.rename, target_path, target_path .. ".bak")
    end

    local f = io.open(target_path, "a")
    if f then
      local start_idx = _phanto_head - _phanto_count
      if start_idx <= 0 then
        start_idx = start_idx + PHANTO_CONFIG.max_entries
      end

      for i = 1, _phanto_count do
        local idx = ((start_idx + i - 2) % PHANTO_CONFIG.max_entries) + 1
        local entry = _phanto_ring[idx]
        if entry then
          local json_line = string.format(
            '{"ts":%d,"ts_iso":%q,"module":%q,"error":%q,"traceback":%q,"context":%q}\n',
            entry.ts,
            entry.ts_iso,
            safe_json_escape(entry.module),
            safe_json_escape(entry.error),
            safe_json_escape(entry.traceback),
            safe_json_escape(entry.context and entry.context.active_file or "nil")
          )
          f:write(json_line)
        end
      end
      f:flush()
      f:close()

      _phanto_ring = {}
      _phanto_head = 1
      _phanto_count = 0
      _G._PHANTO_CRISIS_STATE.ring = _phanto_ring
    end
  end)
end

local _last_errors = {}

local function phanto_capture(module_name, fn, ...)
  if config.phanto_crisis_enabled == false or PHANTO_CONFIG.enabled == false then
    return pcall(fn, ...)
  end
  if _inside_capture then
    return pcall(fn, ...)
  end

  local args = { ... }
  local ok, result = xpcall(function()
    return fn(table.unpack(args))
  end, function(err)
    _inside_capture = true
    local err_msg = tostring(err)
    local err_key = tostring(module_name) .. ":" .. err_msg:sub(1, 60)
    local now = os.clock()
    local record = _last_errors[err_key]

    -- 🛡️ ANTI-FLOOD: Se o mesmo erro ocorreu nos últimos 3 segundos, silencia no log e conta repetições
    if record and (now - record.time) < 3.0 then
      record.count = record.count + 1
      _inside_capture = false
      return err
    end

    local count_str = ""
    if record and record.count > 1 then
      count_str = string.format(" (repetido %dx)", record.count)
    end
    _last_errors[err_key] = { time = now, count = 1 }

    local trace = debug.traceback("", 2) or ""
    local entry = {
      ts = os.time(),
      ts_iso = os.date("%Y-%m-%d %H:%M:%S"),
      module = tostring(module_name or "unknown"),
      error = err_msg .. count_str,
      traceback = trace,
      context = {
        active_file = (core and core.active_view and core.active_view.doc and core.active_view.doc.filename) or "nil",
      }
    }

    _phanto_ring[_phanto_head] = entry
    _phanto_head = (_phanto_head % PHANTO_CONFIG.max_entries) + 1
    if _phanto_count < PHANTO_CONFIG.max_entries then
      _phanto_count = _phanto_count + 1
    end

    _G._PHANTO_CRISIS_STATE.total_captured = _G._PHANTO_CRISIS_STATE.total_captured + 1
    _G._PHANTO_CRISIS_STATE.last_error = err_msg

    if core and core.log then
      core.log(string.format("👻 [PHANTO:%s] %s%s", tostring(module_name), err_msg, count_str))
    end

    _inside_capture = false
    return err
  end)

  return ok, result
end

rawset(_G, "phanto_capture", phanto_capture)
rawset(_G, "phanto_shadow_flush", phanto_shadow_flush)

if core and core.add_thread then
  core.add_thread(function()
    while true do
      coroutine.yield(PHANTO_CONFIG.flush_interval_sec)
      if _phanto_count > 0 then
        phanto_shadow_flush()
      end
    end
  end)
end

if core and core.log then
  core.log("👻 [PHANTO_CRISIS] Core V2.1 Strict-Safe inicializado.")
end

if config.plugins and config.plugins.settings then
  config.plugins.settings.scan_rate = 0.5 -- Acorda a cada 500ms em vez de 10ms
end
