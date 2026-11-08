# Vanna SQLite Runner：查询兼容与可选只读执行

基于 Vanna 的固定版本，用 AI 辅助开发修复 SQLite 查询结果处理，并增加可选只读执行。这里展示的是**一个执行器的改进、复现和验证**。

上游：[vanna-ai/vanna](https://github.com/vanna-ai/vanna)，固定提交 `365d0617c1a4567ffee1b19b40c27feb4206bfcf`，MIT。原说明见 [README-UPSTREAM.md](README-UPSTREAM.md)，来源见 [UPSTREAM.md](UPSTREAM.md)。本地历史始于上游归档导入，不是上游 Git 历史；无上游 PR 或合并记录。

## 改了什么

- 用 `cursor.description` 判断结果集，支持注释开头的查询、CTE、VALUES、空结果列与重名列。
- `INSERT … RETURNING` 先取完结果再提交，修复未取完结果时提交引发的 SQLite 异常。
- 增加可选 `read_only=True`：只打开已有数据库，结合 URI `mode=ro`、`query_only` 和 authorizer 拒绝写入、DDL、ATTACH 和写入型 PRAGMA，允许列明的元数据 PRAGMA。默认仍为读写模式，兼容旧调用。
- 验证特殊路径、缺失文件、失败后再次查询和连接释放。

## 验证结果

| 验证 | 已有结果 | 范围 |
|---|---|---|
| 固定 29 例 before/after | 7/29 → 29/29 符合预期 | 含 12 例新增只读能力；上游没有该参数，这部分属于扩展，不计作上游缺陷 |
| 新增回归 | 44 例通过 | 真实 SQLite 执行 |
| 上游相关测试 | 7 例通过 | 组件相关子集 |
| 独立复验 | 2026-11-07 R1 accepted | 查询兼容与只读组件，不代表整个平台验收 |

[G1 交付与原始证据](docs/G1-交付.md)保留交付时的状态与后续 R1 结论；当前发布说明见 [PUBLICATION.md](PUBLICATION.md)。

## 本地复现

先创建虚拟环境。下列 `python` 指虚拟环境解释器：Windows 为 `.venv/Scripts/python.exe`，Linux/macOS 为 `.venv/bin/python`。

```bash
python -m venv .venv
# 激活虚拟环境后执行
python -m pip install -r requirements-lock.txt
python -m pip install -e .
python tools/reproduce_g1.py --out reproduce-output
python -m pytest tests/test_sqlite_runner_maintenance.py -q
python tools/demo_g1.py
```

复现使用临时 SQLite，无需模型密钥，不调用付费模型。精确环境见交付文档。

## 阅读代码

- [执行器](src/vanna/integrations/sqlite/sql_runner.py)
- [44 例回归](tests/test_sqlite_runner_maintenance.py)
- [冻结上游](baseline/upstream_sql_runner.py)
- [源码补丁](patches/0001-fix-sqlite-runner.patch)
- [一键对照](tools/reproduce_g1.py)

原 MIT 许可与 Vanna.AI 版权保留于 [LICENSE](LICENSE)。上游自动发布及整包工作流归档于 `.github/upstream-workflows/`，个人展示版不触发上游发行任务。本轮没有修改产品源码。

[本次改进的版本与提交映射](SOURCE-HISTORY.md)
