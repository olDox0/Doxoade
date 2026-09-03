-- doxoade/commands/lite_xl_systems/template/chaos_hooks.lua
-- =============================================================================
-- 🛡️ DOXOADE CHAOS DETECTION HOOKS (Silenciador de Probes + Anti-Recursão)
-- =============================================================================
local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)

local _in_hook = false

local function _forensic_sync_write(tag, msg)
  local userdir = USERDIR or "."
  local sep = PATHSEP or "/"
  local log_path = userdir .. sep .. "session_log.txt"
  local f = io.open(log_path, "a")
  if f then
    f:write(string.format("[%s] %s: %s\n", os.date("%H:%M:%S"), tag, tostring(msg)))
    f:flush()
    f:close()
  end
end

-- 1. Hook no pcall (Captura apenas erros reais de execução, ignorando probes de require)
local original_pcall = pcall
_G.pcall = function(fn, ...)
  if _in_hook then
    return original_pcall(fn, ...)
  end

  _in_hook = true
  local results = {original_pcall(fn, ...)}
  _in_hook = false

  if not results[1] then
    local err = tostring(results[2] or "")
    -- 🛑 FILTRO FORENSE: Ignora requires exploratórios do API Guard / Polyfills
    local is_probe_require = err:find("module '") and (err:find("not found:") or err:find("no field package.preload"))
    if not is_probe_require and not err:find("core%.emptyview") then
      _forensic_sync_write("GHOST_PCALL", err)
      if core and core.log then
        core.log("👻 [HOOK] pcall capturou erro: " .. err)
      end
    end
  end

  local unpack_fn = table.unpack or rawget(_G, "unpack")
  if unpack_fn then
    return unpack_fn(results)
  else
    return results[1], results[2], results[3], results[4]
  end
end

-- 2. Hook no core.error
if core and core.error then
  local original_core_error = core.error
  core.error = function(...)
    local msg = table.concat({...}, " ")
    _forensic_sync_write("CORE_ERROR", msg)
    return original_core_error(...)
  end
end

-- 3. Monitor de Globais Vazadas (Alta frequência: 0.2s)
local _tracked_globals = {}
for k in pairs(_G) do _tracked_globals[k] = true end

if core and core.add_thread then
  core.add_thread(function()
    while true do
      coroutine.yield(0.2)
      for k in pairs(_G) do
        if not _tracked_globals[k] and not k:match("^_") then
          _forensic_sync_write("GLOBAL_LEAK", k)
          if core.log then
            core.log("👻 [HOOK] Global vazada: " .. k)
          end
          _tracked_globals[k] = true
        end
      end
    end
  end)
end

_forensic_sync_write("HOOKS_INIT", "Hooks forenses ativos com I/O síncrono e filtro de require.")
