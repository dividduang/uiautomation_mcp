# UIAutomation CLI

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows-blue.svg)]()

> 基于 [Python-UIAutomation-for-Windows](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows) 的 **Windows UI 自动化命令行工具**（纯 CLI 模式，原 MCP Server 的 CLI 化重构）。

**特别感谢** [yinkaisheng](https://github.com/yinkaisheng) 开发的优秀 UI 自动化库。

---

## 简介

`uiautomation-cli` 让你（或 AI agent）通过命令行直接操作 Windows UI 控件：

- 自动化桌面应用程序操作（SAP GUI / 记事本 / 浏览器 / 任意 Win32·WPF·Qt·Electron 应用）
- 控件查找、属性查询与截图
- 键盘鼠标模拟、窗口管理
- 交互式控件拾取器（鼠标点选生成定位代码）

支持的应用类型：Win32、MFC、WPF、Windows Forms、Modern UI (UWP)、Qt、Firefox、Chrome、Electron 等。

---

## 安装

```bash
pip install -e .           # 或 uv sync
pip install comtypes overlay-arrows-and-more
```

## 快速上手

```bash
# 查找窗口（返回 token）
uiautomation-cli find-window --name "无标题 - 记事本"
# {"handle": 200284, "token": "68fba016", "name": "无标题 - 记事本", ...}

# 在窗口内找编辑区
uiautomation-cli find-control --parent-handle 200284 --control-type EditControl

# 输入文本、读取、截图
uiautomation-cli send-keys <token> "Hello"
uiautomation-cli text <token>
uiautomation-cli screenshot <token> --save-path shot.png

# 交互式会话（token 在进程内保持热状态）
uiautomation-cli repl
```

> **Token 机制**：控件被找到后注册到 `~/.uiautomation/registry.json`（持久化 + 5 分钟 TTL）。
> 每次 CLI 调用都是独立进程，token 通过句柄或祖先路径跨进程恢复 —— 这是 CLI 模式下替代
> MCP 会话内存注册表的方案。`uiautomation-cli tokens` 查看，`clear-tokens` 清空。

## 命令一览

### 控件查找
| 命令 | 说明 |
|------|------|
| `find-window` | 按名称/类名/进程ID/句柄查找顶层窗口 |
| `find-control` | 在父控件内查找子控件（type/name/name-contains/regex/automationId/index） |
| `children <token>` | 获取子控件列表（--depth 控制遍历深度） |
| `focused` | 获取当前焦点控件 |
| `foreground` | 获取前台窗口 |
| `from-point <x> <y>` | 获取屏幕坐标处的控件 |

### 交互操作
| 命令 | 说明 |
|------|------|
| `click` | 点击控件或坐标（--button left/right/middle，--double） |
| `send-keys <token> <text>` | 发送键盘输入（{Ctrl}、{Enter} 等特殊键） |
| `set-value <token> <value>` | ValuePattern 设置文本 |
| `close-window <token>` | 关闭窗口（危险操作，需确认或 --yes） |
| `move-window <token>` | 移动/调整窗口（--x --y --width --height） |

### 控件模式（Pattern）
| 命令 | 说明 |
|------|------|
| `invoke <token>` | InvokePattern 调用（对话框按钮推荐，比 click 可靠） |
| `toggle <token>` | TogglePattern 切换 |
| `expand-collapse <token>` | 展开/折叠（--action expand/collapse） |
| `select-item <token>` | SelectionItemPattern 选中 |
| `scroll <token>` | 滚动（--direction --amount） |
| `terminate-process` | 终止进程（危险操作，需确认或 --yes） |

### 查询
| 命令 | 说明 |
|------|------|
| `properties <token>` | 获取属性（--properties name,rect,...） |
| `text <token>` | 读取文本（Value→Text→LegacyIAccessible→Name 逐级回退） |
| `rect <token>` | 边界矩形 + 中心点 |
| `screenshot <token>` | 截图（--save-path，默认 ./screenshots） |
| `exists <token>` | 检查是否存在（--timeout 等待） |
| `wait-for <condition>` | 等待条件（control_exists / control_disappear / window_active） |

### 辅助
| 命令 | 说明 |
|------|------|
| `clipboard-get` / `clipboard-set <text>` | 剪贴板读写 |
| `list-processes` | 列出进程（--filter 名称过滤） |
| `show-desktop` | 最小化所有窗口 |
| `screen-size` | 屏幕分辨率 |
| `highlight` | 控件高亮边框（--color red/#00ff00，--duration 持续秒数） |
| `pick` | 交互式拾取器（鼠标指向控件→点「完成」，输出定位代码） |
| `tokens` / `clear-tokens` | 查看/清空 token 注册表 |
| `repl` | 交互式 REPL 会话 |

## 常用选项

```bash
--json     # 机器可读 JSON 输出（供脚本/AI agent 解析），成功退出码 0，失败 1
--yes      # 跳过危险操作（close-window / terminate-process）的交互确认
```

## 给 AI agent 的使用建议

- **一次调用做一件事**：`find-window` → `find-control` → 操作，通过 token 串联（token 跨进程持久化）。
- **对话框按钮用 `invoke` 而非 `click`**：invoke 走 UIA 协议，不依赖窗口前台焦点，模态对话框也能触发。
- **批量操作用 `--json` + 管道**：`uiautomation-cli find-window --name X --json | jq .data.token`
- **长时间会话用 `repl`**：token 在进程内缓存，恢复更快。

## 从 MCP 模式迁移

- 原 MCP 工具 `ui_find_window` → CLI `find-window`，`ui_click` → `click`，其余一一对应（camelCase → kebab-case）。
- 确认机制：MCP 的 confirmationToken 往返 → CLI 的交互确认 / `--yes`。
- 旧 MCP 代码保留在 `uiautomation_mcp/tools/` 与 `server.py`（需 `pip install fastmcp mcp`），不再作为入口。

## 常见问题

- **控件找不到**：尝试 `--name-contains` 模糊匹配、加大 `--depth`、先用 `children` 看真实控件树。
- **中文乱码**：CLI 已自动将 stdout 设为 UTF-8；如在旧终端仍乱码，执行 `chcp 65001`。
- **需要管理员权限的操作**：以管理员身份运行终端。
- **句柄为 0 的控件**（UWP/Chrome/Qt）：走祖先路径恢复，token 依然可用。

## 项目结构

```
uiautomation_mcp/
├── cli.py          # CLI 入口（argparse 子命令 + REPL）
├── service.py      # 31 个纯逻辑函数（无 MCP 依赖）
├── registry.py     # 跨进程 token 注册表（JSON 持久化 + 路径恢复）
├── core.py         # 控件查找/格式化/确认（与 MCP 共用）
├── models.py       # Pydantic 数据模型
├── picker_gui.py   # 交互式拾取器 GUI
└── tools/ server.py  # 旧 MCP 层（保留，需 fastmcp 才能 import）
```
