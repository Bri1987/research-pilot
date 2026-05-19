from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = PROJECT_ROOT / "data" / "outputs" / "agent_bridge"
TASKS_DIR = BRIDGE_DIR / "tasks"


class AgentBridgeError(RuntimeError):
    pass


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(value or ""))[:80] or "task"


def _command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def _task_paths(task_id: str) -> dict[str, Path]:
    task_dir = TASKS_DIR / task_id
    return {
        "task_dir": task_dir,
        "task_json": task_dir / "task.json",
        "prompt": task_dir / "prompt.md",
        "result": task_dir / "result.md",
        "stderr": task_dir / "stderr.log",
    }


def queue_agent_task(
    *,
    task_type: str,
    prompt: str,
    provider: str = "codex",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = f"{stamp}_{_safe_name(task_type)}_{uuid4().hex[:8]}"
    paths = _task_paths(task_id)
    paths["task_dir"].mkdir(parents=True, exist_ok=True)
    paths["prompt"].write_text(prompt, encoding="utf-8")
    task = {
        "task_id": task_id,
        "task_type": task_type,
        "provider": provider,
        "status": "queued",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "prompt_path": str(paths["prompt"]),
        "result_path": str(paths["result"]),
        "stderr_path": str(paths["stderr"]),
        "payload": payload or {},
    }
    paths["task_json"].write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    return task


def _update_task(task: dict[str, Any], **updates: Any) -> dict[str, Any]:
    task = {**task, **updates, "updated_at": datetime.now().isoformat(timespec="seconds")}
    paths = _task_paths(str(task["task_id"]))
    paths["task_json"].write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    return task


def _codex_command(model: str | None = None) -> list[str]:
    command = [
        "codex",
        "exec",
        "--cd",
        str(PROJECT_ROOT),
        "--sandbox",
        "read-only",
        "--ask-for-approval",
        "never",
        "--color",
        "never",
    ]
    if model:
        command.extend(["--model", model])
    command.append("-")
    return command


def _opencode_command(prompt_path: Path, model: str | None = None) -> list[str]:
    command = [
        "opencode",
        "run",
        "--dir",
        str(PROJECT_ROOT),
        "--agent",
        "research-pilot",
        "--file",
        str(prompt_path),
    ]
    if model:
        command.extend(["--model", model])
    command.append("Complete the attached ResearchPilot task. Return only the requested final output.")
    return command


def run_agent_task(
    *,
    task_type: str,
    prompt: str,
    provider: str = "codex",
    model: str | None = None,
    timeout_seconds: int = 300,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_provider = str(provider or "codex").strip().lower()
    task = queue_agent_task(
        task_type=task_type,
        prompt=prompt,
        provider=normalized_provider,
        payload=payload,
    )
    paths = _task_paths(str(task["task_id"]))
    task = _update_task(task, status="running")

    try:
        custom_command = os.getenv("RESEARCHPILOT_AGENT_COMMAND", "").strip()
        if normalized_provider == "custom":
            if not custom_command:
                raise AgentBridgeError("RESEARCHPILOT_AGENT_COMMAND is not configured.")
            command = shlex.split(custom_command)
            stdin_text = prompt
        elif normalized_provider == "codex":
            if not _command_exists("codex"):
                raise AgentBridgeError("codex CLI was not found on PATH.")
            command = _codex_command(model=model)
            stdin_text = prompt
        elif normalized_provider == "opencode":
            if not _command_exists("opencode"):
                raise AgentBridgeError("opencode CLI was not found on PATH.")
            command = _opencode_command(paths["prompt"], model=model)
            stdin_text = ""
        else:
            raise AgentBridgeError(f"Unsupported agent bridge provider: {provider}")
    except (AgentBridgeError, ValueError) as exc:
        error = str(exc)
        paths["stderr"].write_text(error, encoding="utf-8")
        _update_task(task, status="failed", error=error)
        if isinstance(exc, AgentBridgeError):
            raise
        raise AgentBridgeError(error) from exc

    try:
        completed = subprocess.run(
            command,
            input=stdin_text,
            text=True,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            timeout=max(30, int(timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        paths["stderr"].write_text(str(exc), encoding="utf-8")
        _update_task(task, status="timeout")
        raise AgentBridgeError(f"{normalized_provider} task timed out after {timeout_seconds}s.") from exc

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    paths["result"].write_text(stdout, encoding="utf-8")
    paths["stderr"].write_text(stderr, encoding="utf-8")
    status = "completed" if completed.returncode == 0 else "failed"
    task = _update_task(
        task,
        status=status,
        returncode=completed.returncode,
        command=command,
    )
    if completed.returncode != 0:
        raise AgentBridgeError(
            f"{normalized_provider} exited with code {completed.returncode}. See {paths['stderr']}."
        )
    return {
        **task,
        "output": stdout.strip(),
    }


def list_agent_tasks(limit: int = 20) -> list[dict[str, Any]]:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for task_json in sorted(TASKS_DIR.glob("*/task.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            task = json.loads(task_json.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(task, dict):
            rows.append(task)
        if len(rows) >= limit:
            break
    return rows


def agent_bridge_status() -> dict[str, Any]:
    return {
        "codex_available": _command_exists("codex"),
        "opencode_available": _command_exists("opencode"),
        "custom_command_configured": bool(os.getenv("RESEARCHPILOT_AGENT_COMMAND", "").strip()),
        "tasks_dir": str(TASKS_DIR),
    }
