# 自验证执行记录

本文件仅记录可复现命令和结果，不记录模型内部推理过程，也不包含任何凭据。

## Python 3.11

运行时：CPython 3.11.15（验证 3.11 语言/标准库兼容性），`openpyxl==3.1.5`。

```bash
python3.11 -m compileall -q work
PYTHONPATH=work python3.11 -m unittest discover -s work/tests -q
python3.11 scripts/check_doc_consistency.py
PYTHONPATH=work python3.11 -m stonehenge_wiki.contract_checks
git diff --check
```

结果：103 项测试全部通过；文档一致性通过；合同检查 0 error / 0 warning；diff whitespace 检查通过。

## 竞赛合同回归

```bash
PYTHONPATH=work python3.11 -m unittest \
  work.tests.test_public_group1_reference \
  work.tests.test_competition_scale -v
```

结果：

- 公开 8 题逐字段一致；
- 错误 Agent 路由不能覆盖固定输出合同；
- 210 文件 / 20 题端到端通过；
- 5 路共享目录并发通过，SQLite `integrity_check=ok`，无临时文件残留。

## OpenCode 真实模型边界

使用作品目录之外的 OpenCode GLM-5.2 配置执行只读探活。OpenCode 在空临时目录中以
`--pure --format json` 运行，并注入 deny-all 权限覆盖。结果：批量题型/安全裁决返回
白名单 schema；知识回答返回非空 `datas`；自由批注返回正文中真实存在的最小替换。

## 其他检查

- 4 个 Shell/Wrapper 脚本通过 `bash -n`；
- 当前树中已停用运行时名称内容与文件名均 0 命中；
- 凭据模式扫描 0 个文件命中；
- 本地环境未提供 Rust/Cargo，因此未重跑未改动的 Rust 源码；Python 合同检查仍解析并核对了 30 个 Rust CLI 路径。

## 交付包

最终包由 `scripts/package_submission.py` 的顶层 allowlist 生成并反向验证；只包含
`INSTRUCTION.md`、`work/`、`result/`、`logs/`，唯一根目录与 ZIP 名均为
`01_01_硬控AI三秒钟`，秘密扫描和路径逃逸检查通过。
