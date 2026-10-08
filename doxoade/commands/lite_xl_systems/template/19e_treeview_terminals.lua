-- doxoade/commands/lite_xl_systems/template/19e_treeview_terminals.lua
--[[
  📂 DOXOADE AUTO-TERMINAL ON TREEVIEW & PROJECT LIFECYCLE (V3.0)
  - Auto-Spawn: abre e provisiona terminal assim que um projeto entra no workspace.
  - Sincronização automática no boot para todos os projetos de core.project_directories.
  - Sintonização ao clicar em nós de projeto no TreeView.
  Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
]]
local core = require "core"
local command = require "core.command"

local function normalize_dir(path)
  if not path or path == "" then return nil end
  local p = (system.absolute_path(path) or path):gsub("\\", "/")
  -- 🎯 Ignora diretórios internos da IDE
  if p:find("%.config") or p:find("test_deploy") or p:find("sandbox") then return nil end
  return p
end

local function spawn_terminal_for_project(raw_path, force_open)
  local path = normalize_dir(raw_path)
  if not path then return end

  local mgr = rawget(_G, "_DOXOADE_TERMINAL_SESSION_MGR")
  if mgr and mgr.get_or_create_for_project then
    local session = mgr.get_or_create_for_project(path)
    if force_open ~= false then
      command.perform("doxoade:terminal-launch-real")
    end
    core.redraw = true
    if core.log then
      core.log("📂 [AUTO-TERMINAL] Sessão conectada ao projeto: " .. session:get_display_name())
    end
  end
end

-- ── 1. HOOK: Disparo Automático ao Adicionar Projeto no Workspace ────────────
local orig_add_project_directory = core.add_project_directory
if orig_add_project_directory then
  core.add_project_directory = function(path, ...)
    local res = orig_add_project_directory(path, ...)
    if path then
      core.add_thread(function()
        coroutine.yield(0.15) -- Aguarda estabilização do filesystem e nós da árvore
        spawn_terminal_for_project(path, true)
      end)
    end
    return res
  end
end

-- ── 2. VIGILÂNCIA DE PROJETOS NO BOOT / RESTAURAÇÃO DE SESSÃO ────────────────
core.add_thread(function()
  coroutine.yield(0.6)
  local mgr = rawget(_G, "_DOXOADE_TERMINAL_SESSION_MGR")
  if mgr and core.project_directories then
    for _, p in ipairs(core.project_directories) do
      local p_path = type(p) == "table" and (p.path or p.name) or p
      local norm = normalize_dir(p_path)
      if norm then
        -- Garante a sessão registrada na aba sem forçar spawn imediato
        mgr.get_or_create_for_project(norm)
      end
    end
    core.redraw = true
  end
end)

-- ── 3. RESOLUÇÃO DE DIRETÓRIO DO TREEVIEW ─────────────────────────────────────
local function resolve_target_dir(item)
  local path = nil
  if item and item.filename then
    path = item.filename
  elseif item and item.abs_filename then
    path = item.abs_filename
  elseif type(item) == "string" then
    path = item
  end

  if not path then
    local av = core.active_view
    if av and av.hovered_item then
      return resolve_target_dir(av.hovered_item)
    elseif av and av.selected_item then
      return resolve_target_dir(av.selected_item)
    elseif av and av.doc and av.doc.filename then
      path = av.doc.filename
    end
  end

  if path then
    local info = system.get_file_info(path)
    if info and info.type == "dir" then
      return normalize_dir(path)
    end
    local dir = path:match("^(.*)[/\\].*$")
    if dir then
      return normalize_dir(dir)
    end
  end

  return normalize_dir(core.project_dir) or "."
end

-- ── 4. HOOK DE CLIQUE NO TREEVIEW: Sintoniza o Terminal ao Clicar na Pasta ────
local ok_tv, TreeView = pcall(require, "plugins.treeview.treeview")
if not ok_tv or not TreeView then
  ok_tv, TreeView = pcall(require, "plugins.treeview")
end

if ok_tv and TreeView and TreeView.on_mouse_pressed then
  local orig_tv_on_mouse_pressed = TreeView.on_mouse_pressed
  function TreeView:on_mouse_pressed(button, x, y, clicks)
    local res = orig_tv_on_mouse_pressed(self, button, x, y, clicks)
    if button == "left" and clicks == 2 and self.hovered_item then
      local target = resolve_target_dir(self.hovered_item)
      if target and core.project_directories then
        -- Se for uma pasta raiz de projeto aberta no editor, sintoniza o terminal
        for _, p in ipairs(core.project_directories) do
          local p_path = normalize_dir(type(p) == "table" and (p.path or p.name) or p)
          if p_path and p_path:lower() == target:lower() then
            spawn_terminal_for_project(target, false)
            break
          end
        end
      end
    end
    return res
  end
end

-- ── 5. COMANDOS & CONTEXT MENU ────────────────────────────────────────────────
command.add(function()
  return core.active_view and (
    core.active_view:is(TreeView or Object) or
    (core.active_view.hovered_item ~= nil)
  )
end, {
  ["treeview:open-terminal-here"] = function()
    local tv = core.active_view
    local target = resolve_target_dir(tv and tv.hovered_item)
    if target then
      spawn_terminal_for_project(target, true)
    end
  end,

  ["treeview:open-external-terminal-here"] = function()
    local tv = core.active_view
    local target = resolve_target_dir(tv and tv.hovered_item)
    local mgr = rawget(_G, "_DOXOADE_TERMINAL_SESSION_MGR")
    local term = (mgr and mgr.get_active()) or rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term and target then
      term:launch_external(target, false)
    end
  end,

  ["treeview:open-admin-terminal-here"] = function()
    local tv = core.active_view
    local target = resolve_target_dir(tv and tv.hovered_item)
    local mgr = rawget(_G, "_DOXOADE_TERMINAL_SESSION_MGR")
    local term = (mgr and mgr.get_active()) or rawget(_G, "_DOXOADE_TERMINAL_ENGINE")
    if term and target then
      term:launch_external(target, true)
    end
  end,
})

-- Registra no menu de contexto do botão direito
local ok_ctx, contextmenu = pcall(require, "plugins.contextmenu")
if ok_ctx and contextmenu and contextmenu.register then
  pcall(function()
    contextmenu:register("plugins.treeview.treeview", {
      contextmenu.DIVIDER,
      { text = "Abrir Terminal Neste Projeto", command = "treeview:open-terminal-here" },
      { text = "Abrir Terminal Externo", command = "treeview:open-external-terminal-here" },
      { text = "Abrir Terminal como Admin", command = "treeview:open-admin-terminal-here" },
    })
  end)
end
