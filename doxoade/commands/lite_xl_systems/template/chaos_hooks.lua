-- doxoade/commands/lite_xl_systems/template/chaos_hooks.lua
--[[
  🛡️ DOXOADE CHAOS HOOKS & FORENSIC BUFFER ENGINE (V2.4 Resiliente)
  - Interceptação de pcall com Buffer em Memória (Zero-Blocking I/O).
  - Flush periódico em lote e descarte de ruído de requires de sondagem.
  - Varredura de globais escalonada sem degradação de FPS.
]]
local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)
local _in_hook = false
local _log_buffer = {}
local _last_flush = os.clock()

local function _flush_forensic_buffer()
  if #_log_buffer == 0 then return end
  local userdir = USERDIR or "."
  local sep = PATHSEP or "/"
  local log_path = userdir .. sep .. "session_log.txt"
  local f = io.open(log_path, "a")
  if f then
    f:write(table.concat(_log_buffer, "\n") .. "\n")
    f:flush()
    f:close()
  end
  _log_buffer = {}
  _last_flush = os.clock()
end

local function _forensic_sync_write(tag, msg)
  local line = string.format("[%s] %s: %s", os.date("%H:%M:%S"), tag, tostring(msg))
  table.insert(_log_buffer, line)
  -- Descarrega em lote a cada 15 entradas ou após 1.0s de intervalo
  if #_log_buffer >= 15 or (os.clock() - _last_flush) >= 1.0 then
    _flush_forensic_buffer()
  end
end

local original_pcall = pcall
_G.pcall = function(fn, ...)
  if _in_hook then return original_pcall(fn, ...) end
  _in_hook = true
  local trace = ""
  local results = { xpcall(fn, function(err)
    trace = debug.traceback("", 2) or ""
    return err
  end, ...) }
  _in_hook = false

  if not results[1] then
    local err = tostring(results[2] or "")

    -- ✅ DECLARAÇÃO RESTAURADA (Elimina os 30 erros de variável indefinida):
    local is_probe_require = err:find("module '") and (
      err:find("not found:") or
      err:find("no field package.preload") or
      err:find("no file")
    )

    if not is_probe_require and not err:find("core%.emptyview") then
      local caller = trace:match("\t([^\r\n]+)") or "desconhecido"
      _forensic_sync_write("GHOST_PCALL", err .. " | Origem: " .. caller)
      if core and core.log then
        core.log(string.format("👻 [HOOK] pcall falhou: %s\n   ↳ Origem: %s", err, caller))
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

if core and core.error then
  local original_core_error = core.error
  core.error = function(...)
    local msg = table.concat({...}, " ")
    _forensic_sync_write("CORE_ERROR", msg)
    return original_core_error(...)
  end
end

local _tracked_globals = {}
for k in pairs(_G) do _tracked_globals[k] = true end

-- ⚖️ Whitelist de globais intencionais (registradas via rawset pelos módulos)
local _ALLOWED_GLOBALS = {
    Khonsu = true,
    forensic_data = true,
    DOXOADE_API = true,
    UIForge = true,
    PTYClient = true,
    AnsiParser = true,
    flush_session_log = true,
    phanto_capture = true,
    phanto_shadow_flush = true,
}

if core and core.add_thread then
  -- Flush contínuo do buffer em background
  core.add_thread(function()
    while true do
      coroutine.yield(1.0)
      _flush_forensic_buffer()
    end
  end)

  -- Varredura de vazamento de globais suavizada
  core.add_thread(function()
    coroutine.yield(1.0) -- Aguarda estabilização do boot
    while true do
      coroutine.yield(1.5)
      for k in pairs(_G) do
--        if not _tracked_globals[k] and not k:match("^_") then
        if not _tracked_globals[k] and not k:match("^_") and not _ALLOWED_GLOBALS[k] then
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

_forensic_sync_write("HOOKS_INIT", "Hooks forenses ativos com I/O em buffer (Zero-Freeze).")
_flush_forensic_buffer()
