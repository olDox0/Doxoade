-- doxoade/commands/lite_xl_systems/template/13b_leap_toolbar.lua
--[[
⚡ DOXOADE LEAP SYS KVM CONTROLLER & DISPATCHER (V2.0 Sovereign)
- Acionamento direto do Host no Amaranth (Amaranth -> bluebaby à direita).
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
    last_toggle_time = 0,
}

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
end

-- ── 2. Gravação do Contrato de Estado ─────────────────────────────────────────
local function write_leap_state(active, mode, target, ip)
    local f = io.open(state_file, "w")
    if f then
        local payload = string.format(
            '{\n  "active": %s,\n  "mode": "%s",\n  "target": "%s",\n  "server_ip": "%s",\n  "port": %d,\n  "updated_at": %d\n}',
            active and "true" or "false",
            mode or "idle",
            target or "bluebaby",
            ip or "192.168.18.52",
            LeapHUD.port,
            os.time()
        )
        f:write(payload)
        f:close()
    end
end

-- ── 3. Execução Silenciosa e Desacoplada no Windows ──────────────────────────
local function execute_async(cmd)
    if PLATFORM == "Windows" or os.getenv("OS") == "Windows_NT" then
        -- start /b evita abrir janela de console preta e não trava o Lite XL
        os.execute('start /b cmd /c "' .. cmd .. '" > NUL 2>&1')
    else
        os.execute(cmd .. ' > /dev/null 2>&1 &')
    end
end

-- ── 4. Despachante Soberano de Toggle ─────────────────────────────────────────
local function toggle_leap_state()
    local now = os.clock()
    if (now - LeapHUD.last_toggle_time) < 0.6 then return end
    LeapHUD.last_toggle_time = now

    read_leap_state()

    local hostname = os.getenv("COMPUTERNAME") or "UNKNOWN"
    local is_amaranth = hostname:upper():find("AMARANTH") ~= nil

    if LeapHUD.active then
        -- Parar serviço ativo
        execute_async("sysutils leap stop")
        write_leap_state(false, "idle", "", LeapHUD.server_ip)
        LeapHUD.active = false
        LeapHUD.mode = "idle"
        core.log("🛑 [LEAP] Servidor KVM desativado.")
        core.redraw = true
        return
    end

    if is_amaranth then
        -- AMARANTH -> Dispara como Host com topologia fixada à direita para o bluebaby
        local cmd = "sysutils leap host --client bluebaby --pos right --port 24800 --no-firewall"
        execute_async(cmd)
        write_leap_state(true, "host", "bluebaby", LeapHUD.server_ip)
        LeapHUD.active = true
        LeapHUD.mode = "host"
        core.log("🚀 [LEAP HOST] Servidor KVM ativo em Amaranth ➔ bluebaby (Direita :24800)")
    else
        -- BLUEBABY -> Conecta ao Amaranth
        local cmd = string.format("sysutils leap join %s --port 24800 --name bluebaby", LeapHUD.server_ip)
        execute_async(cmd)
        write_leap_state(true, "client", "Amaranth", LeapHUD.server_ip)
        LeapHUD.active = true
        LeapHUD.mode = "client"
        core.log("🔗 [LEAP CLI] Conectando ao host Amaranth (" .. LeapHUD.server_ip .. ")")
    end

    core.redraw = true
end

-- ── 5. Polling de Sincronia em Background ────────────────────────────────────
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

-- ── 6. Registro de Comandos e Atalhos ────────────────────────────────────────
command.add(nil, {
    ["doxoade:leap-toggle"] = function() toggle_leap_state() end,
    ["doxoade:toggle-leap-service"] = function() toggle_leap_state() end,
    ["doxoade:leap-stop"] = function()
        execute_async("sysutils leap stop")
        write_leap_state(false, "idle", "", LeapHUD.server_ip)
        LeapHUD.active = false
        LeapHUD.mode = "idle"
        core.log("🛑 [LEAP] Processos encerrados.")
        core.redraw = true
    end,
})

keymap.add { ["ctrl+alt+l"] = "doxoade:leap-toggle" }
