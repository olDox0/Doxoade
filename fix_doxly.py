#!/usr/bin/env python3
"""
fix_doxly.py — Aplica as 3 correções pendentes SEM usar `mody patch`.
Usa âncoras de string únicas + idempotência (seguro para re-rodar).

Execute da raiz do projeto:
    python fix_doxly.py
"""
import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
errors: list = []

def _get(rel: str) -> Path | None:
    p = ROOT / rel
    if not p.exists():
        errors.append(f"NOT FOUND: {p}")
        return None
    return p

def _backup(p: Path) -> None:
    b = p.with_suffix(p.suffix + ".bak2")
    if not b.exists():
        shutil.copy2(p, b)

def insert_after(p: Path, anchor: str, addition: str) -> bool:
    content = p.read_text(encoding="utf-8")
    if addition.strip() in content:
        print(f"   ⏭  {p.name}: já aplicado")
        return True
    if anchor not in content:
        errors.append(f"ANCHOR NOT FOUND in {p.name}: {anchor[:60]!r}")
        return False
    content = content.replace(anchor, anchor + addition, 1)
    p.write_text(content, encoding="utf-8")
    print(f"   ✔ {p.name}")
    return True

# ═════════════════════════════════════════════════════════════════
# FIX 1 — 26_doxly_flow_tracer.lua: adiciona guarda-corpo no divider
# ═════════════════════════════════════════════════════════════════
p26 = _get("doxoade/commands/lite_xl_systems/template/26_doxly_flow_tracer.lua")
if p26:
    # 1a. Se arquivo está corrompido, restaura do .bak
    bak = p26.with_suffix(p26.suffix + ".bak")
    if bak.exists():
        bak_txt = bak.read_text(encoding="utf-8")
        cur_txt = p26.read_text(encoding="utf-8")
        if "local results = { pcall(_orig_update_layout" in cur_txt \
           and "local results = { pcall(_orig_update_layout" not in bak_txt:
            shutil.copy2(bak, p26)
            print(f"   🔄 {p26.name}: restaurado do .bak")
    _backup(p26)

    # 1b. Adiciona hook get_divider_overlapping_point
    DIVIDER = '''
-- ═══════════════════════════════════════════════════════════════
-- HOOK Node:get_divider_overlapping_point — guarda-corpo no crash real
-- ═══════════════════════════════════════════════════════════════
local _orig_divider = Node.get_divider_overlapping_point
if _orig_divider then
  Node.get_divider_overlapping_point = function(self, ...)
    local root = core.root_view and core.root_view.root_node
    if root then
      local viols = check_invariants(root)
      if #viols > 0 then
        local repaired = repair_tree(root)
        record({
          phase = "MOUSE_PRECHECK",
          cmd = "get_divider_overlapping_point",
          src = "core.node",
          line = 0,
          info = string.format('{"violations":%d,"repaired":%d,"node_type":"%s"}',
            #viols, repaired, tostring(self and self.type)),
          viol = "[]",
        })
        if repaired > 0 and core.log then
          core.log(string.format("🌊 [FLOW] 🔧 Self-healing (divider): %d reparo(s)", repaired))
        end
      end
    end
    return _orig_divider(self, ...)
  end
end
'''
    insert_after(
        p26,
        "  return ok, err  -- não re-throw (evita cascata)\nend\n",
        DIVIDER,
    )

# ═════════════════════════════════════════════════════════════════
# FIX 2 — 05_split_mover.lua: SWAP / MOVE_FOLLOW / CLOSE_FOLLOW / FOCUS_OPP
# ═════════════════════════════════════════════════════════════════
p05 = _get("doxoade/commands/lite_xl_systems/template/05_split_mover.lua")
if p05:
    _backup(p05)

    # --- swap_split_panels marks ---
    insert_after(p05,
        "local function swap_split_panels()\n",
        '  _fm("SWAP", "start", "")\n')
    insert_after(p05,
        "  if split_node and split_node.a and split_node.b then\n",
        '    _fm("SWAP", "a_type", tostring(split_node.a and split_node.a.type))\n'
        '    _fm("SWAP", "b_type", tostring(split_node.b and split_node.b.type))\n')
    insert_after(p05,
        "    split_node.b = tmp\n",
        '    _fm("SWAP", "swapped", "")\n')
    insert_after(p05,
        '    if core.log then core.log("✔ [SPLIT] Painéis invertidos com sucesso (Swap A ↔ B).") end\n',
        '    _fm("SWAP", "end", "")\n'
        '  else\n'
        '    _fm("SWAP", "no_split", "")\n')

    # --- ensure_leaf_not_empty helper ---
    ENSURE = '''
-- ─── Helper: garantir que um leaf nunca fica vazio ─────────────
local function ensure_leaf_not_empty(leaf)
  if not leaf or #(leaf.views or {}) > 0 then return end
  _fm("SPLIT", "ensure_empty", "leaf")
  local ok_ev, EmptyView = pcall(require, "core.emptyview")
  if ok_ev and EmptyView then
    local ok_new, ev = pcall(EmptyView)
    if ok_new and ev then
      leaf:add_view(ev)
      leaf.active_view = ev
      _fm("SPLIT", "ensure_empty", "emptyview_added")
      return
    end
  end
  if core.open_doc then
    local ok_doc, doc = pcall(core.open_doc)
    if ok_doc and doc then
      local DocView = require "core.docview"
      local v = DocView(doc)
      leaf:add_view(v)
      leaf.active_view = v
      _fm("SPLIT", "ensure_empty", "blank_doc")
    end
  end
end

'''
    insert_after(p05,
        '  _fm("MOVE", "end", "target_views=" .. tostring(#target_leaf.views))\nend\n\n',
        ENSURE)

    # --- ensure em move_following ---
    insert_after(p05,
        "  target_leaf.active_view = target_leaf.views[#target_leaf.views]\n",
        '  ensure_leaf_not_empty(source_leaf)\n'
        '  _fm("MOVE_FOLLOW", "moved", "count=" .. tostring(count))\n')

    # --- ensure em close_following ---
    insert_after(p05,
        "    table.remove(node.views, i)\n    closed = closed + 1\n  end\n",
        '  ensure_leaf_not_empty(node)\n'
        '  _fm("CLOSE_FOLLOW", "closed", "count=" .. tostring(closed))\n')

    # --- FOCUS_OPP marks ---
    insert_after(p05,
        "local function focus_opposite_panel()\n",
        '  _fm("FOCUS_OPP", "start", "")\n')
    insert_after(p05,
        "  local leaves = get_editor_leaves()\n  if #leaves < 2 then return end\n",
        '  _fm("FOCUS_OPP", "leaves", "count=" .. tostring(#leaves))\n')
    insert_after(p05,
        "      core.set_active_view(l.active_view)\n",
        '      _fm("FOCUS_OPP", "target", "type=" .. tostring(l.type))\n')

# ═════════════════════════════════════════════════════════════════
# FIX 3 — cmd_doxly_flow.py: _is_aot_unresolved + aviso AOT
# ═════════════════════════════════════════════════════════════════
pcmd = _get("doxoade/commands/lite_xl_systems/cmd_doxly_flow.py")
if pcmd:
    _backup(pcmd)

    AOT_FN = '''def _is_aot_unresolved(src: str) -> bool:
    """Detecta se `src` é bytecode AOT não-mapeável (tmpXXX.lua)."""
    if not src:
        return False
    s = str(src).lower()
    return s.startswith("tmp") and s.endswith(".lua")


'''
    insert_after(pcmd, "        return None\n\n\n", AOT_FN)

    AOT_WARN = '''    init_file = target / "init.lua"
    if init_file.exists():
        try:
            if init_file.read_bytes()[:4].startswith(b"\\x1bLua"):
                click.echo(f"{Fore.MAGENTA}ℹ Init em AOT bytecode — tracebacks não resolvem. "
                           f"Use `deploy production --no-khonsu` para debug.{Fore.RESET}\\n")
        except OSError:
            pass

'''
    insert_after(pcmd,
        '    flow_file = target / ".doxoade" / "diagnostics" / "flow_trace.ndjson"\n\n',
        AOT_WARN)

# ═════════════════════════════════════════════════════════════════
# RESULTADO
# ═════════════════════════════════════════════════════════════════
if errors:
    print("\n" + "\n".join("✘ " + e for e in errors))
    sys.exit(1)

print("\n✅ Todas as correções aplicadas.")
print("   Próximo passo:")
print("     doxoade doxly check-templates")
print("     doxoade doxly deploy production --force --no-khonsu")
print("     doxoade doxly flow --key ctrl+l --last 10")