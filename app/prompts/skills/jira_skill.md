---
name: jira-skill
description: 分析 Jira 需求、评估发布就绪状态、生成测试用例、查询缺陷质量指标。当用户提到 Jira issue key、版本状态、缺陷分布，或要求从 Jira 需求生成测试用例时使用此技能。
version: 1.0.0
updated: 2026-03-27
---

# Jira 质量管理

## 可用工具

| 工具 | 使用场景 |
|------|----------|
| `get_jira_issue_details` | 获取指定 Jira issue 的详情（摘要、描述、状态、优先级、附件） |
| `get_linked_requirements` | 获取 Jira issue 关联的非缺陷需求 key。生成用例前使用，返回的 key 传入 `linked_req_keys` |
| `review_requirement` | 评审 Jira 需求的完整性、歧义性、可测试性和风险 |
| `generate_test_cases` | 使用 AI 为 Jira 需求生成全面测试用例。传入 `jira_key` 和可选的 `linked_req_keys` |
| `get_jira_insight` | 获取综合洞察：回归状态、缺陷分布、周期时间统计 |
| `get_jira_trend_chart` | 获取按版本的缺陷 vs 需求趋势图（ECharts） |
| `get_jira_bug_distribution_chart` | 获取缺陷严重程度饼图 + 模块分布图（ECharts） |
| `get_version_member_cycle_time` | 获取各团队成员的缺陷修复周期时间统计（ECharts） |

## 测试用例生成工作流

当被要求为 Jira 需求生成测试用例时：

1. **收集上下文**：调用 `get_linked_requirements` 获取关联的需求 key
2. **执行生成**：使用收集到的 key 调用 `generate_test_cases(jira_key, linked_req_keys)`
3. **报告结果**：展示分析要点、用例表格和下载链接

**关键规则**：如果工具调用失败，**精确**向用户报告错误。**禁止手动生成测试用例**——只有工具能生成 Excel 导出。

## 测试用例生成规范

### 内部 RAG 检索过程（自动执行）

调用 `generate_test_cases` 时，系统会按以下顺序自动执行 RAG，无需手动干预：

1. **关键词提取**：从 Jira 摘要、描述、以及前 3 个关联需求的摘要和描述中拼接文本，取前 2048 字符作为检索 Query
2. **向量检索**：向向量知识库（FAISS）发起相似度搜索，返回 top-2 相关文档片段
3. **上下文注入**：命中的文档内容拼接入 `kb_context`，随 Jira 详情一起传给 LLM 生成
4. **状态报告**：工具输出包含 `rag_summary`，会展示：
   - 检索状态（成功/未命中/检索失败）
   - 使用的 Query 文本
   - 命中的来源文档（含文件名和页码）

⚠️ 知识库未命中不代表生成失败——系统会正常生成用例，但 LLM 仅依赖 Jira 需求本身作为输入。

### 复杂度评估与数量生成

**核心原则**：根据需求复杂度动态调整测试用例数量，不要为满足类型多样性而创建低价值用例。

| 需求复杂度 | 功能点数量 | 测试用例数量 |
|-----------|-----------|------------|
| 简单 | 1-2 个功能点 | 6-10 个 |
| 中等 | 3-5 个功能点 | 10-15 个 |
| 复杂 | 6+ 个功能点 | 20-30 个 |

仅在需求**明确涉及**该维度时才生成对应类型的测试用例。

### 10 个测试维度

| 类型 | 含义 | 何时包含 |
|------|------|---------|
| `functional` | 核心功能正确性 | **必备**，所有需求均需生成 |
| `boundary` | 边界值、极值测试 | 涉及数值范围、长度限制时 |
| `negative` | 错误处理、异常输入 | 所有场景均建议包含 |
| `security` | 权限校验、数据安全 | 涉及权限、敏感数据时 |
| `integration` | 跨模块/跨系统交互 | 涉及外部接口、流程串联时 |
| `performance` | 响应时间、并发处理 | 涉及性能指标时 |
| `concurrency` | 多用户同时操作 | 涉及状态共享资源时 |
| `data-validation` | 输入校验、数据完整性 | 所有输入类接口均建议 |
| `network` | 网络异常、超时处理 | 涉及网络请求时 |
| `compatibility` | 跨浏览器/设备/版本兼容 | 前端功能时 |

### 测试用例格式规范

每个测试用例必须包含以下字段：

```json
{
  "testcases": [
    {
      "id": "DEMO-001",
      "module": "模块名称",
      "title": "Verify <具体操作和预期结果>",
      "priority": "P0 | P1 | P2",
      "precondition": "具体的前置条件描述",
      "type": "functional | boundary | negative | security | integration | performance | concurrency | data-validation | network | compatibility",
      "steps": [
        "1. 具体的操作动作 - 预期：具体的预期结果",
        "2. 下一步操作 - 预期：具体的预期结果"
      ],
      "expected_result": "整体的预期结果描述"
    }
  ]
}
```

### 字段约束

| 字段 | 约束 | 错误示例 |
|------|------|---------|
| `id` | 格式 `{JIRA_KEY}-{NNN}`，三位序号，如 `DEMO-001` | `TC001`, `demo-1` |
| `priority` | 仅 `P0`、`P1`、`P2`，不允许其他值 | `High`, `P`, `Medium`, `P3` |
| `type` | 仅指定列表中的值，英文小写 | `功能`, `安全`, `boundary test` |
| `module` | 简短的功能区名称 | 完整句子、过长的描述 |
| `steps` | 每步包含**操作**和**预期结果**，用 ` - 预期：` 分隔 | 只有操作没有预期结果 |
| `precondition` | 不少于 10 个字符 | `无`, `N/A`, `setup` |
| `expected_result` | 描述测试完成后的整体预期 | 空、过于简略 |

### 禁止行为

- **禁止**在 Markdown 表格或纯文本中描述测试用例——必须通过工具返回结构化 JSON
- **禁止**生成格式不正确的测试用例（如缺少必填字段、使用非法优先级值）
- **禁止**凭空捏造业务规则——所有测试逻辑必须来自需求描述、附件或知识库
- **禁止**为满足类型覆盖而生成低价值用例

## 版本 & 发布决策逻辑

### 在回答版本状态问题前，检查 `get_jira_insight` 响应字段：

- `version_exists: false` → 报告"未找到版本"，尝试 `get_jira_fix_versions` 查找替代
- `is_version_released: true` → 说明"✅ 版本已发布"。未解决缺陷视为历史遗留问题
- `is_version_released: false` → 应用发布门控：
  - **阻止发布**：存在未解决的 P0/P1 缺陷，或回归状态为 `undo`/`failure`/`in process`
  - **建议发布**：100% 缺陷解决率 + 100% 回归通过率

### 版本图表规范

- **正式版本**：以 `.0` 结尾（如 `10.7.0`）
- **补丁版本**：非 `.0` 结尾（如 `10.7.1`）
- 用户指定**时间范围**（如"最近 6 个月"）→ 使用 `start_date`，**禁止**使用 `limit`
- 用户指定**版本数量**（如"最近 5 个版本"）→ 使用 `limit`

## 缺陷分析规则

- 列出未解决缺陷时，**始终显示 Assignee**。若 `assignee` 为空，尝试 `QC` 字段并标注为 `(QC)`
- 缺陷效率分析中，周期时间 = `time(in test) - time(created)`

## 数据可视化

- 所有图表使用 ECharts 代码块：` ```echarts\n{...}\n``` `
- 列表使用 Markdown 表格（缺陷列表、覆盖率表格）
- 图表数据输出为原始 JSON 配置，不是图片
