-- doxoade/commands/lite_xl_systems/template/10_ghost_tracer.lua
--[[
  👻 DOXOADE GHOST TRACER (V2.0)
  Tracer de frame e coletor forense de anomalias SDL2.
]]
local core = rawget(_G, "core") or require("core")
rawset(_G, "_DOXOADE_GHOST_TRACER", {
  active = true,
  last_pulse = os.clock(),
})
