# LLM Wiki 运行说明（work）

完整说明见仓库根目录 `INSTRUCTION.md`。这里保留判题所需的最短执行路径。

## 环境

- Python：3.11.0
- Python 依赖：`python3.11 -m pip install -r work/requirements.txt`
- Agent runtime：`opencode`（判题平台提供）
- 旧式 Office 可选依赖：LibreOffice / `soffice`

## 目录自动发现

程序优先使用 `/app/code/judge-assets/01_01_llm_wiki/`，随后使用 `work/` 同级的 `llm-wiki/`，并验证其中存在 `docs/`、`question/` 和 `Permission.json`。仓库内的 `stonehenge-wiki/` 仅作为本地样例回退。可用 `LLM_WIKI_ROOT` 或 `--wiki-root` 显式覆盖。

## OpenCode

平台已配置时：

```bash
./work/skills/stonehenge-wiki/scripts/configure_opencode.sh
```

首次配置 GLM-5.2 时：

```bash
export OPENCODE_API_KEY='<由运行环境安全注入>'
export OPENCODE_PROVIDER='zhipu'
export OPENCODE_MODEL='glm-5.2'
export OPENCODE_BASE_URL='https://open.bigmodel.cn/api/coding/paas/v4'
./work/skills/stonehenge-wiki/scripts/configure_opencode.sh
```

配置只写入用户的 `~/.config/opencode/`，密钥不会进入仓库。

主 harness 会实际加载 `work/subagent/llm-wiki-adjudicator.md`：固定格式解析、数量、
Permission 黑名单与输出 schema 由 Python 确定性执行；模糊题型、安全语义、知识回答
和自由批注修复由 deny-all、空临时目录中的 OpenCode 子 Agent 裁决。评测资产内的
`config.json/.env` 不能选择模型命令、凭据文件或直连接口。

## 执行

运行全部题组：

```bash
PYTHONPATH=work python3.11 work/main.py --wiki-root /app/code/judge-assets/01_01_llm_wiki
PYTHONPATH=work python3.11 work/scripts/validate_answers.py --wiki-root /app/code/judge-assets/01_01_llm_wiki
```

启动 REST 服务：

```bash
./work/scripts/server.sh start
./work/skills/stonehenge-wiki/scripts/llm-wiki health
./work/skills/stonehenge-wiki/scripts/llm-wiki compile
./work/skills/stonehenge-wiki/scripts/llm-wiki ask '统计 docx 文件数量'
```

答案写入 `llm-wiki/output/`，修复文件写入 `llm-wiki/output/fixed/`，高危请求固定返回 `{"error_msg":"高危命令，拒绝访问"}`。
