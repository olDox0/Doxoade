-- doxoade/commands/lite_xl_systems/template/19e_sketch_pad.lua
--[[
🎨 DOXOADE SKETCH PAD (V1.1 Pincel e Borracha)
Sistema de desenho livre integrado ao Bottom Shelf Hub.
- Pincel suave com interpolação linear
- Borracha que remove traços inteiros
- Cores básicas
- Limpar tudo
Compliance: ProDeNov 1.2.1, PASC-6.1.
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local keymap = require "core.keymap"
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

-- =============================================================================
-- POLYFILLS DE RENDERIZAÇÃO
-- =============================================================================
local function draw_rect_safe(x, y, w, h, color)
  if not color or type(color) ~= "table" then color = { 128, 128, 128, 255 } end
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

local function draw_text_safe(font, text, x, y, color)
  if not font or not text or text == "" then return end
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

-- =============================================================================
-- 🎨 SKETCH PAD STATE
-- =============================================================================
local SketchPad = {
  strokes = {},           -- Lista de traços: { {points, color, size}, ... }
  current_stroke = nil,   -- Traço sendo desenhado agora
  color = { 255, 255, 255, 255 },  -- Cor atual (branco)
  brush_size = 3,         -- Tamanho do pincel
  is_eraser = false,      -- Modo borracha
  is_drawing = false,     -- Mouse pressionado
  canvas_x = 0,
  canvas_y = 0,
  canvas_w = 0,
  canvas_h = 0,
}
rawset(_G, "_DOXOADE_SKETCH_PAD", SketchPad)

-- Paleta de cores
local COLOR_PALETTE = {
  { name = "Branco",  color = { 255, 255, 255, 255 } },
  { name = "Preto",   color = { 0, 0, 0, 255 } },
  { name = "Vermelho", color = { 255, 80, 80, 255 } },
  { name = "Verde",   color = { 80, 255, 80, 255 } },
  { name = "Azul",    color = { 80, 180, 255, 255 } },
  { name = "Amarelo", color = { 255, 255, 80, 255 } },
  { name = "Laranja", color = { 255, 160, 50, 255 } },
  { name = "Roxo",    color = { 180, 100, 255, 255 } },
}

-- =============================================================================
-- 🖌️ FUNÇÕES DE DESENHO
-- =============================================================================
function SketchPad:start_stroke(x, y)
  self.current_stroke = {
    color = self.is_eraser and { 20, 20, 20, 255 } or self.color,
    size = self.is_eraser and self.brush_size * 3 or self.brush_size,
    points = { { x = x, y = y } },
    is_eraser = self.is_eraser,
  }
end

function SketchPad:continue_stroke(x, y)
  if not self.current_stroke then return end
  
  local last = self.current_stroke.points[#self.current_stroke.points]
  local dx = x - last.x
  local dy = y - last.y
  local dist_sq = dx * dx + dy * dy
  
  -- Só adiciona ponto se moveu mais de 1px (evita pontos duplicados)
  if dist_sq > 1 then
    table.insert(self.current_stroke.points, { x = x, y = y })
  end
end

function SketchPad:end_stroke()
  if self.current_stroke and #self.current_stroke.points > 0 then
    table.insert(self.strokes, self.current_stroke)
  end
  self.current_stroke = nil
end

function SketchPad:clear()
  self.strokes = {}
  self.current_stroke = nil
  core.redraw = true
end

function SketchPad:undo()
  if #self.strokes > 0 then
    table.remove(self.strokes)
    core.redraw = true
  end
end

-- Verifica se um ponto está dentro de um círculo (para borracha)
local function point_in_circle(px, py, cx, cy, radius)
  local dx = px - cx
  local dy = py - cy
  return dx * dx + dy * dy <= radius * radius
end

-- Verifica se um traço intersecta com o círculo da borracha
function SketchPad:stroke_intersects_eraser(stroke, eraser_x, eraser_y, eraser_radius)
  for _, p in ipairs(stroke.points) do
    if point_in_circle(p.x, p.y, eraser_x, eraser_y, eraser_radius) then
      return true
    end
  end
  return false
end

-- Aplica borracha: remove traços que intersectam com o cursor
function SketchPad:apply_eraser(x, y)
  local eraser_radius = self.brush_size * 2
  local new_strokes = {}
  local removed = false
  
  for _, stroke in ipairs(self.strokes) do
    if not self:stroke_intersects_eraser(stroke, x, y, eraser_radius) then
      table.insert(new_strokes, stroke)
    else
      removed = true
    end
  end
  
  if removed then
    self.strokes = new_strokes
    core.redraw = true
  end
end

-- =============================================================================
-- 🎨 RENDERIZAÇÃO
-- =============================================================================
function SketchPad:draw_viewport(x, y, w, h)
  local font = style.font or style.code_font
  
  -- Define área do canvas
  self.canvas_x = x + 10
  self.canvas_y = y + 10
  self.canvas_w = w - 20
  self.canvas_h = h - 80  -- Deixa espaço para toolbar
  
  -- Fundo do canvas (cinza escuro)
  draw_rect_safe(self.canvas_x, self.canvas_y, self.canvas_w, self.canvas_h, { 20, 20, 20, 255 })
  draw_rect_safe(self.canvas_x, self.canvas_y, self.canvas_w, 2, style.accent or { 38, 188, 95, 255 })
  
  -- Clip para não desenhar fora do canvas
  if core.push_clip_rect then
    pcall(core.push_clip_rect, self.canvas_x, self.canvas_y, self.canvas_w, self.canvas_h)
  end
  
  -- Desenha todos os traços
  for _, stroke in ipairs(self.strokes) do
    self:draw_stroke(stroke)
  end
  
  -- Desenha traço atual (em progresso)
  if self.current_stroke then
    self:draw_stroke(self.current_stroke)
  end
  
  -- Cursor da borracha (se estiver no modo borracha)
  if self.is_eraser and self.last_mouse_x then
    local eraser_radius = self.brush_size * 2
    draw_rect_safe(
      self.last_mouse_x - eraser_radius,
      self.last_mouse_y - eraser_radius,
      eraser_radius * 2,
      eraser_radius * 2,
      { 255, 255, 255, 100 }
    )
  end
  
  if core.pop_clip_rect then
    pcall(core.pop_clip_rect)
  end
  
  -- Toolbar inferior
  self:draw_toolbar(x, y + h - 60, w)
end

function SketchPad:draw_stroke(stroke)
  local points = stroke.points
  if #points == 0 then return end
  
  local color = stroke.color
  local size = stroke.size
  
  if #points == 1 then
    -- Ponto único
    local p = points[1]
    local px = self.canvas_x + p.x
    local py = self.canvas_y + p.y
    draw_rect_safe(px - size/2, py - size/2, size, size, color)
  else
    -- Linha entre pontos consecutivos com interpolação
    for i = 2, #points do
      local p1 = points[i-1]
      local p2 = points[i]
      local x1 = self.canvas_x + p1.x
      local y1 = self.canvas_y + p1.y
      local x2 = self.canvas_x + p2.x
      local y2 = self.canvas_y + p2.y
      
      -- Interpolação linear suave
      local dist = math.sqrt((x2-x1)^2 + (y2-y1)^2)
      local steps = math.max(1, math.floor(dist / (size/3)))
      
      for s = 0, steps do
        local t = s / steps
        local px = x1 + (x2 - x1) * t
        local py = y1 + (y2 - y1) * t
        draw_rect_safe(px - size/2, py - size/2, size, size, color)
      end
    end
  end
end

function SketchPad:draw_toolbar(x, y, w)
  local font = style.font or style.code_font
  
  -- Fundo da toolbar
  draw_rect_safe(x, y, w, 50, { 15, 15, 15, 255 })
  draw_rect_safe(x, y, w, 1, style.accent or { 38, 188, 95, 255 })
  
  -- Cores da paleta
  local color_x = x + 10
  local color_y = y + 5
  local color_size = 20
  
  for i, item in ipairs(COLOR_PALETTE) do
    local is_selected = (not self.is_eraser and 
                        self.color[1] == item.color[1] and 
                        self.color[2] == item.color[2] and 
                        self.color[3] == item.color[3])
    
    draw_rect_safe(color_x, color_y, color_size, color_size, item.color)
    if is_selected then
      draw_rect_safe(color_x - 2, color_y - 2, color_size + 4, color_size + 4, { 255, 255, 255, 255 })
    end
    
    -- Salva região clicável
    item.rect = { x = color_x, y = color_y, w = color_size, h = color_size }
    
    color_x = color_x + color_size + 6
  end
  
  -- Borracha
  local eraser_x = color_x + 10
  draw_rect_safe(eraser_x, color_y, color_size, color_size, { 100, 100, 100, 255 })
  draw_text_safe(font, "E", eraser_x + 6, color_y + 2, { 255, 255, 255, 255 })
  if self.is_eraser then
    draw_rect_safe(eraser_x - 2, color_y - 2, color_size + 4, color_size + 4, { 255, 255, 255, 255 })
  end
  self.eraser_rect = { x = eraser_x, y = color_y, w = color_size, h = color_size }
  
  -- Botões de ação
  local btn_y = color_y
  local btn_h = color_size
  
  -- Limpar
  local clear_x = eraser_x + color_size + 20
  draw_rect_safe(clear_x, btn_y, 60, btn_h, { 40, 40, 45, 255 })
  draw_text_safe(font, "Limpar", clear_x + 8, btn_y + 2, { 220, 220, 220, 255 })
  self.clear_rect = { x = clear_x, y = btn_y, w = 60, h = btn_h }
  
  -- Desfazer
  local undo_x = clear_x + 70
  draw_rect_safe(undo_x, btn_y, 60, btn_h, { 40, 40, 45, 255 })
  draw_text_safe(font, "Desfazer", undo_x + 4, btn_y + 2, { 220, 220, 220, 255 })
  self.undo_rect = { x = undo_x, y = btn_y, w = 60, h = btn_h }
  
  -- Indicador de tamanho do pincel
  local size_x = undo_x + 80
  draw_text_safe(font, string.format("Tamanho: %d", self.brush_size), size_x, btn_y + 2, { 150, 150, 150, 255 })
end

-- =============================================================================
-- 🖱️ INTERAÇÃO COM MOUSE
-- =============================================================================
function SketchPad:on_mouse_pressed(x, y)
  -- Converte para coordenadas do canvas
  local cx = x - self.canvas_x
  local cy = y - self.canvas_y
  
  -- Verifica se clicou na toolbar
  if y > self.canvas_y + self.canvas_h then
    -- Verifica clique em cores
    for _, item in ipairs(COLOR_PALETTE) do
      if item.rect and x >= item.rect.x and x <= item.rect.x + item.rect.w and
         y >= item.rect.y and y <= item.rect.y + item.rect.h then
        self.color = item.color
        self.is_eraser = false
        core.redraw = true
        return true
      end
    end
    
    -- Borracha
    if self.eraser_rect and x >= self.eraser_rect.x and x <= self.eraser_rect.x + self.eraser_rect.w and
       y >= self.eraser_rect.y and y <= self.eraser_rect.y + self.eraser_rect.h then
      self.is_eraser = not self.is_eraser
      core.redraw = true
      return true
    end
    
    -- Limpar
    if self.clear_rect and x >= self.clear_rect.x and x <= self.clear_rect.x + self.clear_rect.w and
       y >= self.clear_rect.y and y <= self.clear_rect.y + self.clear_rect.h then
      self:clear()
      return true
    end
    
    -- Desfazer
    if self.undo_rect and x >= self.undo_rect.x and x <= self.undo_rect.x + self.undo_rect.w and
       y >= self.undo_rect.y and y <= self.undo_rect.y + self.undo_rect.h then
      self:undo()
      return true
    end
    
    return true
  end
  
  -- Dentro do canvas
  if cx >= 0 and cx <= self.canvas_w and cy >= 0 and cy <= self.canvas_h then
    if self.is_eraser then
      -- Borracha: remove traços sob o cursor
      self:apply_eraser(cx, cy)
    else
      -- Pincel: começa novo traço
      self.is_drawing = true
      self:start_stroke(cx, cy)
    end
    core.redraw = true
    return true
  end
  
  return false
end

function SketchPad:on_mouse_moved(x, y, dx, dy)
  local cx = x - self.canvas_x
  local cy = y - self.canvas_y
  
  -- Atualiza posição do mouse para cursor da borracha
  self.last_mouse_x = x
  self.last_mouse_y = y
  
  if self.is_drawing then
    if self.is_eraser then
      self:apply_eraser(cx, cy)
    else
      self:continue_stroke(cx, cy)
    end
    core.redraw = true
    return true
  end
  
  return false
end

function SketchPad:on_mouse_released(x, y)
  if self.is_drawing then
    self.is_drawing = false
    if not self.is_eraser then
      self:end_stroke()
    end
    core.redraw = true
    return true
  end
  return false
end

-- =============================================================================
-- 🎯 INTEGRAÇÃO COM BOTTOM SHELF HUB
-- =============================================================================
local ShelfHub = rawget(_G, "_DOXOADE_SHELF_HUB")
if ShelfHub then
  table.insert(ShelfHub.tabs, { id = "sketch", label = "Sketch (Desenho)" })
end

-- Hook no draw do ShelfHub
if ShelfHub then
  local original_shelf_draw = ShelfHub.draw
  function ShelfHub:draw(...)
    if original_shelf_draw then original_shelf_draw(self, ...) end
    
    if self.visible and self.active_tab == "sketch" then
      local sketch = rawget(_G, "_DOXOADE_SKETCH_PAD")
      if sketch and self.card_rect then
        local r = self.card_rect
        local canvas_y = r.y + self.header_height + 2
        local canvas_h = r.h - self.header_height - 34
        sketch:draw_viewport(r.x + 2, canvas_y, r.w - 4, canvas_h)
      end
    end
  end
end

-- Hook no mouse do ShelfHub
if ShelfHub then
  local orig_on_mouse_pressed = ShelfHub.on_mouse_pressed
  function ShelfHub:on_mouse_pressed(button, x, y, clicks)
    if self.visible and self.active_tab == "sketch" then
      local sketch = rawget(_G, "_DOXOADE_SKETCH_PAD")
      if sketch and self.card_rect then
        local r = self.card_rect
        local canvas_y = r.y + self.header_height + 2
        local canvas_h = r.h - self.header_height - 34
        if x >= r.x and x <= r.x + r.w and y >= canvas_y and y <= canvas_y + canvas_h then
          if sketch:on_mouse_pressed(x, y) then return true end
        end
      end
    end
    if orig_on_mouse_pressed then return orig_on_mouse_pressed(self, button, x, y, clicks) end
  end
  
  local orig_on_mouse_moved = ShelfHub.on_mouse_moved
  function ShelfHub:on_mouse_moved(x, y, dx, dy)
    if self.visible and self.active_tab == "sketch" then
      local sketch = rawget(_G, "_DOXOADE_SKETCH_PAD")
      if sketch and self.card_rect then
        local r = self.card_rect
        local canvas_y = r.y + self.header_height + 2
        local canvas_h = r.h - self.header_height - 34
        if x >= r.x and x <= r.x + r.w and y >= canvas_y and y <= canvas_y + canvas_h then
          if sketch:on_mouse_moved(x, y, dx, dy) then return true end
        end
      end
    end
    if orig_on_mouse_moved then return orig_on_mouse_moved(self, x, y, dx, dy) end
  end
  
  local orig_on_mouse_released = ShelfHub.on_mouse_released
  function ShelfHub:on_mouse_released(button, x, y)
    if self.visible and self.active_tab == "sketch" then
      local sketch = rawget(_G, "_DOXOADE_SKETCH_PAD")
      if sketch then
        if sketch:on_mouse_released(x, y) then return true end
      end
    end
    if orig_on_mouse_released then return orig_on_mouse_released(self, button, x, y) end
  end
end

-- =============================================================================
-- ⌨️ COMANDOS E KEYMAPS
-- =============================================================================
command.add(nil, {
  ["doxoade:open-sketch-pad"] = function()
    local shelf = rawget(_G, "_DOXOADE_SHELF_HUB")
    if shelf then
      shelf.active_tab = "sketch"
      shelf.visible = true
      core.redraw = true
    end
  end,
})

keymap.add {
  ["ctrl+alt+s"] = "doxoade:open-sketch-pad",
}
