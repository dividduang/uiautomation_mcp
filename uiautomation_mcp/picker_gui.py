# -*- coding: utf-8 -*-
"""Interactive UI control picker (lightweight Inspect.exe alternative).

A small always-on-top tkinter window that guides the user to hover over a
target control. After a countdown, it captures the control under the cursor
and its ancestor chain (walking up ``GetParentControl``), recording key
properties for each node.

Run directly::

    python -m uiautomation_mcp.picker_gui [--delay N] [--max-ancestors N]

On exit the collected results are printed to **stdout** as a single JSON
object. All human-facing logs go to **stderr** so stdout stays clean for
machine parsing by the MCP tool wrapper.
"""

import argparse
import json
import sys

# --- Constants ---------------------------------------------------------------

NAME_MAX_LEN = 200  # truncate long control names to keep output readable
DEFAULT_DELAY = 3
HIGHLIGHT_FLASHES = 3


def _log(msg: str) -> None:
    """Write a diagnostic line to stderr (never stdout)."""
    print(msg, file=sys.stderr, flush=True)


def _truncate(text, max_len: int = NAME_MAX_LEN) -> str:
    if text is None:
        return ""
    text = str(text)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _rect_to_dict(rect):
    """Convert a uiautomation Rect to a plain dict; tolerate failures."""
    try:
        return {
            "left": rect.left,
            "top": rect.top,
            "right": rect.right,
            "bottom": rect.bottom,
            "width": rect.width(),
            "height": rect.height(),
        }
    except Exception:  # noqa: BLE001 - defensive, rect may be malformed
        return None


def _safe_getattr(control, attr):
    """Read a control property, returning None on any COM/attribute error."""
    try:
        return getattr(control, attr)
    except Exception:  # noqa: BLE001
        return None


def control_to_node(control) -> dict:
    """Extract the recorded property set from a single control."""
    rect = _safe_getattr(control, "BoundingRectangle")
    return {
        "controlTypeName": _safe_getattr(control, "ControlTypeName"),
        "name": _truncate(_safe_getattr(control, "Name")),
        "className": _safe_getattr(control, "ClassName"),
        "automationId": _safe_getattr(control, "AutomationId"),
        "boundingRectangle": _rect_to_dict(rect) if rect is not None else None,
        "nativeWindowHandle": _safe_getattr(control, "NativeWindowHandle"),
        "processId": _safe_getattr(control, "ProcessId"),
    }


def capture_ancestor_chain(control, max_ancestors=None) -> dict:
    """Capture control, its ancestor chain, depth info, and code suggestion.

    Returns a dict with:
    - ``chain``: [target, parent, grandparent, ...] as node dicts,
      index 0 is the target control itself.
    - ``depth``: depth from desktop root to the target.
    - ``searchDepth``: depth from the nearest WindowControl ancestor
      to the target (the value you'd pass to ``searchDepth=``).
    - ``parentWindow``: the nearest WindowControl ancestor's properties.
    - ``codeSuggestion``: ready-to-use uiautomation Python code.
    """
    nodes = []
    curr = control
    while curr:
        nodes.append(control_to_node(curr))
        if max_ancestors is not None and len(nodes) > max_ancestors:
            break
        try:
            curr = curr.GetParentControl()
        except Exception:  # noqa: BLE001
            break

    # depth from root (last in chain) to target (first in chain)
    depth_from_root = len(nodes) - 1

    # Find nearest WindowControl ancestor (skip target itself at index 0)
    parent_window = None
    search_depth = None
    for i, node in enumerate(nodes):
        if i == 0:
            continue
        if node["controlTypeName"] == "WindowControl":
            parent_window = node
            search_depth = i  # levels between window and target
            break

    # Generate uiautomation Python code suggestion
    code = _generate_code(nodes[0], parent_window, search_depth)

    return {
        "chain": nodes,
        "depth": depth_from_root,
        "searchDepth": search_depth,
        "parentWindow": parent_window,
        "codeSuggestion": code,
    }


def _generate_code(target: dict, parent_window: dict, search_depth: int) -> str:
    """Generate a ready-to-use uiautomation Python code snippet."""
    ctrl_type = target["controlTypeName"] or "Control"
    target_name = target["name"]
    target_aid = target["automationId"]

    # Build the target control selector
    selector_parts = []
    if search_depth is not None:
        selector_parts.append(f"searchDepth={search_depth}")
    if target_name:
        selector_parts.append(f"Name={target_name!r}")
    if target_aid:
        selector_parts.append(f"AutomationId={target_aid!r}")
    selector = ", ".join(selector_parts)

    # Build the parent window selector
    if parent_window:
        win_name = parent_window["name"]
        win_class = parent_window["className"]
        win_parts = []
        if win_name:
            win_parts.append(f"Name={win_name!r}")
        if win_class:
            win_parts.append(f"ClassName={win_class!r}")
        win_selector = ", ".join(win_parts)
        prefix = f"auto.WindowControl({win_selector})"
    else:
        prefix = "auto.GetRootControl()"

    return f"{prefix}.{ctrl_type}({selector})"


def highlight_control(rect) -> None:
    """Flash a red rectangle around ``rect`` using GDI (best effort).

    The uiautomation library ships no DrawOutline helper, so this draws
    directly on the screen DC with ctypes. Any failure is swallowed since
    highlighting is a non-essential nicety.
    """
    try:
        import ctypes

        left = int(rect.left)
        top = int(rect.top)
        right = int(rect.right)
        bottom = int(rect.bottom)
        if right <= left or bottom <= top:
            return

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        hdc = user32.GetDC(0)
        if not hdc:
            return
        try:
            # Red pen, 3px wide, no fill (hollow brush).
            RED = 0x000000FF  # COLORREF is 0x00BBGGRR -> pure red
            PS_SOLID = 0
            NULL_BRUSH = 5  # stock object
            pen = gdi32.CreatePen(PS_SOLID, 3, RED)
            null_brush = gdi32.GetStockObject(NULL_BRUSH)
            old_pen = gdi32.SelectObject(hdc, pen)
            old_brush = gdi32.SelectObject(hdc, null_brush)
            try:
                import time as _time

                for _ in range(HIGHLIGHT_FLASHES):
                    gdi32.Rectangle(hdc, left, top, right, bottom)
                    _time.sleep(0.12)
                    # Ask affected region to repaint so the box disappears.
                    user32.InvalidateRect(0, None, True)
                    _time.sleep(0.12)
                gdi32.Rectangle(hdc, left, top, right, bottom)
                _time.sleep(0.12)
                user32.InvalidateRect(0, None, True)
            finally:
                gdi32.SelectObject(hdc, old_pen)
                gdi32.SelectObject(hdc, old_brush)
                gdi32.DeleteObject(pen)
        finally:
            user32.ReleaseDC(0, hdc)
    except Exception as exc:  # noqa: BLE001
        _log(f"[picker] highlight skipped: {exc}")


class PickerApp:
    """Tkinter controller for the interactive picker window."""

    def __init__(self, delay: int, max_ancestors, quiet: bool = False, result_file: str | None = None):
        import tkinter as tk

        self.tk = tk
        self.delay = delay
        self.max_ancestors = max_ancestors
        self.quiet = quiet
        self.result_file = result_file
        self.results = []
        self._counting = False
        self._remaining = 0

        self.root = tk.Tk()
        self.root.title("UI 控件抓取器")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        self._build_widgets()
        self._place_bottom_right()

        # Force the window to the foreground — when the MCP server
        # process was started hidden (CREATE_NO_WINDOW), a simple
        # -topmost is not always enough.
        self.root.after(100, self._force_foreground)

        # X button -> treat as "finish", emit whatever we have.
        self.root.protocol("WM_DELETE_WINDOW", self.on_finish)

    # -- UI construction ----------------------------------------------------

    def _force_foreground(self) -> None:
        """Use Win32 API to force the tkinter window to the foreground.

        When the parent process has no visible window (e.g. started with
        CREATE_NO_WINDOW), SetForegroundWindow alone may fail because
        Windows only allows the foreground process to steal focus.
        Workaround: briefly attach to the foreground thread's input queue.
        """
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            hwnd = int(self.root.winfo_id())
            # Ensure the window is not minimised and is visible.
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)

            # Attach our thread to the current foreground thread so
            # SetForegroundWindow is allowed to succeed.
            fg_hwnd = user32.GetForegroundWindow()
            fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)
            our_tid = kernel32.GetCurrentThreadId()
            attached = False
            if fg_tid != our_tid:
                attached = bool(user32.AttachThreadInput(our_tid, fg_tid, True))

            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)

            if attached:
                user32.AttachThreadInput(our_tid, fg_tid, False)

            # Re-assert topmost after the focus dance.
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            self.root.lift()
        except Exception as exc:  # noqa: BLE001
            _log(f"[picker] _force_foreground failed (non-fatal): {exc}")

    def _build_widgets(self) -> None:
        tk = self.tk
        pad = {"padx": 8, "pady": 4}

        self.hint = tk.Label(
            self.root,
            text="把鼠标移到目标控件上，点击“下一步”开始倒计时",
            wraplength=280,
            justify="left",
        )
        self.hint.pack(fill="x", **pad)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", **pad)

        self.next_btn = tk.Button(btn_frame, text="下一步", width=12, command=self.on_next)
        self.next_btn.pack(side="left", padx=4)

        self.finish_btn = tk.Button(btn_frame, text="完成", width=12, command=self.on_finish)
        self.finish_btn.pack(side="right", padx=4)

        list_label = tk.Label(self.root, text="已抓取:", anchor="w")
        list_label.pack(fill="x", padx=8)

        list_frame = tk.Frame(self.root)
        list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        self.listbox = tk.Listbox(list_frame, height=6, width=42, yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)

    def _place_bottom_right(self) -> None:
        self.root.update_idletasks()
        w = self.root.winfo_width() or 320
        h = self.root.winfo_height() or 220
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, sw - w - 40)
        y = max(0, sh - h - 80)
        self.root.geometry(f"+{x}+{y}")

    # -- Countdown / capture ------------------------------------------------

    def on_next(self) -> None:
        if self._counting:
            return
        self._counting = True
        self.next_btn.config(state="disabled")
        self.finish_btn.config(state="disabled")
        self._remaining = self.delay
        self._tick()

    def _tick(self) -> None:
        if self._remaining <= 0:
            self.next_btn.config(text="抓取中...")
            # Defer so the label repaints before the (brief) COM capture.
            self.root.after(50, self._do_capture)
            return
        self.next_btn.config(text=str(self._remaining))
        self._remaining -= 1
        self.root.after(1000, self._tick)

    def _do_capture(self) -> None:
        try:
            import uiautomation as auto

            control = auto.ControlFromCursor()
            if not control:
                self._append_status("[未抓到控件] 光标下没有可识别的控件")
                _log("[picker] ControlFromCursor returned None")
            else:
                result = capture_ancestor_chain(control, self.max_ancestors)
                self.results.append(result)
                top = result["chain"][0]
                depth = result["searchDepth"]
                code = result["codeSuggestion"]
                self._append_status(
                    f"[{top['controlTypeName']}] {top['name']} (searchDepth={depth})"
                )
                _log(
                    f"[picker] captured {top['controlTypeName']} "
                    f"name={top['name']!r} searchDepth={depth} "
                    f"ancestors={len(result['chain'])}"
                )
                _log(f"[picker] code: {code}")
                rect = _safe_getattr(control, "BoundingRectangle")
                if rect is not None:
                    highlight_control(rect)
        except Exception as exc:  # noqa: BLE001
            _log(f"[picker] capture failed: {exc}")
            self._append_status(f"[抓取失败] {exc}")
        finally:
            self._reset_buttons()

    def _reset_buttons(self) -> None:
        self._counting = False
        self.next_btn.config(text="下一步", state="normal")
        self.finish_btn.config(state="normal")

    def _append_status(self, text: str) -> None:
        self.listbox.insert(self.tk.END, text)
        self.listbox.see(self.tk.END)

    # -- Exit ---------------------------------------------------------------

    def on_finish(self) -> None:
        self._emit_and_quit()

    def _emit_and_quit(self) -> None:
        payload = {
            "delay": self.delay,
            "maxAncestors": self.max_ancestors,
            "count": len(self.results),
            "captures": self.results,
        }

        # Collect all code suggestions for clipboard
        code_lines = []
        for cap in self.results:
            code = cap.get("codeSuggestion", "")
            if code:
                code_lines.append(code)

        # Copy code suggestions to clipboard
        if code_lines:
            clip_text = "\n".join(code_lines)
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(clip_text)
                # Must call update() so clipboard persists after destroy
                self.root.update()
                _log(f"[picker] copied {len(code_lines)} code snippet(s) to clipboard")
            except Exception as exc:  # noqa: BLE001
                _log(f"[picker] clipboard copy failed: {exc}")

        # Prefer writing JSON to a result file (works with pythonw / DETACHED_PROCESS).
        # Fall back to stdout when not quiet and no result_file is given.
        if self.result_file:
            try:
                with open(self.result_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
                _log(f"[picker] result written to {self.result_file}")
            except Exception as exc:  # noqa: BLE001
                _log(f"[picker] failed to write result file: {exc}")
        elif not self.quiet:
            sys.stdout.write(json.dumps(payload, ensure_ascii=False))
            sys.stdout.flush()
        try:
            self.root.destroy()
        except Exception:  # noqa: BLE001
            pass

    def run(self) -> None:
        self.root.mainloop()


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="uiautomation_mcp.picker_gui",
        description="Interactive UI control picker with topmost countdown window.",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=DEFAULT_DELAY,
        help="Countdown seconds before capture (default: 3).",
    )
    parser.add_argument(
        "--max-ancestors",
        type=int,
        default=None,
        help="Max ancestor levels to record above the target (default: all).",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        default=False,
        help="Suppress JSON output to stdout (code is still copied to clipboard).",
    )
    parser.add_argument(
        "--result-file",
        type=str,
        default=None,
        help="Write JSON result to this file (preferred for detached/pythonw launches).",
    )
    return parser.parse_args(argv)


def _free_console() -> None:
    """Hide and detach the parent console so the black cmd window disappears.

    When launched via CREATE_NEW_CONSOLE the process owns a console that
    would otherwise stay open as a blank ``python.exe`` window.  Hide it
    first (in case FreeConsole is delayed / fails), then detach.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)  # SW_HIDE
        kernel32.FreeConsole()
    except Exception as exc:  # noqa: BLE001
        _log(f"[picker] FreeConsole skipped: {exc}")


def main(argv=None) -> int:
    args = parse_args(argv)
    delay = args.delay if args.delay >= 0 else 0
    # Detach the console *before* creating any GUI window.
    _free_console()
    _log(
        f"[picker] starting window (delay={delay}s, "
        f"max_ancestors={args.max_ancestors})"
    )
    try:
        app = PickerApp(
            delay=delay,
            max_ancestors=args.max_ancestors,
            quiet=args.quiet,
            result_file=args.result_file,
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"[picker] failed to create window: {exc}")
        empty = {
            "delay": delay,
            "maxAncestors": args.max_ancestors,
            "count": 0,
            "captures": [],
            "error": str(exc),
        }
        if args.result_file:
            try:
                with open(args.result_file, "w", encoding="utf-8") as f:
                    json.dump(empty, f, ensure_ascii=False)
            except Exception:  # noqa: BLE001
                pass
        else:
            sys.stdout.write(json.dumps(empty, ensure_ascii=False))
            sys.stdout.flush()
        return 1
    app.run()
    _log("[picker] window closed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
