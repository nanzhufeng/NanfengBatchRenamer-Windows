# 南枫批量改名项目上下文

## 项目身份

- App：南枫批量改名
- 平台：Windows 10/11 桌面
- Git 根目录：`C:\Users\Administrator\Documents\00-日常问答\南枫批量改名`
- GitHub：`nanzhufeng/NanfengBatchRenamer-Windows`（私有）
- 当前正式基准：标签与 GitHub Release `v1.1.4`
- 正式资产：`NanfengBatchRenamer-Windows-v1.1.4-Setup.exe` 与对应 SHA-256 文件

## 第一用户任务

在一个文件夹中读取需要处理的文件，组合规则并实时检查新文件名；确认无非法名称和冲突后批量改名，必要时撤销最近一次成功批次。

完成定义：用户选中的文件按预览结果完成改名；未选中文件不变化；冲突或非法名称阻止执行；结果有中文状态和 JSON 日志；最近一次可安全撤销。

## 技术栈

- Python 3.13.3
- PySide6：Windows 桌面 UI、表格、计时器、剪贴板与文件夹对话框
- Python 标准库：`pathlib`、`dataclasses`、`json`、`re`、`os`、`datetime`
- PyInstaller 6.21.0：单文件、无控制台 Windows EXE
- Inno Setup 7.0.2 x64：中文安装向导、开始菜单、可选桌面快捷方式与卸载
- `unittest` + PySide6 `QTest`：核心与 UI 合同回归
- BAT / PythonW / PowerShell：源码调试与静默启动入口
- GitHub：私有源码仓库、版本标签与 Windows Release

本项目没有数据库、账号、网络请求、云服务、Cookie、API Key 或第三方登录。

## 目录结构

```text
南枫批量改名/
├─ AGENTS.md                         项目级安全与入口规则
├─ README.md                         用户运行和功能说明
├─ docs/
│  ├─ context.md                     本项目稳定上下文与技术栈
│  ├─ domain-rules.md                项目专属业务合同
│  ├─ experience-audit.md            正式经验审计与证据矩阵
│  ├─ decision-log.md                长期有效决策
│  └─ CURRENT_HANDOFF.md             当前动态交接
├─ src/batch_renamer/
│  ├─ app.py                         单窗口 UI、交互与展示状态
│  └─ core/
│     ├─ models.py                    文件、计划、结果、规则数据模型
│     ├─ scanner.py                   当前目录文件扫描与扩展名过滤
│     ├─ rules.py                     唯一规则链
│     ├─ preview.py                   预览、冲突与可执行计划
│     ├─ sorting.py                   自然数字排序键
│     ├─ validator.py                 Windows 文件名和路径校验
│     └─ executor.py                  真实改名、日志与最近一次撤销
├─ tests/                             临时目录核心测试与离屏 UI 合同测试
├─ scripts/                           性能基线与分辨率截图检查
├─ build_assets/                      用户确认的原图、圆角 PNG 与 Windows ICO
├─ test_samples/                      只读固定样本，不用于真实执行测试
├─ packaging_entry.py                 PyInstaller 入口
├─ 南枫批量改名-Windows.spec          Windows 单文件构建配置
├─ installer/                         Inno Setup 7 x64 安装配置
├─ 启动_南枫批量改名.bat              普通源码启动入口
├─ run_silent.pyw                     静默启动与错误日志入口
└─ launch.ps1                         调试启动入口
```

`build/`、`dist/`、`release/`、`logs/` 与 `__pycache__/` 是本地生成物，不进入 Git。

## 运行入口

1. 普通源码入口：`启动_南枫批量改名.bat` -> `run_silent.pyw` -> `batch_renamer.app.run()`。
2. 模块入口：设置 `PYTHONPATH=src` 后运行 `python -m batch_renamer`。
3. 打包入口：`packaging_entry.py` -> `batch_renamer.app.run()`。
4. Windows 安装包构建：`powershell -ExecutionPolicy Bypass -File scripts/build_windows_installer.ps1`。

## 架构与数据流

```text
文件夹 + 扩展名选择
        ↓
scanner.scan_files
        ↓
FileItem 列表 + UI RuleSettings
        ↓
rules.apply_rules（唯一名称变换规则链）
        ↓
preview.build_preview + validator
        ↓
RenamePlan（只含可安全执行且确实变化的行）
        ↓
executor.execute（临时名阶段 → 最终名阶段 → 失败整批回滚）
        ↓
Windows 文件系统 + JSON 日志 + last_undo.json
```

概念所有权：

| 概念 | 唯一所有者 | UI 消费方式 |
|---|---|---|
| 文件扫描与格式过滤 | `core/scanner.py` | 只提供路径和筛选值 |
| 新文件名规则顺序 | `core/rules.py::apply_rules` | 收集 `RuleSettings` 后调用预览 |
| 状态、冲突与执行计划 | `core/preview.py`、`core/validator.py` | 展示结构化状态，不二次猜测 |
| 真实改名与撤销 | `core/executor.py` | 确认后调用并展示结果 |
| 表格、复制提示、排序和拖动选择 | `app.py::MainWindow` | 只改变展示或选择状态 |

## 当前能力边界

已实现：当前目录文件读取、扩展名多选/全部、实时预览、查找替换、前后缀、指定位置插入、开头/结尾/中间删除、自动编号、扩展名大小写、自然数字排序、拖动多选、点击复制、冲突/非法名检查、事务执行、仅大小写改名、失败整批回滚、恢复清单、日志、单级事务撤销和按屏幕等比缩放。

明确不支持：文件夹改名、递归子目录、正则替换、EXIF/元数据、序列帧智能分组、多级历史、跨磁盘移动、账号或云同步。

## 当前验证等级

- 已实现：源码与 Windows Release 均存在。
- 自动合同：见 `tests/`，覆盖规则、预览、扫描、事务执行/撤销、性能报告、五档分辨率、跨屏重复缩放、文字边界与关键无障碍名称。
- 构建：PyInstaller 单文件和 Inno Setup 7 x64 中文安装包构建通过。
- 安装：隔离目录完成静默安装、摘要比对、窗口启动、卸载和注册表清理。
- 真实 Windows：正式 EXE 已启动，窗口标题为“南枫批量改名”，进程响应正常。
- 真实桌面：正式安装的快捷方式显式引用版本化 ICO；小智桌面重启后，实际 48px 图标圆角外显示桌面背景。
- 真实用户文件完整链路：本次沉淀未对用户目录重新执行改名。
- 性能：`docs/performance-baseline.json` 固定记录 `1,000 / 10,000 / 50,000` 条规则、预览、自然排序耗时和 Python 跟踪内存峰值。
- 分辨率：`1280×720` 至 `2200×1152` 离屏截图与布局检查通过；真实双显示器和屏幕阅读器未验。

## 开发与交付入口

开始任务先读：`AGENTS.md` -> `docs/context.md` -> `docs/domain-rules.md` -> `docs/CURRENT_HANDOFF.md`。涉及 UI、Windows 打包或 Release 时再读取用户级 `nanzhufeng-tool-standard`。
