-- doxoade/commands/lite_xl_systems/template/template/03_tab_colors.lua
-- =============================================================================
-- 03. MATRIZ DE CORES DE FUNDO DE ABAS POR PROJETO
-- =============================================================================
local PROJECT_THEMES = {
  { accent = { 56, 189, 248, 255 },  active_bg = { 14, 116, 144, 255 },  hover_bg = { 8, 85, 105, 255 },   inactive_bg = { 8, 48, 60, 255 } },    -- Ciano Oceano
  { accent = { 74, 222, 128, 255 },  active_bg = { 21, 128, 61, 255 },   hover_bg = { 15, 95, 45, 255 },   inactive_bg = { 10, 55, 28, 255 } },   -- Esmeralda
  { accent = { 244, 114, 182, 255 }, active_bg = { 190, 24, 93, 255 },   hover_bg = { 140, 18, 68, 255 },  inactive_bg = { 85, 12, 42, 255 } },   -- Rosa Vibrante
  { accent = { 251, 191, 36, 255 },  active_bg = { 180, 83, 9, 255 },    hover_bg = { 130, 60, 7, 255 },   inactive_bg = { 80, 36, 5, 255 } },    -- Âmbar / Ouro
  { accent = { 167, 139, 250, 255 }, active_bg = { 109, 40, 217, 255 },  hover_bg = { 80, 28, 160, 255 },  inactive_bg = { 50, 18, 100, 255 } },  -- Violeta Real
  { accent = { 45, 212, 191, 255 },  active_bg = { 15, 118, 110, 255 },  hover_bg = { 11, 88, 82, 255 },   inactive_bg = { 8, 55, 50, 255 } },    -- Teal Escuro
  { accent = { 251, 113, 133, 255 }, active_bg = { 185, 28, 28, 255 },   hover_bg = { 135, 20, 20, 255 },  inactive_bg = { 85, 12, 12, 255 } },   -- Carmesim
  { accent = { 129, 140, 248, 255 }, active_bg = { 67, 56, 202, 255 },   hover_bg = { 50, 42, 150, 255 },  inactive_bg = { 32, 26, 95, 255 } },   -- Índigo
}

local DEFAULT_THEME = { accent = { 148, 163, 184, 255 }, active_bg = { 51, 65, 85, 255 }, hover_bg = { 38, 48, 64, 255 }, inactive_bg = { 30, 41, 59, 255 } }

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
    matched_project = clean_fn:match([=[^(.*)[/\\]]=]) or clean_fn
  end

  matched_project = tostring(matched_project or "default")
  local hash = 0
  for i = 1, #matched_project do
    hash = (hash * 31 + matched_project:byte(i)) % #PROJECT_THEMES
  end
  return PROJECT_THEMES[hash + 1] or DEFAULT_THEME
end

local original_draw_tab_title = Node.draw_tab_title
function Node:draw_tab_title(view, font, is_active, is_hovered, x, y, w, h)
  local ok, theme = pcall(function()
    local doc = view and view.doc
    local filename = doc and doc.filename or (view and view:get_name() or nil)
    return get_project_tab_theme(filename)
  end)

  if ok and theme then
    local bg = is_active and theme.active_bg or (is_hovered and theme.hover_bg or theme.inactive_bg)
    if rencache then
      rencache.draw_rect(x, y, w, h, bg)
      rencache.draw_rect(x, y, w, is_active and 3 or 1, theme.accent)
    elseif native_renderer then
      native_renderer.draw_rect(x, y, w, h, bg)
      native_renderer.draw_rect(x, y, w, is_active and 3 or 1, theme.accent)
    end

    local old_text = style.text
    local old_dim = style.dim
    style.text = is_active and { 255, 255, 255, 255 } or (is_hovered and { 240, 240, 240, 255 } or { 190, 190, 190, 255 })
    style.dim = { 180, 180, 180, 255 }

    local res = original_draw_tab_title(self, view, font, is_active, is_hovered, x, y, w, h)

    style.text = old_text
    style.dim = old_dim
    return res
  end

  return original_draw_tab_title(self, view, font, is_active, is_hovered, x, y, w, h)
end