"""Main FastAPI application for the Codex Home Assistant add-on."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .codex_manager import CodexManager
from .config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
manager = CodexManager(settings)
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting Codex Home Assistant add-on")
    settings.codex_home_path.mkdir(parents=True, exist_ok=True)
    settings.workspace_path.mkdir(parents=True, exist_ok=True)
    yield
    manager.stop_terminal()
    logger.info("Stopping Codex Home Assistant add-on")


app = FastAPI(
    title="Codex CLI Add-on",
    description="Run the Codex CLI inside Home Assistant and sign in with OpenAI device auth.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def root() -> str:
    """Serve the browser terminal UI."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex Terminal</title>
  <link rel="stylesheet" href="./static/xterm.css">
  <style>
    :root {{
      --page: #eee8dc;
      --panel: rgba(253, 250, 243, 0.9);
      --border: rgba(20, 36, 29, 0.12);
      --ink: #18221d;
      --muted: #5f675f;
      --accent: #145f68;
      --warn: #8a4b28;
      --shadow: 0 24px 70px rgba(27, 38, 31, 0.14);
      --term: #071713;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(208, 140, 96, 0.22), transparent 28%),
        radial-gradient(circle at right, rgba(20, 95, 104, 0.14), transparent 26%),
        linear-gradient(180deg, #f6f2ea 0%, var(--page) 100%);
    }}
    .page {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 22px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      gap: 18px;
      min-height: calc(100vh - 44px);
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .sidebar {{
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 0.72rem;
      color: var(--accent);
      font-weight: 800;
    }}
    h1 {{
      margin: 8px 0 12px;
      font-size: 2.7rem;
      line-height: 0.92;
      letter-spacing: -0.04em;
    }}
    p {{
      margin: 0;
      line-height: 1.6;
      color: var(--muted);
    }}
    .status {{
      display: grid;
      gap: 10px;
      font-size: 0.95rem;
    }}
    .pill {{
      display: inline-flex;
      width: fit-content;
      align-items: center;
      gap: 10px;
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(20, 95, 104, 0.08);
      color: var(--accent);
      font-weight: 800;
    }}
    .pill::before {{
      content: "";
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: currentColor;
    }}
    .code-box {{
      border-radius: 18px;
      background: rgba(20, 95, 104, 0.06);
      padding: 14px;
      font-family: "SFMono-Regular", "Cascadia Code", monospace;
      overflow-wrap: anywhere;
      min-height: 74px;
    }}
    .device-code {{
      font-size: 1.7rem;
      font-weight: 800;
      letter-spacing: 0.14em;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .shortcut-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 10px;
    }}
    button {{
      border: 0;
      border-radius: 14px;
      padding: 12px 16px;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
      transition: transform 140ms ease, opacity 140ms ease;
    }}
    button:hover {{ transform: translateY(-1px); }}
    button:disabled {{ opacity: 0.55; cursor: not-allowed; transform: none; }}
    .primary {{ background: var(--accent); color: white; }}
    .secondary {{ background: rgba(20, 95, 104, 0.1); color: var(--accent); }}
    .shortcut {{
      text-align: left;
      line-height: 1.25;
      background: rgba(20, 95, 104, 0.08);
      color: var(--accent);
      min-height: 66px;
    }}
    .terminal-shell {{
      display: grid;
      grid-template-rows: auto 1fr;
      min-height: 0;
      overflow: hidden;
    }}
    .terminal-header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 18px 20px;
      border-bottom: 1px solid var(--border);
      align-items: center;
    }}
    .terminal-copy {{
      display: grid;
      gap: 4px;
    }}
    .terminal-copy strong {{
      font-size: 1.3rem;
    }}
    .terminal-wrap {{
      background: linear-gradient(180deg, #0a1c17 0%, var(--term) 100%);
      padding: 14px;
      min-height: 0;
    }}
    #terminal {{
      width: 100%;
      height: 100%;
      min-height: calc(100vh - 130px);
    }}
    .tiny {{
      font-size: 0.88rem;
      color: var(--muted);
    }}
    code {{
      background: rgba(20, 95, 104, 0.08);
      padding: 0.16rem 0.34rem;
      border-radius: 0.4rem;
    }}
    a {{ color: var(--accent); }}
    @media (max-width: 980px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      #terminal {{
        min-height: 68vh;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="layout">
      <aside class="card sidebar">
        <div>
          <div class="eyebrow">Home Assistant Add-on</div>
          <h1>Codex terminal.</h1>
          <p>Use the real Codex CLI in a browser terminal with access to <code>{settings.workspace_dir}</code>. This is the place to inspect logs, edit Home Assistant config, and fix issues directly on the server.</p>
        </div>

        <div class="status">
          <div class="pill" id="auth-pill">Checking login...</div>
          <div id="auth-message" class="tiny"></div>
        </div>

        <div class="actions">
          <button id="login-button" class="primary">Connect with OpenAI</button>
          <button id="refresh-button" class="secondary">Refresh status</button>
          <button id="restart-button" class="secondary">Restart terminal</button>
        </div>

        <div id="device-panel" hidden>
          <p class="tiny">Verification URL</p>
          <div class="code-box"><a id="device-url" href="#" target="_blank" rel="noreferrer"></a></div>
          <p class="tiny" style="margin-top:12px;">One-time code</p>
          <div id="device-code" class="code-box device-code">....-.....</div>
        </div>

        <div>
          <p class="tiny">Defaults</p>
          <p class="tiny">Workspace: <code>{settings.workspace_dir}</code></p>
          <p class="tiny">Sandbox: <code>{settings.sandbox_mode}</code></p>
          <p class="tiny">Approval: <code>{settings.approval_policy}</code></p>
        </div>

        <div>
          <p class="tiny">Home Assistant shortcuts</p>
          <p class="tiny"><code>cd /homeassistant && ls -la</code> starts in your HA config.</p>
          <p class="tiny"><code>cat /homeassistant/automations.yaml</code> opens your automations.</p>
          <p class="tiny"><code>rg "entity_id" /homeassistant</code> searches config references.</p>
          <p class="tiny"><code>codex</code> opens the interactive agent in the current directory.</p>
          <p class="tiny"><code>ha core logs</code> helps with runtime errors when the HA CLI is available.</p>
          <div class="shortcut-grid">
            <button class="shortcut" data-command="cd /homeassistant && ls -la&#10;">Open config</button>
            <button class="shortcut" data-command="cd /homeassistant && sed -n '1,240p' automations.yaml&#10;">Open automations</button>
            <button class="shortcut" data-command="cd /homeassistant && sed -n '1,240p' configuration.yaml&#10;">Open configuration</button>
            <button class="shortcut" data-command="cd /homeassistant && sed -n '1,240p' scripts.yaml&#10;">Open scripts</button>
            <button class="shortcut" data-command="cd /homeassistant && rg &quot;entity_id|service:&quot; .&#10;">Search references</button>
            <button class="shortcut" data-command="ha core logs&#10;">HA logs</button>
          </div>
        </div>
      </aside>

      <main class="card terminal-shell">
        <div class="terminal-header">
          <div class="terminal-copy">
            <strong>Interactive Codex CLI</strong>
            <span class="tiny" id="terminal-status">Starting terminal...</span>
          </div>
        </div>
        <div class="terminal-wrap">
          <div id="terminal"></div>
        </div>
      </main>
    </div>
  </div>

  <script src="./static/xterm.js"></script>
  <script src="./static/xterm-addon-fit.js"></script>
  <script>
    const authPill = document.getElementById("auth-pill");
    const authMessage = document.getElementById("auth-message");
    const devicePanel = document.getElementById("device-panel");
    const deviceUrl = document.getElementById("device-url");
    const deviceCode = document.getElementById("device-code");
    const loginButton = document.getElementById("login-button");
    const refreshButton = document.getElementById("refresh-button");
    const restartButton = document.getElementById("restart-button");
    const terminalStatus = document.getElementById("terminal-status");
    const shortcutButtons = Array.from(document.querySelectorAll(".shortcut"));
    let loginSessionId = null;
    let loginPoller = null;
    let socket = null;

    function apiUrl(path) {{
      return new URL(path, window.location.href).toString();
    }}

    function wsUrl(path) {{
      const url = new URL(path, window.location.href);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      return url.toString();
    }}

    async function parseError(response) {{
      const text = await response.text();
      try {{
        const json = JSON.parse(text);
        return json.detail || json.message || text;
      }} catch (_error) {{
        return text || `Request failed with status ${{response.status}}`;
      }}
    }}

    const term = new Terminal({{
      convertEol: true,
      cursorBlink: true,
      fontFamily: '"SFMono-Regular", Consolas, monospace',
      fontSize: 14,
      theme: {{
        background: "#071713",
        foreground: "#f4f3ed",
        cursor: "#cfe7d3",
        selectionBackground: "rgba(207, 231, 211, 0.25)"
      }},
      scrollback: 5000
    }});
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(document.getElementById("terminal"));
    fitAddon.fit();

    async function refreshStatus() {{
      try {{
        const response = await fetch(apiUrl("api/auth/status"));
        if (!response.ok) throw new Error(await parseError(response));
        const data = await response.json();
        authPill.textContent = data.logged_in ? "Connected" : "Not connected";
        authMessage.textContent = data.message;
        authPill.style.color = data.logged_in ? "var(--accent)" : "var(--warn)";
        authPill.style.background = data.logged_in ? "rgba(20, 95, 104, 0.08)" : "rgba(208, 140, 96, 0.12)";
        if (data.logged_in) {{
          devicePanel.hidden = true;
        }}
      }} catch (error) {{
        authPill.textContent = "Status unavailable";
        authPill.style.color = "var(--warn)";
        authPill.style.background = "rgba(208, 140, 96, 0.12)";
        authMessage.textContent = error.message;
      }}
    }}

    async function startLogin() {{
      loginButton.disabled = true;
      try {{
        const response = await fetch(apiUrl("api/auth/login"), {{ method: "POST" }});
        if (!response.ok) throw new Error(await parseError(response));
        const data = await response.json();
        loginSessionId = data.id;
        if (data.url) {{
          deviceUrl.href = data.url;
          deviceUrl.textContent = data.url;
        }}
        if (data.code) {{
          deviceCode.textContent = data.code;
        }}
        devicePanel.hidden = false;
        authMessage.textContent = "Finish login in your browser. This page will update automatically.";
        if (loginPoller) window.clearInterval(loginPoller);
        loginPoller = window.setInterval(pollLogin, 2000);
      }} catch (error) {{
        authMessage.textContent = error.message;
      }} finally {{
        loginButton.disabled = false;
      }}
    }}

    async function pollLogin() {{
      if (!loginSessionId) return;
      try {{
        const response = await fetch(apiUrl(`api/auth/login/${{loginSessionId}}`));
        if (!response.ok) throw new Error(await parseError(response));
        const data = await response.json();
        if (data.url) {{
          deviceUrl.href = data.url;
          deviceUrl.textContent = data.url;
        }}
        if (data.code) {{
          deviceCode.textContent = data.code;
        }}
        if (data.status === "completed" || data.status === "failed" || data.status === "cancelled") {{
          window.clearInterval(loginPoller);
          loginPoller = null;
          await refreshStatus();
        }}
      }} catch (error) {{
        if (loginPoller) window.clearInterval(loginPoller);
        loginPoller = null;
        authMessage.textContent = error.message;
      }}
    }}

    async function restartTerminal() {{
      restartButton.disabled = true;
      try {{
        const response = await fetch(apiUrl("api/terminal/restart"), {{ method: "POST" }});
        if (!response.ok) throw new Error(await parseError(response));
        term.reset();
        if (socket) socket.close();
        connectTerminal();
      }} catch (error) {{
        terminalStatus.textContent = error.message;
      }} finally {{
        restartButton.disabled = false;
      }}
    }}

    function sendResize() {{
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      fitAddon.fit();
      socket.send(JSON.stringify({{
        type: "resize",
        cols: term.cols,
        rows: term.rows
      }}));
    }}

    function connectTerminal() {{
      terminalStatus.textContent = "Connecting to terminal...";
      socket = new WebSocket(wsUrl("ws/terminal"));

      socket.addEventListener("open", () => {{
        terminalStatus.textContent = "Terminal connected";
        sendResize();
      }});

      socket.addEventListener("message", (event) => {{
        try {{
          const payload = JSON.parse(event.data);
          if (payload.type === "status") {{
            terminalStatus.textContent = payload.running ? `Connected to ${{payload.cwd}}` : "Terminal stopped";
            return;
          }}
          if (payload.type === "output") {{
            term.write(payload.data);
            return;
          }}
        }} catch (_error) {{
          term.write(event.data);
        }}
      }});

      socket.addEventListener("close", () => {{
        terminalStatus.textContent = "Terminal disconnected";
      }});

      socket.addEventListener("error", () => {{
        terminalStatus.textContent = "WebSocket error";
      }});
    }}

    term.onData((data) => {{
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      socket.send(JSON.stringify({{ type: "input", data }}));
    }});

    shortcutButtons.forEach((button) => {{
      button.addEventListener("click", () => {{
        const command = button.dataset.command || "";
        if (!socket || socket.readyState !== WebSocket.OPEN) {{
          terminalStatus.textContent = "Terminal is not connected yet";
          return;
        }}
        socket.send(JSON.stringify({{ type: "input", data: command }}));
      }});
    }});

    window.addEventListener("resize", sendResize);
    loginButton.addEventListener("click", startLogin);
    refreshButton.addEventListener("click", refreshStatus);
    restartButton.addEventListener("click", restartTerminal);

    refreshStatus();
    connectTerminal();
    setTimeout(sendResize, 150);
  </script>
</body>
</html>
"""


@app.get("/health")
async def health() -> JSONResponse:
    """Expose a basic health payload."""
    auth = await manager.login_status()
    terminal = manager.terminal_status()
    return JSONResponse(
        {
            "status": "ok",
            "logged_in": auth["logged_in"],
            "workspace_dir": settings.workspace_dir,
            "codex_home": settings.codex_home,
            "terminal": terminal,
        }
    )


@app.get("/api/auth/status")
async def auth_status() -> JSONResponse:
    """Return the current Codex auth state."""
    return JSONResponse(await manager.login_status())


@app.post("/api/auth/login")
async def auth_login() -> JSONResponse:
    """Start a new device auth login flow."""
    session = manager.start_login()
    for _ in range(20):
        details = await manager.get_login_session(session.id)
        if details.get("url") and details.get("code"):
            return JSONResponse(details)
        await asyncio.sleep(0.25)
    return JSONResponse(await manager.get_login_session(session.id))


@app.get("/api/auth/login/{session_id}")
async def auth_login_status(session_id: str) -> JSONResponse:
    """Inspect a running device auth flow."""
    try:
        return JSONResponse(await manager.get_login_session(session_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Login session not found") from exc


@app.post("/api/terminal/restart")
async def restart_terminal() -> JSONResponse:
    """Restart the interactive Codex PTY."""
    session = manager.restart_terminal(asyncio.get_running_loop())
    return JSONResponse(
        {
            "session_id": session.id,
            "cwd": session.cwd,
            "cols": session.cols,
            "rows": session.rows,
        }
    )


@app.websocket("/ws/terminal")
async def terminal_socket(websocket: WebSocket) -> None:
    """Bridge the browser terminal to the Codex PTY."""
    await websocket.accept()
    loop = asyncio.get_running_loop()
    try:
        queue, session = manager.subscribe_terminal(loop)
        await websocket.send_text(json.dumps({"type": "status", **manager.terminal_status()}))

        async def forward_output() -> None:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                await websocket.send_text(json.dumps({"type": "output", "data": chunk}))

        async def receive_input() -> None:
            while True:
                message = await websocket.receive_text()
                payload = json.loads(message)
                kind = payload.get("type")
                if kind == "input":
                    manager.write_terminal(payload.get("data", ""))
                elif kind == "resize":
                    manager.resize_terminal(
                        int(payload.get("cols", settings.terminal_cols)),
                        int(payload.get("rows", settings.terminal_rows)),
                    )

        sender = asyncio.create_task(forward_output())
        receiver = asyncio.create_task(receive_input())
        done, pending = await asyncio.wait(
            {sender, receiver},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            task.result()
    except WebSocketDisconnect:
        pass
    finally:
        if "queue" in locals():
            manager.unsubscribe_terminal(queue)
