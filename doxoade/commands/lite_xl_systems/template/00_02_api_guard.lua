-- doxoade/commands/lite_xl_systems/template/00_02_api_guard.lua
-- =============================================================================
-- DOXOADE API GUARD — ACTIVE DEFENDER (Estágio 00.2: Defesa Ativa de Patches)
-- =============================================================================

local core = rawget(_G, "core")
local probe = rawget(_G, "_DOXOADE_API_PROBE")

local API = {
  violations = {},
  disabled_features = {},
  patched_symbols = {},
}

function API.has(symbol_path)
  if probe and probe.results and probe.results[symbol_path] then
    return probe.results[symbol_path].status == "present"
  end
  return true
end

function API.type_of(symbol_path)
  if probe and probe.results and probe.results[symbol_path] then
    return probe.results[symbol_path].real_type
  end
  return "unknown"
end

--- Bloqueia monkey-patch em métodos nil para evitar engolir eventos silenciosamente
function API.patch(spec)
  if type(spec) ~= "table" then return false end

  local target_table = spec.target
  local method_name = spec.method
  local feature_name = spec.feature or spec.id or "unknown"

  if not target_table or type(target_table) ~= "table" then
    table.insert(API.violations, {
      type = "TARGET_NIL",
      id = spec.id,
      feature = feature_name,
      message = string.format("Alvo do patch '%s' é nil.", tostring(spec.id))
    })
    if spec.fallback then pcall(spec.fallback) end
    return false
  end

  local original_method = target_table[method_name]

  if original_method == nil and not spec.allow_nil_original then
    table.insert(API.violations, {
      type = "ORIGINAL_METHOD_NIL",
      id = spec.id,
      feature = feature_name,
      message = string.format("Método original '%s' é nil (API inexistente/deprecada). Patch abortado com segurança.", tostring(spec.id))
    })
    if core and core.log then
      core.log(string.format("[API GUARD] ⚠ Patch ignorado para evitar falha silenciosa: %s", tostring(spec.id)))
    end
    if spec.fallback then pcall(spec.fallback) end
    return false
  end

  target_table[method_name] = function(self, ...)
    return spec.wrapper(original_method, self, ...)
  end

  table.insert(API.patched_symbols, spec.id)
  return true
end

rawset(_G, "DOXOADE_API", API)
rawset(_G, "_DOXOADE_API_STATE", {
  probe = probe,
  api = API,
})
