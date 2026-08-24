# Windows UI 自动化 CLI Skill

通用型 Windows UI 自动化工具，通过命令行接口 (CLI) 驱动，兼容所有 AI 编程助手。

**核心原则**: 不绑定任何特定 AI 工具。任何能执行 shell 命令的 AI 助手（Claude Code、Cursor、Copilot、pi、Gemini CLI 等）都可以通过 `uiautomation-cli` 使用本 Skill。

**适用场景**: 操作任何 Windows 桌面应用（SAP GUI、记事本、浏览器、Chrome/Edge、Qt/Electron 应用等）的控件 —— 查找窗口/控件、点击、输入、读取文本、截图、高亮、交互式拾取。

## 安装

```bash
# 方式一：从源码安装（推荐）
cd path/to/uiautomation-cli
pip install -e .
pip install comtypes overlay-arrows-and-more

# 验证安装
uiautomation-cli --version
```

## 核心概念：Token（控件句柄跨进程）

每个被找到的控件会得到一个 token，注册在 `~/.uiautomation/registry.json`（持久化 5 分钟，跨 CLI 进程有效）。

```bash
# 查找窗口 → 拿 token
uiautomation-cli find-window --name "记事本"
# → {handle: 200284, token: "68fba016", name: "无标题 - 记事本", ...}

# 用 token 做后续操作（新进程也能用！）
uiautomation-cli find-control <token> --control-type EditControl
uiautomation-cli click --token <token2>
```

**重要规则**：
- 每次调用都是独立进程，但 token 持久化，跨命令可用。
- 长时间会话建议 `uiautomation-cli repl`（进程内缓存，更快）。
- `uiautomation-cli tokens` 查看已注册控件，`clear-tokens` 清空。

## 标准操作流程

### 1. 查找窗口 / 控件

```bash
# 顶层窗口：按标题 / 类名 / 进程ID
uiautomation-cli find-window --name "无标题 - 记事本"
uiautomation-cli find-window --process-id 12345

# 子控件：在父控件内查找（--parent-handle 或省略从桌面根找）
uiautomation-cli find-control --parent-handle 200284 --control-type EditControl
uiautomation-cli find-control --parent-handle 200284 --name-contains "OK" --control-type ButtonControl
uiautomation-cli find-control --name "登录" --index 1     # 第 N 个匹配

# 浏览控件树
uiautomation-cli children <token>            # 直接子控件
uiautomation-cli children <token> --depth 2  # 更深层
uiautomation-cli foreground / focused        # 前台窗口 / 焦点控件
uiautomation-cli from-point <x> <y>          # 屏幕坐标处控件
```

**找不到控件时的排查**：
1. `children` 看真实控件树，确认类型和名称（控件类型是 EditControl/ButtonControl/WindowControl 等）。
2. 用 `--name-contains` 模糊匹配代替精确 `--name`。
3. 加大 `--depth`（默认无限，但深层遍历慢）。

### 2. 交互操作

```bash
# 点击：控件或坐标
uiautomation-cli click --token <T>
uiautomation-cli click --token <T> --button right --double
uiautomation-cli click --x 100 --y 200 --button left

# 键盘输入（支持特殊键 {Ctrl} {Enter} {Tab} {F5} 等）
uiautomation-cli send-keys <T> "用户名"
uiautomation-cli send-keys <T> "{Ctrl}a{Ctrl}c"   # 全选复制

# 设置值 / 移动窗口
uiautomation-cli set-value <T> "内容"
uiautomation-cli move-window <T> --x 0 --y 0 --width 800 --height 600
```

**重要经验：对话框按钮优先用 `invoke` 而非 `click`**：
`invoke` 走 UI 自动化协议（InvokePattern），不依赖窗口前台焦点，模态对话框也能触发，比物理点击可靠得多。

```bash
uiautomation-cli find-control --parent-handle <dlg> --name-contains "保存" --control-type ButtonControl
uiautomation-cli invoke <button-token>
```

### 3. 读取与验证

```bash
uiautomation-cli text <T>                # 读取文本（Value→Text→Name 逐级回退）
uiautomation-cli properties <T>          # 全部属性
uiautomation-cli properties <T> --properties name,rect,processId
uiautomation-cli rect <T>                # 边界 + 中心点
uiautomation-cli exists <T>              # 是否存在
uiautomation-cli wait-for control_exists --token <T> --timeout 10
uiautomation-cli wait-for control_disappear --token <T> --timeout 10
uiautomation-cli screenshot <T> --save-path ./shot.png
```

### 4. 其他常用

```bash
uiautomation-cli list-processes --filter notepad   # 找进程
uiautomation-cli clipboard-set "内容"              # 写剪贴板
uiautomation-cli clipboard-get                     # 读剪贴板
uiautomation-cli highlight --token <T> --color red --duration 2   # 高亮验证
uiautomation-cli pick --delay 3                    # 交互式拾取器（GUI，鼠标指向+点完成）
uiautomation-cli scroll <T> --direction down --amount large
uiautomation-cli select-item <T> / toggle <T> / expand-collapse <T> --action expand
```

## AI 使用建议（agent 注意事项）

1. **一次调用做一件事**，通过 token 串联。`find-window` → `find-control` → `操作` → `验证`。
2. **操作后必须验证**：用 `text`/`exists`/`screenshot` 确认操作生效，不要盲目假设。
3. **危险操作需确认**：`close-window` 和 `terminate-process` 默认交互确认；agent 应显式加 `--yes`。
4. **脚本化用 `--json`**：
   ```bash
   uiautomation-cli find-window --name "记事本" --json   # 解析 .data.token
   ```
   成功退出码 0，业务失败退出码 1（含错误码/提示）。
5. **Windows 控制台中文**：CLI 已自动 UTF-8 输出；若 agent 解析乱码，检查终端代码页 `chcp 65001`。
6. **需要管理员权限的控件**（部分系统窗口）：以管理员运行终端。
7. **handle 为 0 的控件**（UWP/Chrome/Qt 内部元素）：token 通过祖先路径恢复，依然可用，别慌。

## 典型场景示例

### 示例 1：在记事本中输入并保存

```bash
# 1. 启动并找到窗口
notepad &
uiautomation-cli find-window --name "无标题 - 记事本" --json   # → T_WIN
# 2. 找到编辑区并输入
uiautomation-cli find-control --parent-handle <hwnd> --control-type EditControl --json  # → T_EDIT
uiautomation-cli send-keys <T_EDIT> "Hello from uiautomation-cli"
# 3. 验证
uiautomation-cli text <T_EDIT>            # → Hello from uiautomation-cli
# 4. 保存（Ctrl+S → 文件对话框 → 输入文件名 → 保存）
uiautomation-cli send-keys <T_EDIT> "{Ctrl}s"
uiautomation-cli find-window --name-contains "另存为"   # 对话框（按需适配）
```

### 示例 2：SAP GUI 自动化

```bash
uiautomation-cli find-window --name "SAP Easy Access" --json          # → T_SAP
uiautomation-cli find-control --parent-handle <hwnd> --name-contains "VA03" --json  # 事务码输入
uiautomation-cli set-value <T> "VA03"
uiautomation-cli send-keys <T> "{Enter}"
uiautomation-cli wait-for control_exists --name-contains "物料显示" --timeout 15
```

### 示例 3：调试/定位控件

```bash
# 想知道某个按钮/输入框在哪：高亮 + 截图
uiautomation-cli find-control --parent-handle <hwnd> --name-contains "搜索" --control-type ButtonControl --json
uiautomation-cli highlight --token <T> --color green --duration 3
uiautomation-cli screenshot <parent-token> --save-path ./ui.png
```

## 故障排查

| 问题 | 解法 |
|------|------|
| 找不到控件 | `children` 看真实树；`--name-contains` 模糊匹配；`--depth` 加大 |
| token 失效 | 控件窗口已关闭或 5 分钟过期；重新 `find-*` |
| 点击没反应 | 优先用 `invoke`；确认控件 `enabled/visible`；窗口可能被遮挡，先 `SetFocus`（click 内部会做） |
| 中文乱码 | `chcp 65001`；CLI 已自动 UTF-8 |
| 权限不足 | 管理员运行终端 |
| 前台窗口被抢 | 用 `find-window`+`click`（内部 SetFocus），或 `send-keys` 到目标控件 |
