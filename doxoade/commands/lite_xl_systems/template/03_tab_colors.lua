-- doxoade/commands/lite_xl_systems/template/template/03_tab_colors.lua
-- =============================================================================
-- 03. MATRIZ DE CORES DE FUNDO DE ABAS POR PROJETO
-- =============================================================================
--  { accent = { , , },   active_bg = { , , },    hover_bg = { , , },   inactive_bg = { , , } },     -- x (#)
local PROJECT_THEMES = {
  { accent = { 255, 0, 0 },   active_bg = { 175, 0, 0 },    hover_bg = { 170, 68, 0 },   inactive_bg = { 130, 0, 0 } },        -- fullred (#ff0000)
  { accent = { 255, 103, 0 },   active_bg = { 224, 90, 0 },    hover_bg = { 170, 68, 0 },   inactive_bg = { 90, 36, 0 } },     -- Laranja Blaze (#ff6700)
  { accent = { 232, 170, 0 },   active_bg = { 170, 125, 0 },   hover_bg = { 130, 95, 0 },   inactive_bg = { 70, 50, 0 } },     -- Urobilin (#e8aa00)
  { accent = { 38, 188, 95 },   active_bg = { 25, 123, 63 },   hover_bg = { 18, 90, 46 },    inactive_bg = { 10, 51, 26 } },   -- Esmeralda (#26bc5f)
  { accent = { 0, 108, 255 },   active_bg = { 0, 80, 190 },    hover_bg = { 0, 60, 140 },   inactive_bg = { 0, 35, 80 } },     -- Brandeis Blue (#006cff)
  { accent = { 200, 21, 118 },  active_bg = { 150, 16, 88 },   hover_bg = { 110, 12, 65 },  inactive_bg = { 60, 6, 35 } },     -- Magenta Electric (#c81576)
  { accent = { 77, 145, 232 },  active_bg = { 30, 57, 92 },    hover_bg = { 22, 42, 68 },   inactive_bg = { 14, 28, 45 } },    -- Pastel Blue (#4d91e8)
  { accent = { 206, 105, 158 }, active_bg = { 82, 41, 63 },    hover_bg = { 60, 30, 46 },   inactive_bg = { 38, 19, 29 } },    -- Pastel Pink (#ce699e)
  { accent = { 227, 141, 83 },  active_bg = { 90, 56, 33 },    hover_bg = { 68, 42, 25 },   inactive_bg = { 42, 26, 15 } },    -- Pastel Orange (#e38d53)
}

local DEFAULT_THEME = { accent = { 94, 92, 94 }, active_bg = { 47, 46, 48 }, hover_bg = { 35, 34, 36 }, inactive_bg = { 25, 23, 26 } }

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
