---
description: Run tests for specified or changed files
argument-hint: [file...]
---

运行测试并输出结果：

1. 如果有 $ARGUMENTS，运行对应测试文件：`pytest $ARGUMENTS -v`
2. 如果没有参数，运行全部测试：`pytest tests/ -v`
3. 如果测试失败，分析失败原因并建议修复
