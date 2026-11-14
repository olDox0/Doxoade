-- doxoade/commands/lite_xl_systems/template/30_find_replace_pro.lua
local core = require "core"
local command = require "core.command"
local keymap = require "core.keymap"

command.add("core.docview", {
  ["doxoade:interactive-find-replace"] = function()
    local doc = core.active_view and core.active_view.doc
    if not doc then return end
    local default_find = ""
    if doc.has_selection and doc:has_selection() then
      local l1,c1,l2,c2 = doc:get_selection(true)
      if l1 == l2 then default_find = doc:get_text(l1,c1,l2,c2) end
    end
    core.command_view:enter("1/2 Localizar (Ctrl+H Pro):", {
      text = default_find,
      submit = function(find_text)
        if not find_text or find_text == "" then return end
        if find_text:find("\n") then core.error("Busca multilinha não suportada."); return end
        local count = 0
        for i = 1, #doc.lines do
          local s = 1
          while true do
            local a,b = doc.lines[i]:find(find_text, s, true)
            if not a then break end
            count = count + 1; s = b + 1
          end
        end
        core.command_view:enter(string.format("2/2 Substituir '%s' (%d ocorrência(s)) por:", find_text, count), {
          submit = function(replace_text)
            replace_text = replace_text or ""
            local replaced = 0
            for i = #doc.lines, 1, -1 do
              local line = doc.lines[i]
              local pos, s = {}, 1
              while true do
                local a,b = line:find(find_text, s, true)
                if not a then break end
                table.insert(pos, {a,b}); s = b + 1
              end
              for j = #pos, 1, -1 do
                local a,b = pos[j][1], pos[j][2]
                doc:remove(i, a, i, b+1)
                if #replace_text > 0 then doc:insert(i, a, replace_text) end
                replaced = replaced + 1
              end
            end
            if replaced > 0 then
              core.log(string.format("✔ [CTRL+H] %d substituição(ões). Ctrl+Z desfaz passo a passo.", replaced))
              core.redraw = true
            else
              core.log("Nenhuma ocorrência encontrada.")
            end
          end
        })
      end
    })
  end
})
keymap.add({ ["ctrl+h"] = "doxoade:interactive-find-replace" }, true)
if core.log then core.log("🔁 [CTRL+H Pro] Find/Replace com undo nativo carregado.") end
