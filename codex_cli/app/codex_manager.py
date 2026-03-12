"""Helpers for managing Codex CLI auth and interactive terminal sessions."""

from __future__ import annotations

import asyncio
import fcntl
import os
import pty
import re
import signal
import struct
import subprocess
import termios
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import Settings

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
DEVICE_URL_RE = re.compile(r"https://auth\.openai\.com/\S+")
DEVICE_CODE_RE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{5}\b")
BUFFER_LIMIT = 131072


def strip_ansi(text: str) -> str:
    """Remove terminal control sequences from CLI output."""
    return ANSI_RE.sub("", text)


@dataclass
class LoginSession:
    """Tracks an in-flight device auth session."""

    id: str
    process: subprocess.Popen[str]
    created_at: float = field(default_factory=time.time)
    status: str = "starting"
    url: str | None = None
    code: str | None = None
    output: list[str] = field(default_factory=list)
    returncode: int | None = None


@dataclass
class TerminalSession:
    """Tracks the interactive Codex terminal process."""

    id: str
    process: subprocess.Popen[bytes]
    master_fd: int
    cwd: str
    cols: int
    rows: int
    started_at: float = field(default_factory=time.time)
    status: str = "running"
    returncode: int | None = None
    output_buffer: str = ""


class CodexManager:
    """Wraps the Codex CLI for add-on use."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self._login_sessions: dict[str, LoginSession] = {}
        self._terminal_session: TerminalSession | None = None
        self._subscribers: set[asyncio.Queue[str | None]] = set()
        self._read_loop: asyncio.AbstractEventLoop | None = None

    def _base_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["CODEX_HOME"] = str(self.settings.codex_home_path)
        env.setdefault("HOME", "/data")
        env.setdefault("TERM", "xterm-256color")
        env.setdefault("COLORTERM", "truecolor")
        return env

    async def login_status(self) -> dict[str, str | bool]:
        """Return the current Codex login status."""
        process = await asyncio.create_subprocess_exec(
            "codex",
            "login",
            "status",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=self._base_env(),
        )
        stdout, _ = await process.communicate()
        message = strip_ansi(stdout.decode("utf-8", errors="replace")).strip()
        return {
            "logged_in": process.returncode == 0,
            "message": message,
            "auth_path": str(self.settings.codex_home_path / "auth.json"),
        }

    def start_login(self) -> LoginSession:
        """Start a device authorization flow."""
        with self._lock:
            for session in self._login_sessions.values():
                if session.process.poll() is None:
                    return session

            process = subprocess.Popen(
                ["codex", "login", "--device-auth"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=self._base_env(),
            )
            session = LoginSession(id=str(uuid.uuid4()), process=process)
            self._login_sessions[session.id] = session

            worker = threading.Thread(
                target=self._watch_login_session,
                args=(session.id,),
                daemon=True,
            )
            worker.start()
            return session

    def _watch_login_session(self, session_id: str) -> None:
        session = self._login_sessions[session_id]
        assert session.process.stdout is not None

        for raw_line in session.process.stdout:
            line = strip_ansi(raw_line).rstrip()
            if not line:
                continue
            session.output.append(line)

            if session.url is None:
                match = DEVICE_URL_RE.search(line)
                if match:
                    session.url = match.group(0)

            if session.code is None:
                match = DEVICE_CODE_RE.search(line)
                if match:
                    session.code = match.group(0)

            if session.url and session.code:
                session.status = "waiting_for_browser"

        session.returncode = session.process.wait()
        if session.returncode == 0:
            session.status = "completed"
        elif session.status == "cancelled":
            session.status = "cancelled"
        else:
            session.status = "failed"

    async def get_login_session(self, session_id: str) -> dict[str, object]:
        """Return session details for the given login attempt."""
        session = self._login_sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)

        result: dict[str, object] = {
            "id": session.id,
            "status": session.status,
            "url": session.url,
            "code": session.code,
            "returncode": session.returncode,
            "output": session.output[-20:],
        }
        if session.status == "completed":
            result["login"] = await self.login_status()
        return result

    def cancel_login(self, session_id: str) -> bool:
        """Cancel a pending device auth process."""
        session = self._login_sessions.get(session_id)
        if session is None:
            return False
        if session.process.poll() is None:
            session.status = "cancelled"
            session.process.terminate()
        return True

    def _build_terminal_command(self, cwd: str) -> list[str]:
        command = ["codex"]
        if self.settings.approval_policy:
            command.extend(["-a", self.settings.approval_policy])
        if self.settings.sandbox_mode:
            command.extend(["-s", self.settings.sandbox_mode])
        if self.settings.enable_web_search:
            command.append("--search")
        if self.settings.model:
            command.extend(["-m", self.settings.model])
        command.extend(["-C", cwd, "--no-alt-screen"])
        return command

    def _set_winsize(self, master_fd: int, rows: int, cols: int) -> None:
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

    def ensure_terminal(self, loop: asyncio.AbstractEventLoop) -> TerminalSession:
        """Start the Codex PTY if needed and return the active session."""
        with self._lock:
            if self._terminal_session and self._terminal_session.process.poll() is None:
                self._read_loop = loop
                return self._terminal_session

            cwd = str(self.settings.workspace_path)
            master_fd, slave_fd = pty.openpty()
            self._set_winsize(master_fd, self.settings.terminal_rows, self.settings.terminal_cols)
            env = self._base_env()
            env["COLUMNS"] = str(self.settings.terminal_cols)
            env["LINES"] = str(self.settings.terminal_rows)

            process = subprocess.Popen(
                self._build_terminal_command(cwd),
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=cwd,
                env=env,
                preexec_fn=os.setsid,
            )
            os.close(slave_fd)
            os.set_blocking(master_fd, False)

            session = TerminalSession(
                id=str(uuid.uuid4()),
                process=process,
                master_fd=master_fd,
                cwd=cwd,
                cols=self.settings.terminal_cols,
                rows=self.settings.terminal_rows,
            )
            self._terminal_session = session
            self._read_loop = loop
            reader = threading.Thread(target=self._read_terminal_output, args=(session,), daemon=True)
            reader.start()
            return session

    def _broadcast(self, chunk: str | None) -> None:
        loop = self._read_loop
        if loop is None:
            return
        for queue in list(self._subscribers):
            loop.call_soon_threadsafe(queue.put_nowait, chunk)

    def _read_terminal_output(self, session: TerminalSession) -> None:
        while True:
            try:
                chunk = os.read(session.master_fd, 4096)
            except BlockingIOError:
                if session.process.poll() is not None:
                    break
                time.sleep(0.02)
                continue
            except OSError:
                break

            if chunk:
                text = chunk.decode("utf-8", errors="replace")
                session.output_buffer = (session.output_buffer + text)[-BUFFER_LIMIT:]
                self._broadcast(text)
                continue

            if session.process.poll() is not None:
                break
            time.sleep(0.02)

        session.returncode = session.process.wait()
        session.status = "exited"
        self._broadcast(f"\r\n[Codex exited with status {session.returncode}]\r\n")
        self._broadcast(None)
        try:
            os.close(session.master_fd)
        except OSError:
            pass

    def subscribe_terminal(self, loop: asyncio.AbstractEventLoop) -> tuple[asyncio.Queue[str | None], TerminalSession]:
        """Subscribe to terminal output and return the current session snapshot."""
        session = self.ensure_terminal(loop)
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._subscribers.add(queue)
        if session.output_buffer:
            queue.put_nowait(session.output_buffer)
        return queue, session

    def unsubscribe_terminal(self, queue: asyncio.Queue[str | None]) -> None:
        """Stop delivering terminal output to the given subscriber."""
        self._subscribers.discard(queue)

    def write_terminal(self, data: str) -> None:
        """Write data to the active terminal session."""
        session = self._terminal_session
        if session is None or session.process.poll() is not None:
            raise RuntimeError("Terminal session is not running")
        os.write(session.master_fd, data.encode("utf-8"))

    def resize_terminal(self, cols: int, rows: int) -> None:
        """Resize the active PTY."""
        session = self._terminal_session
        if session is None or session.process.poll() is not None:
            return
        session.cols = cols
        session.rows = rows
        self._set_winsize(session.master_fd, rows, cols)
        try:
            os.killpg(os.getpgid(session.process.pid), signal.SIGWINCH)
        except ProcessLookupError:
            return

    def terminal_status(self) -> dict[str, object]:
        """Return details about the active PTY session."""
        session = self._terminal_session
        running = session is not None and session.process.poll() is None
        return {
            "running": running,
            "session_id": session.id if session else None,
            "cwd": session.cwd if session else str(self.settings.workspace_path),
            "cols": session.cols if session else self.settings.terminal_cols,
            "rows": session.rows if session else self.settings.terminal_rows,
            "returncode": session.returncode if session else None,
        }

    def restart_terminal(self, loop: asyncio.AbstractEventLoop) -> TerminalSession:
        """Terminate the current PTY session and start a new one."""
        self.stop_terminal()
        return self.ensure_terminal(loop)

    def stop_terminal(self) -> None:
        """Stop the active PTY session."""
        with self._lock:
            session = self._terminal_session
            if session is None:
                return
            if session.process.poll() is None:
                try:
                    os.killpg(os.getpgid(session.process.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
            self._terminal_session = None

