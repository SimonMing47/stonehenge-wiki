# Stonehenge Wiki 数据目录

该目录用于放置评测数据。系统不会依赖物理子目录判断业务分类，而是在启动时深度遍历 `docs/`，按文件后缀、正文关键词、批注/TODO 和相对路径动态建立索引。

## 支持的计数文件类型

`doc`, `docx`, `ppt`, `pptx`, `xls`, `xlsx`, `xml`, `java`, `py`, `html`, `md`, `js`

其他后缀也会被尽量读取为普通文本，供知识检索兜底使用，但不会纳入文件类型枚举计数。

`.doc/.ppt/.xls` 老式 Office 文件在安装 LibreOffice/`soffice` 时会先转换为现代 OOXML 格式再索引或修复；未安装时使用二进制文本兜底检索。

## 平台状态

`config.json` 控制平台运行方式。默认运行状态写入：

```text
stonehenge-wiki/.state/wiki.sqlite
```

该数据库包含可重建索引、批注元数据、审计事件和任务记录；不应手工编辑，也不需要提交到 Git。

受保护 API 可通过 `stonehenge-wiki/.env` 启用。复制 `.env.example` 为 `.env`，填入 `STONEHENGE_WIKI_API_TOKEN` 和 `STONEHENGE_WIKI_READ_TOKEN` 后，CLI、HTTP API、skill wrapper 和 readiness 检查都会自动加载；shell 中已经存在的同名环境变量优先。

来源注册表支持 `active`、`quarantined`、`missing` 状态。`quarantined` 来源仍保留路径、hash、版本和风险记录，但不会进入问答、工作台生成和编译后的 `wiki/` 知识面。命中 `Permission.json.file.deny` 的来源会被策略自动隔离。

## 工程一致性检查

建议每次改动文档、CLI、API 后执行：

```bash
python3 scripts/check_doc_consistency.py
```

脚本会校验 `INSTRUCTION.md`/`DESIGN.md`/`work/stonehenge_wiki/DESIGN.md` 中提到的命令与仓库实际 CLI flag 与 API 合约是否一致，避免历史文档与实现漂移。

Raw 页面和 REST CLI 支持查看来源详情，包括 metadata、脱敏抽取预览、版本、审核、风险和关联 wiki 区段：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --source-detail docs/03_学习材料/Knowledge-Notes.md
```

## LLM Agent

`config.json` 中的 `llm.agents` 支持独立 agent 配置。当前默认 agent 为 `opencode`，通过 `~/.hermes/.env` 读取 `DEEPSEEK_API_KEY`，provider 标记为 `opencode-hermes-deepseek`。Rust CLI 仍然只调用 REST API，不直接调用 opencode 或 Python。

可通过 REST CLI 测试 agent 配置和真实连接：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --test-llm-agent opencode --test-llm-live
```

## 编译型 Wiki

`AGENTS.md` 定义 wiki schema。运行：

```bash
./work/scripts/build_skill_cli.sh
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --compile-wiki
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --lint-wiki
```

平台会从 `docs/` 编译生成：

- `wiki/index.md`
- `wiki/sources/*.md`
- `wiki/topics/*.md`
- `wiki/log.md`

## 企业交付门禁

运行：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --readiness-report --group group-demo
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --export-readiness-report --group group-demo
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --export-release-bundle --group group-demo
```

导出的 Markdown 和 JSON 报告位于 `output/reports/readiness-report.*`。该报告以 pass/warn/fail 方式检查题组数量、权限安全、compiled wiki、no-RAG 架构、来源隔离、修复输出、审计、LLM 和 API token scope。release bundle 位于 `output/releases/`，只包含报告、题组、答案和 compiled wiki，不包含原始 `docs/` 或 `.state/wiki.sqlite`。

## 批注/TODO

结构化批注兼容中英文冒号、大小写和不规则空格：

```text
todo: 补充产品报价字段, to: 李四,end_date: 20251231
```

代码 TODO 示例：

```text
# TODO: 待实现接口,to:王五,end_date:20251015
```

## 安全

`Permission.json` 中的 `dir.deny`、`command.deny`、`file.deny` 支持精确匹配和简单 `*` 通配符。凡触发高危命令、黑名单文件、黑名单写目标、非环境信息密码提问或 prompt 注入意图，均统一返回：

```json
{"error_msg":"高危命令，拒绝访问"}
```
