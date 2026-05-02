"""Main FastAPI application for the Codex Home Assistant add-on."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager, suppress
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
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Codex Terminal</title>
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="./static/xterm.css">
  <style>
    :root {
      --terminal-background: #06120f;
      --terminal-foreground: #f4f3ed;
    }
    * {
      box-sizing: border-box;
    }
    html,
    body {
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: var(--terminal-background);
    }
    body {
      position: fixed;
      inset: 0;
      color: var(--terminal-foreground);
      font-family: "SFMono-Regular", Consolas, monospace;
      overscroll-behavior: none;
      touch-action: manipulation;
    }
    #terminal {
      position: fixed;
      inset: 0;
      width: 100%;
      height: 100%;
      padding:
        env(safe-area-inset-top)
        env(safe-area-inset-right)
        env(safe-area-inset-bottom)
        env(safe-area-inset-left);
      background: var(--terminal-background);
    }
    .xterm {
      height: 100%;
      padding: 10px;
    }
    .xterm-viewport,
    .xterm-screen {
      width: 100% !important;
    }
  </style>
</head>
<body>
  <div id="terminal"></div>

  <script src="./static/xterm.js"></script>
  <script src="./static/xterm-addon-fit.js"></script>
  <script>
    let socket = null;
    let resizeTimer = null;

    function wsUrl(path) {
      const url = new URL(path, window.location.href);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      return url.toString();
    }

    const term = new Terminal({
      convertEol: true,
      cursorBlink: true,
      fontFamily: '"SFMono-Regular", Consolas, monospace',
      fontSize: window.matchMedia("(max-width: 600px)").matches ? 12 : 14,
      letterSpacing: 0,
      theme: {
        background: "#06120f",
        foreground: "#f4f3ed",
        cursor: "#cfe7d3",
        selectionBackground: "rgba(207, 231, 211, 0.25)"
      },
      scrollback: 5000
    });
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(document.getElementById("terminal"));

    function fitAndResize() {
      fitAddon.fit();
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      socket.send(JSON.stringify({
        type: "resize",
        cols: term.cols,
        rows: term.rows
      }));
    }

    function scheduleResize() {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(fitAndResize, 60);
    }

    function connectTerminal() {
      socket = new WebSocket(wsUrl("ws/terminal"));

      socket.addEventListener("open", fitAndResize);

      socket.addEventListener("message", (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "status") {
            return;
          }
          if (payload.type === "output") {
            term.write(payload.data);
            return;
          }
        } catch (_error) {
          term.write(event.data);
        }
      });

      socket.addEventListener("close", () => {
        window.setTimeout(connectTerminal, 1500);
      });
    }

    term.onData((data) => {
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      socket.send(JSON.stringify({ type: "input", data }));
    });

    window.addEventListener("resize", scheduleResize);
    window.visualViewport?.addEventListener("resize", scheduleResize);
    window.visualViewport?.addEventListener("scroll", scheduleResize);

    connectTerminal();
    fitAndResize();
    setTimeout(fitAndResize, 150);
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
            try:
                while True:
                    chunk = await queue.get()
                    if chunk is None:
                        break
                    await websocket.send_text(json.dumps({"type": "output", "data": chunk}))
            except (RuntimeError, WebSocketDisconnect):
                pass

        async def receive_input() -> None:
            try:
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
            except WebSocketDisconnect:
                pass

        sender = asyncio.create_task(forward_output())
        receiver = asyncio.create_task(receive_input())
        done, pending = await asyncio.wait(
            {sender, receiver},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in pending:
            with suppress(asyncio.CancelledError):
                await task
        for task in done:
            with suppress(RuntimeError, WebSocketDisconnect):
                task.result()
    except WebSocketDisconnect:
        pass
    finally:
        if "queue" in locals():
            manager.unsubscribe_terminal(queue)
