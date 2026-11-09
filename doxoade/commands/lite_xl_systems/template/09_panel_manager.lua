-- doxoade/commands/lite_xl_systems/template/09_panel_manager.lua
--[[
  📐 DOXOADE PANEL MANAGER (V2.0 — Delegated & Coordinated)
  Integrado ao Sovereign Dual-Split Engine do 05_split_mover.lua.
]]

local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"

local PanelSlots = {}

function PanelSlots.equalize_splits()
  local F = rawget(_G, "DOXOADE_FLOW")
  if F and F.mark then F.mark("PANEL", "equalize_start", "") end
  local root = core.root_view and core.root_view.root_node
  if not root then return end
  local function traverse(n)
    if not n or n.type == "leaf" then return end
    if not (n.a and n.a.locked) and not (n.b and n.b.locked) then
      n.divider = 0.5
    end
    traverse(n.a)
    traverse(n.b)
  end
  traverse(root)
  if root.update_layout then pcall(root.update_layout, root) end
  core.redraw = true
  if F and F.mark then F.mark("PANEL", "equalize_end", "") end
end

rawset(_G, "PanelSlots", PanelSlots)
rawset(_G, "_DOXOADE_PANEL_SLOTS", PanelSlots)

command.add(nil, {
  ["doxoade:equalize-splits"] = function()
    PanelSlots.equalize_splits()
    if core.log then core.log("⚖️ [PANEL] Splits equalizados (50% / 50%).") end
  end,
})

if core.log then
  core.log("📐 [PANEL] Panel Manager V2.0 harmonizado.")
end

return PanelSlots
