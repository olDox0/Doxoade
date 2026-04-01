# -*- coding: utf-8 -*-
# doxoade/commands/impact_systems/impact_html.py
import json
from pathlib import Path

def to_html(mermaid_str: str, stats: dict, issues: list) -> str:
    """Gera o HTML final interpolando os arquivos estáticos separados."""
    data_json = json.dumps({"stats": stats, "alerts": issues}, ensure_ascii=False, indent=2)
    
    # Busca a pasta onde este próprio script python está salvo
    base_dir = Path(__file__).parent
    
    # Lê os arquivos dedicados (Seguro e Conservador)
    try:
        with open(base_dir / "impact_template.html", "r", encoding="utf-8") as f:
            template = f.read()
        with open(base_dir / "impact_style.css", "r", encoding="utf-8") as f:
            style_css = f.read()
        with open(base_dir / "impact_app.js", "r", encoding="utf-8") as f:
            app_js = f.read()
    except FileNotFoundError as e:
        # Fallback de erro se alguém deletar os arquivos sem querer
        return f"<h1>Erro Fatal HTML</h1><p>Arquivos de template não encontrados em: {base_dir}</p><p>{e}</p>"

    # Realiza as substituições com os arquivos e dados
    final_html = (template
                  .replace("{{STYLE_CSS}}", style_css)
                  .replace("{{APP_JS}}", app_js)
                  .replace("{{GRAPH}}", mermaid_str)
                  .replace("{{DATA_JSON}}", data_json))
    
    return final_html