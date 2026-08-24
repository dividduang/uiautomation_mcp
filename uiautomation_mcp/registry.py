# -*- coding: utf-8 -*-
"""Cross-process control registry for CLI mode.

MCP mode keeps :class:`uiautomation.Control` objects alive in the server's
memory, so a token handed out by one tool call can be resolved by the next
call within the same session. A CLI invocation, however, is a fresh process
every time — an in-memory registry dies with it.

This module persists the token → control map to a JSON file
(``~/.uiautomation/registry.json``) and rebuilds the :class:`Control` on
demand using two strategies, in order:

1. **Native handle** — ``ControlFromHandle(handle)``. Fast, but controls
   from UWP / Chrome / Qt often report ``handle == 0`` and can't be found.
2. **Ancestor path** — a chain of selectors (controlType / name /
   automationId / className / sibling index) recorded when the control was
   registered. The control is re-located by walking the chain from the
   desktop root, mirroring how ``ui_find_control`` searches.

Tokens expire after ``TTL`` seconds of inactivity, so stale entries don't
accumulate (SAP sessions, windows being closed, etc.).
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import uiautomation as auto

logger = logging.getLogger(__name__)

#: Where the registry file lives.
REGISTRY_DIR = Path.home() / ".uiautomation"
REGISTRY_FILE = REGISTRY_DIR / "registry.json"

#: Tokens older than this (seconds) are considered expired.
TTL = 300
#: Keep at most this many entries; oldest are evicted first.
MAX_ENTRIES = 500

_lock = threading.Lock()
#: In-process cache: token -> (Control, last_access_ts). Speeds up REPL sessions.
_cache: Dict[str, tuple] = {}


def _load() -> Dict[str, Any]:
    """Read the registry file, returning an empty dict on any failure."""
    try:
        if REGISTRY_FILE.is_file():
            return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to load registry file %s: %s", REGISTRY_FILE, e)
    return {}


def _save(data: Dict[str, Any]) -> None:
    """Atomically write the registry file."""
    try:
        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        tmp = REGISTRY_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(REGISTRY_FILE)
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to write registry file %s: %s", REGISTRY_FILE, e)


def _selector_for(control: auto.Control, index: int) -> Dict[str, Any]:
    """Build a selector dict that can re-locate this control among its siblings."""
    sel: Dict[str, Any] = {}
    if control.ControlTypeName:
        sel["controlType"] = control.ControlTypeName
    if control.Name:
        sel["name"] = control.Name
    if control.AutomationId:
        sel["automationId"] = control.AutomationId
    if control.ClassName:
        sel["className"] = control.ClassName
    if index > 1:  # only record non-trivial index
        sel["index"] = index
    return sel


def _build_path(control: auto.Control) -> List[Dict[str, Any]]:
    """Record the ancestor chain of *control*, top-level window first.

    Returns a list of selector dicts; the last one describes *control*
    itself. A sibling index is recorded per level so ambiguous names
    (e.g. several buttons named "OK") still resolve.
    """
    chain: List[Dict[str, Any]] = []
    current: Optional[auto.Control] = control
    while current is not None:
        try:
            parent = current.GetParent()
        except Exception:  # noqa: BLE001
            parent = None

        index = 1
        if parent is not None:
            try:
                siblings = parent.GetChildren()
                for i, sib in enumerate(siblings, start=1):
                    if sib == current:
                        index = i
                        break
            except Exception:  # noqa: BLE001
                pass

        chain.append(_selector_for(current, index))
        if parent is None:
            break
        current = parent

    # chain is [self, ..., root]; reverse to walk root -> self
    chain.reverse()
    return chain


def _control_from_selector(parent: auto.Control, sel: Dict[str, Any]) -> Optional[auto.Control]:
    """Find one child of *parent* matching *sel* (or a top-level window when parent is root)."""
    params: Dict[str, Any] = {}
    if sel.get("controlType"):
        # Must be the ControlType enum, not the class (e.g. auto.EditControl).
        ctrl_type = getattr(auto.ControlType, sel["controlType"], None)
        if ctrl_type is not None:
            params["ControlType"] = ctrl_type
    if sel.get("name"):
        params["Name"] = sel["name"]
    if sel.get("automationId"):
        params["AutomationId"] = sel["automationId"]
    if sel.get("className"):
        params["ClassName"] = sel["className"]
    if sel.get("index", 1) > 1:
        params["foundIndex"] = sel["index"]
    params["searchFromControl"] = parent
    try:
        return auto.Control(**params)
    except Exception as e:  # noqa: BLE001
        logger.debug("Control lookup failed for %s: %s", sel, e)
        return None


def _restore_from_path(path: List[Dict[str, Any]]) -> Optional[auto.Control]:
    """Re-locate a control by walking its ancestor path from the desktop root."""
    if not path:
        return None
    parent = auto.GetRootControl()
    for sel in path:
        ctrl = _control_from_selector(parent, sel)
        try:
            if ctrl is None or not ctrl.Exists(0, 0):
                return None
        except Exception:  # noqa: BLE001
            return None
        parent = ctrl
    return parent


def _restore(entry: Dict[str, Any]) -> Optional[auto.Control]:
    """Try to rebuild a Control object from a registry entry."""
    handle = entry.get("handle") or 0
    if handle:
        try:
            ctrl = auto.ControlFromHandle(handle)
            if ctrl is not None and ctrl.Exists(0, 0):
                return ctrl
        except Exception:  # noqa: BLE001
            pass

    path = entry.get("path") or []
    if path:
        try:
            ctrl = _restore_from_path(path)
            if ctrl is not None:
                return ctrl
        except Exception as e:  # noqa: BLE001
            logger.debug("Path restore failed: %s", e)
    return None


def register_control(control: auto.Control) -> str:
    """Register a control, persist it to the registry file, and return its token."""
    token = str(uuid.uuid4())[:8]

    with _lock:
        data = _load()
        entries = data.setdefault("tokens", {})
        now = time.time()

        # Evict expired + over-capacity entries.
        for tok in [t for t, e in entries.items() if now - e.get("lastAccess", 0) > TTL]:
            del entries[tok]
        while len(entries) >= MAX_ENTRIES:
            oldest = min(entries, key=lambda t: entries[t].get("lastAccess", 0))
            del entries[oldest]

        try:
            handle = control.NativeWindowHandle or 0
        except Exception:  # noqa: BLE001
            handle = 0

        try:
            path = _build_path(control)
        except Exception as e:  # noqa: BLE001
            logger.debug("Path build failed for handle=%s: %s", handle, e)
            path = []

        entry = {
            "handle": handle,
            "name": getattr(control, "Name", "") or "",
            "controlType": getattr(control, "ControlTypeName", "") or "",
            "processId": getattr(control, "ProcessId", 0) or 0,
            "path": path,
            "createdAt": now,
            "lastAccess": now,
        }
        entries[token] = entry
        _save(data)

    _cache[token] = (control, now)
    return token


def get_control_by_token(token: str) -> Optional[auto.Control]:
    """Resolve a token to a live Control object.

    Checks the in-process cache first, then the persistent registry file.
    Returns ``None`` (and drops the entry) if the control can no longer be
    found — the caller should report it as stale and suggest re-finding it.
    """
    now = time.time()

    # 1. In-process cache.
    cached = _cache.get(token)
    if cached is not None:
        ctrl, ts = cached
        if now - ts <= TTL:
            try:
                if ctrl.Exists(0, 0):
                    _cache[token] = (ctrl, now)
                    return ctrl
            except Exception:  # noqa: BLE001
                pass
        _cache.pop(token, None)

    # 2. Persistent registry.
    with _lock:
        data = _load()
        entries = data.get("tokens", {})
        entry = entries.get(token)
        if entry is None:
            return None
        if now - entry.get("lastAccess", 0) > TTL:
            del entries[token]
            _save(data)
            return None

        ctrl = _restore(entry)
        if ctrl is None:
            del entries[token]
            _save(data)
            return None

        entry["lastAccess"] = now
        _save(data)
        _cache[token] = (ctrl, now)
        return ctrl


def list_tokens() -> List[Dict[str, Any]]:
    """Return a human-readable summary of all live registry entries."""
    with _lock:
        data = _load()
        entries = data.get("tokens", {})
        now = time.time()
        result = []
        for token, e in entries.items():
            if now - e.get("lastAccess", 0) > TTL:
                continue
            result.append({
                "token": token,
                "name": e.get("name", ""),
                "controlType": e.get("controlType", ""),
                "handle": e.get("handle", 0),
                "processId": e.get("processId", 0),
                "ageSeconds": int(now - e.get("lastAccess", now)),
            })
        return result


def clear() -> int:
    """Remove all entries. Returns how many were removed."""
    with _lock:
        data = _load()
        entries = data.get("tokens", {})
        count = len(entries)
        entries.clear()
        _save(data)
    _cache.clear()
    return count
