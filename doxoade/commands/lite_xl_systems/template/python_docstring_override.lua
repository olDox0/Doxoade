-- doxoade/commands/lite_xl_systems/template/python_docstring_override.lua
--[[
🟢 DOXOADE PYTHON DOCSTRING OVERRIDE (V2.0 Shadow-Safe)
Força a coloração verde em docstrings Python (""" ... """).
Corrige o erro de 'nil value (field color)' garantindo imports e conversão segura com fallback.
Compliance: ProDeNov 1.2.1, PASC-6.1.
]]
local core = require "core"
local style = require "core.style"
local common = require "core.common"
local syntax = require "core.syntax"

-- =============================================================================
-- 🎨 PALETA DE VERDES PARA DOCSTRINGS (Conversão Segura de HEX com Fallback)
-- =============================================================================
local function safe_color(hex)
    -- Tenta usar o conversor nativo do Lite XL
    local ok, res = pcall(common.color, hex)
    if ok and res then return res end
    
    -- Fallback manual absoluto se common.color falhar no Shadow Pass
    local r = tonumber(hex:sub(2, 3), 16) or 255
    local g = tonumber(hex:sub(4, 5), 16) or 255
    local b = tonumber(hex:sub(6, 7), 16) or 255
    return { r, g, b, 255 }
end

-- =============================================================================
-- 🎨 PALETA DE VERDES PARA DOCSTRINGS (Valores Literais RGBA)
-- =============================================================================
local DOCSTRING_GREEN = { 34, 197, 94, 255 }        -- #22c55e
local DOCSTRING_GREEN_DARK = { 21, 128, 61, 255 }   -- #15803d

style.syntax = style.syntax or {}
style.syntax["string.docstring"] = DOCSTRING_GREEN
style.syntax["string.docstring.delimiter"] = DOCSTRING_GREEN_DARK

-- =============================================================================
-- 🔧 INJEÇÃO DE PATTERNS NO SYNTAX PYTHON
-- =============================================================================
local function override_python_syntax()
    local python_syn = nil
    if syntax and syntax.items then
        for _, syn in ipairs(syntax.items) do
            if syn.name == "Python" or (syn.files and syn.files[1] == "%.py$") then
                python_syn = syn
                break
            end
        end
    end
    
    if not python_syn then return end
    
    -- Evita duplicação de patterns (idempotente)
    if python_syn._doxoade_docstring_override then return end
    python_syn._doxoade_docstring_override = true

    -- Patterns de docstrings (devem vir PRIMEIRO para ter prioridade máxima)
    local docstring_patterns = {
        { pattern = { '"""', '"""', '\\' }, type = "string.docstring" },
        { pattern = { "'''", "'''", '\\' }, type = "string.docstring" },
        { pattern = { '[fF][rR]"""', '"""', '\\' }, type = "string.docstring" },
        { pattern = { '[rR][fF]"""', '"""', '\\' }, type = "string.docstring" },
        { pattern = { '[fF]"""', '"""', '\\' }, type = "string.docstring" },
        { pattern = { '[rR]"""', '"""', '\\' }, type = "string.docstring" },
        { pattern = { '[bB]"""', '"""', '\\' }, type = "string.docstring" },
        { pattern = { '[uU]"""', '"""', '\\' }, type = "string.docstring" },
    }
    
    -- Insere no início da lista de patterns
    for i = #docstring_patterns, 1, -1 do
        table.insert(python_syn.patterns, 1, docstring_patterns[i])
    end
    
    if core.log then 
        core.log("🟢 [DOXOADE] Syntax Python sobrescrito com docstrings verdes!") 
    end
end

-- 1. Executa após um pequeno delay para garantir que o syntax original já carregou
core.add_thread(function()
    coroutine.yield(0.5)
    pcall(override_python_syntax)
end)

-- 2. Hook para futuros syntax loads (garante funcionamento mesmo em hot-reload)
if syntax and syntax.add then
    local original_add = syntax.add
    syntax.add = function(syn, ...)
        local result = original_add(syn, ...)
        if syn.name == "Python" or (syn.files and syn.files[1] == "%.py$") then
            core.add_thread(function()
                coroutine.yield(0.1)
                pcall(override_python_syntax)
            end)
        end
        return result
    end
end
