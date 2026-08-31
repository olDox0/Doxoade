-- doxoade/commands/lite_xl_systems/template/13_toolbar_doxoade.lua
--[[ Barra de Status e HUD Soberano do Doxoade.
     Exibe badges de indentação, auditoria Ma'at, atalhos rápidos e contador dinâmico de seleção. ]]
local core = require "core"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local StatusView = require "core.statusview"

-- 🛠️ Registrador Universal de Itens no StatusView
local function register_status_item(name, alignment, get_item_fn, action_fn, position)
  if not core.status_view or not core.status_view.add_item then return end
  local ok = pcall(function()
    core.status_view:add_item({
      name = name,
      predicate = function() return true end,
      alignment = alignment or StatusView.Item.LEFT,
      get_item = get_item_fn,
      command = action_fn,
      position = position or 10
    })
  end)
  if not ok then
    pcall(function()
      core.status_view:add_item(
        function() return true end,
        name,
        alignment or StatusView.Item.LEFT,
        get_item_fn,
        action_fn,
        position or 10
      )
    end)
  end
end

-- ═══════════════════════════════════════════════════════════
-- REGISTRO DOS ITENS DO HUD NO RODAPÉ
-- =============================================================
core.add_thread(function()
  coroutine.yield(0.02)
  pcall(function()
    if rawget(_G, "_DOXOADE_STATUS_HUD_REGISTERED") then return end
    rawset(_G, "_DOXOADE_STATUS_HUD_REGISTERED", true)
    local DIVIDER_COLOR = { 76, 69, 82, 255 }

    -- 1. BADGE DOXOADE
    register_status_item(
      "doxoade:badge",
      StatusView.Item.LEFT,
      function()
        return {
          { 38, 188, 95, 255 }, "⚡ DOXOADE ",
          DIVIDER_COLOR, "| "
        }
      end,
      function()
        command.perform("doxoade:copy-path-menu")
      end,
      1
    )

    -- 2. CONTADOR DINÂMICO DE SELEÇÃO (LINHAS / CARACTERES)
    register_status_item(
      "doxoade:selection_counter",
      StatusView.Item.LEFT,
      function()
        local view = core.active_view
        local doc = view and view.doc
        if doc and doc.has_selection and doc:has_selection() then
          local l1, c1, l2, c2 = doc:get_selection(true)
          local line_count = math.abs(l2 - l1) + 1
          local text
          if line_count > 1 then
            text = string.format("📊 Sel: %d lin ", line_count)
          else
            local char_count = math.abs(c2 - c1)
            text = string.format("📊 Sel: %d car ", char_count)
          end
          return {
            { 56, 189, 248, 255 }, text,
            DIVIDER_COLOR, "| "
          }
        end
        return {}
      end,
      nil,
      2
    )

    -- 3. STATUS DA INDENTAÇÃO
    register_status_item(
      "doxoade:indent_status",
      StatusView.Item.LEFT,
      function()
        local is_on = (config.draw_indent_guides ~= false)
        local doc = core.active_view and core.active_view.doc
        local indent_size = 4
        if doc then
          local fn = tostring(doc.filename or ""):lower()
          if fn:find("%.lua$") then indent_size = 2 end
        end
        local text = is_on and string.format("📐 Indent: %dx%d (ON) ", indent_size, indent_size) or "📐 Indent: OFF "
        local col = is_on and { 38, 188, 95, 255 } or { 130, 130, 130, 255 }
        return {
          col, text,
          DIVIDER_COLOR, "| "
        }
      end,
      function()
        command.perform("doxoade:toggle-indent-guides")
      end,
      3
    )

    -- 4. STATUS DO AUDIT MA'AT / CHECK
    register_status_item(
      "doxoade:check_status",
      StatusView.Item.LEFT,
      function()
        local summary = rawget(_G, "_DOXOADE_AUDIT_SUMMARY")
        local text = "⚖️ Check "
        local col = { 244, 114, 182, 255 } 
        if summary and type(summary) == "table" then
          local errors_cnt = tonumber(summary.errors) or 0
          local warnings_cnt = tonumber(summary.warnings) or 0
          local total_cnt = tonumber(summary.total) or (errors_cnt + warnings_cnt)
          if total_cnt > 0 then
            if errors_cnt > 0 then
              text = string.format("⚖️ Check: %dE %dW ", errors_cnt, warnings_cnt)
              col = { 255, 60, 60, 255 } 
            else
              text = string.format("⚖️ Check: %dW ", warnings_cnt)
              col = { 234, 179, 8, 255 } 
            end
          elseif rawget(_G, "_DOXOADE_AUDIT_CHECKED") then
            text = "⚖️ Check: Clean "
            col = { 38, 188, 95, 255 } 
          end
        end
        return {
          col, text,
          DIVIDER_COLOR, "| "
        }
      end,
      function()
        local summary = rawget(_G, "_DOXOADE_AUDIT_SUMMARY")
        local total_cnt = summary and (tonumber(summary.total) or (tonumber(summary.errors) or 0) + (tonumber(summary.warnings) or 0)) or 0
        if total_cnt > 0 then
          command.perform("doxoade:next-audit-incident")
        else
          command.perform("doxoade:trigger-active-check")
        end
      end,
      4
    )

    -- 5. ATALHOS RÁPIDOS DE NOTE & POT
    register_status_item(
      "doxoade:note_status",
      StatusView.Item.LEFT,
      function()
        return {
          { 56, 189, 248, 255 }, "📝 Note ",
          DIVIDER_COLOR, "| "
        }
      end,
      function()
        command.perform("doxoade:note-hub-menu")
      end,
      5
    )
    register_status_item(
      "doxoade:dumppot_status",
      StatusView.Item.LEFT,
      function()
        return {
          { 251, 191, 36, 255 }, "📋 Pot ",
          DIVIDER_COLOR, "| "
        }
      end,
      function()
        command.perform("doxoade:open-pot-in-right-panel")
      end,
      6
    )
  end)
end)
