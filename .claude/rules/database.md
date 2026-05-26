---
paths:
  - "src/paper_trading/models.py"
---

# 数据库规范

## 模型定义
- 所有模型继承自 pydantic `BaseModel`
- 字段必须有类型注解

## 命名约定
- 模型类名使用 PascalCase
- 字段名使用 snake_case

## 数据验证
- 使用 pydantic validators 进行业务逻辑验证
- 敏感字段不记录到日志
