-- doxoade/commands/lite_xl_systems/template/10_forensic_engine.lua
-- =============================================================================
-- DOXOADE FORENSIC ENGINE (Horus/Anúbis Protocol)
-- Coleta telemetria de erros, performance e ambiente para o Doxoade CLI.
-- =============================================================================
local core = require "core"
local config = require "core.config"

local diag_dir = USERDIR .. PATHSEP .. ".doxoade" .. PATHSEP .. "diagnostics"
pcall(function() system.mkdir(diag_dir) end)
local report_path = diag_dir .. PATHSEP .. "forensic_report.txt"

local forensic_data = {
    errors = {},
    performance = {},
    env_plugins = {},
    start_time = os.time()
}

-- 🐺 1. QUEM E ONDE (Error Interception)
local original_core_error = core.error
function core.error(...)
    local msg = table.concat({...}, " ")
    local traceback = debug.traceback("", 2)
    
    local culprit = "core"
    local culprit_file = "unknown"
    local culprit_line = 0
    
    -- Parseia o traceback para achar o primeiro arquivo fora do core
    for line in traceback:gmatch("[^\r\n]+") do
        if not line:match("core[/\\]init%.lua") and 
           not line:match("forensic_engine%.lua") and
           not line:match("%[C%]:") and
           not line:match("%[string") then
            local file, ln = line:match("(.-):(%d+):")
            if file and not file:match("core[/\\]") then
                culprit_file = file
                culprit_line = tonumber(ln) or 0
                culprit = file:match("plugins[/\\](.-)[/\\]") or 
                          file:match("plugins[/\\](.-)%.lua") or "user_config"
                break
            end
        end
    end

    table.insert(forensic_data.errors, {
        msg = msg,
        culprit = culprit,
        file = culprit_file,
        line = culprit_line,
        trace = traceback,
        time = os.date("%H:%M:%S")
    })

    return original_core_error(...)
end

-- 🏹 2. QUANTO (Filesystem & Performance Bottleneck)
local original_add_dir = core.add_project_directory
function core.add_project_directory(path, ...)
    local start = os.clock()
    local ok, res = pcall(original_add_dir, path, ...)
    local elapsed = os.clock() - start
    
    table.insert(forensic_data.performance, {
        action = "index_project",
        target = path,
        duration = string.format("%.3f", elapsed),
        status = elapsed > 1.5 and "BOTTLENECK" or "OK",
        time = os.date("%H:%M:%S")
    })
    
    if ok then return res else error(res) end
end

-- 🦅 3. EXPORTAÇÃO DO RELATÓRIO (Thread de Background)
core.add_thread(function()
    coroutine.yield(3.0) -- Espera os plugins carregarem
    
    -- Captura plugins ativos
    if core.plugins then
        for name, _ in pairs(core.plugins) do
            table.insert(forensic_data.env_plugins, name)
        end
    end

    -- Gera o relatório em disco (Formato TXT estruturado para o Doxoade Python)
    local f = io.open(report_path, "w")
    if f then
        f:write("=== DOXOADE FORENSIC REPORT ===\n")
        f:write(string.format("Generated: %s\n\n", os.date("%Y-%m-%d %H:%M:%S")))
        
        f:write("--- ERRORS ---\n")
        if #forensic_data.errors == 0 then
            f:write("No errors captured.\n")
        else
            for _, err in ipairs(forensic_data.errors) do
                f:write(string.format("[%s] CULPRIT: %s | FILE: %s:%d\n", err.time, err.culprit, err.file, err.line))
                f:write(string.format("MSG: %s\n", err.msg))
                f:write(string.format("TRACE: %s\n\n", err.trace))
            end
        end
        
        f:write("--- PERFORMANCE ---\n")
        if #forensic_data.performance == 0 then
            f:write("No performance events.\n")
        else
            for _, perf in ipairs(forensic_data.performance) do
                f:write(string.format("[%s] ACTION: %s | TARGET: %s | DURATION: %ss | STATUS: %s\n", 
                    perf.time, perf.action, perf.target, perf.duration, perf.status))
            end
        end
        
        f:write("--- ENVIRONMENT ---\n")
        f:write("Platform: " .. (PLATFORM or "Unknown") .. "\n")
        f:write("Plugins: " .. table.concat(forensic_data.env_plugins, ", ") .. "\n")
        
        f:close()
    end
end)
