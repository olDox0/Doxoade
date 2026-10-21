-- doxoade/commands/lite_xl_systems/template/13b_leap_toolbar.lua
--[[
⚡ DOXOADE LEAP SYS KVM CONTROLLER & DISPATCHER (V3.0 Sovereign Locator)
- Sonda autônoma com persistência de caminho para sysutils.exe (PC-A e PC-B).
- Despacho desacoplado no Windows (sem congelar o loop gráfico do Lite XL).
- Escrita e leitura direta do contrato ~/.doxoade/leap_state.json.
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local StatusView = require "core.statusview"

if rawget(_G, "_DOXOADE_LEAP_TOOLBAR_LOADED") then return end
rawset(_G, "_DOXOADE_LEAP_TOOLBAR_LOADED", true)

local sep = PATHSEP or "/"
local home = os.getenv("USERPROFILE") or os.getenv("HOME") or "."
local state_file = home .. sep .. ".doxoade" .. sep .. "leap_state.json"

local LeapHUD = {
    active = false,
    mode = "idle",
    target = "bluebaby",
    server_ip = "192.168.18.52", -- IP Wi-Fi padrão do Amaranth
    port = 24800,
    sysutils_bin = nil,
    last_toggle_time = 0,
}

-- ── 0. Verificador de Existência de Arquivo ─────────────────────────────────
local function file_exists(path)
    if not path or path == "" then return false end
    local info = system.get_file_info(path)
    return info ~= nil and info.type == "file"
end

-- ── 1. Leitura O(1) do Contrato de Estado ────────────────────────────────────
local function read_leap_state()
    local f = io.open(state_file, "r")
    if not f then
        LeapHUD.active = false
        LeapHUD.mode = "idle"
        return
    end
    local content = f:read("*a") or ""
    f:close()

    LeapHUD.active = content:find('"active":%s*true') ~= nil
    LeapHUD.mode = content:match('"mode":%s*"([^"]+)"') or "idle"
    LeapHUD.target = content:match('"target":%s*"([^"]+)"') or "bluebaby"

    local ip = content:match('"server_ip":%s*"([^"]+)"')
    if ip and ip ~= "" then LeapHUD.server_ip = ip end

    local bin = content:match('"sysutils_bin":%s*"([^"]+)"')
    if bin and bin ~= "" then
        bin = bin:gsub("\\\\", "\\")
        if file_exists(bin) then LeapHUD.sysutils_bin = bin end
    end
end

-- ── 2. Gravação do Contrato de Estado ─────────────────────────────────────────
local function write_leap_state(active, mode, target, ip)
    local f = io.open(state_file, "w")
    if f then
        local escaped_bin = (LeapHUD.sysutils_bin or ""):gsub("\\", "\\\\")
        local payload = string.format(
            '{\n  "active": %s,\n  "mode": "%s",\n  "target": "%s",\n  "server_ip": "%s",\n  "port": %d,\n  "sysutils_bin": "%s",\n  "updated_at": %d\n}',
            active and "true" or "false",
            mode or "idle",
            target or "bluebaby",
            ip or "192.168.18.52",
            LeapHUD.port,
            escaped_bin,
            os.time()
        )
        f:write(payload)
        f:close()
    end
end

-- ── 3. Sonda Autônoma do Executável SysUtils (PC-B e PC-A) ───────────────────
local function resolve_sysutils()
    if LeapHUD.sysutils_bin and file_exists(LeapHUD.sysutils_bin) then
        return LeapHUD.sysutils_bin
    end

    read_leap_state()
    if LeapHUD.sysutils_bin and file_exists(LeapHUD.sysutils_bin) then
        return LeapHUD.sysutils_bin
    end

    local userprofile = os.getenv("USERPROFILE") or ("C:\\Users\\" .. (os.getenv("USERNAME") or ""))
    local candidates = {
        -- PC-B (Bluebaby)
        "C:\\Users\\Victor Alexandre\\Documents\\Sysutils_proj\\venv\\Scripts\\sysutils.exe",
        userprofile .. "\\Documents\\Sysutils_proj\\venv\\Scripts\\sysutils.exe",
        userprofile .. "\\Documents\\Sysutils_proj\\sysutils.exe",
        -- PC-A (Amaranth)
        "C:\\Users\\olDox222\\Documents\\A20251122\\DOSSIER\\Altonomo\\Projetos_E_Programas\\Projeto SysUtils\\venv\\Scripts\\sysutils.exe",
        userprofile .. "\\Documents\\A20251122\\DOSSIER\\Altonomo\\Projetos_E_Programas\\Projeto SysUtils\\venv\\Scripts\\sysutils.exe",
        userprofile .. "\\Documents\\SysUtils\\venv\\Scripts\\sysutils.exe",
    }

    for _, path in ipairs(candidates) do
        if file_exists(path) then
            LeapHUD.sysutils_bin = path
            write_leap_state(LeapHUD.active, LeapHUD.mode, LeapHUD.target, LeapHUD.server_ip)
            core.log("[LEAP] 🎯 SysUtils localizado e vinculado: %s", path)
            return path
        end
    end

    -- Sonda via 'where' no PATH do sistema
    local p = io.popen("where sysutils.exe 2>nul")
    if p then
        local line = p:read("*l")
        p:close()
        if line and file_exists(line) then
            LeapHUD.sysutils_bin = line
            write_leap_state(LeapHUD.active, LeapHUD.mode, LeapHUD.target, LeapHUD.server_ip)
            core.log("[LEAP] 🎯 SysUtils localizado no PATH: %s", line)
            return line
        end
    end

    core.error("[LEAP] ✘ 'sysutils.exe' não localizado! Verifique a pasta Sysutils_proj.")
    return nil
end

-- ── 4. Execução Silenciosa e Desacoplada no Windows ──────────────────────────
local function execute_async(cmd)
    if PLATFORM == "Windows" or os.getenv("OS") == "Windows_NT" then
        os.execute('start /b cmd /c "' .. cmd .. '" > NUL 2>&1')
    else
        os.execute(cmd .. ' > /dev/null 2>&1 &')
    end
end

-- ── 5. Despachante Soberano de Toggle ─────────────────────────────────────────
local function toggle_leap_state()
    local now = os.clock()
    if (now - LeapHUD.last_toggle_time) < 0.6 then return end
    LeapHUD.last_toggle_time = now

    read_leap_state()

    local bin = resolve_sysutils()
    if not bin then return end
    local qbin = '"' .. bin .. '"'

    local hostname = (os.getenv("COMPUTERNAME") or "UNKNOWN"):upper()
    local is_amaranth = hostname:find("AMARANTH") ~= nil

    if LeapHUD.active then
        -- Parar serviço ativo
        execute_async(qbin .. " leap stop")
        write_leap_state(false, "idle", "", LeapHUD.server_ip)
        LeapHUD.active = false
        LeapHUD.mode = "idle"
        core.log("🛑 [LEAP] Servidor KVM desativado.")
        core.redraw = true
        return
    end

    if is_amaranth then
        -- AMARANTH -> Dispara como Host com topologia fixada à direita para o bluebaby
        local cmd = string.format('%s leap host --client bluebaby --pos right --port 24800 --no-firewall', qbin)
        execute_async(cmd)
        write_leap_state(true, "host", "bluebaby", LeapHUD.server_ip)
        LeapHUD.active = true
        LeapHUD.mode = "host"
        core.log("🚀 [LEAP HOST] Servidor KVM ativo em Amaranth ➔ bluebaby (Direita :24800)")
    else
        -- BLUEBABY -> Conecta ao Amaranth
        local cmd = string.format('%s leap join %s --port 24800 --name bluebaby', qbin, LeapHUD.server_ip)
        execute_async(cmd)
        write_leap_state(true, "client", "Amaranth", LeapHUD.server_ip)
        LeapHUD.active = true
        LeapHUD.mode = "client"
        core.log("🔗 [LEAP CLI] Conectando ao host Amaranth (" .. LeapHUD.server_ip .. ")")
    end

    core.redraw = true
end

-- ── 6. Polling de Sincronia em Background ────────────────────────────────────
if core and core.add_thread then
    core.add_thread(function()
        while true do
            coroutine.yield(1.0)
            local prev_active = LeapHUD.active
            local prev_mode = LeapHUD.mode
            read_leap_state()
            if prev_active ~= LeapHUD.active or prev_mode ~= LeapHUD.mode then
                core.redraw = true
            end
        end
    end)
end

-- ── 7. Registro de Comandos e Atalhos ────────────────────────────────────────
command.add(nil, {
    ["doxoade:leap-toggle"] = function() toggle_leap_state() end,
    ["doxoade:toggle-leap-service"] = function() toggle_leap_state() end,
    ["doxoade:leap-locate-sysutils"] = function()
        LeapHUD.sysutils_bin = nil
        local bin = resolve_sysutils()
        if bin then
            core.log("[LEAP] ✔ Vinculado a: %s", bin)
        end
    end,
    ["doxoade:leap-stop"] = function()
        local bin = resolve_sysutils()
        if bin then
            execute_async('"' .. bin .. '" leap stop')
        end
        write_leap_state(false, "idle", "", LeapHUD.server_ip)
        LeapHUD.active = false
        LeapHUD.mode = "idle"
        core.log("🛑 [LEAP] Processos encerrados.")
        core.redraw = true
    end,
})

keymap.add { ["ctrl+alt+l"] = "doxoade:leap-toggle" }
