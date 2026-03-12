"""Main FastAPI application for the Codex Home Assistant add-on."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .codex_manager import CodexManager, strip_ansi
from .config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
manager = CodexManager(settings)


class PromptRequest(BaseModel):
    """Request body for prompt execution."""

    prompt: str = Field(..., min_length=1)
    cwd: str | None = None
    model: str | None = None
    sandbox_mode: str | None = None
    approval_policy: str | None = None
    web_search: bool | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting Codex Home Assistant add-on")
    settings.codex_home_path.mkdir(parents=True, exist_ok=True)
    settings.workspace_path.mkdir(parents=True, exist_ok=True)
    yield
    logger.info("Stopping Codex Home Assistant add-on")


app = FastAPI(
    title="Codex CLI Add-on",
    description="Run the Codex CLI inside Home Assistant and sign in with OpenAI device auth.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def root() -> str:
    """Serve the built-in ingress UI."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex CLI</title>
  <style>
    :root {{
      --bg: #f3efe6;
      --card: rgba(255, 252, 245, 0.88);
      --ink: #1c241f;
      --muted: #5d655f;
      --accent: #135d66;
      --warn: #8a4b28;
      --border: rgba(28, 36, 31, 0.1);
      --shadow: 0 24px 70px rgba(29, 40, 32, 0.14);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(208, 140, 96, 0.22), transparent 35%),
        radial-gradient(circle at right, rgba(19, 93, 102, 0.15), transparent 30%),
        linear-gradient(180deg, #f7f4eb 0%, var(--bg) 100%);
    }}
    .shell {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 24px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.3fr 0.9fr;
      gap: 20px;
      align-items: stretch;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .intro, .auth-card, .panel {{
      padding: 24px;
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 0.72rem;
      color: var(--accent);
      margin-bottom: 14px;
      font-weight: 700;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2rem, 4vw, 3.7rem);
      line-height: 0.95;
      font-weight: 800;
      max-width: 10ch;
    }}
    h2 {{
      margin-top: 0;
      margin-bottom: 10px;
      font-size: 1.15rem;
    }}
    p {{
      color: var(--muted);
      line-height: 1.6;
    }}
    .auth-card {{
      display: flex;
      flex-direction: column;
      gap: 16px;
      justify-content: center;
    }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      width: fit-content;
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(19, 93, 102, 0.08);
      color: var(--accent);
      font-weight: 700;
    }}
    .status-pill::before {{
      content: "";
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: currentColor;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }}
    button, input, textarea {{
      font: inherit;
    }}
    button {{
      border: 0;
      border-radius: 14px;
      padding: 12px 18px;
      font-weight: 700;
      cursor: pointer;
      transition: transform 160ms ease, opacity 160ms ease;
    }}
    button:hover {{
      transform: translateY(-1px);
    }}
    button:disabled {{
      opacity: 0.55;
      cursor: not-allowed;
      transform: none;
    }}
    .primary {{
      background: var(--accent);
      color: white;
    }}
    .secondary {{
      background: rgba(19, 93, 102, 0.1);
      color: var(--accent);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 20px;
      margin-top: 20px;
    }}
    .code {{
      margin: 0;
      padding: 16px;
      border-radius: 18px;
      background: #18231f;
      color: #f5f3ee;
      min-height: 110px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-family: "SFMono-Regular", "Cascadia Code", monospace;
    }}
    .device-code {{
      font-size: 2rem;
      letter-spacing: 0.18em;
      font-weight: 800;
      margin: 8px 0 0;
    }}
    label {{
      display: block;
      margin-bottom: 8px;
      font-size: 0.9rem;
      font-weight: 700;
      color: var(--muted);
    }}
    textarea, input {{
      width: 100%;
      border: 1px solid rgba(19, 93, 102, 0.18);
      border-radius: 16px;
      padding: 14px;
      background: rgba(255, 255, 255, 0.9);
      color: var(--ink);
    }}
    textarea {{
      min-height: 180px;
      resize: vertical;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin-top: 16px;
    }}
    .tiny {{
      font-size: 0.88rem;
      color: var(--muted);
    }}
    .stream {{
      min-height: 420px;
      max-height: 62vh;
      overflow: auto;
    }}
    a {{ color: var(--accent); }}
    code {{
      background: rgba(19, 93, 102, 0.08);
      padding: 0.15rem 0.35rem;
      border-radius: 0.4rem;
    }}
    @media (max-width: 900px) {{
      .hero, .grid, .meta {{
        grid-template-columns: 1fr;
      }}
      .shell {{
        padding: 16px;
      }}
      .device-code {{
        font-size: 1.6rem;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <article class="card intro">
        <div class="eyebrow">Home Assistant Add-on</div>
        <h1>Codex in your sidebar.</h1>
        <p>
          Sign in with OpenAI device auth, keep the Codex session persisted in <code>{settings.codex_home}</code>,
          and run prompts against your Home Assistant config or shared folders without leaving Home Assistant.
        </p>
        <p class="tiny">
          Default workspace: <code>{settings.workspace_dir}</code> |
          Default sandbox: <code>{settings.sandbox_mode}</code> |
          Default approval policy: <code>{settings.approval_policy}</code>
        </p>
      </article>
      <aside class="card auth-card">
        <div class="status-pill" id="auth-pill">Checking login...</div>
        <div id="auth-message" class="tiny"></div>
        <div class="actions">
          <button id="login-button" class="primary">Connect with OpenAI</button>
          <button id="refresh-button" class="secondary">Refresh status</button>
        </div>
        <div id="device-panel" hidden>
          <div class="tiny">Verification URL</div>
          <p><a id="device-url" href="#" target="_blank" rel="noreferrer"></a></p>
          <div class="tiny">One-time code</div>
          <div id="device-code" class="device-code">....-.....</div>
        </div>
      </aside>
    </section>

    <section class="grid">
      <article class="card panel">
        <h2>Run a prompt</h2>
        <label for="prompt">Prompt</label>
        <textarea id="prompt" placeholder="Explain this automation, refactor YAML, or review a script in /config."></textarea>
        <div class="meta">
          <div>
            <label for="cwd">Working directory</label>
            <input id="cwd" value="{settings.workspace_dir}" />
          </div>
          <div>
            <label for="model">Model (optional)</label>
            <input id="model" value="{settings.model}" placeholder="Use Codex default if blank" />
          </div>
        </div>
        <div class="actions" style="margin-top: 16px;">
          <button id="run-button" class="primary">Run Codex</button>
        </div>
      </article>

      <article class="card panel">
        <h2>CLI output</h2>
        <pre id="output" class="code stream">Waiting for a prompt...</pre>
      </article>
    </section>
  </div>

  <script>
    const authPill = document.getElementById("auth-pill");
    const authMessage = document.getElementById("auth-message");
    const devicePanel = document.getElementById("device-panel");
    const deviceUrl = document.getElementById("device-url");
    const deviceCode = document.getElementById("device-code");
    const loginButton = document.getElementById("login-button");
    const refreshButton = document.getElementById("refresh-button");
    const runButton = document.getElementById("run-button");
    const promptInput = document.getElementById("prompt");
    const cwdInput = document.getElementById("cwd");
    const modelInput = document.getElementById("model");
    const output = document.getElementById("output");
    let loginSessionId = null;
    let loginPoller = null;

    function apiUrl(path) {{
      return new URL(path, window.location.href).toString();
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

    async function refreshStatus() {{
      try {{
        const response = await fetch(apiUrl("api/auth/status"));
        if (!response.ok) {{
          throw new Error(await parseError(response));
        }}
        const data = await response.json();
        authPill.textContent = data.logged_in ? "Connected" : "Not connected";
        authMessage.textContent = data.message;
        authPill.style.color = data.logged_in ? "var(--accent)" : "var(--warn)";
        authPill.style.background = data.logged_in ? "rgba(19, 93, 102, 0.08)" : "rgba(208, 140, 96, 0.12)";
        if (data.logged_in) {{
          devicePanel.hidden = true;
        }}
      }} catch (error) {{
        authPill.textContent = "Status unavailable";
        authMessage.textContent = error.message;
        authPill.style.color = "var(--warn)";
        authPill.style.background = "rgba(208, 140, 96, 0.12)";
      }}
    }}

    async function startLogin() {{
      loginButton.disabled = true;
      try {{
        const response = await fetch(apiUrl("api/auth/login"), {{ method: "POST" }});
        if (!response.ok) {{
          throw new Error(await parseError(response));
        }}
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
        if (loginPoller) {{
          window.clearInterval(loginPoller);
        }}
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
        if (!response.ok) {{
          throw new Error(await parseError(response));
        }}
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
        if (loginPoller) {{
          window.clearInterval(loginPoller);
          loginPoller = null;
        }}
        authMessage.textContent = error.message;
      }}
    }}

    async function runPrompt() {{
      const prompt = promptInput.value.trim();
      if (!prompt) return;
      runButton.disabled = true;
      output.textContent = "";
      try {{
        const response = await fetch(apiUrl("api/exec"), {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{
            prompt,
            cwd: cwdInput.value.trim() || null,
            model: modelInput.value.trim() || null
          }})
        }});
        if (!response.ok || !response.body) {{
          throw new Error(await parseError(response));
        }}

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        while (true) {{
          const {{ value, done }} = await reader.read();
          if (done) break;
          output.textContent += decoder.decode(value, {{ stream: true }});
          output.scrollTop = output.scrollHeight;
        }}
      }} catch (error) {{
        output.textContent = error.message;
      }} finally {{
        runButton.disabled = false;
      }}
    }}

    loginButton.addEventListener("click", startLogin);
    refreshButton.addEventListener("click", refreshStatus);
    runButton.addEventListener("click", runPrompt);
    refreshStatus();
  </script>
</body>
</html>
"""


@app.get("/health")
async def health() -> JSONResponse:
    """Expose a basic health payload."""
    auth = await manager.login_status()
    return JSONResponse(
        {
            "status": "ok",
            "logged_in": auth["logged_in"],
            "workspace_dir": settings.workspace_dir,
            "codex_home": settings.codex_home,
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


@app.delete("/api/auth/login/{session_id}")
async def auth_login_cancel(session_id: str) -> JSONResponse:
    """Cancel a running device auth flow."""
    if not manager.cancel_login(session_id):
        raise HTTPException(status_code=404, detail="Login session not found")
    return JSONResponse({"ok": True})


@app.post("/api/exec")
async def exec_prompt(payload: PromptRequest) -> StreamingResponse:
    """Stream Codex CLI output for a single prompt."""
    auth = await manager.login_status()
    if not auth["logged_in"]:
        raise HTTPException(
            status_code=409,
            detail="Codex is not logged in. Start device auth first.",
        )

    try:
        command, workdir = manager.build_exec_command(
            prompt=payload.prompt,
            cwd=payload.cwd,
            model=payload.model,
            sandbox_mode=payload.sandbox_mode,
            approval_policy=payload.approval_policy,
            web_search=payload.web_search,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def stream() -> AsyncIterator[str]:
        logger.info("Running Codex prompt in %s", workdir)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=manager._base_env(),
        )
        assert process.stdout is not None
        while True:
            chunk = await process.stdout.read(1024)
            if not chunk:
                break
            yield strip_ansi(chunk.decode("utf-8", errors="replace"))

        returncode = await process.wait()
        if returncode != 0:
            yield f"\\n\\n[Codex exited with status {returncode}]"

    return StreamingResponse(stream(), media_type="text/plain; charset=utf-8")
