# doxoade\commands\lan_git\web_lan_git\ui_templates_lan_git.py
""" Templates HTML5 e CSS3 Embutidos para o Portal Web Doxoade.
Design moderno, tema Soft Dark, 100% autocontido (Zero CDNs / Zero dependências externas). """

from typing import Optional


CSS_STYLES = """
:root {
    --bg-dark: #0f172a;
    --card-bg: #1e293b;
    --border-color: #334155;
    --accent-blue: #38bdf8;
    --accent-green: #4ade80;
    --accent-yellow: #facc15;
    --accent-red: #f87171;
    --text-main: #f8fafc;
    --text-muted: #94a3b8;
}
* { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }
body { background: var(--bg-dark); color: var(--text-main); display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }
.container { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; width: 100%; max-width: 620px; padding: 32px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); }
.header { border-bottom: 1px solid var(--border-color); padding-bottom: 16px; margin-bottom: 24px; text-align: center; }
.header h1 { font-size: 24px; color: var(--accent-blue); letter-spacing: 0.5px; }
.header p { font-size: 14px; color: var(--text-muted); margin-top: 4px; }
.card-grid { display: grid; gap: 16px; margin-top: 24px; }
.action-card { background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-color); border-radius: 8px; padding: 16px; display: flex; align-items: center; justify-content: space-between; transition: 0.2s ease; }
.action-card:hover { border-color: var(--accent-blue); transform: translateY(-2px); }
.action-card-highlight { background: rgba(74, 222, 128, 0.08); border-color: rgba(74, 222, 128, 0.4); }
.action-card-highlight:hover { border-color: var(--accent-green); }
.action-info h3 { font-size: 16px; color: var(--text-main); }
.action-info p { font-size: 13px; color: var(--text-muted); }
.btn { background: var(--accent-blue); color: #0f172a; font-weight: 600; padding: 10px 18px; border-radius: 6px; text-decoration: none; border: none; cursor: pointer; transition: 0.2s ease; display: inline-flex; align-items: center; gap: 6px; }
.btn:hover { background: #7dd3fc; }
.btn-green { background: var(--accent-green); color: #0f172a; }
.btn-green:hover { background: #86efac; }
.btn-logout { background: transparent; border: 1px solid var(--border-color); color: var(--text-muted); font-size: 12px; padding: 6px 12px; }
.btn-logout:hover { color: var(--accent-red); border-color: var(--accent-red); background: transparent; }
.input-field { width: 100%; padding: 12px 16px; background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); border-radius: 6px; color: #fff; font-size: 16px; margin-bottom: 16px; outline: none; }
.input-field:focus { border-color: var(--accent-blue); }
.alert-error { background: rgba(248, 113, 113, 0.1); border: 1px solid var(--accent-red); color: var(--accent-red); padding: 12px; border-radius: 6px; font-size: 14px; margin-bottom: 16px; text-align: center; }
.code-box { background: rgba(15, 23, 42, 0.9); border: 1px dashed var(--border-color); border-radius: 6px; padding: 12px; font-family: monospace; font-size: 13px; color: var(--accent-green); word-break: break-all; margin-top: 8px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; background: rgba(56, 189, 248, 0.15); color: var(--accent-blue); }
"""


class UIPortalTemplates:
    """Renderizador de páginas HTML estáticas e seguras."""

    @staticmethod
    def render_login_page(error_msg: Optional[str] = None, lockout_remaining: int = 0) -> str:
        error_html = ""
        if lockout_remaining > 0:
            error_html = f'<div class="alert-error">🔒 IP Bloqueado por excesso de tentativas. Aguarde {lockout_remaining}s.</div>'
        elif error_msg:
            error_html = f'<div class="alert-error">⚠️ {error_msg}</div>'

        disabled_attr = 'disabled style="opacity: 0.5;"' if lockout_remaining > 0 else ""

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Doxoade LAN Portal - Autenticação</title>
    <style>{CSS_STYLES}</style>
</head>
<body>
    <div class="container" style="max-width: 420px;">
        <div class="header">
            <h1>🛡️ DOXOADE PORTAL</h1>
            <p>Acesso Seguro ao Hub de Distribuição Local</p>
        </div>
        {error_html}
        <form method="POST" action="/login">
            <label style="font-size: 13px; color: var(--text-muted); display: block; margin-bottom: 6px;">Senha ou PIN de Acesso:</label>
            <input type="password" name="password" class="input-field" placeholder="Digite a chave..." required {disabled_attr}>
            <button type="submit" class="btn" style="width: 100%; justify-content: center;" {disabled_attr}>Acessar Repositório</button>
        </form>
    </div>
</body>
</html>"""

    @staticmethod
    def render_dashboard(repo_name: str, branch: str, commit_short: str, commit_msg: str, host_ip: str, port: int) -> str:
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Doxoade Portal - {repo_name}</title>
    <style>{CSS_STYLES}</style>
</head>
<body>
    <div class="container">
        <div class="header" style="display: flex; justify-content: space-between; align-items: center; text-align: left;">
            <div>
                <h1>📦 {repo_name}</h1>
                <p>Branch: <span class="badge">{branch}</span> Commit: <span class="badge">{commit_short}</span></p>
            </div>
            <a href="/logout" class="btn btn-logout">Desconectar</a>
        </div>

        <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">
            📝 <i>"{commit_msg}"</i>
        </p>

        <div class="card-grid">
            <!-- Destaque: FastPack Offline -->
            <div class="action-card action-card-highlight">
                <div class="action-info">
                    <h3 style="color: var(--accent-green);">⚡ FastPack Offline (.py)</h3>
                    <p>Código + Dependências pré-compiladas (Instala em ~4s sem internet)</p>
                </div>
                <a href="/download/fastpack" class="btn btn-green">Baixar FastPack</a>
            </div>

            <div class="action-card">
                <div class="action-info">
                    <h3>Download do Projeto (.ZIP)</h3>
                    <p>Pacote sanitizado sem arquivos confidenciais</p>
                </div>
                <a href="/download/zip" class="btn">Baixar ZIP</a>
            </div>

            <div class="action-card">
                <div class="action-info">
                    <h3>Instalador Automático (.BAT)</h3>
                    <p>Configura venv e dependências via internet</p>
                </div>
                <a href="/download/bootstrap" class="btn">Baixar .BAT</a>
            </div>

            <div class="action-card">
                <div class="action-info">
                    <h3>Git Bundle Autocontido</h3>
                    <p>Arquivo binário com histórico completo de commits</p>
                </div>
                <a href="/download/bundle" class="btn">Baixar Bundle</a>
            </div>
        </div>

        <div style="margin-top: 28px;">
            <p style="font-size: 13px; color: var(--text-muted);">Ou clone diretamente via Terminal Git:</p>
            <div class="code-box">git clone http://{host_ip}:{port}/git/{repo_name}.git</div>
        </div>
    </div>
</body>
</html>"""