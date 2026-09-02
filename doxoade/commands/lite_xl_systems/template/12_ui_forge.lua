-- doxoade/commands/lite_xl_systems/template/12_ui_forge.lua
-- =============================================================================
local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"
local style = require "core.style"
local View = require "core.view"
local config = require "core.config"

local UIForge = {
  views = {}
}
rawset(_G, "UIForge", UIForge)

local SovereignDockedView = View:extend()

function SovereignDockedView:new(config)
  SovereignDockedView.super.new(self)
  config = config or {}
  self.title = config.title or "Painel Soberano"
  self.height = config.height or 85
  self.visible = false
  self.inputs = config.inputs or {} 
  self.buttons = config.buttons or {} 
  self.active_input_idx = 1
  self.hovered_btn_idx = nil
  self.previous_active_view = nil
end

function SovereignDockedView:get_target_height()
  return self.visible and self.height or 0
end

function SovereignDockedView:show()
  if not self.visible then
    self.visible = true
    self.previous_active_view = core.active_view
    core.set_active_view(self)
    core.redraw = true
  end
end

function SovereignDockedView:hide()
  if self.visible then
    self.visible = false
    if self.previous_active_view then
      core.set_active_view(self.previous_active_view)
    end
    core.redraw = true
  end
end

function SovereignDockedView:toggle()
  if self.visible then self:hide() else self:show() end
end

function SovereignDockedView:on_text_input(text)
  if not self.visible or #self.inputs == 0 then return end
  local input = self.inputs[self.active_input_idx]
  if input then
    input.text = (input.text or "") .. text
    core.redraw = true
  end
end

function SovereignDockedView:draw()
  if not self.visible then return end
  self:draw_background(style.background2)
  local x, y = self.position.x, self.position.y
  local w, h = self.size.x, self.size.y
  local font = style.font
  renderer.draw_rect(x, y, w, 1, style.divider or { 76, 69, 82, 255 })
  renderer.draw_rect(x, y, w, 2, style.accent or { 38, 188, 95, 255 })
  renderer.draw_text(font, self.title, x + 14, y + 8, style.accent)
end

function SovereignDockedView:get_name()
    return self.title or "Sovereign Dock"
end

function UIForge.build_all()
  -- Inicializador seguro
end

UIForge.build_all()
