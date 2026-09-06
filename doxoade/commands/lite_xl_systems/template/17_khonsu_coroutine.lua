-- doxoade/commands/lite_xl_systems/template/17_khonsu_coroutine.lua
--[[
  🌙 KHONSU ASYNC & TIME-SLICING WORKER (V1.2 Resiliente)
  - Time-Slicing: Fatiamento de tarefas com orçamento máximo de 1.5ms por tick.
  - Job Generation Guard: Rastreamento atômico em active_jobs para cancelar tarefas obsoletas.
  - Debounce: Execução diferida após cessar digitação ou scroll.
  - Throttle: Limitação de taxa de disparo para I/O e telemetria.
]]
local core = require "core"
local config = require "core.config"

if config.doxoade_khonsu == false then
  pcall(function()
    core.log("🌙 [KHONSU] Desativado via config.doxoade_khonsu = false.")
  end)
  return 
end

local Khonsu = {
  active_jobs = {},
  job_generations = {},
  debounce_timers = {},
  throttle_timers = {},
  default_budget_ms = 1.5,
}

rawset(_G, "Khonsu", Khonsu)

-- =============================================================================
-- 1. DEBOUNCE (Adia execução até cessar a atividade)
-- =============================================================================
function Khonsu.debounce(id, delay_sec, action_fn)
  Khonsu.debounce_timers[id] = {
    target_time = os.clock() + (delay_sec or 0.08),
    action = action_fn
  }
end

-- =============================================================================
-- 2. THROTTLE (Garante no máximo 1 execução por intervalo)
-- =============================================================================
function Khonsu.throttle(id, interval_sec, action_fn)
  local now = os.clock()
  local last = Khonsu.throttle_timers[id] or 0
  if now - last >= (interval_sec or 0.25) then
    Khonsu.throttle_timers[id] = now
    pcall(action_fn)
  end
end

-- =============================================================================
-- 3. TIME-SLICING WORKER COM JOB GENERATION GUARD
-- =============================================================================
function Khonsu.run_sliced_task(job_id, items_list, process_item_fn, on_complete_fn, budget_ms)
  if not items_list or #items_list == 0 then
    if on_complete_fn then pcall(on_complete_fn) end
    return
  end

  local max_ms = budget_ms or Khonsu.default_budget_ms
  local gen = (Khonsu.job_generations[job_id] or 0) + 1
  Khonsu.job_generations[job_id] = gen
  Khonsu.active_jobs[job_id] = true

  core.add_thread(function()
    local idx = 1
    local total = #items_list

    while idx <= total do
      -- Se um novo job com o mesmo ID foi disparado, cancela a execução obsoleta
      if Khonsu.job_generations[job_id] ~= gen then
        return
      end

      local t0 = os.clock()
      while idx <= total do
        local item = items_list[idx]
        pcall(process_item_fn, item, idx, total)
        idx = idx + 1

        local elapsed_ms = (os.clock() - t0) * 1000
        if elapsed_ms >= max_ms then
          coroutine.yield()
          break
        end
      end
    end

    if Khonsu.job_generations[job_id] == gen then
      Khonsu.active_jobs[job_id] = nil
      if on_complete_fn then
        pcall(on_complete_fn)
      end
    end
  end)
end

-- =============================================================================
-- 4. EVENT LOOP SENTINEL (Processa Debounces Registrados a 50 Hz)
-- =============================================================================
if core.add_thread then
  core.add_thread(function()
    while true do
      coroutine.yield(0.02)
      local now = os.clock()
      for id, timer in pairs(Khonsu.debounce_timers) do
        if now >= timer.target_time then
          local fn = timer.action
          Khonsu.debounce_timers[id] = nil
          if fn then pcall(fn) end
        end
      end
    end
  end)
end

if core.log then
  core.log("🌙 [KHONSU] Motor de Time-Slicing e Debounce Ativado.")
end

-- =============================================================================
-- 5. SYNTAX SENTINEL (Auditor de Integridade Estrutural)
-- =============================================================================
Khonsu.syntax_sentinel = {
  enabled = true,
  validated_count = 0,
  corrupted_count = 0,
}

function Khonsu.validate_syntax_integrity(syn)
  if not Khonsu.syntax_sentinel.enabled then return true end
  if not syn or type(syn.patterns) ~= "table" then return false end

  for idx, p in ipairs(syn.patterns) do
    if type(p) ~= "table" then
      Khonsu.syntax_sentinel.corrupted_count = Khonsu.syntax_sentinel.corrupted_count + 1
      if core and core.log then
        core.log(string.format(
          "🌙 [KHONSU SENTINEL] Pattern #%d inválido (tipo: %s) em syntax '%s'",
          idx, type(p), tostring(syn.name or "unknown")))
      end
      return false
    end
    if p.pattern == nil then
      Khonsu.syntax_sentinel.corrupted_count = Khonsu.syntax_sentinel.corrupted_count + 1
      if core and core.log then
        core.log(string.format(
          "🌙 [KHONSU SENTINEL] Pattern #%d sem campo 'pattern' em syntax '%s'",
          idx, tostring(syn.name or "unknown")))
      end
      return false
    end
    if type(p.pattern) == "table" then
      if not p.pattern[1] or not p.pattern[2] then
        Khonsu.syntax_sentinel.corrupted_count = Khonsu.syntax_sentinel.corrupted_count + 1
        if core and core.log then
          core.log(string.format(
            "🌙 [KHONSU SENTINEL] Pattern #%d com range incompleto em syntax '%s'",
            idx, tostring(syn.name or "unknown")))
        end
        return false
      end
      if type(p.pattern[1]) ~= "string" or type(p.pattern[2]) ~= "string" then
        Khonsu.syntax_sentinel.corrupted_count = Khonsu.syntax_sentinel.corrupted_count + 1
        if core and core.log then
          core.log(string.format(
            "🌙 [KHONSU SENTINEL] Pattern #%d com range não-string em syntax '%s'",
            idx, tostring(syn.name or "unknown")))
        end
        return false
      end
    elseif type(p.pattern) ~= "string" then
      Khonsu.syntax_sentinel.corrupted_count = Khonsu.syntax_sentinel.corrupted_count + 1
      if core and core.log then
        core.log(string.format(
          "🌙 [KHONSU SENTINEL] Pattern #%d com tipo inesperado (%s) em syntax '%s'",
          idx, type(p.pattern), tostring(syn.name or "unknown")))
      end
      return false
    end
  end
  Khonsu.syntax_sentinel.validated_count = Khonsu.syntax_sentinel.validated_count + 1
  return true
end


if core and core.add_thread then
  core.add_thread(function()
    coroutine.yield(2.0)
    local syntax_mod = rawget(_G, "syntax") or (pcall(require, "core.syntax") and require("core.syntax") or nil)
    if syntax_mod and syntax_mod.items then
      local total = #syntax_mod.items
      local valid = 0
      local invalid = 0
      for _, syn in ipairs(syntax_mod.items) do
        if Khonsu.validate_syntax_integrity(syn) then
          valid = valid + 1
        else
          invalid = invalid + 1
        end
      end
      if core and core.log then
        core.log(string.format(
          "🌙 [KHONSU SENTINEL] Validação de syntax: %d/%d íntegras, %d corrompidas",
          valid, total, invalid))
      end
    end
  end)
end
