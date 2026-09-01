# doxoade/commands/lite_xl_systems/chaos_payload.py
""" 🍷 DOXOADE CHAOS PAYLOAD — Mega-Payload de Estresse Isolado.
Contém os vetores de falha para injeção no Sandbox via Runner. """

MEGA_CHAOS_PAYLOAD = """
local core = require "core"
local API = rawget(_G, "DOXOADE_API")
core.log("🍷 [SANDBOX] Mega-Payload de Caos carregado. Vetores armados...")

-- VETOR 1: Fantasma da API (Anúbis)
core.add_thread(function()
    coroutine.yield(1.5) 
    core.log("💥 [CAOS 1] Tentando patchear método inexistente...")
    if API then
        API.patch({
            id = "chaos:nil_method", target = core, method = "this_method_does_not_exist",
            feature = "Chaos Test 1",
            wrapper = function(original, self, ...) return original(self, ...) end,
            fallback = function() core.log("🐺 [API GUARD] Fallback de emergência ativado!") end
        })
    end
end)

-- VETOR 2: Colapso da Árvore (Ártemis)
core.add_thread(function()
    coroutine.yield(3.0)
    core.log("💥 [CAOS 2] Esvaziando views do nó ativo...")
    local active_node = core.root_view:get_active_node()
    if active_node and active_node.views then
        active_node.views = {}
        active_node.active_view = nil
    end
    core.redraw = true
end)

-- VETOR 3: Gargalo de Chronos (Hórus)
core.add_thread(function()
    coroutine.yield(5.0)
    core.log("🐌 [CAOS 3] Iniciando thread pesada...")
    local start = os.clock()
    while os.clock() - start < 2.0 do
        local x = 0
        for i=1, 100000 do x = x + math.sqrt(i) end
        coroutine.yield(0)
    end
    core.log("✔ [CAOS 3] Thread pesada concluída.")
end)

-- VETOR 4: Pecado da Global (Ma'at)
core.add_thread(function()
    coroutine.yield(8.0)
    core.log("💥 [CAOS 4] Tentando indexar valor nil...")
    local ok, err = pcall(function()
        local x = nil
        x.y = 1 
    end)
    if not ok then
        core.log("🛡️ [MA'AT] Erro capturado: " .. tostring(err))
    end
end)
"""
