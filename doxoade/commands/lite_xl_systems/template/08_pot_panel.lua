-- doxoade/commands/lite_xl_systems/template/08_pot_panel.lua
--[[
  Módulo de Painel Dumppot, Markdown Dinâmico e Divisão Direita Soberana.
  - Scratchpad persistente integrado (.doxoade/dumppot.txt).
  - Destacador de sintaxe Markdown multi-linguagem.
  - Comandos de busca e transferência de seleção entre painéis opostos.
]]
local core    = require "core"
local common  = require "core.common"
local DocView = require "core.docview"
local command = require "core.command"

local doxoade_cfg_dir = (USERDIR or ".") .. (PATHSEP or "/") .. ".doxoade"
pcall(function() system.mkdir(doxoade_cfg_dir) end)

local dumppot_file = doxoade_cfg_dir .. (PATHSEP or "/") .. "dumppot.txt"
local cheat_sheet_file = doxoade_cfg_dir .. (PATHSEP or "/") .. "cheat_sheet.txt"
local log_path = (USERDIR or ".") .. (PATHSEP or "/") .. "session_log.txt"

-- Localização global na home do usuário
local home_dir = os.getenv("USERPROFILE") or os.getenv("HOME") or (USERDIR or ".")
local global_doxoade_dir = home_dir .. (PATHSEP or "/") .. ".doxoade"
pcall(function() system.mkdir(global_doxoade_dir) end)
local global_shared_notes = global_doxoade_dir .. (PATHSEP or "/") .. "shared_notes.md"

-- Garante que o arquivo exista
pcall(function()
  local f = io.open(global_shared_notes, "a")
  if f then f:close() end
end)

-- =============================================================================
-- 1. SINTAXE DUMPPOT MARKDOWN
-- =============================================================================
pcall(function()
  local syntax = require "core.syntax"
  syntax.add {
    name = "Dumppot Markdown",
    files = { "dumppot%.txt$", "cheat_sheet%.txt$", "%.doxpot$", "%.pot$" },
    comment = "#",
    patterns = {
      { pattern = { "```%s*lua", "```" },        type = "string",   syntax = ".lua" },
      { pattern = { "```%s*python", "```" },     type = "string",   syntax = ".py" },
      { pattern = { "```%s*py", "```" },         type = "string",   syntax = ".py" },
      { pattern = { "```%s*c", "```" },          type = "string",   syntax = ".c" },
      { pattern = { "```%s*cpp", "```" },        type = "string",   syntax = ".cpp" },
      { pattern = { "```%s*json", "```" },       type = "string",   syntax = ".json" },
      { pattern = { "```%s*diff", "```" },       type = "string",   syntax = ".diff" },
      { pattern = { "```", "```" },              type = "string" },
      { pattern = "^#+%s.*",                     type = "keyword" },
      { pattern = "`.-`",                        type = "keyword2" },
      { pattern = "%*%*.-%*%*",                  type = "keyword" },
      { pattern = "https?://%S+",                type = "operator" },
      { pattern = "^===+.*===+",                 type = "keyword" },
      { pattern = "^%-%-%-+.*",                  type = "comment" },
    },
    symbols = {}
  }
end)

-- =============================================================================
-- 2. UTILITÁRIOS DE PAINEL DIREITO
-- =============================================================================
local function create_docview_safe(doc)
    if not doc then return nil end
    if type(DocView) == "table" and DocView.new then
        return DocView:new(doc)
    end
    local ok, view = pcall(DocView, doc)
    if ok and view then return view end
    
    -- 🛡️ FALLBACK MA'AT: Retorna um objeto estruturado em vez de tabela órfã
    local orphan_view = { doc = doc }
    orphan_view.get_name = function(self) return "Pot Panel" end
    orphan_view.get_title = function(self) return self:get_name() end
    orphan_view.is = function(self, class) return false end
    orphan_view.draw = function(self) end -- Evita crash de renderização
    return orphan_view
end

local function get_doc_leaves(n, list)
  list = list or {}
  if not n then return list end
  if n.type == "leaf" and not n.locked then
    table.insert(list, n)
  elseif n.type ~= "leaf" then
    get_doc_leaves(n.a, list)
    get_doc_leaves(n.b, list)
  end
  return list
end

local function get_or_create_right_panel()
  local leaves = get_doc_leaves(core.root_view.root_node)
  if #leaves >= 2 then
    return leaves[#leaves]
  elseif #leaves == 1 then
    return leaves[1]:split("right")
  end
  return core.root_view.root_node:get_primary_node()
end

local function open_in_right_panel(file_path, log_msg)
  local right_node = get_or_create_right_panel()
  local doc = type(file_path) == "string" and core.open_doc(file_path) or file_path
  if not doc then return nil end

  for _, v in ipairs(right_node.views or {}) do
    if v and v.doc == doc then
      right_node.active_view = v
      core.set_active_view(v)
      core.redraw = true
      return v
    end
  end

  local ok_v, view = pcall(DocView, doc)
  if ok_v and view and view.position then
    if right_node.add_view then
      right_node:add_view(view)
    end
    core.set_active_view(view)
    if log_msg then core.log(log_msg) end
    core.redraw = true
    return view
  end
  return nil
end

-- =============================================================================
-- 3. COMANDOS SOBERANOS DO DUMPPOT E PAINÉIS
-- =============================================================================
command.add(nil, {
  ["doxoade:open-pot-in-right-panel"] = function()
    open_in_right_panel(dumppot_file, "📋 Dumppot aberto no painel direito.")
  end,
  ["doxoade:open-init-lua"] = function()
    local init_file = (USERDIR or ".") .. (PATHSEP or "/") .. "init.lua"
    open_in_right_panel(init_file, "⚡ init.lua aberto no painel direito.")
  end,
  ["doxoade:open-workspace-hub"] = function()
    open_in_right_panel(dumppot_file, "📂 Workspace Hub aberto.")
  end,
  ["doxoade:open-pantheon"] = function()
    local init_file = (USERDIR or ".") .. (PATHSEP or "/") .. "init.lua"
    local settings_file = (USERDIR or ".") .. (PATHSEP or "/") .. "user_settings.lua"
    open_in_right_panel(init_file, "⚡ init.lua aberto no Panteão.")
    open_in_right_panel(log_path, "📜 session_log.txt aberto no Panteão.")
    open_in_right_panel(dumppot_file, "📋 Dumppot aberto no Panteão.")
    open_in_right_panel(cheat_sheet_file, "📖 Cheat Sheet aberto no Panteão.")
    open_in_right_panel(settings_file, "⚙️ user_settings.lua aberto no Panteão.") -- ✅ CORRIGIDO
    core.log("🏛️ Panteão Soberano invocado. 5 abas de diagnóstico abertas à direita.")
  end,
  ["doxoade:show-shortcuts-cheat-sheet"] = function()
    open_in_right_panel(cheat_sheet_file, "📖 Cheat Sheet aberto.")
  end,
  ["doxoade:open-log"] = function()
    local f = io.open(log_path, "a")
    if f then f:close() end
    open_in_right_panel(log_path, "📜 Log da sessão aberto.")
  end,
  ["doxoade:open-user-settings"] = function()
    local settings_file = (USERDIR or ".") .. (PATHSEP or "/") .. "user_settings.lua"
    pcall(function()
      local f = io.open(settings_file, "a")
      if f then f:close() end
    end)
    open_in_right_panel(settings_file, "⚙️ user_settings.lua aberto no painel direito.")
  end,
  ["doxoade:find-selection-in-opposite-split"] = function()
    local view = core.active_view
    local doc = view and view.doc
    if not doc or not doc.has_selection or not doc:has_selection() then
      core.log("Selecione um texto para buscar no painel oposto.")
      return
    end
    local l1, c1, l2, c2 = doc:get_selection(true)
    local query = doc:get_text(l1, c1, l2, c2)
    if not query or query == "" then return end
    local leaves = get_doc_leaves(core.root_view.root_node)
    local active_node = core.root_view:get_active_node()
    local target_node = nil
    for _, leaf in ipairs(leaves) do
      if leaf ~= active_node then
        target_node = leaf
        break
      end
    end
    if not target_node or not target_node.active_view or not target_node.active_view.doc then
      core.error("Nenhum documento aberto no painel oposto.")
      return
    end
    local target_doc = target_node.active_view.doc
    local found_line = nil
    for line_idx, line_text in ipairs(target_doc.lines or {}) do
      if line_text:find(query, 1, true) then
        found_line = line_idx
        break
      end
    end
    if found_line then
      core.set_active_view(target_node.active_view)
      target_doc:set_selection(found_line, 1, found_line, 1)
      core.log(string.format("Encontrado na linha %d: '%s'", found_line, query))
      core.redraw = true
    else
      core.log(string.format("Termo '%s' não encontrado no painel oposto.", query))
    end
  end,
  -- ═════════════════════════════════════════════════════════════════
  -- MENU DE OPÇÕES DO DOXNOTE E CONTROLE DE SYNC EM BACKGROUND
  -- ═════════════════════════════════════════════════════════════════
  ["doxoade:shared-hub-menu"] = function()
    local is_active = rawget(_G, "_DOXOADE_NOTE_SYNC_ACTIVE") == true
    local toggle_label = is_active and "🛑 Parar Sincronização em Background" 
                                   or  "⚡ Iniciar Sincronização em Background (Sync Ativa)"
    local options = {
      "1. 📝 Abrir Bloco de Notas (shared_notes.md)",
      "2. " .. toggle_label,
      "3. 📥 Puxar Notas do Host Agora (Pull)",
      "4. 📤 Enviar Notas para o Host Agora (Push)",
    }
    core.command_view:enter("Opções do Bloco de Notas LAN", {
      submit = function(item)
        if item:find("1.") then
          command.perform("doxoade:open-shared-notes")
        elseif item:find("2.") then
          command.perform("doxoade:toggle-note-sync-daemon")
        elseif item:find("3.") then
          command.perform("doxoade:pull-shared-notes")
        elseif item:find("4.") then
          command.perform("doxoade:push-shared-notes")
        end
      end,
      suggest = function(text)
        return common.fuzzy_match(options, text)
      end
    })
  end,

  ["doxoade:toggle-note-sync-daemon"] = function()
    local is_active = rawget(_G, "_DOXOADE_NOTE_SYNC_ACTIVE") == true
    if is_active then
      -- Desliga
      rawset(_G, "_DOXOADE_NOTE_SYNC_ACTIVE", false)
      local pid = rawget(_G, "_DOXOADE_NOTE_SYNC_PID")
      if pid and PLATFORM == "Windows" then
        pcall(system.exec, string.format('taskkill /F /PID %d', pid))
      end
      rawset(_G, "_DOXOADE_NOTE_SYNC_PID", nil)
      core.log("🛑 [NOTE] Sincronização em background desativada.")
    else
      -- Liga
      local py_anchor = (USERDIR or ".") .. (PATHSEP or "/") .. ".doxoade" .. (PATHSEP or "/") .. "python_path.txt"
      local py_exe = "python"
      local finfo = system.get_file_info(py_anchor)
      if finfo and finfo.type == "file" then
        local f = io.open(py_anchor, "r")
        if f then
          local l = f:read("*l") or ""
          f:close()
          if l ~= "" then py_exe = l:gsub("[\r\n]", "") end
        end
      end
      local cmd = string.format('start /b "" "%s" -m doxoade lan-git note --daemon', py_exe)
      pcall(system.exec, cmd)
      rawset(_G, "_DOXOADE_NOTE_SYNC_ACTIVE", true)
      core.log("⚡ [NOTE] Sincronização em background ativada. Status: Sync Ativa.")
    end
    core.redraw = true
  end,

  ["doxoade:pull-shared-notes"] = function()
    core.log("📥 Puxando notas mais recentes do Host...")
    pcall(system.exec, 'doxoade lan-git note --pull')
  end,

  ["doxoade:push-shared-notes"] = function()
    core.log("📤 Enviando notas locais para o Host...")
    pcall(system.exec, 'doxoade lan-git note --push')
  end,
  ["doxoade:open-shared-notes"] = function()
    open_in_right_panel(global_shared_notes, "📝 Bloco de Notas Global aberto no painel direito.")
  end,
  -- mantem os demais comandos existentes...
})
