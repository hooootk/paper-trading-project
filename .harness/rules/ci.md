# CI 规范文档

## 概述

本项目使用 [GitHub Actions](https://docs.github.com/en/actions) 作为持续集成平台。每次推送到 `main`/`develop` 分支或提交 Pull Request 时自动触发检查。

## 工作流定义

配置文件位于 `.github/workflows/ci.yml`，包含两个并行 Job：

```
push / PR → ┌─ lint ──────┐
            │  ruff check  │
            │  mypy strict │
            └──────────────┘
            ┌─ test ───────────────────────┐
            │  pytest (3.12 + 3.13 matrix) │
            │  coverage report             │
            └──────────────────────────────┘
```

## Job 明细

### 1. Lint & Type Check

| 步骤 | 命令 | 说明 |
| --- | --- | --- |
| 安装依赖 | `pip install .[dev]` | 安装项目及开发依赖 |
| Ruff 检查 | `ruff check .` | 代码风格检查，配置见 `pyproject.toml` `[tool.ruff]` |
| Mypy 检查 | `mypy src/` | 静态类型检查，strict 模式零容忍 |

### 2. Test

| 步骤 | 命令 | 说明 |
| --- | --- | --- |
| 安装依赖 | `pip install .[dev]` | 同上 |
| 运行测试 | `pytest --cov=paper_trading --cov-report=term-missing --cov-report=xml -v` | 运行全部测试并生成覆盖率报告 |
| 上传覆盖率 | codecov/codecov-action@v4 | 仅 3.12 执行，`fail_ci_if_error: false` 不阻塞 CI |

Python 版本矩阵：`3.12` 和 `3.13`，确保向前兼容。

## 触发规则

| 事件 | 触发条件 |
| --- | --- |
| `push` | 推送到 `main`、`master`、`develop` 分支 |
| `pull_request` | 向 `main`、`master` 分支发起 PR |

## 本地前置检查

提交前建议在本地运行以下命令，避免 CI 失败后反复修正：

```bash
ruff check .          # 代码风格
mypy src/             # 类型检查
pytest                # 运行测试
```

或使用 pre-commit 自动执行：

```bash
pip install pre-commit
pre-commit install
```

## 通过标准

- **Lint Job**：ruff 零告警 + mypy strict 零错误，任一失败则 Job 失败
- **Test Job**：全部测试通过，任一用例失败则 Job 失败
- **PR 合并条件**：两个 Job 均通过（建议在 GitHub 分支保护规则中设置）

## 与项目规范的对应关系

| CLAUDE.md 硬性规则 | CI 中的对应检查 |
| --- | --- |
| 所有函数必须有类型注解 | `mypy strict` 模式强制检查 |
| 禁止 `import *` | `ruff check` 中的 `F403`/`F405` 规则 |
| 新增代码必须有测试 | `pytest --cov` 覆盖率报告 |
| 单文件 ≤ 400 行 | 未纳入自动检查，CR 时人工审查 |
| 提交规范 | 未接入 commitlint，后续可加 |
