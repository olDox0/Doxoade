-- doxoade/commands/lite_xl_systems/template/07_keymaps_and_help.lua
-- =============================================================================
-- 07. GUIA DE ATALHOS & LOCALIZAR / SUBSTITUIR INTERATIVO (NOTEPAD++ PARITY)
-- =============================================================================

local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"

-- =====================================================
-- FALLBACK: NOVO DOCUMENTO
-- =====================================================
command.add(nil, {
  ["doxoade:new-doc"] = function()
    local doc = core.open_doc()
    core.root_view:open_doc(doc)
    core.redraw = true
  end,
})

-- =====================================================
-- 📖 1. GUIA DE ATALHOS COMPLETO
-- =====================================================
command.add(nil, {
  ["doxoade:show-shortcuts-cheat-sheet"] = function()
    local doc = core.open_doc()
    doc.filename = "Guia_de_Atalhos_LiteXL.txt"

    doc:insert(1, 1, [[
================================================================================
      📖 GUIA DE ATALHOS RÁPIDOS - LITE XL SOVEREIGN
================================================================================

[ 🎨 VISUAL, CORES E ABAS ]
  Abas com Fundo Sólido   : Cores automáticas por Projeto Raiz
  Linha Amarela (Aba)     : Indicador de arquivo modificado e não salvo
  Linhas de Indentação    : Grade 4x4 (Python) e 2x2 (Lua) contínua
  Ctrl + Alt + I          : Ligar / Desligar Guias de Indentação

[ 🔍 BUSCA E NAVEGAÇÃO NOTEPAD++ ]
  Ctrl + F          : Localizar texto (Highlight Azul persistente)
  Ctrl + H          : Localizar e Substituir interativo em 2 passos
  F3 / Shift + F3   : Próxima / Anterior ocorrência da busca
  Ctrl + G          : Ir para a linha (Go to line)
  F2 / Shift + F2   : Próximo / Anterior achado de auditoria Ma'at

[ 📋 COPIAR NOMES & CAMINHOS ]
  Botão Direito na Aba : Menu flutuante (Copy Name, Proj. Address, Total Address)
  Ctrl + Alt + C       : Hub interativo de cópia de caminhos
  Ctrl + Shift + C     : Copiar endereço relativo no projeto
  Ctrl + Alt + E       : Revelar arquivo no Windows Explorer

[ ✂️ DIVISÃO DE TELAS E ABAS ]
  Ctrl + Alt + D    : Mover aba entre painéis (Esquerda ⇄ Direita)
  Ctrl + Alt + P    : Fixar Dumppot na direita
  Alt + D           : Dividir tela à direita (Split Right)
  Alt + Shift + D   : Dividir tela abaixo (Split Down)
  Ctrl + W / Alt + W: Fechar aba / divisão atual
  Ctrl + Tab        : Próxima aba
  Ctrl + Shift + Tab: Aba anterior

[ ⚡ EDIÇÃO RÁPIDA ]
  Ctrl + N          : Novo documento em branco
  Ctrl + S          : Salvar arquivo
  Ctrl + Shift + S  : Salvar todos os arquivos
  Ctrl + D          : Duplicar linha atual
  Ctrl + L          : Deletar linha inteira
  Ctrl + Q          : Comentar/Descomentar linha

[ 📝 NOTAS, TAREFAS & AUDITORIA ]
  Ctrl + Alt + N       : Criar arquivo interativo
  Ctrl + Alt + Shift+N : Hub do Doxoade Note & Agenda
  Ctrl + Alt + A       : Abrir Agenda de Tarefas
  Ctrl + Alt + K       : Disparar auditoria Ma'at Check no arquivo ativo
  Ctrl + Alt + Shift+K : Diagnóstico live
  F1 / Ctrl+Shift+/ / Ctrl+Alt+/ : Abrir este Guia de Atalhos

================================================================================
]])

    core.root_view:open_doc(doc)
  end
})

-- =====================================================
-- 🔄 2. LOCALIZAR E SUBSTITUIR SEGURO EM 2 PASSOS
-- =====================================================
command.add("core.docview", {
  ["doxoade:interactive-find-replace"] = function()
    local doc = core.active_view and core.active_view.doc
    if not doc then return end

    local default_find = ""

    if doc:has_selection() then
      local l1, c1, l2, c2 = doc:get_selection(true)
      if l1 == l2 then
        default_find = doc:get_text(l1, c1, l2, c2)
      end
    end

    core.command_view:enter("1/2 Localizar texto para substituir", {
      text = default_find,
      submit = function(find_query)
        if not find_query or find_query == "" then return end

        if find_query:find("\n") then
          core.error("Busca com quebra de linha não suportada neste modo.")
          return
        end

        local prompt_label = string.format("2/2 Substituir '%s' por:", find_query)

        core.command_view:enter(prompt_label, {
          submit = function(replace_query)
            replace_query = replace_query or ""

            if replace_query:find("\n") then
              core.error("Substituição com quebra de linha não suportada neste modo.")
              return
            end

            local count = 0
            local escaped_pat = find_query:gsub(
              "[%(%)%.%%%+%-%*%?%[%]%^%$]",
              "%%%1"
            )

            for line_idx = 1, #doc.lines do
              local line_text = doc.lines[line_idx]
              local s_idx = 1
              local line_hits = 0

              while true do
                local s, e = line_text:find(find_query, s_idx, true)
                if not s then break end

                line_hits = line_hits + 1
                s_idx = e + 1
              end

              if line_hits > 0 then
                local new_text = line_text:gsub(
                  escaped_pat,
                  function()
                    return replace_query
                  end
                )

                -- Usa API nativa do Doc para preservar melhor undo/dirty.
                doc:remove(line_idx, 1, line_idx, #line_text + 1)

                if new_text ~= "" then
                  doc:insert(line_idx, 1, new_text)
                end

                count = count + line_hits
              end
            end

            if count > 0 then
              core.log(string.format(
                "✔ Substituídas %d ocorrências de '%s' por '%s'",
                count,
                find_query,
                replace_query
              ))
              core.redraw = true
            else
              core.log(string.format(
                "Nenhuma ocorrência de '%s' encontrada.",
                find_query
              ))
            end
          end
        })
      end
    })
  end
})

-- =====================================================
-- ⌨️ 3. MAPEAMENTO GLOBAL CANÔNICO NOTEPAD++ / DOXOADE
-- =====================================================
keymap.add {
  -- Painéis, abas e navegação
  ["alt+d"] = "root:split-right",
  ["alt+shift+d"] = "root:split-down",
  ["ctrl+alt+d"] = "root:move-tab-to-opposite-panel",
  ["ctrl+w"] = "root:close",
  ["alt+w"] = "root:close",
  ["ctrl+tab"] = "root:switch-to-next-tab",
  ["ctrl+shift+tab"] = "root:switch-to-previous-tab",

  -- Opcional: somente se esses comandos existirem na sua versão do Lite XL.
  ["ctrl+alt+left"] = "root:switch-to-left",
  ["ctrl+alt+right"] = "root:switch-to-right",

  -- Sistema Doxoade
  ["ctrl+,"] = "doxoade:open-init-lua",
  ["ctrl+alt+\\"] = "doxoade:open-workspace-hub",
  ["ctrl+alt+u"] = "doxoade:toggle-litexl-in-tree",
  ["ctrl+alt+p"] = "doxoade:open-pot-in-right-panel",
  ["ctrl+shift+l"] = "doxoade:open-log",
  ["ctrl+f2"] = "doxoade:open-log",

  -- Cheat sheet
  ["f1"] = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+shift+/"] = "doxoade:show-shortcuts-cheat-sheet",
  ["ctrl+alt+/"] = "doxoade:show-shortcuts-cheat-sheet",

  -- Notas, agenda e auditoria
  ["ctrl+alt+n"] = "doxoade:create-file-interactive",
  ["ctrl+alt+shift+n"] = "doxoade:note-hub-menu",
  ["ctrl+alt+a"] = "doxoade:open-agenda-view",
  ["ctrl+alt+i"] = "doxoade:toggle-indent-guides",
  ["ctrl+alt+k"] = "doxoade:trigger-active-check",
  ["ctrl+alt+shift+k"] = "doxoade:diagnose-live",
  ["f2"] = "doxoade:next-audit-incident",
  ["shift+f2"] = "doxoade:prev-audit-incident",

  -- Opcional: atalho alternativo para Note Hub.
  -- ["ctrl+alt+m"] = "doxoade:note-hub-menu",

  -- Caminhos / Explorer
  ["ctrl+alt+c"] = "doxoade:copy-path-menu",
  ["ctrl+shift+c"] = "doxoade:tab-copy-relative-path",
  --["ctrl+alt+shift+c"] = "doxoade:tab-copy-full-path",
  ["ctrl+alt+e"] = "doxoade:tab-open-in-explorer",

  -- Projetos / Treeview
  ["ctrl+alt+o"] = "treeview:add-project-folder",
  ["ctrl+alt+r"] = "treeview:remove-project-folder",

  -- Busca e navegação Notepad++
  ["ctrl+f"] = "find-replace:find",
  ["ctrl+h"] = "doxoade:interactive-find-replace",
  ["f3"] = "find-replace:repeat-find",
  ["shift+f3"] = "find-replace:previous-find",
  ["ctrl+g"] = "doc:go-to-line",

  -- Opcional: se o auditor canônico exigir Ctrl+H nativo, use:
  ["ctrl+h"] = "find-replace:replace",
  ["ctrl+alt+h"] = "doxoade:interactive-find-replace",

  -- Edição rápida
  ["ctrl+n"] = "doxoade:new-doc",
  ["ctrl+o"] = "core:open-file",
  ["ctrl+s"] = "doc:save",
  ["ctrl+shift+s"] = "doc:save-all",
  ["ctrl+d"] = "doc:duplicate-lines",
  ["ctrl+l"] = "doc:delete-lines",
  ["ctrl+q"] = "doc:toggle-line-comments",

  -- Opcional: somente se o comando existir.
  ["ctrl+alt+f"] = "doxoade:find-selection-in-opposite-split",
}
