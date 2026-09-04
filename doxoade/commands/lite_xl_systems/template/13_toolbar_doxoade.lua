-- doxoade/commands/lite_xl_systems/template/13_toolbar_doxoade.lua
--[[ ⚡ DOXOADE STATUS BAR HUD & SOVEREIGN BADGES (V2.0 UX Calibrada)
  Exibe badges dinâmicos de indentação, auditoria Ma'at, atalhos rápidos e contador de seleção. ]]

local core = require "core"
local config = require "core.config"
local style = require "core.style"
local command = require "core.command"
local StatusView = require "core.statusview"

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

core.add_thread(function()
  coroutine.yield(0.02)
  pcall(function()
    if rawget(_G, "_DOXOADE_STATUS_HUD_REGISTERED") then return end
    rawset(_G, "_DOXOADE_STATUS_HUD_REGISTERED", true)

    local DIVIDER_COLOR = style.divider or { 76, 69, 82, 255 }
    local ACCENT_GREEN = style.accent or { 38, 188, 95, 255 }

    -- 1. Badge Doxoade
    register_status_item(
      "doxoade:badge",
      StatusView.Item.LEFT,
      function()
        return {
          ACCENT_GREEN, "⚡ DOXOADE ",
          DIVIDER_COLOR, "| "
        }
      end,
      function()
        command.perform("doxoade:open-pantheon")
      end,
      1
    )

    -- 2. Contador Dinâmico de Seleção (Linhas / Caracteres)
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

    -- 3. Indicador de Indentação Ativa
    register_status_item(
      "doxoade:indent_status",
      StatusView.Item.LEFT,
      function()
        local is_on = (config.draw_indent_guides ~= false)
        local doc = core.active_view and core.active_view.doc
        local indent_size = config.indent_size or 4
        if doc then
          local fn = tostring(doc.filename or ""):lower()
          if fn:find("%.lua$") then indent_size = 2 end
        end
        local text = is_on and string.format("📐 %dx%d (ON) ", indent_size, indent_size) or "📐 Indent: OFF "
        local col = is_on and ACCENT_GREEN or { 130, 130, 130, 255 }
        return {
          col, text,
          DIVIDER_COLOR, "| "
        }
      end,
      function()
        config.draw_indent_guides = not config.draw_indent_guides
        core.redraw = true
      end,
      3
    )

    -- 4. Status de Auditoria Ma'at / Check
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
            col = ACCENT_GREEN
          end
        end
        return {
          col, text,
          DIVIDER_COLOR, "| "
        }
      end,
      function()
        command.perform("doxoade:diagnose-live")
      end,
      4
    )

    -- 5. Scratchpad Dumppot
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
  end)
end)
