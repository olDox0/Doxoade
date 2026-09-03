# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/chaos_deep_payloads.py
"""
🏜️ SET ENGINE — Payloads de Caos Profundo (Crash, Falha, Erro Oculto).
Cada payload possui uma categoria e uma expectativa de detecção clara.
"""

# =============================================================================
# 1. CRASHES DE BOOT (Top-Level: Executados diretamente, matam o processo C)
# =============================================================================

CRASH_NIL_INDEX = """
-- 💥 CRASH FATAL DE BOOT: Indexação de nil direta no chunk principal
local ghost = nil
ghost.method() -- BOOM imediato no boot
"""

CRASH_STACK_OVERFLOW = """
-- 💥 CRASH FATAL DE BOOT: Stack overflow real (o '+ 1' impede a otimização de tail-call)
local function recursive_death(n)
    local x = recursive_death(n + 1) + 1
    return x
end
recursive_death(0)
"""

CRASH_INVALID_REQUIRE = """
-- 💥 CRASH FATAL DE BOOT: require inexistente sem pcall no chunk principal
local ghost_module = require "this.module.does.not.exist.anywhere.in.universe"
"""

# =============================================================================
# 2. FALHAS EM RUNTIME (Threads assíncronas protegidas ou gerenciadas)
# =============================================================================

FAIL_ORPHAN_VIEWS = """
-- 🕳️ FALHA: Injeção de view corrompida sem métodos contratuais
core.add_thread(function()
    coroutine.yield(1.0)
    local node = core.root_view and core.root_view:get_active_node()
    if node and node.views then
        table.insert(node.views, { doc = nil, position = {x=0, y=0}, size = {x=100, y=100} })
        core.redraw = true
        core.log("🕳️ [SET] View órfã injetada no nó ativo.")
    end
end)
"""

FAIL_CONFIG_CORRUPTION = """
-- 🕳️ FALHA: Tipagem corrompida em variáveis críticas de configuração
core.add_thread(function()
    coroutine.yield(1.0)
    local config = require "core.config"
    config.always_show_tabs = "NOT_A_BOOLEAN_VALUE"
    config.treeview_indent = -9999
    core.redraw = true
    core.log("🕳️ [SET] Configurações corrompidas injetadas.")
end)
"""

FAIL_THREAD_LEAK = """
-- 🕳️ FALHA: 50 threads zumbis consumindo ciclos de CPU
core.add_thread(function()
    coroutine.yield(1.0)
    for i = 1, 50 do
        core.add_thread(function()
            while true do
                coroutine.yield(0.1)
                local _ = math.sqrt(os.clock())
            end
        end)
    end
    core.log("🕳️ [SET] 50 threads zumbis disparadas.")
end)
"""

# =============================================================================
# 3. ERROS OCULTOS E VAZAMENTOS (Devem ser capturados pelos Hooks)
# =============================================================================

HIDDEN_SWALLOWED_ERROR = """
-- 👻 ERRO OCULTO: pcall engolindo exceção crítica silenciosamente
core.add_thread(function()
    coroutine.yield(1.0)
    pcall(function()
        local config = require "core.config"
        config.nonexistent_field.critical_subfield = true
    end)
end)
"""

HIDDEN_MONKEY_PATCH_NIL = """
-- 👻 ERRO OCULTO: Monkey-patch inseguro sobre método nil
core.add_thread(function()
    coroutine.yield(1.0)
    local RootView = require "core.rootview"
    local original_ghost = RootView.method_that_never_existed
    RootView.method_that_never_existed = function(self)
        if original_ghost then return original_ghost(self) end
    end
    core.log("👻 [SET] Monkey patch aplicado em símbolo nil.")
end)
"""

HIDDEN_GLOBAL_LEAK = """
-- 👻 ERRO OCULTO: Poluição do escopo global sem declaração _G
core.add_thread(function()
    coroutine.yield(1.0)
    AccidentalGlobalLeakVar = "Vazamento detectado pelo Ma'at"
    AnotherLeakedTable = { leaked = true }
end)
"""

# =============================================================================
# CATÁLOGO DE VETORES DE CAOS
# =============================================================================

DEEP_CHAOS_VECTORS = [
    {"id": "CRASH_NIL",       "name": "Nil Index Fatal",        "category": "crash",  "payload": CRASH_NIL_INDEX,       "expected_detector": "process_exit"},
    {"id": "CRASH_STACK",     "name": "Stack Overflow",         "category": "crash",  "payload": CRASH_STACK_OVERFLOW,  "expected_detector": "process_exit"},
    {"id": "CRASH_REQUIRE",   "name": "Require Fantasma",       "category": "crash",  "payload": CRASH_INVALID_REQUIRE, "expected_detector": "process_exit"},
    {"id": "FAIL_ORPHAN",     "name": "Views Órfãs",            "category": "fault",  "payload": FAIL_ORPHAN_VIEWS,     "expected_detector": "log_match"},
    {"id": "FAIL_CONFIG",     "name": "Config Corrompida",      "category": "fault",  "payload": FAIL_CONFIG_CORRUPTION,"expected_detector": "log_match"},
    {"id": "FAIL_THREADS",    "name": "Thread Leak (50 zumbis)","category": "fault",  "payload": FAIL_THREAD_LEAK,      "expected_detector": "log_match"},
    {"id": "HIDDEN_PCALL",    "name": "pcall Silencioso",       "category": "hidden", "payload": HIDDEN_SWALLOWED_ERROR,"expected_detector": "hook_pcall"},
    {"id": "HIDDEN_PATCH",    "name": "Patch em Nil Silencioso","category": "hidden", "payload": HIDDEN_MONKEY_PATCH_NIL,"expected_detector": "hook_patch"},
    {"id": "HIDDEN_GLOBAL",   "name": "Vazamento de Global",    "category": "hidden", "payload": HIDDEN_GLOBAL_LEAK,   "expected_detector": "hook_global"},
]
