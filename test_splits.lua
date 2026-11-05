-- test_splits.lua
local core = require "core"
local command = require "core.command"

local tests = {
    ["doxoade:move-tab-to-opposite-panel"] = "Ctrl+Alt+D",
    ["doxoade:toggle-split-orientation"] = "Ctrl+L",
    ["doxoade:swap-split-panels"] = "Ctrl+Shift+L",
    ["doxoade:focus-opposite-panel"] = "F6",
}

for cmd_name, shortcut in pairs(tests) do
    if command.map and command.map[cmd_name] then
        print(string.format("✅ [TEST] %s (%s) registrado.", shortcut, cmd_name))
    else
        print(string.format("❌ [TEST] %s (%s) NÃO registrado.", shortcut, cmd_name))
    end
end