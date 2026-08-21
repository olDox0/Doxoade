-- doxoade/commands/lite_xl_systems/template/template/07_keymaps_and_help.lua
-- =============================================================================
-- 07. GUIA DE ATALHOS & KEYMAP CONSOLIDADO
-- =============================================================================
command.add(nil, {
  ["doxoade:show-shortcuts-cheat-sheet"] = function()
    local doc = core.open_doc()
    doc.filename = "Guia_de_Atalhos_LiteXL.txt"
    doc:insert(1, 1, [[
================================================================================
          📖 GUIA DE ATALHOS RÁPIDOS - LITE XL SOVEREIGN
================================================================================

[ 🎨 VISUAL, CORES E ABAS ]
  Abas com Fundo Sólido   : Cor automática e preenchimento total por Projeto
  #00FF00 / {R,G,B} texto : Fundo do texto preenchido com a cor exata referida
  Linha Amarela           : Indicador de linhas modificadas e não salvas

[ 🔍 BUSCA E NAVEGAÇÃO NOTEPAD++ ]
  Ctrl + F          : Abre busca (Highlight em Azul Anil persistente e global)
  Enter (no painel) : Pula para a PRÓXIMA ocorrência
  Shift + Enter     : Volta para a ocorrência ANTERIOR
  F3 / Shift + F3   : Navega entre ocorrências mesmo sem a busca aberta
  Ctrl + H          : Localizar e Substituir texto
  Ctrl + G          : Ir para a linha (Go to line)

[ 📂 GESTÃO DE PROJETOS NA ÁRVORE ]
  Ctrl + Alt + O    : Adicionar qualquer pasta/projeto à árvore lateral
  Ctrl + Alt + R    : Remover projeto da árvore lateral (Menu com busca Fuzzy)
  Ctrl + P          : Fuzzy Finder (Busca arquivos em todos os projetos)

[ ✂️ DIVISÃO DE TELAS E ABAS ]
  Ctrl + Alt + D    : Move o arquivo atual entre os painéis (Esquerda ⇄ Direita)
  Ctrl + Alt + \    : Abre Hub de Ferramentas (Dumppot, Init, Log) na direita
  Ctrl + Alt + P    : Fixa dumppot.txt no painel da direita
  Alt + D           : Cria uma nova divisão vazia à direita
  Alt + Shift + D   : Divide a tela na horizontal (baixo)
  Ctrl + Alt + Left : Foca no painel da esquerda
  Ctrl + Alt + Right: Foca no painel da direita
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
  Ctrl + ,          : Abrir init.lua para edição instantânea
  Ctrl + Alt + U    : Colocar/Remover a pasta do Lite XL na Árvore
  Ctrl + Shift + L  : Abrir aba de Logs (copiável e com busca)
  F1 / Ctrl+Shift+/ : Abrir este Guia de Atalhos
================================================================================
]])
    core.root_view:open_doc(doc)
  end
})

keymap.add {
  -- Criação & Arquivos
  ["ctrl+n"]           = "doxoade:new-doc",
  ["ctrl+o"]           = "core:open-file",
  ["ctrl+s"]           = "doc:save",
  ["ctrl+shift+s"]     = "doc:save-all",

  -- Config do Editor, Logs & Dumppot
  ["ctrl+,"]           = "doxoade:open-init-lua",
  ["ctrl+alt+u"]       = "doxoade:toggle-litexl-in-tree",
  ["ctrl+shift+l"]     = "doxoade:open-log",
  ["ctrl+f2"]          = "doxoade:open-log",
  ["ctrl+alt+p"]       = "doxoade:open-pot-in-right-panel",
  ["ctrl+alt+\\"]      = "doxoade:open-workspace-hub",

  -- Ajuda e Cheat Sheet
  ["f1"]               = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+shift+?"]     = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+shift+/"]     = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+/"]           = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+alt+/"]       = "doxoade:show-shortcuts-cheat-sheet",

  -- Busca e Navegação Notepad++
  ["ctrl+f"]           = "find-replace:find",
  ["f3"]               = "find-replace:repeat-find",
  ["shift+f3"]         = "find-replace:previous-find",
  ["ctrl+h"]           = "find-replace:replace",
  ["ctrl+g"]           = "doc:go-to-line",

  -- Divisões e Abas (Bidirecional)
  ["ctrl+alt+d"]       = "root:move-tab-to-opposite-panel",
  ["alt+d"]            = "root:split-right",
  ["alt+shift+d"]      = "root:split-down",
  ["ctrl+alt+left"]    = "root:switch-to-left",
  ["ctrl+alt+right"]   = "root:switch-to-right",
  ["alt+w"]            = "root:close",
  ["ctrl+w"]           = "root:close",
  ["ctrl+tab"]         = "root:switch-to-next-tab",
  ["ctrl+shift+tab"]   = "root:switch-to-previous-tab",

  -- Edição Rápida
  ["ctrl+d"]           = "doc:duplicate-lines",
  ["ctrl+l"]           = "doc:delete-lines",
  ["ctrl+q"]           = "doc:toggle-line-comments",

  -- Projetos e Pastas na Treeview
  ["ctrl+alt+o"]       = "treeview:add-project-folder",
  ["ctrl+alt+r"]       = "treeview:remove-project-folder",
}