-- doxoade/commands/lite_xl_systems/template/03b_tab_compact_staircase.lua
--[[
Módulo 03b — MOTOR NOTEPAD++ V5 (Caixas Compactas + COR POR TODO O BLOCO).
- Resolver de cores AUTÔNOMO (hash por diretório-projeto): não depende do 03.
- Cor do projeto preenchendo TODO o bloco (ativa vívida, inativas em tint).
- Caixa retangular do tamanho do texto; 'X' aparece só no hover.
]]
local core = require "core"
local common = require "core.common"
local style = require "core.style"
local config = require "core.config"
local Node = require "core.node"

if rawget(_G, "_DOXOADE_NPP_HOOKED") then return end
rawset(_G, "_DOXOADE_NPP_HOOKED", true)

config.always_show_tabs = true
config.doxoade_npp_min_tab_width = 46
config.doxoade_npp_max_tab_width = 260

core.log("🚀 [03b] MOTOR NOTEPAD++ V5 (cor por todo o bloco + resolver autônomo).")

-- ── Paleta autônoma de projetos (mesma família visual do 03) ────────────────
local PROJECT_ACCENTS = {
	{ 38, 188, 95 }, { 255, 0, 0 }, { 0, 255, 0 }, { 255, 255, 0 },
	{ 0, 0, 255 }, { 255, 0, 255 }, { 0, 255, 255 }, { 115, 115, 115},
  { 255, 115, 0 }, { 115, 255, 0 }, { 255, 255, 115 }, { 0, 115, 255 },
  { 255, 115, 255 }, { 115, 255, 255 }, { 115, 0, 255 },
}
--  { 0, 0, 0}, { 0, 0, 0}, { 0, 0, 0}, { 0, 0, 0}, { 0, 0, 0},

local function hash_string(s)
	local h = 0
	for i = 1, #s do
		h = (h * 31 + s:byte(i)) % 2147483647
	end
	return h
end
local function get_accent(filename)
	-- 1) Respeita o resolvedor do 03 se ele existir (consistência de tema)
	local fn = rawget(_G, "DOXOADE_GET_TAB_THEME")
	if fn then
		local ok, t = pcall(fn, filename)
		if ok and t and t.accent then return t.accent end
	end
	-- 2) Fallback autônomo: hash do diretório = cor estável por projeto
	local key = tostring(filename or "default"):gsub("\\", "/"):lower()
	local dir = key:match("^(.*)/") or key
	return PROJECT_ACCENTS[(hash_string(dir) % #PROJECT_ACCENTS) + 1]
end

-- ── Utilidades ──────────────────────────────────────────────────────────────
local cached_compact_font = nil
local function get_compact_font()
	if cached_compact_font then return cached_compact_font end
	local ok, f = pcall(function()
		if style.font and style.font.copy then
			return style.font:copy(math.max(9, math.floor(style.font:get_height() * 0.85)))
		end
		return style.font
	end)
	cached_compact_font = (ok and f) or style.font
	return cached_compact_font
end

local PAD_X = 6
local PAD_Y = 2

local function row_height()
	local f = get_compact_font()
	return f:get_height() + PAD_Y * 2 + 1, 1
end
local function close_metrics()
	local cw = style.icon_font:get_width("C")
	return cw, 4
end
local function mix_color(base, accent, t)
	return {
		math.floor(base[1] + (accent[1] - base[1]) * t),
		math.floor(base[2] + (accent[2] - base[2]) * t),
		math.floor(base[3] + (accent[3] - base[3]) * t),
		255,
	}
end

-- ── Layout: caixa = tamanho do texto ────────────────────────────────────────
local function npp_layout(node)
	local c = node._npp_cache
	local views = node.views
	local n = #views
	if c and c.views == views and c.n == n and c.w == node.size.x
		and c.px == node.position.x and c.py == node.position.y then
		local same = true
		for i = 1, n do
			if c.ids[i] ~= views[i] then same = false break end
		end
		if same then return c end
	end
	local row_h, margin = row_height()
	local font = get_compact_font()
	local max_w = math.max(node.size.x, 80)
	local min_tab = (config.doxoade_npp_min_tab_width or 46) * (SCALE or 1)
	local max_tab = (config.doxoade_npp_max_tab_width or 260) * (SCALE or 1)

	local rects, ids = {}, {}
	local cur_x, cur_row = 0, 1
	for i, view in ipairs(views) do
		local ok_name, name = pcall(function() return view:get_name() end)
		name = (ok_name and name) or "…"
		local w = math.min(math.max(font:get_width(name) + PAD_X * 2, min_tab), max_tab, max_w)
		if cur_x > 0 and cur_x + w > max_w then
			cur_row = cur_row + 1
			cur_x = 0
		end
		rects[i] = {
			x = node.position.x + cur_x,
			y = node.position.y + (cur_row - 1) * row_h,
			w = w, h = row_h,
		}
		cur_x = cur_x + w
		ids[i] = view
	end

	c = {
		views = views, n = n, w = node.size.x,
		px = node.position.x, py = node.position.y,
		rects = rects, ids = ids,
		row_h = row_h, margin = margin,
		total_h = cur_row * row_h,
	}
	node._npp_cache = c
	return c
end

-- ── Overrides das primitivas de geometria ───────────────────────────────────
function Node:get_visible_tabs_number() return #self.views end

function Node:get_tab_rect(idx)
	local L = npp_layout(self)
	local r = L.rects[idx] or { x = self.position.x, y = self.position.y, w = 0, h = L.row_h }
	return r.x, r.y, r.w, r.h, L.margin
end

function Node:get_tab_overlapping_point(px, py)
	if not self:should_show_tabs() then return nil end
	local L = npp_layout(self)
	for i = 1, L.n do
		local r = L.rects[i]
		if px >= r.x and px < r.x + r.w and py >= r.y and py < r.y + r.h then
			return i
		end
	end
	return nil
end

function Node:get_scroll_button_rect(index)
	local L = npp_layout(self)
	return self.position.x + self.size.x, self.position.y, 0, L.total_h, 0
end

function Node:is_in_tab_area(x, y)
	if not self:should_show_tabs() then return false end
	local L = npp_layout(self)
	return y >= self.position.y and y < self.position.y + L.total_h
end

function Node:tab_hovered_update(px, py)
	self.hovered_scroll_button = 0
	self.hovered_tab = nil
	self.hovered_close = 0
	if self.type ~= "leaf" then return end
	local idx = self:get_tab_overlapping_point(px, py)
	self.hovered_tab = idx
	if idx and config.tab_close_button then
		local x, y, w, h = self:get_tab_rect(idx)
		local cw, cpad = close_metrics()
		local cx = x + w - cw - cpad
		if px >= cx and px < cx + cw + cpad then
			self.hovered_close = idx
		end
	end
end

-- ── Desenho: COR POR TODO O BLOCO + caixa compacta + X só no hover ──────────
function Node:draw_tab(view, is_active, is_hovered, is_close_hovered, x, y, w, h, standalone)
	local by, bh = y + 1, h - 1
	local accent = get_accent(view and view.doc and view.doc.filename or (view and view:get_name()))
	local base = style.background2 or { 40, 38, 42, 255 }
	-- Cor preenche o bloco INTEIRO: ativa vívida, hover média, inativa visível
	local t = is_active and 0.90 or (is_hovered and 0.55 or 0.38)
	local bg = mix_color(base, accent, t)

	renderer.draw_rect(x, by, w, bh, bg)

	local font = get_compact_font()
	core.push_clip_rect(x, by, w, bh)
	self:draw_tab_title(view, font, is_active, is_hovered, x, by, w, bh)
	core.pop_clip_rect()

	-- 'X' somente ao passar o mouse
	if is_hovered and not standalone and config.tab_close_button then
		local cw, cpad = close_metrics()
		local cx = x + w - cw - cpad
		renderer.draw_rect(cx - cpad, by + 1, cw + cpad * 2, bh - 2, { 0, 0, 0, 110 })
		common.draw_text(style.icon_font,
			is_close_hovered and { 255, 255, 255, 255 } or { 225, 225, 225, 255 },
			"C", nil, cx, by, cw, bh)
	end

	-- Borda retangular (ativa = cor de identidade pura)
	local box_col = is_active and accent or (style.divider or { 38, 34, 41, 255 })
	renderer.draw_rect(x, by, w, 1, box_col)
	renderer.draw_rect(x, by + bh - 1, w, 1, box_col)
	renderer.draw_rect(x, by, 1, bh, box_col)
	renderer.draw_rect(x + w - 1, by, 1, bh, box_col)
end

function Node:draw_tabs()
	local L = npp_layout(self)
	local x, y = self.position.x, self.position.y
	renderer.draw_rect(x, y, self.size.x, L.total_h, style.background2)
	renderer.draw_rect(x, y + L.total_h - style.divider_size, self.size.x, style.divider_size, style.divider)
	core.push_clip_rect(x, y, self.size.x, L.total_h)
	for i, view in ipairs(self.views) do
		local r = L.rects[i]
		self:draw_tab(view, view == self.active_view,
			i == self.hovered_tab, i == self.hovered_close,
			r.x, r.y, r.w, r.h)
	end
	core.pop_clip_rect()
end

-- ── Reserva vertical multi-linha para o conteúdo do editor ──────────────────
local original_update_layout = Node.update_layout
function Node:update_layout(...)
	original_update_layout(self, ...)
	if self.type == "leaf" and self.active_view and self:should_show_tabs() then
		local L = npp_layout(self)
		local av = self.active_view
		av.position.x, av.position.y = self.position.x, self.position.y + L.total_h
		av.size.x, av.size.y = self.size.x, math.max(self.size.y - L.total_h, 10)
	end
end
