-- doxoade/commands/lite_xl_systems/template/08_pot_panel.lua
-- =============================================================================
-- 08. HUB DUMPPOT & SINTAXE MULTILINGUAGEM (```lua, ```python, ```c, ETC.)
-- =============================================================================
local core = require "core"
local DocView = require "core.docview"
local command = require "core.command"

local doxoade_cfg_dir = USERDIR .. PATHSEP .. ".doxoade"
pcall(function() system.mkdir(doxoade_cfg_dir) end)
local dumppot_file = doxoade_cfg_dir .. PATHSEP .. "dumppot.txt"
local cheat_sheet_file = doxoade_cfg_dir .. PATHSEP .. "cheat_sheet.txt"

pcall(function()
  local f = io.open(dumppot_file, "a")
  if f then f:close() end
end)

-- 🎨 SINTAXE MULTILINGUAGEM PARA O DUMPPOT (Code Blocks ```lang ... ```)
pcall(function()
  local syntax = require "core.syntax"
  syntax.add {
    name = "Dumppot Markdown",
    files = { "dumppot%.txt$", "cheat_sheet%.txt$", "%.doxpot$", "%.pot$" },
    comment = "--",
    patterns = {
      -- 1. Sub-sintaxes para blocos cercados por ```
      { pattern = { "```%s*lua", "```" },        type = "string",   syntax = ".lua" },
      { pattern = { "```%s*python", "```" },     type = "string",   syntax = ".py" },
      { pattern = { "```%s*py", "```" },         type = "string",   syntax = ".py" },
      { pattern = { "```%s*c", "```" },          type = "string",   syntax = ".c" },
      { pattern = { "```%s*cpp", "```" },        type = "string",   syntax = ".cpp" },
      { pattern = { "```%s*json", "```" },       type = "string",   syntax = ".json" },
      { pattern = { "```%s*sh", "```" },         type = "string",   syntax = ".sh" },
      { pattern = { "```%s*bash", "```" },       type = "string",   syntax = ".sh" },
      { pattern = { "```%s*zsh", "```" },        type = "string",   syntax = ".sh" },
      { pattern = { "```%s*diff", "```" },       type = "string",   syntax = ".diff" },
      { pattern = { "```%s*patch", "```" },      type = "string",   syntax = ".diff" },
      { pattern = { "```%s*html", "```" },       type = "string",   syntax = ".html" },
      { pattern = { "```%s*css", "```" },        type = "string",   syntax = ".css" },
      { pattern = { "```%s*js", "```" },         type = "string",   syntax = ".js" },
      { pattern = { "```%s*javascript", "```" }, type = "string",   syntax = ".js" },
      { pattern = { "```%s*ts", "```" },         type = "string",   syntax = ".ts" },
      { pattern = { "```%s*typescript", "```" }, type = "string",   syntax = ".ts" },
      { pattern = { "```%s*yaml", "```" },       type = "string",   syntax = ".yaml" },
      { pattern = { "```%s*yml", "```" },        type = "string",   syntax = ".yaml" },
      { pattern = { "```%s*xml", "```" },        type = "string",   syntax = ".xml" },
      { pattern = { "```%s*sql", "```" },        type = "string",   syntax = ".sql" },
      { pattern = { "```%s*rust", "```" },       type = "string",   syntax = ".rs" },
      { pattern = { "```%s*rs", "```" },         type = "string",   syntax = ".rs" },
      { pattern = { "```%s*go", "```" },         type = "string",   syntax = ".go" },
      { pattern = { "```", "```" },              type = "string" }, -- Bloco genérico

      -- 2. Elementos Markdown
      { pattern = "^#+%s.*",                     type = "keyword" },  -- Títulos # H1, ## H2
      { pattern = "`.-`",                        type = "keyword2" }, -- `código inline`
      { pattern = "%*%*.-%*%*",                  type = "keyword" },  -- **negrito**
      { pattern = "%*.-%*",                      type = "operator" }, -- *itálico*
      { pattern = "%[.-%]%b()",                  type = "symbol" },   -- [links](url)
      { pattern = "https?://%S+",                type = "operator" }, -- URLs diretas
      { pattern = "^===+.*===+",                 type = "keyword" },  -- Banners Doxoade
      { pattern = "^%-%-%-+.*",                  type = "comment" },  -- Linhas divisoras ---
    },
    symbols = {}
  }
end)

local function get_or_create_right_panel()
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
  local doc = core.open_doc(file_path)
  for _, v in ipairs(right_node.views) do
    if v.doc == doc then
      right_node.active_view = v
      core.set_active_view(v)
      core.redraw = true
      return v
    end
  end
  local view = DocView(doc)
  right_node:add_view(view)
  core.set_active_view(view)
  if log_msg then core.log(log_msg) end
  core.redraw = true
  return view
end

local CHEAT_SHEET_CONTENT = [[
================================================================================
          📖 GUIA DE ATALHOS RÁPIDOS - LITE XL SOVEREIGN
================================================================================

[ 🎨 VISUAL, CORES E ABAS ]
  Abas com Fundo Sólido   : 16 Paletas automáticas por Projeto Raiz
  #00FF00 / {R,G,B} texto : Fundo do texto preenchido com a cor exata referida
  Linha Amarela (Gutter)  : Indicador de linhas modificadas não salvas

[ 🔍 BUSCA E NAVEGAÇÃO NOTEPAD++ ]
  Ctrl + F          : Abre busca (Highlight em Azul Anil global)
  Ctrl + Alt + F    : Busca seleção na aba oposta (Esquerda ⇄ Direita)
  Enter (no painel) : Pula para a PRÓXIMA ocorrência
  Shift + Enter     : Volta para a ocorrência ANTERIOR
  F3 / Shift + F3   : Navega entre ocorrências mesmo sem a busca aberta
  Ctrl + H          : Localizar e Substituir texto
  Ctrl + G          : Ir para a linha (Go to line)

[ 📋 COPIAR CAMINHOS E NOMES (Botão Direito no Arquivo/Árvore) ]
  Copy Project Relative Path : Ex: doxoade/commands/cmd_lite_xl.py
  Copy Full Absolute Path    : Ex: C:\Users\...\cmd_lite_xl.py
  Copy Filename              : Ex: cmd_lite_xl.py

[ 📂 GESTÃO DE PROJETOS NA ÁRVORE ]
  Botão Direito na Árvore   : Menu contextual (Add / Remove Project Folder)
  Ctrl + Alt + O    : Adicionar qualquer pasta/projeto à árvore lateral
  Ctrl + Alt + R    : Remover projeto da árvore lateral (Menu com busca Fuzzy)
  Ctrl + Alt + U    : Fixar / Desafixar pasta do Lite XL na Árvore
  Ctrl + B          : Ocultar / Exibir Árvore Lateral (Sidebar)
  Ctrl + P          : Fuzzy Finder (Busca arquivos em todos os projetos)

[ ✂️ DIVISÃO DE TELAS E ABAS ]
  Ctrl + Alt + D    : Move o arquivo atual entre os painéis (Esquerda ⇄ Direita)
  Ctrl + Alt + \    : Abre Workspace Hub (Dumppot, Init, Log) na direita
  Ctrl + Alt + P    : Abre dumppot.txt no painel da direita
  Alt + D           : Cria uma nova divisão vazia à direita
  Alt + Shift + D   : Divide a tela na horizontal (baixo)
  Ctrl + W / Alt + W: Fecha a aba / divisão atual
  Ctrl + Tab        : Próxima aba
  Ctrl + Shift + Tab: Aba anterior

[ ⚡ EDIÇÃO RÁPIDA ]
  Ctrl + N          : Novo documento em branco
  Ctrl + S          : Salvar arquivo
  Ctrl + Shift + S  : Salvar todos os arquivos
  Ctrl + D          : Duplicar linha atual
  Ctrl + L          : Deletar linha inteira
  Ctrl + Q          : Comentar/Descomentar linha

[ ⚙️ CONFIGURAÇÃO & LOGS ]
  Ctrl + ,          : Abrir init.lua no painel direito
  Ctrl + Shift + L  : Abrir aba de Logs no painel direito
  F1 / Ctrl+Shift+/ : Abre este Guia em cheat_sheet.txt
================================================================================
]]

command.add(nil, {
  -- Guia de atalhos em arquivo próprio (protege o dumppot)
  ["doxoade:show-shortcuts-cheat-sheet"] = function()
    local doc = core.open_doc(cheat_sheet_file)
    if #doc.lines <= 1 then
      doc:insert(1, 1, CHEAT_SHEET_CONTENT)
      doc:save()
    end
    open_in_right_panel(cheat_sheet_file, "Guia de atalhos aberto na direita.")
  end,

  -- Dumppot permanece livre para rascunhos do desenvolvedor
  ["doxoade:open-pot-in-right-panel"] = function()
    open_in_right_panel(dumppot_file, "Dumppot fixado na direita.")
  end,
  ["doxoade:open-workspace-hub"] = function()
    open_in_right_panel(dumppot_file, "Workspace Hub ativado na direita.")
  end,
  ["doxoade:open-init-lua"] = function()
    open_in_right_panel(USERDIR .. PATHSEP .. "init.lua", "init.lua aberto na direita.")
  end,

  ["doxoade:open-log"] = function()
    local log_path = USERDIR .. PATHSEP .. "session_log.txt"
    -- 🛡️ Garante que o arquivo exista antes de abrir
    local f = io.open(log_path, "a")
    if f then f:close() end
    
    local right_node = get_or_create_right_panel()
    for _, doc in ipairs(core.docs or {}) do
      local dname = (doc.get_name and doc:get_name()) or doc.filename or ""
      if dname == "Log" or dname:find("Log") or (doc.filename and doc.filename:find("Log")) then
        for _, v in ipairs(right_node.views) do
          if v.doc == doc then
            right_node.active_view = v
            core.set_active_view(v)
            core.redraw = true
            return
          end
        end
        local v = DocView(doc)
        right_node:add_view(v)
        core.set_active_view(v)
        core.redraw = true
        return
      end
    end
    command.perform("core:open-log")
  end,

  ["doxoade:open-workspace-hub"] = function()
    open_in_right_panel(USERDIR .. PATHSEP .. "init.lua")
    command.perform("doxoade:open-log")
    open_in_right_panel(dumppot_file, "Workspace Hub ativado na direita.")
    open_in_right_panel(log_path, "📜 Session Log aberto no painel direito.")
  end
})

-- Comandos no DocView
command.add("core.docview", {
  ["doxoade:find-selection-in-opposite-split"] = function()
    local active_view = core.active_view
    if not active_view or not active_view.doc then return end

    local query = nil
    if active_view.doc:has_selection() then
      local l1, c1, l2, c2 = active_view.doc:get_selection(true)
      query = active_view.doc:get_text(l1, c1, l2, c2)
    end

    if not query or #query == 0 then
      core.error("Selecione um texto para buscar no painel oposto.")
      return
    end

    local current_node = core.root_view:get_active_node()
    local target_leaf = nil

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

    for _, leaf in ipairs(get_doc_leaves(core.root_view.root_node)) do
      if leaf ~= current_node then
        target_leaf = leaf
        break
      end
    end

    if target_leaf and target_leaf.active_view and target_leaf.active_view.doc then
      core.set_active_view(target_leaf.active_view)
      local t_doc = target_leaf.active_view.doc
      local line, col = t_doc:get_selection()
      local start_line = line or 1
      local found_line, found_col = nil, nil

      for idx = start_line, #t_doc.lines do
        local s, e = t_doc.lines[idx]:find(query, (idx == start_line and (col or 1) + 1 or 1), true)
        if s then found_line, found_col = idx, s break end
      end

      if not found_line then
        for idx = 1, start_line do
          local s, e = t_doc.lines[idx]:find(query, 1, true)
          if s then found_line, found_col = idx, s break end
        end
      end

      if found_line then
        t_doc:set_selection(found_line, found_col, found_line, found_col + #query)
        target_leaf.active_view:scroll_to_line(found_line, true)
        core.log("Encontrado na linha %d: '%s'", found_line, query)
      else
        core.log("Termo '%s' não encontrado no painel oposto.", query)
        -- core.error("Termo '%s' não encontrado no painel oposto.", query)
      end
      core.redraw = true
    else
      core.error("Abra um documento no painel oposto para pesquisar.")
    end
  end
})
