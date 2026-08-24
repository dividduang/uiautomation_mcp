# -*- coding: utf-8 -*-
"""uiautomation-cli — drive Windows UI Automation from the command line.

Pure CLI replacement for the old MCP server. Every MCP tool became a
subcommand with the same capabilities:

    uiautomation-cli find-window --name "记事本"
    uiautomation-cli find-control --token <T> --name "编辑区" --control-type EditControl
    uiautomation-cli click --token <T2>
    uiautomation-cli screenshot --token <T2> --save-path shot.png

Controls found by one invocation are remembered in a persistent registry
(``~/.uiautomation/registry.json``) and can be reused by the next
invocation through their token — the CLI analogue of the MCP session
token. Run ``uiautomation-cli repl`` for an interactive session where
tokens stay warm in one process.

Global flags::

    --json          print machine-readable JSON (for scripts / AI agents)
    --yes           skip interactive confirmation for dangerous ops
    --log-level     python logging level (default: WARNING)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import __version__, registry
from . import service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _emit(response: Dict[str, Any], as_json: bool) -> int:
    """Print a service response and return the process exit code."""
    if as_json:
        _print_json(response)
        return 0 if response.get("success") else 1

    if response.get("success"):
        data = response.get("data")
        _human(data)
        return 0

    error = response.get("error", {})
    print(f"错误 [{error.get('code', 'UNKNOWN')}]: {error.get('message', '未知错误')}", file=sys.stderr)
    for s in error.get("suggestions", []):
        print(f"  提示: {s}", file=sys.stderr)
    return 1


def _human(data: Any) -> None:
    """Render data in a human-friendly way."""
    if data is None:
        return
    if isinstance(data, list):
        if not data:
            print("(空)")
            return
        # Table: derive columns from the first dict, show the rest aligned.
        keys = list(data[0].keys()) if isinstance(data[0], dict) else []
        if keys and all(isinstance(item, dict) for item in data):
            headers = [str(k) for k in keys]
            rows = [[_short(str(item.get(k, ""))) for k in keys] for item in data]
            widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
            print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
            print("  ".join("-" * w for w in widths))
            for row in rows:
                print("  ".join(c.ljust(w) for c, w in zip(row, widths)))
        else:
            for item in data:
                print(_short(str(item)))
        return

    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                print(f"{k}: {json.dumps(v, ensure_ascii=False)}")
            else:
                print(f"{k}: {v}")
        return

    print(data)


def _short(s: str, limit: int = 48) -> str:
    return s if len(s) <= limit else s[: limit - 3] + "..."


def _confirm(prompt: str, yes_flag: bool) -> bool:
    """Interactive confirmation; --yes short-circuits. Returns True if approved."""
    if yes_flag:
        return True
    if not sys.stdin.isatty():
        return False
    try:
        answer = input(f"{prompt} [y/N] ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# ---------------------------------------------------------------------------
# Sub-command implementations
# ---------------------------------------------------------------------------

def _cmd_find_window(args) -> int:
    return _emit(service.find_window(args.name, args.class_name, args.process_id, args.handle), args.json)


def _cmd_find_control(args) -> int:
    return _emit(
        service.find_control(
            parent_handle=args.parent_handle,
            control_type=args.control_type,
            name=args.name,
            name_contains=args.name_contains,
            name_regex=args.name_regex,
            class_name=args.class_name,
            automation_id=args.automation_id,
            depth=args.depth,
            index=args.index,
        ),
        args.json,
    )


def _cmd_children(args) -> int:
    return _emit(service.get_children(args.token, args.depth), args.json)


def _cmd_focused(args) -> int:
    return _emit(service.get_focused(), args.json)


def _cmd_foreground(args) -> int:
    return _emit(service.get_foreground(), args.json)


def _cmd_from_point(args) -> int:
    return _emit(service.control_from_point(args.x, args.y), args.json)


def _cmd_click(args) -> int:
    return _emit(
        service.click(token=args.token, x=args.x, y=args.y, button=args.button, double=args.double),
        args.json,
    )


def _cmd_send_keys(args) -> int:
    return _emit(service.send_keys(args.token, args.text, args.interval), args.json)


def _cmd_set_value(args) -> int:
    return _emit(service.set_value(args.token, args.value), args.json)


def _cmd_close_window(args) -> int:
    if not _confirm("确认关闭该窗口?", args.yes):
        return _emit({"success": False, "error": {"code": "ABORTED", "message": "用户取消操作"}}, args.json)
    return _emit(service.close_window(args.token, confirmed=True), args.json)


def _cmd_move_window(args) -> int:
    return _emit(service.move_window(args.token, args.x, args.y, args.width, args.height), args.json)


def _cmd_invoke(args) -> int:
    return _emit(service.invoke(args.token), args.json)


def _cmd_toggle(args) -> int:
    return _emit(service.toggle(args.token), args.json)


def _cmd_expand_collapse(args) -> int:
    return _emit(service.expand_collapse(args.token, args.action), args.json)


def _cmd_select_item(args) -> int:
    return _emit(service.select_item(args.token), args.json)


def _cmd_scroll(args) -> int:
    return _emit(service.scroll(args.token, args.direction, args.amount), args.json)


def _cmd_terminate_process(args) -> int:
    if not _confirm(f"确认终止进程 {args.process_name or args.process_id}?", args.yes):
        return _emit({"success": False, "error": {"code": "ABORTED", "message": "用户取消操作"}}, args.json)
    return _emit(service.terminate_process(args.process_id, args.process_name, confirmed=True), args.json)


def _cmd_properties(args) -> int:
    props = args.properties.split(",") if args.properties else None
    return _emit(service.get_properties(args.token, props), args.json)


def _cmd_text(args) -> int:
    return _emit(service.get_text(args.token), args.json)


def _cmd_rect(args) -> int:
    return _emit(service.get_rect(args.token), args.json)


def _cmd_screenshot(args) -> int:
    return _emit(service.screenshot(args.token, args.save_path, args.capture_cursor), args.json)


def _cmd_exists(args) -> int:
    return _emit(service.exists(args.token, args.timeout), args.json)


def _cmd_wait_for(args) -> int:
    return _emit(
        service.wait_for(
            condition=args.condition,
            timeout=args.timeout,
            token=args.token,
            name=args.name,
            class_name=args.class_name,
            automation_id=args.automation_id,
            control_type=args.control_type,
            depth=args.depth,
        ),
        args.json,
    )


def _cmd_clipboard_get(args) -> int:
    return _emit(service.clipboard_get(), args.json)


def _cmd_clipboard_set(args) -> int:
    return _emit(service.clipboard_set(args.text), args.json)


def _cmd_list_processes(args) -> int:
    return _emit(service.list_processes(args.filter), args.json)


def _cmd_show_desktop(args) -> int:
    return _emit(service.show_desktop(), args.json)


def _cmd_screen_size(args) -> int:
    return _emit(service.get_screen_size(), args.json)


def _cmd_highlight(args) -> int:
    return _emit(
        service.highlight(args.token, args.handle, args.color, args.thickness, args.duration, args.delay),
        args.json,
    )


def _cmd_tokens(args) -> int:
    return _emit({"success": True, "data": registry.list_tokens()}, args.json)


def _cmd_clear_tokens(args) -> int:
    removed = registry.clear()
    return _emit({"success": True, "data": {"removed": removed}}, args.json)


def _cmd_pick(args) -> int:
    """Launch the interactive picker GUI and block until it finishes."""
    pick_id = uuid.uuid4().hex[:8]
    tmp_dir = Path(tempfile.gettempdir())
    out_file = tmp_dir / f"uiamcp_pick_{pick_id}.json"
    try:
        out_file.unlink(missing_ok=True)
    except OSError:
        pass

    python = Path(sys.executable)
    if os.name == "nt":
        candidate = python.with_name("pythonw.exe")
        if candidate.is_file():
            python = candidate

    cmd = [str(python), "-m", "uiautomation_mcp.picker_gui",
           "--delay", str(args.delay), "--result-file", str(out_file)]
    if args.max_ancestors and args.max_ancestors > 0:
        cmd += ["--max-ancestors", str(args.max_ancestors)]

    print(f"拾取器已启动，将鼠标移到目标控件上，然后点击「完成」… (Ctrl+C 取消)")
    try:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         close_fds=True, start_new_session=True)
    except Exception as e:  # noqa: BLE001
        return _emit({"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}, args.json)

    deadline = time.time() + (args.timeout if args.timeout > 0 else 3600)
    while time.time() < deadline:
        if out_file.is_file() and out_file.stat().st_size > 0:
            try:
                data = json.loads(out_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                time.sleep(0.2)
                continue
            out_file.unlink(missing_ok=True)
            return _emit({"success": True, "data": data}, args.json)
        time.sleep(0.2)
    return _emit({"success": False, "error": {"code": "TIMEOUT", "message": "等待拾取结果超时"}}, args.json)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出 (供脚本/agent 解析)")
    parser.add_argument("--yes", action="store_true", help="跳过危险操作的交互确认")
    parser.add_argument("--log-level", default="WARNING", help="日志级别 (DEBUG/INFO/WARNING/ERROR)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uiautomation-cli",
        description="Windows UI Automation 命令行工具 (替代 MCP Server)",
        epilog="示例:\n"
               "  uiautomation-cli find-window --name 记事本\n"
               "  uiautomation-cli find-control --token <T> --control-type EditControl\n"
               "  uiautomation-cli click --token <T2>\n"
               "  uiautomation-cli repl     # 交互式会话",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"uiautomation-cli {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="命令")

    # ---- discovery ----
    p = sub.add_parser("find-window", help="按名称/类/进程ID/句柄查找顶层窗口")
    p.add_argument("--name", help="窗口标题 (精确匹配)")
    p.add_argument("--class-name", dest="class_name", help="窗口类名")
    p.add_argument("--process-id", dest="process_id", type=int, help="进程 ID")
    p.add_argument("--handle", type=int, help="窗口句柄 (直接返回)")
    _add_common(p)
    p.set_defaults(func=_cmd_find_window)

    p = sub.add_parser("find-control", help="在父控件内查找子控件")
    p.add_argument("--parent-handle", dest="parent_handle", type=int, help="父控件句柄 (缺省从桌面根查找)")
    p.add_argument("--control-type", dest="control_type", help="控件类型 (如 ButtonControl/EditControl)")
    p.add_argument("--name", help="精确名称匹配")
    p.add_argument("--name-contains", dest="name_contains", help="名称包含")
    p.add_argument("--name-regex", dest="name_regex", help="名称正则匹配")
    p.add_argument("--class-name", dest="class_name", help="窗口类名")
    p.add_argument("--automation-id", dest="automation_id", help="Automation ID")
    p.add_argument("--depth", type=int, default=0xFFFFFFFF, help="搜索深度 (默认无限制)")
    p.add_argument("--index", type=int, default=1, help="第 N 个匹配控件 (从 1 开始)")
    _add_common(p)
    p.set_defaults(func=_cmd_find_control)

    p = sub.add_parser("children", help="获取控件的子控件列表")
    p.add_argument("token", help="父控件 token")
    p.add_argument("--depth", type=int, default=1, help="遍历深度 (默认 1 = 直接子控件)")
    _add_common(p)
    p.set_defaults(func=_cmd_children)

    p = sub.add_parser("focused", help="获取当前焦点控件")
    _add_common(p)
    p.set_defaults(func=_cmd_focused)

    p = sub.add_parser("foreground", help="获取前台窗口")
    _add_common(p)
    p.set_defaults(func=_cmd_foreground)

    p = sub.add_parser("from-point", help="获取屏幕坐标处的控件")
    p.add_argument("x", type=int, help="屏幕 X 坐标")
    p.add_argument("y", type=int, help="屏幕 Y 坐标")
    _add_common(p)
    p.set_defaults(func=_cmd_from_point)

    # ---- interaction ----
    p = sub.add_parser("click", help="点击控件或屏幕坐标")
    p.add_argument("--token", help="控件 token (与 x/y 二选一)")
    p.add_argument("--x", type=int, help="绝对 X 坐标 (无 token 时)")
    p.add_argument("--y", type=int, help="绝对 Y 坐标 (无 token 时)")
    p.add_argument("--button", default="left", choices=["left", "right", "middle"], help="鼠标按键")
    p.add_argument("--double", action="store_true", help="双击")
    _add_common(p)
    p.set_defaults(func=_cmd_click)

    p = sub.add_parser("send-keys", help="向控件发送键盘输入")
    p.add_argument("token", help="控件 token")
    p.add_argument("text", help="要发送的文本/按键 (如 {Ctrl}, {Enter})")
    p.add_argument("--interval", type=float, default=0.05, help="按键间隔秒数")
    _add_common(p)
    p.set_defaults(func=_cmd_send_keys)

    p = sub.add_parser("set-value", help="通过 ValuePattern 设置控件文本值")
    p.add_argument("token", help="控件 token")
    p.add_argument("value", help="要设置的值")
    _add_common(p)
    p.set_defaults(func=_cmd_set_value)

    p = sub.add_parser("close-window", help="关闭窗口 (危险操作，需确认)")
    p.add_argument("token", help="窗口 token")
    _add_common(p)
    p.set_defaults(func=_cmd_close_window)

    p = sub.add_parser("move-window", help="移动/调整窗口大小")
    p.add_argument("token", help="窗口 token")
    p.add_argument("--x", type=int, help="新 X 坐标")
    p.add_argument("--y", type=int, help="新 Y 坐标")
    p.add_argument("--width", type=int, help="新宽度")
    p.add_argument("--height", type=int, help="新高度")
    _add_common(p)
    p.set_defaults(func=_cmd_move_window)

    # ---- patterns ----
    p = sub.add_parser("invoke", help="通过 InvokePattern 调用控件")
    p.add_argument("token", help="控件 token")
    _add_common(p)
    p.set_defaults(func=_cmd_invoke)

    p = sub.add_parser("toggle", help="通过 TogglePattern 切换控件状态")
    p.add_argument("token", help="控件 token")
    _add_common(p)
    p.set_defaults(func=_cmd_toggle)

    p = sub.add_parser("expand-collapse", help="通过 ExpandCollapsePattern 展开/折叠")
    p.add_argument("token", help="控件 token")
    p.add_argument("--action", default="expand", choices=["expand", "collapse"], help="操作")
    _add_common(p)
    p.set_defaults(func=_cmd_expand_collapse)

    p = sub.add_parser("select-item", help="通过 SelectionItemPattern 选中列表项")
    p.add_argument("token", help="控件 token")
    _add_common(p)
    p.set_defaults(func=_cmd_select_item)

    p = sub.add_parser("scroll", help="滚动控件 (ScrollPattern, 回退滚轮)")
    p.add_argument("token", help="控件 token")
    p.add_argument("--direction", default="down", choices=["up", "down", "left", "right"], help="方向")
    p.add_argument("--amount", default="large", choices=["large", "small"], help="滚动量")
    _add_common(p)
    p.set_defaults(func=_cmd_scroll)

    p = sub.add_parser("terminate-process", help="终止进程 (危险操作，需确认)")
    p.add_argument("--process-id", dest="process_id", type=int, help="进程 ID")
    p.add_argument("--process-name", dest="process_name", help="进程名 (与 process-id 二选一)")
    _add_common(p)
    p.set_defaults(func=_cmd_terminate_process)

    # ---- query ----
    p = sub.add_parser("properties", help="获取控件属性")
    p.add_argument("token", help="控件 token")
    p.add_argument("--properties", help="逗号分隔的属性名 (缺省全部): name,className,controlType,automationId,processId,enabled,visible,helpText,frameworkId,handle,rect")
    _add_common(p)
    p.set_defaults(func=_cmd_properties)

    p = sub.add_parser("text", help="获取控件文本内容")
    p.add_argument("token", help="控件 token")
    _add_common(p)
    p.set_defaults(func=_cmd_text)

    p = sub.add_parser("rect", help="获取控件边界矩形")
    p.add_argument("token", help="控件 token")
    _add_common(p)
    p.set_defaults(func=_cmd_rect)

    p = sub.add_parser("screenshot", help="截图控件区域")
    p.add_argument("token", help="控件 token")
    p.add_argument("--save-path", dest="save_path", help="保存路径 (缺省自动生成到 ./screenshots)")
    p.add_argument("--capture-cursor", dest="capture_cursor", action="store_true", help="捕获光标")
    _add_common(p)
    p.set_defaults(func=_cmd_screenshot)

    p = sub.add_parser("exists", help="检查控件是否存在")
    p.add_argument("token", help="控件 token")
    p.add_argument("--timeout", type=float, default=0, help="等待秒数 (默认立即检查)")
    _add_common(p)
    p.set_defaults(func=_cmd_exists)

    p = sub.add_parser("wait-for", help="等待条件满足")
    p.add_argument("condition", choices=["control_exists", "control_disappear", "window_active"], help="条件类型")
    p.add_argument("--timeout", type=float, help="超时秒数 (缺省用配置默认值)")
    p.add_argument("--token", help="控件 token (control_exists/disappear/window_active)")
    p.add_argument("--name", help="控件名称选择器")
    p.add_argument("--class-name", dest="class_name", help="窗口类名选择器")
    p.add_argument("--automation-id", dest="automation_id", help="Automation ID 选择器")
    p.add_argument("--control-type", dest="control_type", help="控件类型选择器")
    p.add_argument("--depth", type=int, default=0xFFFFFFFF, help="搜索深度")
    _add_common(p)
    p.set_defaults(func=_cmd_wait_for)

    # ---- helpers ----
    p = sub.add_parser("clipboard-get", help="获取剪贴板文本")
    _add_common(p)
    p.set_defaults(func=_cmd_clipboard_get)

    p = sub.add_parser("clipboard-set", help="设置剪贴板文本")
    p.add_argument("text", help="要设置的文本")
    _add_common(p)
    p.set_defaults(func=_cmd_clipboard_set)

    p = sub.add_parser("list-processes", help="列出运行中的进程")
    p.add_argument("--filter", help="按进程名过滤 (包含匹配)")
    _add_common(p)
    p.set_defaults(func=_cmd_list_processes)

    p = sub.add_parser("show-desktop", help="显示桌面 (最小化所有窗口)")
    _add_common(p)
    p.set_defaults(func=_cmd_show_desktop)

    p = sub.add_parser("screen-size", help="获取屏幕分辨率")
    _add_common(p)
    p.set_defaults(func=_cmd_screen_size)

    # ---- highlight / picker / registry ----
    p = sub.add_parser("highlight", help="在控件周围绘制高亮边框")
    p.add_argument("--token", help="控件 token (与 --handle 二选一)")
    p.add_argument("--handle", type=int, help="控件句柄")
    p.add_argument("--color", default="red", help="颜色 (名称或十六进制，如 '#00ff00')")
    p.add_argument("--thickness", type=int, default=3, help="边框粗细 (像素)")
    p.add_argument("--duration", type=float, default=0.0, help="持续秒数 (0 = 一次性)")
    p.add_argument("--delay", type=float, default=0.05, help="持续高亮的刷新间隔")
    _add_common(p)
    p.set_defaults(func=_cmd_highlight)

    p = sub.add_parser("pick", help="启动交互式控件拾取器 (鼠标指向控件，点「完成」)")
    p.add_argument("--delay", type=int, default=3, help="每次捕获前倒计时秒数")
    p.add_argument("--max-ancestors", dest="max_ancestors", type=int, default=0, help="记录的最大祖先层级 (0/负值 = 全部)")
    p.add_argument("--timeout", type=int, default=0, help="等待超时秒数 (0 = 不限)")
    _add_common(p)
    p.set_defaults(func=_cmd_pick)

    p = sub.add_parser("tokens", help="列出注册表中的控件 token")
    _add_common(p)
    p.set_defaults(func=_cmd_tokens)

    p = sub.add_parser("clear-tokens", help="清空控件 token 注册表")
    _add_common(p)
    p.set_defaults(func=_cmd_clear_tokens)

    p = sub.add_parser("repl", help="交互式 REPL 会话 (token 在进程内保持)")
    _add_common(p)
    p.set_defaults(func=_cmd_repl)

    return parser


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

def _cmd_repl(args) -> int:
    parser = build_parser()
    print(f"uiautomation-cli REPL v{__version__} — 输入命令 (不带 uiautomation-cli)，help 查看，exit 退出")
    while True:
        try:
            line = input("ui> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("exit", "quit", "q"):
            break
        try:
            argv = shlex.split(line)
        except ValueError as e:
            print(f"解析错误: {e}")
            continue
        try:
            ns = parser.parse_args(argv)
            ns.json = True  # REPL 统一 JSON 输出，便于查看完整结构
            ns.yes = True   # REPL 内交互确认由输入决定，不再二次弹窗
            if hasattr(ns, "func"):
                ns.func(ns)
            else:
                parser.print_help()
        except SystemExit:
            pass
        except Exception as e:  # noqa: BLE001
            print(f"执行异常: {e}")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    # Ensure UTF-8 output on Windows consoles (GBK default breaks Chinese/emoji).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.WARNING),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not hasattr(args, "func"):
        parser.print_help()
        return 2

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        return 130
    except Exception as e:  # noqa: BLE001
        logger.exception("unhandled error")
        print(f"未处理异常: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
