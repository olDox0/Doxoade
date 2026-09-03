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
config.doxoade_npp_min_tab_width = 40
config.doxoade_npp_max_tab_width = 260

core.log("🚀 [03b] MOTOR NOTEPAD++ V5 (cor por todo o bloco + resolver autônomo).")

-- ── Paleta autônoma de projetos (mesma família visual do 03) ────────────────
local PROJECT_ACCENTS = {
{ 105, 0, 0}, { 0, 105, 0}, { 105, 105, 0}, { 0, 0, 105}, { 105, 0, 105}, { 0, 105, 105}, { 115, 105, 85}, { 60, 40, 60},
{ 165, 0, 0}, { 0, 165, 0}, { 165, 165, 0}, { 0, 0, 165}, { 165, 0, 165}, { 0, 165, 165}, { 175, 165, 145}, { 40, 50, 40},
{ 255, 0, 0}, { 0, 255, 0}, { 215, 215, 0}, { 0, 0, 255}, { 255, 0, 255}, { 0, 255, 255}, { 255, 255, 255}, { 30, 20, 20},
{ 255, 70, 0}, { 140, 255, 0}, { 195, 195, 80}, { 70, 70, 255}, { 255, 100, 255}, { 100, 255, 255}, { 145, 155, 115}, { 40, 0, 40},
{ 255, 140, 0}, { 0, 255, 140}, { 115, 115, 140}, { 100, 100, 255}, { 255, 160, 255}, { 150, 255, 255}, { 75, 55, 65}, { 0, 50, 50},
{ 255, 0, 50}, { 255, 0, 150}, { 205, 0, 255}, { 155, 0, 255},{ 95, 0, 255}, { 0, 95, 255}, { 0, 155, 255}, { 0, 205, 255}, 
}
--  { 0, 0, 0}, { 0, 0, 0}, { 0, 0, 0}, { 0, 0, 0},

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

-- ── Layout: caixa = texto + PREENCHIMENTO elegante (linha fecha à direita) ──
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

	-- Passagem 1: largura-base = tamanho do texto + quebra de linhas
	local base_w, row_of, rows, row_w = {}, {}, {}, {}
	local cur_row, cur_x = 1, 0
	for i, view in ipairs(views) do
		local ok_name, name = pcall(function() return view:get_name() end)
		name = (ok_name and name) or "…"
		local w = math.min(math.max(font:get_width(name) + PAD_X * 2, min_tab), max_tab, max_w)
		if cur_x > 0 and cur_x + w > max_w then
			cur_row = cur_row + 1
			cur_x = 0
		end
		base_w[i] = w
		row_of[i] = cur_row
		rows[cur_row] = rows[cur_row] or {}
		table.insert(rows[cur_row], i)
		row_w[cur_row] = (row_w[cur_row] or 0) + w
		cur_x = cur_x + w
	end

	-- Passagem 2: PREENCHIMENTO elegante (sem buraco morto à direita)
	-- Distribui o leftover igualmente com teto max_tab; o ÚLTIMO da linha
	-- absorve o resto e fecha a fileira rente à borda direita (estilo Notepad++).
	local final_w = {}
	for r, idxs in pairs(rows) do
		local leftover = max_w - (row_w[r] or 0)
		if leftover > 0 and #idxs > 0 then
			local add = math.floor(leftover / #idxs)
			local acc = 0
			for j, i in ipairs(idxs) do
				local extra
				if j == #idxs then
					extra = leftover - acc
				else
					extra = math.min(add, math.max(0, max_tab - base_w[i]))
				end
				acc = acc + extra
				final_w[i] = base_w[i] + extra
			end
		else
			for _, i in ipairs(idxs) do final_w[i] = base_w[i] end
		end
	end

	-- Passagem 3: retângulos absolutos
	local rects, ids = {}, {}
	local cx, cr = 0, 1
	for i = 1, n do
		if row_of[i] ~= cr then cr = row_of[i] cx = 0 end
		rects[i] = {
			x = node.position.x + cx,
			y = node.position.y + (cr - 1) * row_h,
			w = final_w[i], h = row_h,
		}
		cx = cx + final_w[i]
		ids[i] = views[i]
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

-- ── Algoritmo de Contraste Dinâmico (W3C Relative Luminance) ────────────────
local function get_contrast_color(bg_color)
	-- Normaliza RGB para 0-1 e aplica gamma correction (sRGB)
	-- 🛡️ FIX Ma'at: Lua 5.4 removeu math.pow. Usando operador ^ nativo.
	local function linearize(c)
		c = c / 255
		return c <= 0.03928 and c / 12.92 or ((c + 0.055) / 1.055) ^ 2.4
	end
	local r = linearize(bg_color[1])
	local g = linearize(bg_color[2])
	local b = linearize(bg_color[3])
	-- Luminância relativa (W3C WCAG 2.1)
	local luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
	-- Se fundo claro (luminance > 0.5) → texto escuro; senão → texto claro
	if luminance > 0.5 then
		return { 30, 30, 30, 255 } -- Texto escuro para fundo claro
	else
		return { 245, 245, 245, 255 } -- Texto claro para fundo escuro
	end
end

-- ── Desenho: COR POR TODO O BLOCO + CONTRASTE DINÂMICO ─────────────────────
function Node:draw_tab(view, is_active, is_hovered, is_close_hovered, x, y, w, h, standalone)
	local by, bh = y + 1, h - 1
	local accent = get_accent(view and view.doc and view.doc.filename or (view and view:get_name()))
	local base = style.background2 or { 40, 38, 42, 255 }
	-- Cor preenche o bloco INTEIRO: ativa vívida, hover média, inativa visível
	local t = is_active and 0.90 or (is_hovered and 0.55 or 0.38)
	local bg = mix_color(base, accent, t)

	renderer.draw_rect(x, by, w, bh, bg)

	-- CONTRASTE DINÂMICO: calcula a cor do texto baseada na luminância do fundo
	local text_color = get_contrast_color(bg)
	local dim_color = {
		math.floor(text_color[1] * 0.7),
		math.floor(text_color[2] * 0.7),
		math.floor(text_color[3] * 0.7),
		255,
	}

	local font = get_compact_font()
	core.push_clip_rect(x, by, w, bh)
	
	-- Aplica o contraste dinâmico antes de renderizar o título
	local old_text = style.text
	local old_dim = style.dim
	style.text = text_color
	style.dim = dim_color
	
	self:draw_tab_title(view, font, is_active, is_hovered, x, by, w, bh)
	
	-- Restaura as cores globais
	style.text = old_text
	style.dim = old_dim

	rawset(_G, "_DOXOADE_TAB_BG", bg)
	self:draw_tab_title(view, font, is_active, is_hovered, x, by, w, bh)
	rawset(_G, "_DOXOADE_TAB_BG", nil)
	
	core.pop_clip_rect()

	-- 'X' somente ao passar o mouse (cor do X também contrasta)
	if is_hovered and not standalone and config.tab_close_button then
		local cw, cpad = close_metrics()
		local cx = x + w - cw - cpad
		renderer.draw_rect(cx - cpad, by + 1, cw + cpad * 2, bh - 2, { 0, 0, 0, 110 })
		common.draw_text(style.icon_font,
			is_close_hovered and text_color or dim_color,
			"C", nil, cx, by, cw, bh)
	end

	-- Borda retangular (ativa = cor de identidade pura)
	local box_col = is_active and accent or (style.divider or { 94, 92, 94 , 255 })
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
