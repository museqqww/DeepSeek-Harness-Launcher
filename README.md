# DeepSeek Harness 服务启动器（DSH Controller）

给 [DeepSeek Harness](https://www.deepseek.com/harness) 做的 **Windows 图形化服务控制器**：用一个小窗口完成「打开服务 / 关闭服务 / 开机常驻 / 一键打开网页 / 指定浏览器」，把后台服务变成完全可控。

> 非官方工具。DeepSeek 是 DeepSeek AI 的商标，本项目与其无隶属关系。

---

## 为什么需要它

官方 `dsh` 只有 **CLI + Web UI**，没有桌面客户端。`dsh web` 启动的是一个后台服务（默认 `http://127.0.0.1:3080`），实际用起来有三个坑：

1. **每次启动都会生成一个新的访问 token**，且只打印在启动那一刻的标准输出里，服务运行中无法找回；
2. 用 bat 手动起服务时容易重复点击，第二次实例因端口占用（EADDRINUSE）崩溃，**还会把含 token 的日志覆盖掉**，之后再也拿不到链接；
3. 服务随命令行会话结束被带走，没法稳定常驻。

本工具就是围绕这三点做的：日志留存、防重复启动、进程独立常驻。

---

## 功能

| 功能 | 说明 |
| --- | --- |
| **打开服务** | 后台启动 `dsh web --no-open`，输出写入 `dsh-web.log`；界面显示已等待秒数，就绪后状态变绿 |
| **关闭服务** | `taskkill /F /T` 杀整棵进程树，避免残留子进程占着 3080 |
| **打开网页** | 先嗅探：服务已运行 → 直接打开正确链接；未运行 → 先启动、就绪后自动打开。**不会重启或关闭服务** |
| **开机自启（长期加载）** | 在开始菜单「启动」目录写/删静默 VBS，勾选即生效 |
| **浏览器设定** | 自动探测 Chrome / Edge / Firefox，也可手动选 exe，设置自动保存 |
| **重建快捷方式** | 换电脑或换目录后，一键在开始菜单重建带图标的快捷方式 |
| **状态自检** | 每 2.5 秒刷新：运行中 / 已停止、PID、端口、当前访问地址 |

快捷键之外，命令行也提供两个入口：

```bat
python dsh-control.pyw --mkshortcut   :: 重建开始菜单快捷方式
python dsh-control.pyw --mkicon       :: 从 DeepSeek 官网下载图标（可选）
```

---

## 环境要求

- Windows 10/11
- **带 tkinter 的 Python**（python.org 官方安装包默认包含；精简版/嵌入式版可能没有）
- 已安装 DeepSeek Harness，即目录里存在 `node_modules\.bin\dsh.cmd`
- 端口 3080 未被占用

---

## 安装与使用

**第 1 步** 把这三个文件复制到 DeepSeek Harness 的安装目录（就是有 `node_modules` 的那个文件夹）：

```
dsh-control.pyw   主程序
pylnk3.py         生成快捷方式用（第三方，LGPL-3.0）
dsh-icon.ico      可选，不提供则自动尝试从官网下载
```

**第 2 步** 双击 `dsh-control.pyw`（`.pyw` 无控制台黑窗）。

**第 3 步** 点 **「打开网页」**：服务没起会自动起，约 10 秒后在浏览器打开带 token 的页面。也可以先点「打开服务」再点「打开网页」。

**可选 · 放到开始菜单**

```bat
python dsh-control.pyw --mkshortcut
```

或直接在窗口底部点 **「重建快捷方式」**。之后开始菜单搜「DeepSeek」即可找到，可右键固定到任务栏或开始屏幕。

---

## 换电脑 / 换目录

程序是**自定位**的：`dsh-control.pyw` 放在哪个目录，就管理哪个目录里的 dsh 服务。

所以迁移只需要把上面 3 个文件复制到新电脑的 dsh 目录即可，**盘符、路径变了都不用改代码**；快捷方式在新电脑上重建一次就行（pythonw 路径会按当前 Python 自动推导，不写死用户名）。

---

## 实现要点

- **状态检测**：`netstat -ano` 查 3080 端口的 LISTENING 项，取监听进程 PID
- **启动**：`subprocess.Popen` 起 `dsh.cmd web --no-open`，`CREATE_NO_WINDOW` 无窗口，stdout/stderr 重定向到 `dsh-web.log`
- **就绪判定**：日志中出现带 token 的 URL（真正可访问的标志），而不是「端口起来了」
- **失败判定**：只认「启动的进程本身已退出」+「端口也没监听」+「过 8 秒宽限」，三条件同时满足才报失败；此时弹窗会附上日志末尾内容
- **关闭**：`taskkill /F /T`
- **防重复启动**：启动过程中按钮置灰，`launch_service()` 入口另有端口检查

### 关于 token（重要）

token 每次启动都会变，且**无法从运行中的服务找回**（`--trusted-host` 也不能绕过鉴权）。所以：

- 服务一定要由本工具启动，才能保证日志里有 token；
- 如果服务是别的方式启动的，本工具会提示「关闭服务 → 打开服务」重新拿链接。

dsh 的鉴权流程是：带 token 访问 → `303` 跳转并种下 Cookie → 之后凭 Cookie 访问。因此拿到链接后**请直接用**，过期/失效会返回 401。

---

## 常见问题

| 现象 | 原因与处理 |
| --- | --- |
| 提示「读取不到访问链接」 | 该服务不是由本工具启动的，日志里没有 token。点「关闭服务」再点「打开服务」即可 |
| 报端口占用 / EADDRINUSE | 已有实例在跑（或上次没杀干净）。点「关闭服务」后再启动；失败弹窗里有日志原文 |
| 双击 `.pyw` 没反应 | Python 未安装 tkinter，或 `.pyw` 文件关联异常。可改用命令 `pythonw dsh-control.pyw` 试 |
| 浏览器打开后 401 | 链接不是本次启动的（token 已失效）。回到控制器重新点「打开网页」 |
| 点了按钮像没反应 | 按钮始终可点，无效操作会弹窗说明原因；只有启动过程中会短暂置灰 |
| 启动要十几秒 | 正常，dsh 冷启动较慢，界面会显示已等待秒数 |

---

## 文件说明

| 文件 | 许可 | 说明 |
| --- | --- | --- |
| `dsh-control.pyw` | MIT | 主程序，仅依赖 Python 标准库 + tkinter |
| `pylnk3.py` | LGPL-3.0 | 第三方单文件库，用于创建 `.lnk` 快捷方式；来源 <https://github.com/strayge/pylnk>，许可证见 `LICENSE-pylnk3.txt` |
| `LICENSE` | MIT | 本仓库主程序许可 |
| `LICENSE-pylnk3.txt` | LGPL-3.0 | 第三方组件许可 |

仓库不包含 DeepSeek 官方图标文件（避免直接分发第三方商标素材）；图标会在需要时从官网下载，缺失也不影响功能。

---

## 相关链接

- DeepSeek Harness 官网：<https://www.deepseek.com/harness>
- DeepSeek Harness 文档：<https://deepseek-harness.github.io/deepseek-harness/>
- pylnk3（本项目内置的第三方库）：<https://github.com/strayge/pylnk>
