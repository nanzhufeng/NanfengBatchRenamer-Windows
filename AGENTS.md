# 南枫批量改名项目规则

- 本项目是 Windows 桌面批量文件改名工具，仓库根目录即本文件所在目录。
- 开始修改前先读 `docs/context.md`、`docs/domain-rules.md` 与 `docs/CURRENT_HANDOFF.md`。
- 业务规则以 `src/batch_renamer/core/` 为唯一所有者；UI 不得另写一套文件名生成、冲突或执行规则。
- 测试真实改名时只能使用测试创建的临时目录，不得对用户目录或 `test_samples/` 执行改名。
- 不引入网络、账号、Cookie、Token、签名密钥或遥测；日志不得进入 Git。
- Windows 工具 UI、打包与发布继续使用 `nanzhufeng-tool-standard`。
- 先运行 `python -m unittest discover -s tests -v` 与 `python -m compileall src`；只有用户明确要求时才重新打包或发布。
