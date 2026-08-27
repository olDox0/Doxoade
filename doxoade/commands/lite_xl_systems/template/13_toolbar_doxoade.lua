-- doxoade/commands/lite_xl_systems/template/13_toolbar_doxoade.lua
-- =============================================================================
-- 13. DOXOADE STATUS BAR HUD (CONTROLES INTERATIVOS E CLICÁVEIS NO RODAPÉ)
-- =============================================================================
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

    local DIVIDER_COLOR = { 76, 69, 82, 255 }

    -- 1. ⚡ Badge Doxoade
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

    -- 2. 📐 Indent Guide Toggle Dinâmico
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
      2
    )

    -- 3. ⚖️ Check Button com Placar Dinâmico e Blindagem contra nil
    register_status_item(
      "doxoade:check_status",
      StatusView.Item.LEFT,
      function()
        local summary = rawget(_G, "_DOXOADE_AUDIT_SUMMARY")
        local text = "⚖️ Check "
        local col = { 244, 114, 182, 255 } -- Rosa Doxoade

        if summary and type(summary) == "table" then
          local errors_cnt = tonumber(summary.errors) or 0
          local warnings_cnt = tonumber(summary.warnings) or 0
          local total_cnt = tonumber(summary.total) or (errors_cnt + warnings_cnt)

          if total_cnt > 0 then
            if errors_cnt > 0 then
              text = string.format("⚖️ Check: %dE %dW ", errors_cnt, warnings_cnt)
              col = { 255, 60, 60, 255 } -- Vermelho Erro
            else
              text = string.format("⚖️ Check: %dW ", warnings_cnt)
              col = { 234, 179, 8, 255 } -- Âmbar Aviso
            end
          elseif rawget(_G, "_DOXOADE_AUDIT_CHECKED") then
            text = "⚖️ Check: Clean "
            col = { 38, 188, 95, 255 } -- Verde Esmeralda
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
      3
    )

    -- 4. 📝 Note Hub
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
      4
    )

    -- 5. 📋 Dumppot
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
      5
    )

    -- 6. 📜 Logs
    register_status_item(
      "doxoade:log_status",
      StatusView.Item.LEFT,
      function()
        return {
          { 167, 139, 250, 255 }, "📜 Log "
        }
      end,
      function()
        command.perform("doxoade:open-log")
      end,
      6
    )

    rawset(_G, "_DOXOADE_STATUS_HUD_REGISTERED", true)
    core.redraw = true
  end)
end)