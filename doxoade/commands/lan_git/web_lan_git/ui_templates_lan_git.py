# doxoade/commands/lan_git/web_lan_git/ui_templates_lan_git.py
""" Templates HTML5 e CSS3 Embutidos para o Portal Web Doxoade.
Design moderno, tema Soft Dark, 100% autocontido e imune a conflito de chaves f-strings. """

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
    --accent-purple: #c084fc;
    --text-main: #f8fafc;
    --text-muted: #94a3b8;
}
* { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }
body { background: var(--bg-dark); color: var(--text-main); display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 24px; }
.container { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; width: 100%; max-width: 680px; padding: 32px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); }
.container-wide { max-width: 1100px; }
.header { border-bottom: 1px solid var(--border-color); padding-bottom: 16px; margin-bottom: 20px; text-align: center; }
.header h1 { font-size: 24px; color: var(--accent-blue); letter-spacing: 0.5px; }
.header p { font-size: 14px; color: var(--text-muted); margin-top: 4px; }
.card-grid { display: grid; gap: 16px; margin-top: 24px; }
.action-card { background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-color); border-radius: 8px; padding: 16px; display: flex; align-items: center; justify-content: space-between; transition: 0.2s ease; }
.action-card:hover { border-color: var(--accent-blue); transform: translateY(-2px); }
.action-card-highlight { background: rgba(74, 222, 128, 0.08); border-color: rgba(74, 222, 128, 0.4); }
.action-card-highlight:hover { border-color: var(--accent-green); }
.action-card-purple { background: rgba(168, 85, 247, 0.08); border-color: rgba(168, 85, 247, 0.4); }
.action-card-purple:hover { border-color: var(--accent-purple); }
.action-info h3 { font-size: 16px; color: var(--text-main); }
.action-info p { font-size: 13px; color: var(--text-muted); }
.btn { background: var(--accent-blue); color: #0f172a; font-weight: 600; padding: 10px 18px; border-radius: 6px; text-decoration: none; border: none; cursor: pointer; transition: 0.2s ease; display: inline-flex; align-items: center; gap: 6px; font-size: 14px; }
.btn:hover { background: #7dd3fc; }
.btn-green { background: var(--accent-green); color: #0f172a; }
.btn-green:hover { background: #86efac; }
.btn-purple { background: #a855f7; color: #fff; }
.btn-purple:hover { background: #c084fc; }
.btn-outline { background: transparent; border: 1px solid var(--border-color); color: var(--text-muted); font-size: 13px; padding: 7px 14px; border-radius: 6px; text-decoration: none; cursor: pointer; }
.btn-outline:hover { color: var(--text-main); border-color: var(--text-muted); }
.btn-danger { color: var(--accent-red); border-color: rgba(248, 113, 113, 0.3); }
.btn-danger:hover { background: rgba(248, 113, 113, 0.1); border-color: var(--accent-red); }
.input-field { width: 100%; padding: 12px 16px; background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); border-radius: 6px; color: #fff; font-size: 16px; margin-bottom: 16px; outline: none; }
.input-field:focus { border-color: var(--accent-blue); }
.alert-error { background: rgba(248, 113, 113, 0.1); border: 1px solid var(--accent-red); color: var(--accent-red); padding: 12px; border-radius: 6px; font-size: 14px; margin-bottom: 16px; text-align: center; }
.alert-warn { background: rgba(250, 204, 21, 0.1); border: 1px solid var(--accent-yellow); color: var(--accent-yellow); padding: 10px; border-radius: 6px; font-size: 13px; margin-bottom: 16px; text-align: center; }
.code-box { background: rgba(15, 23, 42, 0.9); border: 1px dashed var(--border-color); border-radius: 6px; padding: 12px; font-family: monospace; font-size: 13px; color: var(--accent-green); word-break: break-all; margin-top: 8px; }
.badge { display: inline-block; padding: 3px 10px; border-radius: 4px; font-size: 12px; font-weight: bold; background: rgba(56, 189, 248, 0.15); color: var(--accent-blue); }
.notepad-area { width: 100%; height: 60vh; min-height: 420px; background: #0b1120; border: 1px solid var(--border-color); border-radius: 8px; padding: 18px; color: #f1f5f9; font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace; font-size: 14px; line-height: 1.6; resize: vertical; outline: none; }
.notepad-area:focus { border-color: var(--accent-purple); box-shadow: 0 0 0 2px rgba(192, 132, 252, 0.2); }
.status-bar { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; font-size: 13px; color: var(--text-muted); }
.pulse-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; background: var(--accent-green); box-shadow: 0 0 8px var(--accent-green); }
"""


class UIPortalTemplates:
    """Renderizador de páginas HTML estáticas e seguras."""

    @staticmethod
    def render_login_page(error_msg: Optional[str] = None, lockout_remaining: int = 0, attempts_left: int = 5) -> str:
        error_html = ""
        if lockout_remaining > 0:
            error_html = f'<div class="alert-error">🔒 <b>IP Bloqueado por Força Bruta.</b><br>Aguarde {lockout_remaining}s para tentar novamente.</div>'
        elif error_msg:
            error_html = f'<div class="alert-error">⚠️ {error_msg}</div>'
            if attempts_left < 5:
                error_html += f'<div class="alert-warn">Atenção: restam <b>{attempts_left}</b> tentativa(s) antes do bloqueio de 5 minutos.</div>'

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
            <p>Hub Seguro de Sincronização Local</p>
        </div>
        {error_html}
        <form method="POST" action="/login">
            <label style="font-size: 13px; color: var(--text-muted); display: block; margin-bottom: 6px;">Senha Obrigatória do Silo:</label>
            <input type="password" name="password" class="input-field" placeholder="Digite a chave definida no Host..." required {disabled_attr} autofocus>
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
            <a href="/logout" class="btn-outline">Desconectar</a>
        </div>

        <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">
            📝 <i>"{commit_msg}"</i>
        </p>

        <div class="card-grid">
            <div class="action-card action-card-purple">
                <div class="action-info">
                    <h3 style="color: #c084fc;">📝 Bloco de Notas LAN (Scratchpad)</h3>
                    <p>Troque textos, comandos e prompts entre Amaranth e Bluebaby em tempo real</p>
                </div>
                <a href="/notepad" class="btn btn-purple">Abrir Bloco</a>
            </div>

            <div class="action-card action-card-highlight">
                <div class="action-info">
                    <h3 style="color: var(--accent-green);">⚡ FastPack Offline (.pyz)</h3>
                    <p>Código + Dependências pré-compiladas (Instala em ~4s sem internet)</p>
                </div>
                <a href="/download/fastpack" class="btn btn-green">Baixar FastPack</a>
            </div>

            <div class="action-card">
                <div class="action-info">
                    <h3>Download Sanitizado (.ZIP)</h3>
                    <p>Sem arquivos confidenciais ou lixo temporário</p>
                </div>
                <a href="/download/zip" class="btn">Baixar ZIP</a>
            </div>

            <div class="action-card">
                <div class="action-info">
                    <h3>Git Bundle Autocontido</h3>
                    <p>Arquivo binário SHA-256 com histórico completo</p>
                </div>
                <a href="/download/bundle" class="btn">Baixar Bundle</a>
            </div>
        </div>

        <div style="margin-top: 28px;">
            <p style="font-size: 13px; color: var(--text-muted);">Comando de Clone Direto para o BabyBlue / PC-B:</p>
            <div class="code-box">doxoade lan-git clone "{repo_name}" . --web --host {host_ip}</div>
        </div>
    </div>
</body>
</html>"""

    @staticmethod
    def render_notepad(content: str, repo_name: str) -> str:
        """
        [PRODENOV 3.1.5] Renderizador do Bloco de Notas imune a SyntaxError.
        Utiliza template estático puro com interpolação controlada via .replace().
        """
        template = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bloco de Notas LAN - __REPO_NAME__</title>
    <style>__CSS_STYLES__</style>
</head>
<body>
    <div class="container container-wide">
        <div class="header" style="display: flex; justify-content: space-between; align-items: center; text-align: left;">
            <div>
                <h1 style="color: #c084fc;">📝 Bloco de Notas LAN</h1>
                <p>Silo: <span class="badge">__REPO_NAME__</span> | Arquivo: <code>shared_notes.md</code></p>
            </div>
            <div style="display: flex; gap: 8px;">
                <button onclick="copiarTexto()" class="btn-outline">📋 Copiar Tudo</button>
                <button onclick="limparTexto()" class="btn-outline btn-danger">🧹 Limpar</button>
                <a href="/dashboard" class="btn-outline">Voltar ao Hub</a>
                <a href="/logout" class="btn-outline">Sair</a>
            </div>
        </div>

        <textarea id="pad" class="notepad-area" placeholder="Digite ou cole aqui qualquer texto para transmitir instantaneamente entre Amaranth e Bluebaby...">__CONTENT__</textarea>

        <div class="status-bar">
            <div>
                <span id="dot" class="pulse-dot"></span>
                <span id="sync-status" style="color: var(--accent-green);">⚡ Tempo Real Ativo (Push SSE)</span>
                <span id="latency-badge" style="margin-left: 10px; color: var(--accent-purple); font-family: monospace;">[RTT: -- ms]</span>
            </div>
            <div>
                <span id="char-count">0 caracteres</span>
            </div>
        </div>
    </div>

    <script>
        const pad = document.getElementById('pad');
        const syncStatus = document.getElementById('sync-status');
        const charCount = document.getElementById('char-count');
        const dot = document.getElementById('dot');
        const latencyBadge = document.getElementById('latency-badge');
        let saveTimeout = null;
        let isEditing = false;
        let currentRev = 1;
        let sseActive = false;

        function updateStats() {
            charCount.textContent = `${pad.value.length} caracteres | ${pad.value.split('\\n').length} linhas`;
        }
        updateStats();

        // [PLANO C] Sobrevivência Offline
        const localDraft = localStorage.getItem('dox_notepad_draft');
        if (localDraft && localDraft !== pad.value && pad.value.trim() === '') {
            pad.value = localDraft;
            updateStats();
        }

        // Suporte à tecla TAB
        pad.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = pad.selectionStart;
                const end = pad.selectionEnd;
                pad.value = pad.value.substring(0, start) + '    ' + pad.value.substring(end);
                pad.selectionStart = pad.selectionEnd = start + 4;
                pad.dispatchEvent(new Event('input'));
            }
        });

        // Transmissão com medição de RTT ao digitar
        pad.addEventListener('input', () => {
            isEditing = true;
            updateStats();
            localStorage.setItem('dox_notepad_draft', pad.value);

            dot.style.background = "var(--accent-yellow)";
            dot.style.boxShadow = "0 0 8px var(--accent-yellow)";
            syncStatus.textContent = "Transmitindo...";
            syncStatus.style.color = "var(--accent-yellow)";

            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(() => {
                const t0 = performance.now();
                fetch('/api/notepad', {
                    method: 'POST',
                    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
                    body: pad.value
                })
                .then(r => {
                    const rtt = Math.round(performance.now() - t0);
                    if (latencyBadge) latencyBadge.textContent = `[RTT Envio: ${rtt}ms]`;
                    if (r.ok) return r.json();
                    if (r.status === 401 || r.status === 302) window.location.href = '/login';
                    throw new Error('Falha no POST');
                })
                .then(data => {
                    currentRev = data.rev;
                    dot.style.background = "var(--accent-green)";
                    dot.style.boxShadow = "0 0 8px var(--accent-green)";
                    syncStatus.textContent = sseActive ? "⚡ Tempo Real Ativo (Push SSE)" : "✔ Sincronizado";
                    syncStatus.style.color = "var(--accent-green)";
                    setTimeout(() => { isEditing = false; }, 400);
                })
                .catch(() => {
                    syncStatus.textContent = "✖ Falha de conexão (Salvo no navegador)";
                    syncStatus.style.color = "var(--accent-red)";
                    isEditing = false;
                });
            }, 350);
        });

        // [PLANO A] SSE de Baixa Latência com medição de propagação
        function initSSE() {
            const evtSource = new EventSource('/api/notepad/events');

            evtSource.onopen = () => {
                sseActive = true;
                dot.style.background = "var(--accent-green)";
                dot.style.boxShadow = "0 0 8px var(--accent-green)";
                syncStatus.textContent = "⚡ Tempo Real Ativo (Push SSE)";
                syncStatus.style.color = "var(--accent-green)";
            };

            evtSource.addEventListener('init', (e) => {
                const data = JSON.parse(e.data);
                currentRev = data.rev;
                if (!isEditing && pad.value !== data.text) {
                    pad.value = data.text;
                    updateStats();
                }
            });

            evtSource.addEventListener('update', (e) => {
                const data = JSON.parse(e.data);
                if (data.ts && latencyBadge) {
                    const transitMs = Math.max(1, Math.round((Date.now() / 1000 - data.ts) * 1000));
                    latencyBadge.textContent = `[Latência SSE: ${transitMs}ms | Rev: ${data.rev}]`;
                }
                currentRev = data.rev;
                if (!isEditing && pad.value !== data.text) {
                    const start = pad.selectionStart;
                    const end = pad.selectionEnd;
                    pad.value = data.text;
                    pad.setSelectionRange(start, end);
                    updateStats();

                    dot.style.background = "var(--accent-blue)";
                    dot.style.boxShadow = "0 0 10px var(--accent-blue)";
                    syncStatus.textContent = "⚡ Atualizado instantaneamente via SSE";
                    syncStatus.style.color = "var(--accent-blue)";

                    setTimeout(() => {
                        dot.style.background = "var(--accent-green)";
                        dot.style.boxShadow = "0 0 8px var(--accent-green)";
                        syncStatus.textContent = "⚡ Tempo Real Ativo (Push SSE)";
                        syncStatus.style.color = "var(--accent-green)";
                    }, 1500);
                }
            });

            evtSource.onerror = () => {
                sseActive = false;
                dot.style.background = "var(--accent-yellow)";
                syncStatus.textContent = "🟡 SSE reconectando... (Plano B ativo)";
                syncStatus.style.color = "var(--accent-yellow)";
                evtSource.close();
                setTimeout(initSSE, 4000);
            };
        }
        initSSE();

        // [PLANO B] Polling de Contingência por Revisão (Sem leitura de disco)
        setInterval(() => {
            if (sseActive || isEditing) return;

            fetch(`/api/notepad?rev=${currentRev}`)
                .then(r => {
                    if (r.status === 304) return null;
                    if (r.status === 401 || r.status === 302 || r.redirected) {
                        window.location.href = '/login';
                        return null;
                    }
                    if (!r.ok) return null;
                    const revHeader = r.headers.get('X-Notepad-Revision');
                    if (revHeader) currentRev = parseInt(revHeader, 10);
                    return r.text();
                })
                .then(remoteText => {
                    if (remoteText !== null && !isEditing && remoteText !== pad.value) {
                        const start = pad.selectionStart;
                        const end = pad.selectionEnd;
                        pad.value = remoteText;
                        pad.setSelectionRange(start, end);
                        updateStats();
                    }
                })
                .catch(() => {});
        }, 3000);

        function copiarTexto() {
            navigator.clipboard.writeText(pad.value).then(() => {
                alert("Texto copiado para a área de transferência!");
            });
        }

        function limparTexto() {
            if (confirm("Deseja realmente limpar todo o bloco de notas?")) {
                pad.value = "";
                pad.dispatchEvent(new Event('input'));
            }
        }
    </script>
</body>
</html>"""
        return template.replace("__REPO_NAME__", repo_name).replace("__CONTENT__", content).replace("__CSS_STYLES__", CSS_STYLES)
