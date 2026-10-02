-- doxoade/commands/lite_xl_systems/template/03_tab_colors.lua
--[[
  🎨 DOXOADE BOUNDED CHROMATIC DEPTH (V3.0 TreeView Project Anchors)
  - Identifica os projetos ativos inspecionando as raízes da TreeView.
  - Setor Circular Limitado:
      * Doxoade: Arco restrito Vermelho (4°) -> Laranja (38°).
      * Outros Projetos: Setores circulares exclusivos de 35° bem espaçados.
  - Escuridão por Profundidade: Arquivos da raiz são claros/vivos; subpastas vão escurecendo.
  - Variação por Arquivo: Micro-ajustes de claridade/saturação para arquivos da mesma pasta.
  - Cache O(1) em RAM com invalidação reativa quando a TreeView ganha/perde projetos.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local style = require "core.style"
local Node = require "core.node"

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

-- =============================================================================
-- MOTOR MATEMÁTICO HSL -> RGB
-- =============================================================================
local function hsl_to_rgb(h, s, l)
  h = (h % 360) / 360
  s = math.max(0, math.min(1, s))
  l = math.max(0, math.min(1, l))

  local r, g, b
  if s == 0 then
    r, g, b = l, l, l
  else
    local function hue2rgb(p, q, t)
      if t < 0 then t = t + 1 end
      if t > 1 then t = t - 1 end
      if t < 1/6 then return p + (q - p) * 6 * t end
      if t < 1/2 then return q end
      if t < 2/3 then return p + (q - p) * (2/3 - t) * 6 end
      return p
    end
    local q = l < 0.5 and (l * (1 + s)) or (l + s - l * s)
    local p = 2 * l - q
    r = hue2rgb(p, q, h + 1/3)
    g = hue2rgb(p, q, h)
    b = hue2rgb(p, q, h - 1/3)
  end

  return {
    math.floor(r * 255 + 0.5),
    math.floor(g * 255 + 0.5),
    math.floor(b * 255 + 0.5),
    255
  }
end

local function hash_string(str)
  local s = tostring(str or "")
  local h = 0
  for i = 1, #s do
    h = (h * 31 + s:byte(i)) % 2147483647
  end
  return h
end

-- =============================================================================
-- RESOLUÇÃO DE PROJETOS NA TREEVIEW COM INVALIDAÇÃO DINÂMICA
-- =============================================================================
local _cached_projects = nil
local _last_project_signature = ""

local function get_treeview_projects()
  local sig = ""
  if core.project_directories then
    for _, p in ipairs(core.project_directories) do
      sig = sig .. tostring(type(p) == "table" and (p.path or p.name) or p or "") .. "|"
    end
  end
  if core.project_dir then
    sig = sig .. tostring(core.project_dir) .. "|"
  end

  if _cached_projects and sig == _last_project_signature then
    return _cached_projects
  end

  local projects = {}
  local seen = {}

  local function add_proj(name, path)
    if not path or path == "" then return end
    local abs = (system.absolute_path(path) or path):gsub("\\", "/"):gsub("/+$", "")
    local key = abs:lower()
    if not seen[key] then
      seen[key] = true
      name = name or abs:match("[^/]+$") or "project"
      table.insert(projects, {
        name = tostring(name),
        path = abs,
        len = #abs,
      })
    end
  end

  if core.project_directories then
    for _, p in ipairs(core.project_directories) do
      local p_name = type(p) == "table" and (p.name or p.path) or p
      local p_path = type(p) == "table" and (p.path or p.name) or p
      add_proj(p_name, p_path)
    end
  end

  if #projects == 0 and core.project_dir then
    local abs = (system.absolute_path(core.project_dir) or core.project_dir):gsub("\\", "/"):gsub("/+$", "")
    add_proj(abs:match("[^/]+$") or "project", abs)
  end

  if #projects == 0 then
    local cwd = (system.absolute_path(".") or "."):gsub("\\", "/"):gsub("/+$", "")
    add_proj(cwd:match("[^/]+$") or "project", cwd)
  end

  -- Ordena por tamanho decrescente para garantir correspondência com a pasta mais específica
  table.sort(projects, function(a, b) return a.len > b.len end)

  _cached_projects = projects
  _last_project_signature = sig
  return projects
end

-- =============================================================================
-- CÁLCULO DE ARCO CROMÁTICO DELIMITADO & ESCURIDÃO POR PROFUNDIDADE
-- =============================================================================
local _color_cache = {}
local _color_cache_count = 0
local MAX_CACHE = 800

local function resolve_file_location(filename)
  if not filename or filename == "" then
    return "default", "", 0, "Untitled"
  end

  local clean_fn = tostring(filename):gsub("\\", "/"):gsub("/+$", "")
  local fname = clean_fn:match("[^/]+$") or clean_fn
  local projects = get_treeview_projects()
  local matched_proj = nil
  local rel_path = ""

  for _, proj in ipairs(projects) do
    if clean_fn:lower():sub(1, proj.len) == proj.path:lower() then
      matched_proj = proj
      rel_path = clean_fn:sub(proj.len + 2)
      break
    end
  end

  if not matched_proj then
    matched_proj = { name = clean_fn:match("^/?[^/]+") or "default", path = "" }
    rel_path = clean_fn
  end

  -- Calcula a profundidade a partir dos separadores do caminho relativo
  local dir_part = rel_path:match("^(.*)/") or ""
  local depth = 0
  if dir_part ~= "" then
    for _ in dir_part:gmatch("[^/]+") do
      depth = depth + 1
    end
  end

  return matched_proj.name, rel_path, depth, fname
end

local function compute_bounded_accent(filename)
  local proj_name, rel_path, depth, fname = resolve_file_location(filename)
  local proj_lower = proj_name:lower()
  local is_doxoade = (proj_lower:find("doxoade") ~= nil)

  local base_hue = 0
  local arc_span = 34 -- Amplitude máxima do arco circular (graus)
  local max_depth_clamp = 5
  local depth_ratio = math.min(depth / max_depth_clamp, 1.0)

  if is_doxoade then
    -- 🔴 DOXOADE: Começa em Vermelho Carmim (4°) e gira em direção ao Laranja (38°)
    base_hue = 4
    arc_span = 34
  else
    -- 🟢🔵 OUTROS PROJETOS: Setores exclusivos de 35° distribuídos harmoniosamente
    local p_hash = hash_string(proj_lower)
    base_hue = (p_hash * 137.508) % 360
    
    -- Se colidir com o setor vermelho-alaranjado do Doxoade (345° a 45°), afasta para dar contraste
    if base_hue > 345 or base_hue < 45 then
      base_hue = (base_hue + 75) % 360
    end
    arc_span = 32
  end

  -- Rotação no arco delimitado
  local final_hue = (base_hue + (depth_ratio * arc_span)) % 360

  -- 🌑 ESCURIDÃO CONFORME PROFUNDIDADE:
  -- Raiz (depth 0): Luminosidade viva (0.55)
  -- Pastas profundas: Escurece suavemente até 0.30 (sem ficar opaco ou ilegível)
  local base_lightness = 0.55 - (depth_ratio * 0.25)
  local base_saturation = is_doxoade and (0.86 - (depth_ratio * 0.08)) or (0.78 - (depth_ratio * 0.06))

  -- 📄 MICRO-VARIAÇÃO POR ARQUIVO NA MESMA PASTA:
  -- Pequeno offset determinístico para distinguir abas da mesma subpasta
  local f_hash = hash_string(fname)
  local file_lum_offset = (((f_hash % 9) - 4) * 0.015) -- +/- 6%
  local file_sat_offset = ((((math.floor(f_hash / 9)) % 7) - 3) * 0.018)

  local final_lightness = math.max(0.28, math.min(0.62, base_lightness + file_lum_offset))
  local final_saturation = math.max(0.65, math.min(0.95, base_saturation + file_sat_offset))

  local rgb = hsl_to_rgb(final_hue, final_saturation, final_lightness)

  return {
    accent = rgb,
    project = proj_name,
    depth = depth,
    hue = final_hue,
    lightness = final_lightness,
    is_doxoade = is_doxoade
  }
end

local function doxoade_resolve_tab_theme(filename)
  local key = tostring(filename or "default")

  -- Invalida o cache de cores se as pastas da TreeView mudaram
  local sig = ""
  if core.project_directories then
    for _, p in ipairs(core.project_directories) do
      sig = sig .. tostring(type(p) == "table" and (p.path or p.name) or p or "") .. "|"
    end
  end
  if sig ~= _last_project_signature then
    _color_cache = {}
    _color_cache_count = 0
  end

  local cached = _color_cache[key]
  if cached then return cached end

  if _color_cache_count >= MAX_CACHE then
    _color_cache = {}
    _color_cache_count = 0
  end

  local theme = compute_bounded_accent(key)
  _color_cache[key] = theme
  _color_cache_count = _color_cache_count + 1
  return theme
end

rawset(_G, "DOXOADE_GET_TAB_THEME", doxoade_resolve_tab_theme)

-- =============================================================================
-- HOOK DE RENDERIZAÇÃO DE TÍTULO DE ABA (CONTRASTE WCAG & LINHA SUTIL)
-- =============================================================================
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
  if theme and theme.accent then
    local is_dirty = false
    pcall(function()
      if view and view.doc and view.doc.is_dirty then
        is_dirty = view.doc:is_dirty()
      end
    end)

    if is_dirty then
      -- Borda de modificação amarela quando o buffer estiver dirty
      local YEL = { 254, 139, 8, 255 }
      draw_rect_safe(x, y, w, 2, YEL)
      draw_rect_safe(x, y + 2, w, 1, { 254, 139, 8, 115 })
      draw_rect_safe(x, y, 1, h, YEL)
      draw_rect_safe(x + w - 1, y, 1, h, YEL)
      draw_rect_safe(x, y + h - 1, w, 1, YEL)
    else
      local a = theme.accent
      local alpha = is_active and 240 or (is_hovered and 160 or 90)
      draw_rect_safe(x, y, w, is_active and 2 or 1, { a[1], a[2], a[3], alpha })
    end

    -- Contraste inteligente baseado na luminância da aba
    local old_text = style.text
    local old_dim = style.dim
    local bg = rawget(_G, "_DOXOADE_TAB_BG")
    
    if type(bg) == "table" then
      local lum = 0.2126 * (bg[1] / 255) + 0.7152 * (bg[2] / 255) + 0.0722 * (bg[3] / 255)
      if lum > 0.45 then
        style.text = { 20, 20, 24, 255 }
        style.dim  = { 60, 60, 65, 255 }
      else
        style.text = { 248, 248, 250, 255 }
        style.dim  = { 180, 180, 190, 255 }
      end
    else
      style.text = is_active and { 250, 250, 250, 255 } or { 185, 185, 185, 255 }
      style.dim  = { 160, 160, 160, 255 }
    end

    local ok, res = pcall(original_draw_tab_title, self, view, font, is_active, is_hovered, x, y, w, h)
    style.text = old_text
    style.dim = old_dim
    if ok then return res end
  end

  return original_draw_tab_title(self, view, font, is_active, is_hovered, x, y, w, h)
end
