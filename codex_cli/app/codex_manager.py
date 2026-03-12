"""Helpers for managing Codex CLI auth and prompt execution."""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import Settings

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
DEVICE_URL_RE = re.compile(r"https://auth\.openai\.com/\S+")
DEVICE_CODE_RE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{5}\b")


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


class CodexManager:
    """Wraps the Codex CLI for add-on use."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()
        self._login_sessions: dict[str, LoginSession] = {}

    def _base_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["CODEX_HOME"] = str(self.settings.codex_home_path)
        env.setdefault("HOME", "/data")
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

    def build_exec_command(
        self,
        prompt: str,
        cwd: str | None = None,
        model: str | None = None,
        sandbox_mode: str | None = None,
        approval_policy: str | None = None,
        web_search: bool | None = None,
    ) -> tuple[list[str], Path]:
        """Build a Codex exec invocation for the supplied request."""
        workdir = Path(cwd or self.settings.workspace_dir).expanduser()
        if not workdir.exists():
            raise FileNotFoundError(f"Workspace does not exist: {workdir}")

        command = ["codex"]
        selected_approval = approval_policy or self.settings.approval_policy
        if selected_approval:
            command.extend(["-a", selected_approval])

        if web_search if web_search is not None else self.settings.enable_web_search:
            command.append("--search")

        command.extend(
            [
                "exec",
                "--skip-git-repo-check",
                "--color",
                "never",
                "--sandbox",
                sandbox_mode or self.settings.sandbox_mode,
            ]
        )

        selected_model = model if model is not None else self.settings.model
        if selected_model:
            command.extend(["-m", selected_model])
        command.append(prompt)
        return command, workdir
