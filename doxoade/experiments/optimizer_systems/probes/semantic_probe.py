def semantic_probe(ast_info: dict) -> bool:
    # PMV: só rejeita código sem loop (não é CPU puro)
    return ast_info.get("has_loops", False)