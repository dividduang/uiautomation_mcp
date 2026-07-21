# -*- coding: utf-8 -*-
"""MCP tool: interactive UI control picker (non-blocking).

Launch chain (Windows)::

    MCP server
      → Popen(DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
        → pythonw.exe -m uiautomation_mcp.picker_gui --result-file ...

``pythonw.exe`` has no console, so no black window flashes.
``DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`` fully detaches from the
MCP server's (possibly hidden) process tree / window station.

``ui_interactive_pick`` returns immediately with a pick_id.
``ui_pick_result`` polls the result file written by the GUI process.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

PICKER_MODULE = "uiautomation_mcp.picker_gui"

# In-flight pickers keyed by pick_id.
_pickers: dict[str, dict] = {}


def _error(code: str, message: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message}}


def _windows_pythonw(python: Path) -> Path:
    """Prefer pythonw.exe next to the given interpreter (no console)."""
    candidate = python.with_name("pythonw.exe")
    return candidate if candidate.is_file() else python


def register_picker_tools(mcp: FastMCP):
    """Register the interactive picker tools with the MCP server."""

    @mcp.tool()
    def ui_interactive_pick(
        delay_seconds: int = 3,
        max_ancestors: int = 0,
    ) -> dict:
        """Launch the interactive picker window (non-blocking).

        Pops up a topmost tkinter window guiding the user to point the
        mouse at target controls. Returns immediately with a ``pick_id``.
        Use ``ui_pick_result(pick_id)`` to retrieve the captures once the
        user clicks "完成" (Finish).

        Args:
            delay_seconds: Countdown seconds before each capture (default 3).
            max_ancestors: Max ancestor levels above the target to record;
                0 or negative means record the whole chain (default 0 = all).

        Returns:
            {"success": True, "pick_id": "...", "message": "..."}
        """
        pick_id = uuid.uuid4().hex[:8]
        tmp_dir = Path(tempfile.gettempdir())
        out_file = tmp_dir / f"uiamcp_pick_{pick_id}.json"
        err_file = tmp_dir / f"uiamcp_pick_{pick_id}.err"

        # Remove any leftover result so we don't read a stale one.
        try:
            out_file.unlink(missing_ok=True)
        except OSError:
            pass

        python = Path(sys.executable)
        if os.name == "nt":
            python = _windows_pythonw(python)

        cmd = [
            str(python),
            "-m",
            PICKER_MODULE,
            "--delay",
            str(delay_seconds),
            "--result-file",
            str(out_file),
        ]
        if max_ancestors and max_ancestors > 0:
            cmd += ["--max-ancestors", str(max_ancestors)]

        logger.info("Launching picker (pick_id=%s): %s", pick_id, " ".join(cmd))

        try:
            err_fh = err_file.open("ab", buffering=0)
            kwargs: dict = {
                "stdin": subprocess.DEVNULL,
                "stdout": err_fh,   # pythonw has no stdout; log there just in case
                "stderr": subprocess.STDOUT,
                "close_fds": True,
            }
            if os.name == "nt":
                # Match the proven mcp-tkinter-launcher pattern.
                kwargs["creationflags"] = (
                    subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                kwargs["start_new_session"] = True

            proc = subprocess.Popen(cmd, **kwargs)
            # Parent no longer needs the handle; child keeps the fd.
            err_fh.close()
        except Exception as e:  # noqa: BLE001
            logger.exception("ui_interactive_pick failed to launch")
            return _error("INTERNAL_ERROR", str(e))

        _pickers[pick_id] = {
            "proc": proc,
            "out_file": str(out_file),
            "err_file": str(err_file),
            "started": time.time(),
        }

        return {
            "success": True,
            "pick_id": pick_id,
            "message": (
                "Picker window launched. The user should capture controls "
                "and click '完成'. Call ui_pick_result(pick_id) to get results."
            ),
        }

    @mcp.tool()
    def ui_pick_result(
        pick_id: str,
        timeout_seconds: int = 5,
    ) -> dict:
        """Get the result of a previously launched interactive picker.

        If the picker is still running and timeout_seconds > 0, waits up to
        that many seconds for it to finish. Use timeout_seconds=0 to just
        check status without waiting.

        Args:
            pick_id: The pick_id returned by ui_interactive_pick.
            timeout_seconds: Max seconds to wait (default 5, 0 = no wait).

        Returns:
            - If still running: {"success": True, "status": "running", ...}
            - If finished: {"success": True, "status": "done", "data": {...}}
            - If error: {"success": False, "error": {...}}
        """
        entry = _pickers.get(pick_id)
        if not entry:
            return _error(
                "INVALID_PICK_ID",
                f"No picker found with pick_id={pick_id!r}. "
                f"Active pickers: {list(_pickers.keys())}",
            )

        proc: subprocess.Popen = entry["proc"]
        out_file = Path(entry["out_file"])
        err_file = Path(entry["err_file"])

        deadline = time.time() + max(0, timeout_seconds)
        while True:
            # Result file written by picker_gui on finish — preferred signal.
            if out_file.is_file() and out_file.stat().st_size > 0:
                break
            # Process exited without writing a file.
            if proc.poll() is not None:
                break
            if time.time() >= deadline:
                break
            time.sleep(0.2)

        # Still no result and process alive?
        if (not out_file.is_file() or out_file.stat().st_size == 0) and proc.poll() is None:
            elapsed = int(time.time() - entry["started"])
            return {
                "success": True,
                "status": "running",
                "pick_id": pick_id,
                "elapsed_seconds": elapsed,
                "message": (
                    "Picker is still running. The user hasn't clicked '完成' yet. "
                    "Call ui_pick_result again later."
                ),
            }

        # Read stderr/log
        stderr = ""
        if err_file.is_file():
            try:
                stderr = err_file.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:  # noqa: BLE001
                pass
        if stderr:
            logger.debug("picker log:\n%s", stderr)

        # Read result
        stdout = ""
        if out_file.is_file():
            try:
                stdout = out_file.read_text(encoding="utf-8").strip()
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to read picker output: %s", e)

        # Clean up
        for f in [out_file, err_file]:
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
        _pickers.pop(pick_id, None)

        if not stdout:
            return _error(
                "NO_OUTPUT",
                "Picker produced no JSON. log: " + (stderr[-500:] or "<empty>"),
            )

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse picker JSON: %s", e)
            return _error(
                "PARSE_ERROR",
                f"Invalid JSON from picker: {e}. Raw: {stdout[:500]}",
            )

        return {"success": True, "status": "done", "pick_id": pick_id, "data": data}
