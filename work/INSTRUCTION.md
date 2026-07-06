# stonehenge-wiki 运行说明（Work Scope）

## 环境

- 首选入口：`work/skills/stonehenge-wiki/scripts/llm-wiki`（skill 脚本 CLI）
- 推荐依赖：`openpyxl`（更完整读取 Excel 批注）、`LibreOffice/soffice`（老式 Office 文件转换与修复）
- 无需 Rust/Cargo 也可以完成完整运行；Rust 二进制不再是运行入口。

## 目录

评测运行时，`work/` 同级应存在 `stonehenge-wiki/`：

```text
stonehenge-wiki/
  docs/
  wiki/
  question/
  output/
  Permission.json
work/
  main.py
  stonehenge_wiki/
result/
  output.md
```

## 平台能力

- `StonehengeWikiPlatform`：统一承载索引、问答、修复、审计、任务与治理
- `SQLiteStore`：保存来源、批注、审计、任务和指标（`stonehenge-wiki/.state/wiki.sqlite`）
- `wiki/`：保留 `docs/` 编译后的知识层（`wiki/index.md`、`wiki/sources`、`wiki/topics`）
- `HTTP API + 前端控制台 + skill 脚本` 共用同一套实现
- 鉴权：`STONEHENGE_WIKI_API_TOKEN` / `STONEHENGE_WIKI_READ_TOKEN`（`X-STONEHENGE-WIKI-TOKEN`）

## CLI 入口（首选）

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki
```

该脚本只做 HTTP 调用，不直接调用 Python 进程和 `opencode`。

### 关键环境变量

- `LLM_WIKI_URL`：API 地址（默认 `http://127.0.0.1:8765`）
- `LLM_WIKI_TOKEN`：`X-STONEHENGE-WIKI-TOKEN`
- `LLM_WIKI_ROOT`：默认 `--wiki-root`

### 最小三步能力链路

1. **配置 opencode 到系统**

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki configure-opencode
```

2. **编译知识库（传真实路径）**

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki compile --wiki-root /path/to/stonehenge-wiki
```

3. **提问并返回结果**

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki ask --wiki-root /path/to/stonehenge-wiki --question-id api-1 --level 简单 "统计 docx 文件数量"
```

一条命令完成 1~3：

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki quick-start --wiki-root /path/to/stonehenge-wiki --question-id api-1 --level 简单 "统计 docx 文件数量"
```

健康与契约检查：

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki health
./work/skills/stonehenge-wiki/scripts/llm-wiki api-contract
```

服务端启动后访问：

```text
http://127.0.0.1:8765/
```

## 进程与生命周期

```bash
./work/scripts/server.sh start
./work/scripts/server.sh status
./work/scripts/server.sh inspect
./work/scripts/server.sh restart
./work/scripts/server.sh stop
./work/scripts/server.sh tail
./work/scripts/health_check.sh
```

- `server.sh status` 返回码：`0=ok`、`1=degraded`、`2=blocked`
- `health_check.sh` 与 CI 兼容，可作为稳定健康闸门。

## 本地交付与一致性检查

```bash
python3 scripts/check_doc_consistency.py
PYTHONPATH=work python3 -m stonehenge_wiki.contract_checks
PYTHONPATH=work python3 -m unittest discover -s work/tests -q
```

## LLM Agent 与 opencode 配置

### 推荐配置入口

`stonehenge-wiki/config.json` 使用 agent 方式；`opencode` 作为默认 runtime：

- `default_agent: opencode`
- `llm.agents.opencode` 与 `category_agents` 按知识类别路由

若本机没有 opencode，可先运行配置脚本：

```bash
./work/skills/stonehenge-wiki/scripts/configure_opencode_from_hermes.sh
```

脚本行为：

- 自动安装 `~/.opencode/bin/opencode`（缺失时）
- 从 `~/.hermes/.env` 读取可用密钥（优先 `OPENCODE_API_KEY`，找不到再尝试 `OPENAI_API_KEY` / `DEEPSEEK_API_KEY`）
- 写 `~/.config/opencode/opencode-runtime.key`（`0600`）
- 写 `~/.config/opencode/opencode.json`（provider/model 以本机 runtime 约定为准）

### 示例验证

```bash
opencode --version
opencode models opencode-runtime
opencode run --pure --format json "只回复 OK"
./work/skills/stonehenge-wiki/scripts/llm-wiki configure-opencode
./work/skills/stonehenge-wiki/scripts/llm-wiki health
curl -s http://127.0.0.1:8765/llm/config | python3 -m json.tool
```

## HTTP API（节选）

- `GET /health`：健康状态与统计
- `GET /api/contract`：路由/字段/CLI 映射
- `GET /sources`、`GET /sources/detail`、`GET /sources/history`：来源管理视图
- `GET /wiki/compile`、`GET /wiki/sections`、`GET /wiki/search`：wiki 编译与检索
- `POST /wiki/compile`：编译 `docs/` 到 `wiki/`
- `POST /ask`：基于编译知识回答问题
- `POST /llm/test`：测试 LLM/agent 可用性
- `POST /groups/run`：运行题组
- `POST /slides/generate`：生成工作台演示
- `GET /reports/governance`、`POST /reports/readiness`：治理与门禁

如设置 token，`/ask` 和 `/explain` 默认公开，其余接口按 read/admin scope 控制。

## Skill 调用

仓库内建 skill 目录：

```text
work/skills/stonehenge-wiki/
```

推荐执行：

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki quick-start --wiki-root /path/to/stonehenge-wiki --question-id api-1 "统计 docx 文件数量"
```

## 输出约定

- 索引与审计：`stonehenge-wiki/.state/wiki.sqlite`
- 题组答案：`stonehenge-wiki/output/<group>-answer.md`
- 工作台与报告：`stonehenge-wiki/output/...`
- 高风险请求统一返回 JSON 错误信息
