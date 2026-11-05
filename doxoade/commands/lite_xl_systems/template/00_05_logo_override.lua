local core = require "core"
local style = require "core.style"

local _has_font_api = (
  renderer
  and renderer.font
  and type(renderer.font.load) == "function"
)
if not _has_font_api then
  return
end

local function find_doxoade_logo_font()
  local user_dir = USERDIR or "."
  local sep = PATHSEP or "/"
  local candidates = {
    user_dir .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "logo.ttf",
    user_dir .. sep .. "assets" .. sep .. "logo.ttf",
    user_dir .. sep .. ".doxoade" .. sep .. "assets" .. sep .. "logo.otf",
    user_dir .. sep .. "assets" .. sep .. "logo.otf",
  }
  if core.project_dir then
    local proj = core.project_dir
    table.insert(candidates, proj .. sep .. "lite_xl_systems" .. sep .. "assets" .. sep .. "logo.ttf")
    table.insert(candidates, proj .. sep .. ".." .. sep .. "lite_xl_systems" .. sep .. "assets" .. sep .. "logo.ttf")
  end
  for _, path in ipairs(candidates) do
    local f = io.open(path, "rb")
    if f then f:close(); return path end
  end
  return nil
end

local logo_font_path = find_doxoade_logo_font()
if not logo_font_path then
  return
end

local logo_font = nil
pcall(function()
  logo_font = renderer.font.load(logo_font_path, 256)
end)

if not logo_font then
  if core.log then
    core.log("🎨 [LOGO] Falha ao carregar fonte TTF: " .. logo_font_path)
  end
  return
end

if not core.draw_logo then
  if core.log then
    core.log("🎨 [LOGO] core.draw_logo indisponível — override ignorado.")
  end
  return
end

--local LOGO_GLYPH = "\u{E000}"
local LOGO_GLYPH = "A"  -- TTF atual tem o glifo em 0x41

local original = core.draw_logo
core.draw_logo = function(...)
  local res = original(...)
  if not core.root_view or not core.root_view.size then
    return res
  end
  local view_w = core.root_view.size.x or 800
  local view_h = core.root_view.size.y or 600
  local draw_size = math.min(view_w, view_h) * 0.4
  if draw_size < 64 then draw_size = 64 end
  if draw_size > 400 then draw_size = 400 end
  if not logo_font._dox_current_size or logo_font._dox_current_size ~= draw_size then
    pcall(function()
      logo_font = renderer.font.load(logo_font_path, math.floor(draw_size))
      if logo_font then logo_font._dox_current_size = draw_size end
    end)
  end
  if not logo_font then return res end
  local glyph_w = logo_font:get_width(LOGO_GLYPH)
  local glyph_h = logo_font:get_height()
  if not glyph_w or glyph_w <= 0 then
    return res
  end
  local x = math.floor((view_w - glyph_w) / 2)
  local y = math.floor((view_h - glyph_h) / 2) - 60
  local color = style.accent or { 38, 188, 95, 180 }
  color[4] = 180
  if renderer.draw_text then
    pcall(renderer.draw_text, logo_font, LOGO_GLYPH, x, y, color)
  end
  return res
end

if core.log then
  core.log("🎨 [LOGO] Fonte TTF carregada: " .. logo_font_path .. " (glifo 'A')")
--  core.log("🎨 [LOGO] Fonte TTF carregada: " .. logo_font_path .. " (glifo U+E000)")
end
