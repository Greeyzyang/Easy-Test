---
name: testing-skill
description: 分析测试报告、诊断失败原因、查询测试执行数据。当用户询问测试结果、失败分析、报告摘要，或需要通过 SQL 查询测试相关数据时使用此技能。
version: 1.0.0
updated: 2026-03-27
---

# 测试与质量保障

## 可用工具

| 工具 | 使用场景 |
|------|----------|
| `list_recent_reports` | 用户想查看最近的测试执行报告 |
| `get_test_report_summary` | 用户想获取特定报告的详情（通过率、数量） |
| `diagnose_test_failure` | 用户想理解某个测试或报告失败的原因 |
| `run_sql_query` | 用户需要查询原始测试数据（仅限 SELECT） |

## 快速上手

1. 优先使用工具获取数据，不要凭空捏造数字
2. 所有分析结论必须基于工具返回的真实数据
3. 报告失败时，提供可操作的建议（不只是描述问题）

## 分析测试失败

诊断失败时：

1. 调用 `diagnose_test_failure(report_id)`——可选传入 `case_id` 聚焦单个用例
2. 审查返回的错误信息和堆栈跟踪
3. 按严重程度总结，给出建议操作

**输出格式**：按严重程度（Critical/High/Medium/Low）总结发现，并给出建议操作。

| 严重程度 | 判定标准 | 建议操作 |
|---------|---------|---------|
| Critical | 核心流程阻断、主流程失败 | 立即处理，阻塞上线 |
| High | 重要功能缺陷、数据错误 | 尽快修复，影响当前迭代 |
| Medium | 非核心功能缺陷、边界问题 | 记录，下个迭代处理 |
| Low | UI 样式、提示文案问题 | 记录，优化版本处理 |

## SQL 查询规范

- **仅允许 SELECT 查询**——任何写操作（INSERT/UPDATE/DELETE/DROP）都会被拒绝
- 查询 `testreports` 和 `execution_details` 表以了解测试历史
- 为可读性限制结果为 10 行；在查询中使用 `LIMIT`
- 禁止在 SQL 中包含敏感凭据或硬编码 ID

**常用查询参考：**

```sql
-- 查询最近失败的用例
SELECT er.id, er.case_id, er.name, er.status, er.error_message, er.created_at
FROM execution_details er
JOIN testreports tr ON er.report_id = tr.id
WHERE er.status = 'FAIL'
ORDER BY er.created_at DESC
LIMIT 10;

-- 查询项目通过率趋势
SELECT tr.name, tr.total, tr.passed, tr.failed,
       ROUND(tr.passed * 100.0 / NULLIF(tr.total, 0), 1) as pass_rate
FROM testreports tr
ORDER BY tr.created_at DESC
LIMIT 20;
```

## 测试报告解读

- 优先使用本地测试报告数据回答"测试报告"或"执行详情"相关问题
- 使用 Jira 数据获取更高层次的质量视图（缺陷趋势、发布就绪状态）
- 报告摘要必须包含：**总用例数、通过率、失败数、阻塞数**
- 失败用例分析必须包含：**失败率、最高失败模块、主要错误类型**
