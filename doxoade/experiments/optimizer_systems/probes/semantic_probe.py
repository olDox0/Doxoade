# doxoade/doxoade/experiments/optimizer_systems/probes/semantic_probe.py
def semantic_probe(ast_info: dict) -> bool:
    return ast_info.get('has_loops', False)