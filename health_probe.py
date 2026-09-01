# health_probe.py
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

init_path = LiteXLEngine.get_init_lua_path()

def dump(label, fn):
    print(f"\n=== {label} ===")
    try:
        r = fn()
        print("type:", type(r).__name__)
        if isinstance(r, dict):
            print("keys:", list(r.keys()))
            for k, v in r.items():
                if k == "files" and isinstance(v, dict):
                    print(f"  files: {len(v)} entries")
                    if v:
                        k0 = next(iter(v)); print(f"    sample[{k0!r}] = {v[k0]!r}")
                else:
                    print(f"  {k} = {v!r}")
        elif isinstance(r, list):
            print("len:", len(r))
            for x in r[:6]: print(f"  {x!r}")
    except Exception as e:
        print("ERROR:", type(e).__name__, e)

dump("run_shadow_audit()", lambda: LiteXLEngine.run_shadow_audit())
dump("parse_keybindings(init)", lambda: LiteXLEngine.parse_keybindings(init_path))
dump("get_session_artifacts()", lambda: LiteXLEngine.get_session_artifacts())
