# LLM-Wiki-System 运行说明

## 环境

- Python 3.11.0
- 必需依赖：无
- 推荐依赖：`openpyxl`，用于更完整地读取 Excel 单元格批注并生成透视表/透视图文件

安装推荐依赖：

```bash
python3 -m pip install openpyxl
```

## 目录

评测运行时，`work/` 同级应存在 `llm-wiki/`：

```text
llm-wiki/
  docs/
  question/
  output/
  Permission.json
work/
  main.py
  llm_wiki/
result/
  output.md
```

## CLI 入口

处理 `llm-wiki/question/` 下全部 `group-*.md`：

```bash
python3 work/main.py
```

处理指定题组：

```bash
python3 work/main.py --group group-1
```

指定 wiki 目录：

```bash
python3 work/main.py --wiki-root /path/to/llm-wiki --group group-1
```

单问调试：

```bash
python3 work/main.py --ask "统计 docx 文件数量"
```

索引检查：

```bash
python3 work/main.py --dump-index
```

自验证：

```bash
python3 work/main.py --self-test
```

## Skill 调用

仓库内置 Codex skill 位于：

```text
work/skills/llm-wiki/
```

可直接通过 wrapper 调用 CLI：

```bash
python3 work/skills/llm-wiki/scripts/run_llm_wiki.py --group group-1
```

如需安装到本机 Codex，可将 `work/skills/llm-wiki` 复制到 `${CODEX_HOME:-$HOME/.codex}/skills/`。

## 输出约定

- 答案写入 `llm-wiki/output/<group>-answer.md`
- 修复文件写入 `llm-wiki/output/fixed/`
- 成功运行日志追加到 `result/output.md`
- 高危命令统一返回 `{"error_msg":"高危命令，拒绝访问"}`

