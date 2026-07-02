# Contributing to Stonehenge Wiki

本项目按 3 人协作模型维护：平台/API/安全、Web Console/产品体验、CLI/Skill/质量与发布。所有变更都应保持 `main` 可运行。

## 分支

- `feature/<area>-<summary>`：功能开发
- `fix/<area>-<summary>`：缺陷修复
- `docs/<summary>`：文档更新

## 提交前检查

按变更范围选择验证命令：

```bash
python3 -m compileall -q work
PYTHONPATH=work python3 -m stonehenge_wiki.contract_checks
PYTHONPATH=work python3 -m unittest discover -s work/tests -q
cargo fmt --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml --check
cargo test --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml
./work/scripts/build_skill_cli.sh
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --health
```

UI 变更需要在 `http://127.0.0.1:8765/` 做浏览器检查；安全、鉴权、输出 schema、SQLite schema、REST API 或 CLI 参数变更需要补充测试或说明。

## PR 内容

打开 PR 时使用 `.github/pull_request_template.md`。模板会提示 owner area、API/CLI/Web/security/data/release 影响、架构 guardrails、验证结果和证据链接。

每个 PR 至少包含：

- 变更范围
- 影响模块
- 验证命令和结果
- UI 变更截图或说明
- 安全/鉴权影响
- 是否涉及数据迁移或向后兼容

## Issue 内容

Bug 和 Feature 使用 `.github/ISSUE_TEMPLATE/` 下的表单。Issue 必须标明 area，并说明复现步骤或验收标准；涉及 CLI、release、auth、安全、Web Console 或 API contract 时，应给出相应证据和验证命令。

## Review 规则

- API、schema、安全、鉴权、输出格式变更：平台 owner 和质量 owner 必须 review。
- UI 变更：Web owner 主审，平台 owner 确认 API，质量 owner 确认测试。
- CLI/skill/release 变更：质量 owner 主审，平台 owner 确认 API，Web owner 确认文案。
- 文档变更：至少 1 人 review；涉及安全或发布时 2 人 review。

## 禁止事项

- 公开 Rust CLI 不得调用 Python、本地项目代码或绕过 REST API。
- 不得引入向量库/RAG 作为核心检索面。
- release bundle 不得打包原始 `docs/` 或 `.state/wiki.sqlite`。
- 页面品牌不得回退到旧名称。
- 页面生成入口不得显示 “PPT” 作为主要文案。
