# UIAutomation MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![MCP](https://img.shields.io/badge/Protocol-MCP-green.svg)](https://modelcontextprotocol.io/)

> 基于 [Python-UIAutomation-for-Windows](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows) 的 MCP (Model Context Protocol) 服务器

**特别感谢** [yinkaisheng](https://github.com/yinkaisheng) 开发的优秀 UI 自动化库，本项目是其 MCP 封装实现。

---

## 简介

UIAutomation MCP Server 让 AI 助手（如 Claude、ChatGPT）能够通过 MCP 协议直接操作 Windows UI 控件，实现：

- 自动化桌面应用程序操作
- 控件信息查询与截图
- 键盘鼠标模拟
- 窗口管理

支持的应用类型：Win32、MFC、WPF、Windows Forms、Modern UI (UWP)、Qt、Firefox、Chrome、Electron 等。

## 安装

### 方式 1: uv 安装 (推荐)

```bash
uv sync
```


## 配置

在 Claude Desktop 或其他 MCP 客户端的配置文件中添加：



### 方式 : uv 开发模式

```json
{
  "mcpServers": {
    "uiautomation": {
      "command": "uv",
      "args": [
        "--directory",
        "D:\\path\\to\\Python-UIAutomation-for-Windows",
        "run",
        "--no-project",
        "main.py"
      ],
      "type": "stdio"
    }
  }
}
```


## 可用工具

### 控件查找 (6)

| 工具 | 描述 |
|------|------|
| `ui_find_window` | 查找顶层窗口 |
| `ui_find_control` | 查找子控件 |
| `ui_get_children` | 获取子控件列表 |
| `ui_get_focused` | 获取当前焦点控件 |
| `ui_get_foreground` | 获取前台窗口 |
| `ui_control_from_point` | 获取屏幕坐标处的控件 |

### 交互操作 (5)

| 工具 | 描述 |
|------|------|
| `ui_click` | 点击控件 (支持左键/右键/双击) |
| `ui_send_keys` | 发送键盘输入 |
| `ui_set_value` | 设置文本值 |
| `ui_close_window` | 关闭窗口 (需确认) |
| `ui_move_window` | 移动/调整窗口 |

### 信息查询 (6)

| 工具 | 描述 |
|------|------|
| `ui_get_properties` | 获取控件属性 |
| `ui_get_text` | 获取文本内容 |
| `ui_get_rect` | 获取边界矩形 |
| `ui_screenshot` | 控件/窗口截图 |
| `ui_exists` | 检查控件是否存在 |
| `ui_wait_for` | 等待条件满足 |

### Pattern 操作 (6)

| 工具 | 描述 |
|------|------|
| `ui_invoke` | 调用按钮 (InvokePattern) |
| `ui_toggle` | 切换状态 (TogglePattern) |
| `ui_expand_collapse` | 展开/折叠 (ExpandCollapsePattern) |
| `ui_select_item` | 选择项 (SelectionItemPattern) |
| `ui_scroll` | 滚动控件 (ScrollPattern) |
| `ui_terminate_process` | 终止进程 (需确认) |

### 辅助工具 (5)

| 工具 | 描述 |
|------|------|
| `ui_clipboard_get` | 获取剪贴板内容 |
| `ui_clipboard_set` | 设置剪贴板内容 |
| `ui_list_processes` | 列出运行中的进程 |
| `ui_show_desktop` | 显示/最小化所有窗口 |
| `ui_get_screen_size` | 获取屏幕尺寸 |

### 交互式控件抓取 (2)

| 工具 | 描述 |
|------|------|
| `ui_interactive_pick` | 非阻塞启动 tkinter 抓取器，立即返回 `pick_id` |
| `ui_pick_result` | 按 `pick_id` 查询抓取结果；`timeout_seconds=0` 仅检查状态 |

用法示例：

```text
1. 调用 ui_interactive_pick(delay_seconds=3)
2. 用户把鼠标移到目标控件 → 点“下一步” → 倒计时抓取 → 点“完成”
3. 调用 ui_pick_result(pick_id) 获取结果
```

返回内容包含：

- `chain`：目标控件 + 祖先链
- `searchDepth`：从最近 `WindowControl` 到目标的层数（可直接用于 `searchDepth=`）
- `parentWindow`：最近父窗口信息
- `codeSuggestion`：可直接复制的 uiautomation Python 代码，例如：

```python
auto.WindowControl(Name='请选择导入Excel文件', ClassName='#32770').EditControl(
    searchDepth=3, Name='文件名(N):', AutomationId='1148'
)
```

点击“完成”后，所有 `codeSuggestion` 会自动复制到剪贴板。

也可以在终端手动启动抓取器（不走 MCP）：

```bash
# 推荐：不打印 JSON，完成后代码进剪贴板
uv run python -m uiautomation_mcp.picker_gui --delay 3 -q
```

**实现说明（Windows）**：为避免 Claude Code / MCP 以隐藏进程启动时 tkinter 窗口不可见，`ui_interactive_pick` 使用：

```text
pythonw.exe + DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
```

结果通过 `--result-file` 写临时 JSON，由 `ui_pick_result` 读取。

## 环境变量

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `UIAUTOMATION_LOG_LEVEL` | `INFO` | 日志级别 (DEBUG/INFO/WARNING/ERROR) |
| `UIAUTOMATION_TIMEOUT` | `10` | 默认操作超时秒数 |
| `UIAUTOMATION_ADMIN_CHECK` | `true` | 是否检查管理员权限 |
| `UIAUTOMATION_CONFIRMATION_ENABLED` | `true` | 危险操作确认机制 |

## 安全机制

以下操作需要用户确认才会执行：

- `ui_close_window` - 关闭窗口
- `ui_terminate_process` - 终止进程

可通过设置 `UIAUTOMATION_CONFIRMATION_ENABLED=false` 禁用确认机制（不推荐）。

## 使用示例

配置完成后，你可以对 AI 助手说：

```
请帮我打开记事本，输入 "Hello World"，然后保存到桌面
```

```
截图当前活动窗口并保存
```

```
列出所有打开的 Chrome 标签页
```

## 系统要求

- **操作系统**: Windows 7 SP1 或更高版本
- **Python**: 3.10 或更高版本
- **权限**: 建议以管理员权限运行以获得最佳兼容性

## 注意事项

1. **管理员权限**: 要自动化以管理员权限运行的应用，MCP 服务器也需要管理员权限
2. **Chrome/Electron**: 需要添加 `--force-renderer-accessibility` 启动参数
3. **UWP 应用**: 部分现代应用可能有访问限制

## 致谢

- [yinkaisheng/Python-UIAutomation-for-Windows](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows) - 核心库
- [Model Context Protocol](https://modelcontextprotocol.io/) - 协议规范

## License

Apache License 2.0
