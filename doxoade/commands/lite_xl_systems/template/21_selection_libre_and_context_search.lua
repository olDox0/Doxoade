-- doxoade/commands/lite_xl_systems/template/21_selection_libre_and_context_search.lua
--[[
  🔍 DOXOADE CONTEXTUAL SEARCH & SELECTION LIBRE (V47.0 — Fase 3.1)
  ----------------------------------------------------------------------------
  Correção do "Frameless Split Killer": o Alt+F salvava e restaurava o active_view,
  mas o Lite XL colapsava o split durante o ciclo de vida do CommandView.
  Solução: restaurar o nó ativo FORÇADAMENTE após o CommandView fechar.
--]]

local core = require "core"
local config = require "core.config"
local command = require "core.command"
local keymap = require "core.keymap"
local common = require "core.common"

if config.doxoade_contextual_search == false then return end
if rawget(_G, "_DOXOADE_CONTEXTUAL_SEARCH_LOADED") then return end
rawset(_G, "_DOXOADE_CONTEXTUAL_SEARCH_LOADED", true)

-- Utilidades
local function safe_log(msg)
  if core and core.log then pcall(core.log, msg) end
end
local function safe_error(msg)
  if core and core.error then pcall(core.error, msg) end
end
local function is_treeview(view)
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
    if ok and type(name) == "string" and name:lower():find("tree") then return true end
  end
  return false
end

-- Seleções Múltiplas
local function get_all_selections(doc)
  if not doc then return {} end
  local sels = {}
  if type(doc.get_selections) == "function" then
    local ok, native_sels = pcall(doc.get_selections, doc)
    if ok and type(native_sels) == "table" and #native_sels > 0 then
      for _, s in ipairs(native_sels) do
        if type(s) == "table" and s[1] and s[3] then
          table.insert(sels, { s[1], s[2] or 1, s[3], s[4] or 1 })
        end
      end
    end
  end
  if #sels == 0 and type(doc.has_selection) == "function" and doc:has_selection() then
    local ok, l1, c1, l2, c2 = pcall(doc.get_selection, doc, true)
    if ok and l1 and l2 then table.insert(sels, { l1, c1 or 1, l2, c2 or 1 }) end
  end
  if #sels == 0 and type(doc.get_selection) == "function" then
    local ok, l, c = pcall(doc.get_selection, doc, true)
    if ok and l then table.insert(sels, { l, c or 1, l, c or 1 }) end
  end
  for i, s in ipairs(sels) do
    if s[1] > s[3] or (s[1] == s[3] and s[2] > s[4]) then
      sels[i] = { s[3], s[4], s[1], s[2] }
    end
  end
  table.sort(sels, function(a, b)
    if a[1] ~= b[1] then return a[1] < b[1] end
    return a[2] < b[2]
  end)
  return sels
end
rawset(_G, "DOXOADE_GET_ALL_SELECTIONS", get_all_selections)

local function get_selected_term(doc)
  if not doc or type(doc.has_selection) ~= "function" or not doc:has_selection() then return nil end
  local ok, l1, c1, l2, c2 = pcall(doc.get_selection, doc, true)
  if not ok or not l1 or l1 ~= l2 then return nil end
  local ok2, text = pcall(doc.get_text, doc, l1, c1, l2, c2)
  if not ok2 or not text or text == "" then return nil end
  text = text:gsub("^%s+", ""):gsub("%s+$", "")
  if #text == 0 or #text > 120 then return nil end
  return text
end

-- Paleta (sem race, com on_close_fn)
local function open_search_palette(prompt, default_term, submit_fn, on_close_fn)
  if not core.command_view or type(core.command_view.enter) ~= "function" then
    safe_error("⚠ [SEARCH] command_view indisponível.")
    return false
  end
  local ok, err = pcall(core.command_view.enter, core.command_view, prompt, {
    text = default_term or "",
    suggest = function(text)
      local suggestions = {}
      if core.docs then
        for _, d in ipairs(core.docs) do
          if d.filename then
            table.insert(suggestions, d.filename:match("[^/\\]+$") or d.filename)
          end
        end
      end
      if #suggestions == 0 or not text or text == "" then return suggestions end
      local lower = text:lower()
      local filtered = {}
      for _, s in ipairs(suggestions) do
        if s:lower():find(lower, 1, true) then table.insert(filtered, s) end
      end
      return filtered
    end,
    submit = function(query)
      if on_close_fn then pcall(on_close_fn) end
      if not query or query:match("^%s*$") then return end
      submit_fn(query)
    end,
    on_escape = function()
      if on_close_fn then pcall(on_close_fn) end
    end,
  })
  if not ok then
    safe_error("⚠ [SEARCH] command_view.enter falhou: " .. tostring(err))
    return false
  end
  return true
end

-- Comando Principal
command.add(nil, {
  ["doxoade:contextual-search"] = function()
    local view = core.active_view
    if is_treeview(view) then
      command.perform("doxoade:search-in-treeview-path")
      return
    end

    local doc = view and view.doc
    local default_term = get_selected_term(doc) or ""

    if core.log then
      core.log(string.format("🔍 [SEARCH] Abrindo paleta | default_term='%s'", tostring(default_term)))
    end

    -- 🛡️ [FASE 3.1] O Segredo: Restaurar o Split SEMPRE que a paleta fechar
    -- Usamos um delay de 0.05s APÓS o close para garantir que o Lite XL terminou o layout.
    local function restore_split_safely()
      if not core.add_thread then return end
      core.add_thread(function()
        coroutine.yield(0.05) -- Aguarda o CommandView sumir completamente
        local active_node = core.root_view and core.root_view:get_active_node()
        if active_node then
          if core.root_view.set_active_node then
            pcall(core.root_view.set_active_node, core.root_view, active_node)
          end
          if active_node.active_view and core.set_active_view then
            pcall(core.set_active_view, active_node.active_view)
          end
        end
        core.redraw = true
        if core.log then core.log("🛡️ [SEARCH] Split preservado após CommandView.") end
      end)
    end

    local ok = open_search_palette(
      "🔍 Buscar no Projeto (Alt+F)",
      default_term,
      function(query)
        if not query or query:match("^%s*$") then return end

        -- ✅ Defesa 1: collapse a seleção ANTES do submit (Enter keyup não acha texto pra substituir)
        local doc = core.active_view and core.active_view.doc
        if doc and doc.has_selection and doc:has_selection() then
          local ok_sel, l, c = pcall(doc.get_selection, doc, true)
          if ok_sel and l and c then
            pcall(doc.set_selection, doc, l, c, l, c)
          end
        end

        -- ✅ Defesa 2: defer a busca 10ms (keyup do Enter já foi dispatchado)
        core.add_thread(function()
          coroutine.yield(0.01)
          local executor = rawget(_G, "DOXOADE_EXECUTE_GLOBAL_SEARCH")
          if type(executor) == "function" then
            pcall(executor, query, nil)
          else
            command.perform("doxoade:global-project-search")
          end
        end)
      end,
      restore_split_safely
    )
  end,
})

-- Keymap com prioridade
pcall(function()
  if keymap and keymap.unbind then keymap.unbind("alt+f") end
  keymap.add({ ["alt+f"] = "doxoade:contextual-search" }, true)
end)

safe_log("🔍 [SEARCH] Contextual Search & Selection Libre V47.0 carregado (Split Fix).")
