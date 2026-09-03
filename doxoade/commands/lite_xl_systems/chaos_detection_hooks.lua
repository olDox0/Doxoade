-- doxoade/commands/lite_xl_systems/chaos_detection_hooks.lua
-- =============================================================================
-- 🛡️ HOOKS DE DETECÇÃO EM RUNTIME (Para capturar erros ocultos)
-- =============================================================================

local core = rawget(_G, "core") or require("core")

-- 1. Hook no pcall para logar erros engolidos
local original_pcall = pcall
_G.pcall = function(fn, ...)
    local results = {original_pcall(fn, ...)}
    if not results[1] then
        -- Erro capturado, loga no session_log
        if core and core.log then
            core.log("👻 [HOOK] pcall capturou erro: " .. tostring(results[2]))
        end
    end
    return table.unpack(results)
end

-- 2. Monitor de globais vazadas (executa a cada 5 segundos)
local _tracked_globals = {}
for k in pairs(_G) do
    _tracked_globals[k] = true
end

core.add_thread(function()
    while true do
        coroutine.yield(5.0)
        for k in pairs(_G) do
            if not _tracked_globals[k] and not k:match("^_") then
                core.log("👻 [HOOK] Global vazada detectada: " .. k)
                _tracked_globals[k] = true
            end
        end
    end
end)

-- 3. Hook no core.error para capturar todos os erros
local original_core_error = core.error
core.error = function(...)
    local msg = table.concat({...}, " ")
    core.log("💥 [HOOK] core.error chamado: " .. msg)
    return original_core_error(...)
end

core.log("🛡️ [HOOKS] Hooks de detecção de caos ativados.")
