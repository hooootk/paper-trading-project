---
paths:
  - "tests/**/*.py"
---

# 测试规范

## 测试结构
- 每个源文件对应一个 `test_*.py` 文件
- 使用 pytest fixtures 共享测试数据

## 命名约定
- 测试函数以 `test_` 开头
- 函数名描述测试场景：`test_<what>_<condition>`

## 覆盖要求
- 核心业务逻辑覆盖率 > 90%
- 每个公开函数至少一个测试
