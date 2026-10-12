# Project Status

## Verified
- Last verified: 2026-10-13 +08:00
- Branch: main
- Code baseline: v1.2.0 发布源码（提交与远端状态见本轮交接）
- Status: Active
- Scope: Windows 源码工作台、真实控件、隔离临时文件改名/撤销、BAT启动。详细恢复见 CURRENT_HANDOFF.md。

## Current
- 灰白三栏工作台、固定类型筛选槽、完整五组规则、十列宽度比例、设置和关于已落实。
- BAT实际启动窗口标题“南枫批量改名”，响应正常，启动错误日志为空。
- 包含子文件夹已打通：勾选后递归读取，按原目录预览/检查冲突/事务改名/撤销；格式筛选仍有效。
- 关闭时保存窗口正常大小和最大化状态，下次启动恢复；超出当前屏幕的大小自动收窄，不保存文件选择或改名规则。
- 风险复查已修复旧预览执行、选择/排序后编号滞后、手动缩放控件未适配，以及空路径误读工作目录；执行前重新生成计划和检查冲突。

## Tests
| 层级 | 结果 | 范围/证据 |
|---|---|---|
| Core/UI | PASS | 47项 unittest；包括最新规则执行、选择/排序、手动缩放和空路径回归；artifacts/workbench-tests.log |
| Compile | PASS | compileall src tests scripts |
| Native rendering | PASS | artifacts/workbench-acceptance/main-window.png、settings.png、about.png |
| BAT launch | PASS | 源码窗口真实启动并响应，验证后正常关闭 |
| Package | PASS | v1.2.0 PyInstaller EXE及Inno Setup安装包；实际EXE窗口响应正常；发布合同14/14；EXE和安装包NotSigned |
| Release | PENDING | 正在提交源码、上传安装包并回验远端哈希 |

## In Progress / Blocked
无。

## Gaps
- 真实多显示器跨DPI、屏幕阅读器、高对比模式及大规模真实文件列表未本轮验证。
- 未覆盖本机已安装版本，安装器覆盖升级未本轮实测。

## Next
- 用户使用启动_南枫批量改名.bat验收。
- 完成GitHub上传与下载哈希回验。
