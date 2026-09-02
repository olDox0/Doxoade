-- doxoade/commands/lite_xl_systems/template/03_tab_colors.lua
-- =============================================================================
-- 03. TEMA E CORES DE ABAS POR PROJETO RAIZ COM INDICADOR DE MODIFICADO
-- =============================================================================
local core = require "core"

local style = require "core.style"
local Node = require "core.node"

-- 🛡️ Polyfill Universal Doxoade
local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if rencache then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

-- 🎨 Paleta de Projetos
local PROJECT_THEMES = {
  { accent = { 255, 0, 0 },     active_bg = { 175, 0, 0 },   hover_bg = { 170, 68, 0 },  inactive_bg = { 130, 0, 0 } },
  { accent = { 255, 103, 0 },   active_bg = { 224, 90, 0 },  hover_bg = { 170, 68, 0 },  inactive_bg = { 90, 36, 0 } },
  { accent = { 255, 170, 0 },   active_bg = { 170, 125, 0 }, hover_bg = { 130, 95, 0 },  inactive_bg = { 70, 50, 0 } },
  { accent = { 227, 141, 83 },  active_bg = { 90, 56, 33 },  hover_bg = { 68, 42, 25 },   inactive_bg = { 42, 26, 15 } },
  { accent = { 138, 205, 25 },   active_bg = { 78, 105, 25 }, hover_bg = { 38, 95, 25 },  inactive_bg = { 28, 65, 15 } },
  { accent = { 38, 188, 95 },   active_bg = { 25, 123, 63 }, hover_bg = { 18, 90, 46 },  inactive_bg = { 10, 51, 26 } },
  { accent = { 77, 145, 232 },  active_bg = { 30, 57, 92 },  hover_bg = { 22, 42, 68 },   inactive_bg = { 14, 28, 45 } },
  { accent = { 0, 0, 255 },   active_bg = { 0, 0, 120 },  hover_bg = { 0, 0, 80 },  inactive_bg = { 0, 0, 50 } },
  { accent = { 200, 21, 118 },  active_bg = { 150, 16, 88 }, hover_bg = { 110, 12, 65 }, inactive_bg = { 60, 6, 35 } },
  { accent = { 206, 105, 158 }, active_bg = { 82, 41, 63 },  hover_bg = { 60, 30, 46 },  inactive_bg = { 38, 19, 29 } },
}

local DEFAULT_THEME = { accent = { 94, 92, 94 }, active_bg = { 47, 46, 48 }, hover_bg = { 35, 34, 36 }, inactive_bg = { 25, 23, 26 } }

-- 🟡 Cor de Alerta: Linha Amarela de Modificado / Não Salvo
local MODIFIED_YELLOW = { 234, 179, 8, 255 }

local function get_project_tab_theme(filename)
  if not filename then return DEFAULT_THEME end
  local clean_fn = tostring(filename):gsub("\\", "/"):lower()
  local matched_project = nil

  if core.project_directories then
    for _, proj in ipairs(core.project_directories) do
      local ppath = type(proj) == "table" and (proj.path or proj.name) or proj
      if ppath and type(ppath) == "string" then
        local clean_ppath = tostring(ppath):gsub("\\", "/"):lower()
        if clean_fn:sub(1, #clean_ppath) == clean_ppath then
          matched_project = type(proj) == "table" and (proj.name or proj.path) or proj
          break
        end
      end
    end
  end

  if not matched_project then
    matched_project = clean_fn:match("^(.*)[/\\]") or clean_fn
  end

  matched_project = tostring(matched_project or "default")
  local hash = 0
  for i = 1, #matched_project do
    hash = (hash * 31 + matched_project:byte(i)) % #PROJECT_THEMES
  end
  return PROJECT_THEMES[hash + 1] or DEFAULT_THEME
end

local function mix_color(base, accent, t)
	return {
		math.floor(base[1] + (accent[1] - base[1]) * t),
		math.floor(base[2] + (accent[2] - base[2]) * t),
		math.floor(base[3] + (accent[3] - base[3]) * t),
		255,
	}
end

local function doxoade_hash_string(s)
	s = tostring(s or "")
	local h = 0
	for i = 1, #s do
		h = (h * 31 + s:byte(i)) % 2147483647
	end
	return h
end

local DOXOADE_TAB_PALETTE = {
	{ 96, 165, 250, 255 },  -- azul pálido
	{ 129, 140, 248, 255 }, -- índigo
	{ 168, 85, 247, 255 },  -- violeta
	{ 244, 114, 182, 255 }, -- rosa
	{ 45, 212, 191, 255 },  -- teal
	{ 52, 211, 153, 255 },  -- verde
	{ 251, 146, 60, 255 },  -- laranja suave
}

local function doxoade_resolve_tab_theme(filename)
	local key = tostring(filename or "default")
	local h = doxoade_hash_string(key)
	local accent = DOXOADE_TAB_PALETTE[(h % #DOXOADE_TAB_PALETTE) + 1]
	return {
		accent = accent,
	}
end

rawget(_G, "DOXOADE_GET_TAB_THEME")

local original_draw_tab_title = Node.draw_tab_title

function Node:draw_tab_title(view, font, is_active, is_hovered, x, y, w, h)
	local filename = nil

	pcall(function()
		if view and view.doc and view.doc.filename then
			filename = view.doc.filename
		elseif view and view.get_name then
			filename = view:get_name()
		end
	end)

	local theme = doxoade_resolve_tab_theme(filename)

	if theme then
		local is_dirty = false

		pcall(function()
			if view and view.doc and view.doc.is_dirty then
				is_dirty = view.doc:is_dirty()
			end
		end)

		if is_dirty then
			-- 🟡 Arquivo modificado: identidade visual amarelada.
			local YEL = { 234, 179, 8, 255 }

			draw_rect_safe(x, y, w, 2, YEL)
			draw_rect_safe(x, y + 2, w, 1, { 234, 179, 8, 115 })
			draw_rect_safe(x, y + 3, w, 1, { 234, 179, 8, 45 })

			draw_rect_safe(x, y, 1, h, YEL)
			draw_rect_safe(x + w - 1, y, 1, h, YEL)
			draw_rect_safe(x, y + h - 1, w, 1, YEL)
		else
			-- Filete pálido de identidade do projeto/arquivo.
			local a = theme.accent
			local alpha = is_active and 220 or 120
			draw_rect_safe(x, y, w, is_active and 2 or 1, {
				a[1], a[2], a[3], alpha
			})
		end

		local old_text = style.text
		local old_dim = style.dim

		style.text = is_active
			and { 245, 245, 245, 255 }
			or  (is_hovered and { 220, 220, 220, 255 } or { 178, 178, 178, 255 })

		style.dim = { 150, 150, 150, 255 }

		local ok, res = pcall(
			original_draw_tab_title,
			self,
			view,
			font,
			is_active,
			is_hovered,
			x,
			y,
			w,
			h
		)

		style.text = old_text
		style.dim = old_dim

		if ok then return res end
	end

	return original_draw_tab_title(self, view, font, is_active, is_hovered, x, y, w, h)
end
