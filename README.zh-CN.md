# llama-doctor

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

**针对你当前安装的 llama.cpp build，检查、诊断并迁移启动命令。**

`llama-doctor` 会探测你实际选择的 `llama-server` 或 `llama-cli`，读取它自己的 `--help` 输出，并按照这一份 build 的真实参数表验证命令。

项目定位刻意保持单纯：它是 **命令检查器 + 迁移助手**，不是模型启动器，也不是性能优化器。

## 语言

桌面 GUI 支持：

- English
- 简体中文
- 日本語

GUI 会尽量按照系统语言启动，并记住你最后选择的语言。

CLI 可以对每条命令指定输出语言：

```bash
llama-doctor check --lang en ...
llama-doctor check --lang zh ...
llama-doctor check --lang ja ...
```

为了兼容原有脚本，CLI 默认仍然使用英文。诊断 `code` 永远不会因为语言改变，例如 `UNKNOWN_FLAG`、`MISSING_VALUE`，因此自动化脚本可以稳定依赖这些代码。

## 版本与兼容性

版本号同时记录这一版实际验证过的 llama.cpp 基线：

```text
llama-doctor  0.3.2.10731
                ^     ^
                |     llama.cpp build 编号
                llama.cpp 版本基线
```

这**不代表只能使用这一份 build**。参数表始终从你当前选择的可执行文件中读取，因此新版或旧版 llama.cpp 仍然可以被检查。版本号末尾的 build 编号只是用来记录这一版项目实际验证过的上游基线。

当前基线仍然是：

```text
llama.cpp 0.3.0-dev (build 10731)
```

## 功能

- 通过 `--version` 与 `--help` 探测你选择的可执行文件
- 为当前这份 llama.cpp build 动态建立参数表
- 识别 `-h,    --help, --usage` 这种带间距的别名
- 支持必填值、可选值、枚举值、显式数值范围和基础数值类型
- 支持常见 CMD、PowerShell、Bash 多行命令
- 支持带引号的 Unicode / 中文 / 日文路径
- 检测未知参数并给出相近参数建议
- 检测缺少值和不该出现的值
- 检测基础 integer / float / enum 错误
- 区分真正的 alias 和 `--perf / --no-perf` 这种正反开关
- 检测重复参数、alias 重复、正反开关冲突
- 当命令中的可执行文件名和当前选中的 build 不一致时给出提醒
- 在 llama.cpp help 暴露环境变量时报告 CLI 与环境变量重叠
- 直接从 help 中识别 `(DEPRECATED)`
- 报告已知的弃用 / 迁移参数
- 从多种 llama.cpp help 格式中提取 enum 选项
- 已移除的旧参数会作为错误，直到迁移完成
- 只自动应用明确标记为安全的迁移
- 多个旧参数映射到同一个新参数时拒绝擅自迁移
- Fix 后重新验证命令
- 将别名规范化成长参数
- 支持 JSON 诊断和稳定 exit code
- 本地缓存解析后的参数表
- 提供 Typer/Rich CLI 和 PySide6 GUI
- 运行时支持中 / 日 / 英三语

## 明确不做的事情

目前不做：

- 模型下载
- 模型管理
- Chat UI
- Benchmark
- VRAM 优化
- 自动性能调参

即：

```text
doctor != optimizer
```

## 开发环境安装

```bash
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -e .

# 需要桌面 GUI 时
pip install -e ".[gui]"
```

Linux / macOS：

```bash
source .venv/bin/activate
```

## CLI

检查命令：

```bash
llama-doctor check --exe "C:\AI\llama.cpp\llama-server.exe" "llama-server.exe -m model.gguf -c 32768"
```

中文输出：

```bash
llama-doctor check --lang zh --exe ./llama-server "./llama-server -m model.gguf -c 32768"
```

日文输出：

```bash
llama-doctor check --lang ja --exe ./llama-server "./llama-server -m model.gguf -c 32768"
```

从 stdin 读取：

```bash
echo "./llama-server -m model.gguf -c 32768" | llama-doctor check --exe ./llama-server -
```

输出 JSON：

```bash
llama-doctor check --json --lang zh --exe ./llama-server "./llama-server -m model.gguf -c 32768"
```

检查解析出的参数表：

```bash
llama-doctor probe --exe ./llama-server
llama-doctor probe --json --exe ./llama-server
```

规范化 alias：

```bash
llama-doctor normalize --exe ./llama-server "./llama-server -m model.gguf -c 32768"
```

应用安全迁移：

```bash
llama-doctor fix --exe ./llama-server "./llama-server --no-mmap -m model.gguf"
```

强制重新读取 `--help`：

```bash
llama-doctor check --no-cache --exe ./llama-server "./llama-server -m model.gguf"
```

### Exit code

| Code | 含义 |
| ---: | --- |
| `0` | 没有验证错误 |
| `1` | 验证错误、解析错误、修复后仍有错误，或需要人工确认 |
| `2` | llama-doctor 内部错误 |
| `3` | 可执行文件探测失败 |

## GUI

```bash
pip install -e ".[gui]"
llama-doctor-gui
```

使用流程：

1. 选择 English / 中文 / 日本語。
2. 选择 `llama-server` 或 `llama-cli`。
3. 探测可执行文件。
4. 粘贴命令。
5. 点击 **分析**。
6. 查看诊断结果。
7. 需要时使用 **修复命令** 或 **规范化**。

## 工作原理

当前选择的可执行文件自己的 `--help` 是主要事实来源。`llama-doctor` 不打算内置一份永远需要追着 llama.cpp 更新的完整参数数据库。

静态规则目录只保存无法从 `--help` 稳定推断的内容，例如：

- 已知参数迁移
- 不安全的旧参数组合

解析后的 schema 会根据可执行文件路径、大小、修改时间等信息缓存。可以设置：

```text
LLAMA_DOCTOR_CACHE_DIR
```

来修改缓存目录。

## 迁移安全

即使某条 migration rule 被标记为 safe，如果整条命令导致迁移结果存在歧义，`llama-doctor` 仍然不会擅自修改。

例如多个旧 mmap/mlock 参数可能最终都折叠到新的 `--load-mode`。如果多个旧参数同时影响同一个目标，程序会保留原命令并提示 **需要人工确认**，而不是猜测用户想要什么。

## 测试

```bash
python -m pytest -q
```

当前三语版本共有 **91 个测试**。除了原有 parser、validator、cache 等测试，还新增了：

- 语言代码归一化
- 中文 / 日文诊断文本
- 本地化 JSON
- 中文 CLI
- 日文 CLI
- 英文默认兼容性

## Windows 可执行文件

项目包含 PyInstaller 构建脚本：

```powershell
./scripts/build_windows.ps1
```

输出位于 `dist/`。带 `v*` tag 的 GitHub push 也会触发项目自带的 release workflow。

## 重要限制

- Shell parser 是保守实现，不会完整模拟 CMD、PowerShell 或 Bash。
- 当前一次只验证一条粘贴进来的 llama.cpp 命令。
- 从 `--help` 推断类型时故意偏保守，避免误报合法命令。
- Migration rule 只应该在上游行为已有文档或验证证据时加入。
- GUI 运行时需要可选依赖 PySide6。

## 隐私

所有验证都在本地进行。`llama-doctor` 不上传命令、不上传模型，也不要求联网。

## License

MIT
