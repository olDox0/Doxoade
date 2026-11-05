-- doxoade/commands/lite_xl_systems/template/11_tab_context_menu.lua
--[[
 DOXOADE TAB CONTEXT MENU (Menu Flutuante Soberano de Abas) V2
- Copia caminhos com 1 clique: Nome, Caminho Relativo e Caminho Absoluto.
- Proj. Address: relativo a partir da raiz do projeto MAIS LONGO na TreeView.
- Invalidação automática de cache ao adicionar/remover projetos.
- Abertura de arquivo no gerenciador de arquivos nativo do SO.
]]
local core = require "core"
local style = require "core.style"
local command = require "core.command"
local Node = require "core.node"
local RootView = require "core.rootview"
local keymap = require "core.keymap"

if rawget(_G, "DOXOADE_TAB_CONTEXT_LOADED") then
  return
end
rawset(_G, "DOXOADE_TAB_CONTEXT_LOADED", true)

local rencache = rawget(_G, "rencache") or (pcall(require, "core.rencache") and require("core.rencache") or nil)
local native_renderer = rawget(_G, "renderer") or (pcall(require, "renderer") and require("renderer") or nil)

-- =============================================================================
-- 🛠️ UTILITÁRIOS DE RENDERIZAÇÃO (declarados UMA VEZ)
-- =============================================================================
local function draw_rect_safe(x, y, w, h, color)
  if rencache and rencache.draw_rect then
    rencache.draw_rect(x, y, w, h, color)
  elseif native_renderer and native_renderer.draw_rect then
    native_renderer.draw_rect(x, y, w, h, color)
  end
end

local function draw_text_safe(font, text, x, y, color)
  if rencache and rencache.draw_text then
    rencache.draw_text(font, text, x, y, color)
  elseif native_renderer and native_renderer.draw_text then
    native_renderer.draw_text(font, text, x, y, color)
  end
end

-- =============================================================================
-- 📂 RESOLUÇÃO SOBERANA DE CAMINHOS (V2 — Best-Root + Cache Invalidation)
-- =============================================================================
local _path_cache = {}
local _last_project_signature = ""

-- Invalida o cache sempre que a lista de projetos muda
local function _invalidate_path_cache_if_needed()
  local sig = ""
  if core.project_directories then
    for _, p in ipairs(core.project_directories) do
      sig = sig .. tostring(type(p) == "table" and (p.path or p.name) or p or "") .. "|"
    end
  end
  if sig ~= _last_project_signature then
    _path_cache = {}
    _last_project_signature = sig
  end
end

local function resolve_active_paths(view)
    view = view or core.active_view
    if not view or not view.doc or not view.doc.filename then return nil end

    _invalidate_path_cache_if_needed()

    local raw = view.doc.filename
    if _path_cache[raw] then return _path_cache[raw] end

    local abs = system.absolute_path(raw) or raw
    local clean_abs = abs:gsub("\\", "/"):lower()
    local fname = raw:match("[/\\]([^/\\]+)$") or raw

    -- Coleta todas as raízes de projeto normalizadas
    local project_roots = {}
    if core.project_directories then
        for _, proj in ipairs(core.project_directories) do
            local p_str = type(proj) == "table" and (proj.path or proj.name) or tostring(proj or "")
            if p_str and p_str ~= "" then
                local clean_p = (system.absolute_path(p_str) or p_str):gsub("\\", "/"):lower():gsub("/+$", "")
                if clean_p ~= "" then
                    table.insert(project_roots, clean_p)
                end
            end
        end
    end
    
    -- DEBUG: Log das raízes encontradas
    if core.log then
        core.log(string.format("🔍 [Proj.Address] Raízes de projeto: %d", #project_roots))
        for i, root in ipairs(project_roots) do
            core.log(string.format("   Raiz %d: %s", i, root))
        end
        core.log(string.format("🔍 [Proj.Address] Arquivo: %s", clean_abs))
    end

    -- Encontra o projeto raiz MAIS LONGO que contém o arquivo
    local best_root = nil
    local best_len = 0
    for _, root in ipairs(project_roots) do
        if clean_abs:sub(1, #root) == root then
            if #root > best_len then
                best_root = root
                best_len = #root
            end
        end
    end

    -- DEBUG: Log do best_root encontrado
    if core.log then
        if best_root then
            core.log(string.format("🔍 [Proj.Address] Best root: %s (len=%d)", best_root, best_len))
        else
            core.log("⚠️ [Proj.Address] Nenhum projeto raiz encontrado para este arquivo")
        end
    end

    -- Calcula o relativo
    local rel = clean_abs
    if best_root and best_len > 0 then
        rel = clean_abs:sub(best_len + 1):gsub("^/", "")
    end
    if rel == "" then rel = fname end

    -- DEBUG: Log do relativo calculado
    if core.log then
        core.log(string.format("🔍 [Proj.Address] Relativo calculado: %s", rel))
    end

    -- Converte para separador nativo do SO
    local clean_native_abs = abs:gsub("[/\\]", PATHSEP or "\\")
    local clean_native_rel = rel:gsub("/", PATHSEP or "\\")
    local dir = clean_native_abs:match("^(.*)[/\\]") or clean_native_abs

    local result = {
        filename = fname,
        relative = clean_native_rel,
        absolute = clean_native_abs,
        dir = dir,
        raw = abs
    }

    _path_cache[raw] = result
    return result
end

-- =============================================================================
-- 🖥️ ABERTURA NO EXPLORER
-- =============================================================================
local function open_in_file_manager(path)
  if system.show_in_file_manager then
    system.show_in_file_manager(path)
    return
  end
  if PLATFORM == "Windows" then
    system.exec('explorer.exe /select,"' .. tostring(path):gsub('"', '""') .. '"')
  else
    local dir = tostring(path):match("^(.*)[/\\]") or path
    system.exec("xdg-open '" .. tostring(dir):gsub("'", "'\\''") .. "'")
  end
end

-- =============================================================================
-- 📋 MENU FLUTUANTE
-- =============================================================================
local FloatingMenu = {
  visible = false,
  x = 0, y = 0, w = 260, h = 100,
  hovered_idx = nil,
  items = {},
}

local PADDING_X = 14
local PADDING_Y = 6

local function get_item_height()
  local font = style.font or style.code_font
  return font:get_height() + (PADDING_Y * 2)
end

local function build_menu_items(paths)
  if not paths then return nil end
  return {
    {
      text = "📋 Copy Name     : " .. paths.filename,
      action = function()
        system.set_clipboard(paths.filename)
        core.log("Copiado (Nome): " .. paths.filename)
      end
    },
    {
      text = "📂 Proj. Address : " .. paths.relative,
      action = function()
        system.set_clipboard(paths.relative)
        core.log("Copiado (Proj. Address): " .. paths.relative)
      end
    },
    {
      text = " Total Address : " .. paths.absolute,
      action = function()
        system.set_clipboard(paths.absolute)
        core.log("Copiado (Total Address): " .. paths.absolute)
      end
    },
    {
      text = "🖥️ Open Explorer : " .. paths.dir,
      action = function()
        open_in_file_manager(paths.raw)
        core.log("Explorer aberto em: " .. paths.dir)
      end
    },
    {
      text = "🧹 Close Tabs to Right",
      action = function()
        command.perform("root:close-following-tabs")
      end
    },
  }
end

local function open_floating_menu(view, mx, my)
  local paths = resolve_active_paths(view)
  local items = build_menu_items(paths)
  if not items then return end

  local font = style.font or style.code_font
  local item_h = get_item_height()
  local max_w = 200

  for _, it in ipairs(items) do
    local tw = font:get_width(it.text)
    if tw > max_w then max_w = tw end
  end

  local menu_w = max_w + (PADDING_X * 2) + 12
  local menu_h = (#items * item_h) + 8

  local screen_w = core.root_view and core.root_view.size and core.root_view.size.x or 1200
  local screen_h = core.root_view and core.root_view.size and core.root_view.size.y or 800

  local fx = (mx + menu_w > screen_w) and (screen_w - menu_w - 6) or mx
  local fy = (my + menu_h > screen_h) and (screen_h - menu_h - 6) or my
  fx = math.max(4, fx)
  fy = math.max(4, fy)

  FloatingMenu.x = fx
  FloatingMenu.y = fy
  FloatingMenu.w = menu_w
  FloatingMenu.h = menu_h
  FloatingMenu.items = items
  FloatingMenu.hovered_idx = nil
  FloatingMenu.visible = true
  core.redraw = true
end

-- =============================================================================
-- HOOKS DE RENDERIZAÇÃO E INTERAÇÃO
-- =============================================================================
local original_rootview_draw = RootView.draw
function RootView:draw(...)
  original_rootview_draw(self, ...)
  if not FloatingMenu.visible or #FloatingMenu.items == 0 then return end

  local x, y, w, h = FloatingMenu.x, FloatingMenu.y, FloatingMenu.w, FloatingMenu.h
  local item_h = get_item_height()
  local font = style.font or style.code_font

  draw_rect_safe(x - 2, y - 2, w + 4, h + 4, { 10, 10, 10, 200 })
  draw_rect_safe(x, y, w, h, style.background2 or { 25, 23, 26, 255 })
  draw_rect_safe(x, y, 3, h, style.accent or { 38, 188, 95, 255 })
  draw_rect_safe(x, y, w, 1, style.divider or { 76, 69, 82, 255 })

  local curr_y = y + 4
  for i, it in ipairs(FloatingMenu.items) do
    local is_hovered = (FloatingMenu.hovered_idx == i)
    if is_hovered then
      draw_rect_safe(x + 3, curr_y, w - 4, item_h, style.background3 or { 47, 46, 48, 255 })
    end
    local text_color = is_hovered and { 255, 255, 255, 255 } or (style.text or { 210, 220, 230, 255 })
    draw_text_safe(font, it.text, x + PADDING_X, curr_y + PADDING_Y, text_color)
    curr_y = curr_y + item_h
  end
end

local original_rootview_mouse_moved = RootView.on_mouse_moved
function RootView:on_mouse_moved(x, y, ...)
  if not FloatingMenu.visible then
    return original_rootview_mouse_moved(self, x, y, ...)
  end
  original_rootview_mouse_moved(self, x, y, ...)

  local mx, my, mw, mh = FloatingMenu.x, FloatingMenu.y, FloatingMenu.w, FloatingMenu.h
  if x >= mx and x <= mx + mw and y >= my and y <= my + mh then
    local item_h = get_item_height()
    local idx = math.floor((y - my - 4) / item_h) + 1
    FloatingMenu.hovered_idx = (idx >= 1 and idx <= #FloatingMenu.items) and idx or nil
    core.redraw = true
  else
    if FloatingMenu.hovered_idx ~= nil then
      FloatingMenu.hovered_idx = nil
      core.redraw = true
    end
  end
end

local original_rootview_mouse_pressed = RootView.on_mouse_pressed
function RootView:on_mouse_pressed(button, x, y, clicks)
  if not FloatingMenu.visible then
    return original_rootview_mouse_pressed(self, button, x, y, clicks)
  end

  local mx, my, mw, mh = FloatingMenu.x, FloatingMenu.y, FloatingMenu.w, FloatingMenu.h
  if (button == "left" or button == 1) and x >= mx and x <= mx + mw and y >= my and y <= my + mh then
    local item_h = get_item_height()
    local idx = math.floor((y - my - 4) / item_h) + 1
    local item = FloatingMenu.items[idx]
    FloatingMenu.visible = false
    core.redraw = true
    if item and item.action then item.action() end
    return true
  end

  FloatingMenu.visible = false
  core.redraw = true
  return true
end

local contextmenu = nil
pcall(function() contextmenu = require "plugins.contextmenu" end)

local original_node_mouse_pressed = Node.on_mouse_pressed
function Node:on_mouse_pressed(button, x, y, clicks)
  if button == "right" or button == 2 then
    -- [FASE 3] Captura o item do TreeView ANTES do menu abrir.
    -- Só executa se a view ativa for TreeView (defesa em profundidade).
    -- NÃO altera o comportamento do context menu de abas do DocView.
    local idx = self:get_tab_overlapping_point(x, y)
    if idx and self.views and self.views[idx] then
      local view = self.views[idx]
      self:set_active_view(view)
      core.set_active_view(view)
      if contextmenu and contextmenu.show then
        local ok = pcall(contextmenu.show, contextmenu, x, y)
        if ok then return true end
      elseif command and command.perform then
        local ok = pcall(command.perform, "context-menu:show", x, y)
        if ok then return true end
      end
      open_floating_menu(view, x, y)
      return true
    end
  end
  return original_node_mouse_pressed(self, button, x, y, clicks)
end

-- =============================================================================
-- REGISTRO DE COMANDOS
-- =============================================================================
command.add("core.docview", {
  ["doxoade:tab-copy-filename"] = function()
    local p = resolve_active_paths()
    if p then system.set_clipboard(p.filename); core.log("Copiado (Nome): " .. p.filename) end
  end,

  ["doxoade:tab-copy-relative-path"] = function()
    local p = resolve_active_paths()
    if p then system.set_clipboard(p.relative); core.log("Copiado (Proj. Address): " .. p.relative) end
  end,

  ["doxoade:tab-copy-full-path"] = function()
    local p = resolve_active_paths()
    if p then system.set_clipboard(p.absolute); core.log("Copiado (Total Address): " .. p.absolute) end
  end,

  ["doxoade:tab-open-in-explorer"] = function()
    local p = resolve_active_paths()
    if p then open_in_file_manager(p.raw); core.log("Explorer aberto em: " .. p.dir) end
  end,

  ["doxoade:copy-path-menu"] = function()
    local p = resolve_active_paths()
    if not p then core.error("Nenhum documento ativo."); return end

    core.command_view:enter("Copiar Endereço (1: Nome, 2: Relativo, 3: Completo, 4: Explorer)", {
      submit = function(text)
        local opt = tostring(text):match("%d") or text:lower()
        if opt == "1" or opt:find("nome") or opt:find("name") then
          system.set_clipboard(p.filename); core.log("Copiado (Nome): " .. p.filename)
        elseif opt == "2" or opt:find("rel") or opt:find("proj") then
          system.set_clipboard(p.relative); core.log("Copiado (Proj. Address): " .. p.relative)
        elseif opt == "3" or opt:find("comp") or opt:find("total") then
          system.set_clipboard(p.absolute); core.log("Copiado (Total Address): " .. p.absolute)
        elseif opt == "4" or opt:find("exp") then
          open_in_file_manager(p.raw); core.log("Explorer aberto em: " .. p.dir)
        end
      end
    })
  end
})

-- =============================================================================
-- REGISTRO NO CONTEXTMENU NATIVO (para DocView — mantido)
-- =============================================================================
pcall(function()
  if contextmenu and contextmenu.register then
    local divider = contextmenu.DIVIDER or { divider = true }
    local items = {
      divider,
      { text = "Copy Name",        command = "doxoade:tab-copy-filename" },
      { text = "Proj. Address",    command = "doxoade:tab-copy-relative-path" },
      { text = "Total Address",    command = "doxoade:tab-copy-full-path" },
      divider,
      { text = "Open in Explorer", command = "doxoade:tab-open-in-explorer" },
    }
    local function predicate()
      local v = core.active_view
      return v and v.doc and v.doc.filename ~= nil
    end
    contextmenu:register(predicate, items)
  end
end)

-- =============================================================================
-- [FASE 5] UTILITÁRIOS DO TREEVIEW (definidos ANTES de qualquer uso)
-- =============================================================================

local function _is_treeview_instance(view)
  if not view then return false end
  local ok_tv, TreeView = pcall(require, "plugins.treeview")
  if not ok_tv or not TreeView then
    ok_tv, TreeView = pcall(require, "plugins.treeview.treeview")
  end
  if ok_tv and TreeView and type(view.is) == "function" then
    local ok, res = pcall(view.is, view, TreeView)
    if ok and res then return true end
  end
  if type(view.get_name) == "function" then
    local ok, name = pcall(view.get_name, view)
    if ok and type(name) == "string" and name:lower():find("tree") then
      return true
    end
  end
  return false
end

local function _resolve_item_path(item)
  if not item then return nil end
  local raw = item.filename or item.abs_filename or item.path
  if type(raw) ~= "string" or raw == "" then return nil end
  local abs = (system.absolute_path and system.absolute_path(raw)) or raw
  abs = abs:gsub("\\", "/")
  local finfo = system.get_file_info and system.get_file_info(abs)
  if finfo and finfo.type == "dir" then
    return abs
  elseif finfo and finfo.type == "file" then
    local dir = abs:match("^(.*)[/\\][^/\\]+$")
    return dir and dir:gsub("\\", "/") or nil
  end
  return abs
end

-- =============================================================================
-- [FASE 5] HOOK DIRETO NO TREEVIEW (botão direito → busca contextual)
-- =============================================================================
-- Em vez de competir com o contextmenu nativo do TreeView, interceptamos o
-- clique com botão direito. Se o alvo for uma pasta válida, abrimos a paleta
-- de busca IMEDIATAMENTE (UX de 1 clique + digitar).
-- =============================================================================
pcall(function()
  local ok_tv, TreeView = pcall(require, "plugins.treeview")
  if not ok_tv or not TreeView then
    ok_tv, TreeView = pcall(require, "plugins.treeview.treeview")
  end
  if not ok_tv or not TreeView or type(TreeView.on_mouse_pressed) ~= "function" then
    return
  end

  if rawget(_G, "_DOXOADE_TREE_CTX_FASE5_HOOKED") then return end
  rawset(_G, "_DOXOADE_TREE_CTX_FASE5_HOOKED", true)

  local original_tv_pressed = TreeView.on_mouse_pressed
  function TreeView:on_mouse_pressed(button, x, y, clicks)
    -- Captura o item antes do original (que pode mudar hovered_item)
    local captured_item = nil
    if type(self.get_item_under_pos) == "function" then
      local ok, item = pcall(self.get_item_under_pos, self, x, y)
      if ok and item then captured_item = item end
    end

    -- Se for botão direito, abre a busca contextual ANTES do menu nativo
    if button == "right" or button == 2 then
      local target = captured_item or self.hovered_item or self.selected_item
      local path = _resolve_item_path(target)

      -- Sempre limpa resíduo
      rawset(_G, "_DOXOADE_TREE_CONTEXT_TARGET", nil)
      if path then
        rawset(_G, "_DOXOADE_TREE_CONTEXT_TARGET", path)

        -- Consome a seleção ativa (se houver) para pré-preencher a paleta
        local default_term = ""
        local active_doc = core.active_view and core.active_view.doc
        if active_doc and active_doc.has_selection and active_doc:has_selection() then
          local l1, c1, l2, c2 = active_doc:get_selection(true)
          if l1 == l2 then
            local ok2, txt = pcall(active_doc.get_text, active_doc, l1, c1, l2, c2)
            if ok2 and txt then
              txt = txt:gsub("^%s+", ""):gsub("%s+$", "")
              if #txt > 0 and #txt <= 120 then default_term = txt end
            end
          end
        end

        -- Abre a paleta de busca restrita (1 clique = 1 ação)
        if core.command_view and type(core.command_view.enter) == "function" then
          pcall(function() core.command_view:hide() end)

          local short_scope = path:match("[^/\\]+$") or path
          core.command_view:enter(
            string.format("🔍 Buscar em '%s'...", short_scope),
            {
              text = default_term,
              -- [FASE 5] `suggest` obrigatório para renderização
              suggest = function() return {} end,
              submit = function(query)
                if not query or query:match("^%s*$") then return end
                local executor = rawget(_G, "DOXOADE_EXECUTE_GLOBAL_SEARCH")
                if type(executor) == "function" then
                  pcall(executor, query, path)
                elseif core.log then
                  pcall(core.log, "⚠ [SEARCH] execute_global_search indisponível.")
                end
              end,
            }
          )

          if core.log then
            pcall(core.log, string.format("🔍 [TREE-CTX] Busca contextual aberta em: %s", path))
          end
          return true  -- Consome o clique (não abre o menu nativo)
        end
      end
    end

    -- Fallback: comportamento padrão do TreeView (não interceptamos)
    return original_tv_pressed(self, button, x, y, clicks)
  end

  if core.log then
    core.log("🔍 [FASE 5] TreeView hook instalado: botão direito abre busca contextual.")
  end
end)

-- =============================================================================
-- KEYMAPS
-- =============================================================================
keymap.add {
  ["ctrl+alt+e"]   = "doxoade:tab-copy-filename",
  ["ctrl+alt+c"]   = "doxoade:copy-path-menu",
  ["ctrl+shift+c"] = "doxoade:tab-copy-relative-path",
}
