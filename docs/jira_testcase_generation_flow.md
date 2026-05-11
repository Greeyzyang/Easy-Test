# Jira 需求生成测试用例流程说明

## 1. 文档目的

本文档用于梳理当前项目中“根据 Jira 需求生成测试用例”的实际执行流程，并明确以下职责边界：

- 前端如何发起生成与展示结果
- 后端 Task / Service / Prompt 的职责分工
- Jira 信息、历史需求、知识库（RAG）在生成链路中的参与方式
- 最终结果如何展示、查询和导出

本文档基于当前代码实现整理，重点描述已经落地的真实流程，而不是理想设计。

---

## 2. 总体流程概览

当前链路已经是一个显式包含知识库检索阶段的生成流程，而不是单纯的 Jira + 大模型直出。

整体流程如下：

1. 前端提交 `jira_key` 和可选 `linked_req_keys`
2. 后端启动异步任务 `generate_testcases_task`
3. Task 调用共享生成服务 `testcase_generation_service.generate_from_jira(...)`
4. Service 依次执行：
   - 缓存检查
   - 获取 Jira 主需求
   - 获取历史需求
   - 调用向量数据库检索相关产品文档（RAG）
   - 调用模型生成测试用例
   - 解析与归一化结果
   - 写缓存与任务结果
   - 推送实时进度
5. 前端通过 WebSocket 或轮询展示生成过程与最终结果
6. 用户可导出 Excel，导出文件中会保留知识库来源

---

## 3. 分层职责

### 3.1 前端层

前端页面位于：

- `vue-admin-template/src/views/assistant/index.vue`

前端主要职责：

- 接收用户输入的 `jira_key`
- 可选接收历史需求 keys
- 调用生成接口启动任务
- 通过 WebSocket 优先、轮询兜底的方式获取任务状态
- 展示以下内容：
  - 任务进度步骤条
  - 产品文档检索过程
  - 生成后的知识库参与情况
  - 分析要点
  - 测试用例列表
  - 覆盖建议与质量提示
- 触发 Excel 导出

### 3.2 Router 层

相关接口位于：

- `app/routers/testcases.py`

主要职责：

- 提供生成任务入口 `POST /rest/v1/testcases/ai-generate/`
- 提供任务状态查询 `GET /rest/v1/testcases/ai-task/{task_id}/`
- 提供导出接口 `GET /rest/v1/testcases/ai-export/{task_id}/`

当前特点：

- 状态查询优先读取 Redis 中的统一结果缓存
- 导出优先读取统一缓存，其次兼容 Celery 结果
- 导出时会额外抽取知识库来源并写入 Excel

### 3.3 Task 层

相关代码位于：

- `app/tasks/ai_tasks.py`

`generate_testcases_task` 当前主要是同步包装器，职责已经尽量收缩：

- 接收 Celery 任务上下文
- 调用共享 service
- 传入 `task_id` 与 `celery_task`

Task 不再承担主要业务逻辑，避免再次出现“Task 一套、Agent 一套”的分叉实现。

### 3.4 Service 层

核心实现位于：

- `app/services/testcase_generation_service.py`

这是当前 Jira 测试用例生成的真正编排核心，负责：

- 构建缓存 key
- 检查缓存是否命中
- 获取 Jira 主需求详情
- 获取历史需求详情
- 显式执行知识库检索（RAG）
- 将 Jira + 历史需求 + 知识上下文注入模型
- 解析模型输出
- 归一化测试用例结构
- 附加知识库检索元数据
- 保存统一结果
- 推送进度事件

### 3.5 Prompt 层

相关 Prompt 位于：

- `app/prompts/skills/jira_skill.md`
- `app/prompts/skills/knowledge_skill.md`

当前职责边界：

- `jira_skill.md`
  - 负责定义如何基于 Jira 需求设计测试用例
  - 负责测试分析、覆盖策略、输出结构、用例字段要求
  - 不再把“执行知识库检索”定义为自己必须完成的流程步骤

- `knowledge_skill.md`
  - 负责定义如何使用知识库内容
  - 负责检索结果的引用规则、缺失处理、冲突处理
  - 不负责决定某次 Jira 用例生成是否必须执行检索

结论：

- 是否执行 RAG 检索由 Service / Workflow 决定
- Prompt 只负责“如何使用已提供的知识上下文”

---

## 4. 当前生成流程的详细步骤

### 4.1 启动任务

用户在前端输入：

- `jira_key`
- `linked_req_keys`（可选）

前端调用：

- `startAiGenerationTask(...)`

后端启动：

- `generate_testcases_task`

任务创建后，前端立即进入进度展示阶段。

---

### 4.2 生成 Service 开始执行

Service 入口：

- `generate_from_jira(jira_key, linked_req_keys, task_id, celery_task)`

一进入 service，会先尝试获取当前模型名，用于进度信息和结果元数据展示。

---

### 4.3 缓存检查

Service 会先根据以下信息生成缓存 key：

- `jira_key`
- `linked_req_keys`
- `prompt_version`

如果命中缓存：

- 直接返回结构化结果
- 标记 `meta.cache_hit = true`
- 推送完成事件
- 同时保存统一 generation result

这一步避免重复生成相同需求。

---

### 4.4 获取 Jira 主需求

如果没有命中缓存，Service 会：

- 调用 `ai_service.get_jira_issue_details(jira_key)`
- 在失败时进行有限重试
- 成功后推送“核心需求获取成功”进度

如果 Jira 主需求无法获取：

- 任务直接失败
- 返回 `status = FAILURE`

---

### 4.5 获取历史需求

如果用户提供了 `linked_req_keys`：

- Service 会逐个调用 `ai_service.get_jira_issue_details(...)`
- 获取到的历史需求会作为补充上下文参与后续生成

这里的目标是补充：

- 关联功能背景
- 上下游行为约束
- 跨需求集成点

历史需求获取失败不会直接中断整个任务，但会记录日志。

---

### 4.6 显式执行知识库检索（RAG）

这是当前链路中最关键的增强点。

Service 会使用 Jira 的以下内容构造检索 query：

- `summary`
- `description`

然后调用：

- `ai_service.query_kb(kb_query, top_k=2)`

当前行为：

- 这是一个显式的生成阶段
- 前端会看到“正在调用向量数据库检索产品文档”
- 成功时会记录：
  - `kb_used = true`
  - `kb_query`
  - `kb_sources`
  - `kb_context`
- 未命中时：
  - 记录“知识库未命中相关业务规则”
- 异常时：
  - 记录“知识库检索异常，降级为纯大模型生成”
  - 不阻断整体生成

这一步说明：

- 当前系统中的 RAG 已经不是“静默增强项”
- 而是正式的流程节点

---

### 4.7 调用模型生成测试用例

在完成 Jira 与知识上下文准备后，Service 调用：

- `ai_service.generate_testcases_from_jira(...)`

传入的关键上下文包括：

- `issue_details`
- `linked_req_details`
- `jira_key`
- `kb_context`

所以模型当前并不是只基于 Jira 描述生成，而是基于：

- Jira 主需求
- 历史需求
- 产品文档检索上下文

---

### 4.8 解析与修复模型输出

模型返回后，Service 会：

- 尝试从输出中抽取 JSON
- 如果结构不标准，则尝试做恢复解析
- 对测试用例做统一归一化

归一化内容包括：

- `id`
- `task`
- `module`
- `priority`
- `type`
- `steps`
- `expected_result`
- `precondition`

这一步的目标是保证：

- 输出可展示
- 输出可导出
- 输出结构稳定

---

### 4.9 结果增强与落库

生成成功后，Service 会补充结构化元数据，例如：

- `jira_key`
- `kb_used`
- `kb_query`
- `kb_sources`
- `rag_summary`
- `meta.model`
- `meta.cache_hit`

并执行：

- Redis 缓存写入
- 统一 generation result 写入
- 任务状态更新
- WebSocket 进度推送

当前 `rag_summary` 主要用于：

- 前端结果展示
- 任务状态轮询返回
- Excel 导出中的知识来源提取

---

## 5. 前端当前如何展示流程

### 5.1 加载中展示

前端会显示步骤条：

1. 获取 Jira
2. 检索文档
3. 生成上下文
4. 生成用例
5. 完成

同时会展示“产品文档检索过程”卡片，内容包括：

- 检索状态
- 检索词
- 命中的文档来源

### 5.2 生成完成后展示

生成完成后，前端还会展示“知识库参与情况”卡片，内容包括：

- 是否命中知识库
- 检索状态
- 检索 query
- 参考文档来源

这意味着当前用户不只知道“生成了测试用例”，还可以知道：

- 这批测试用例是否参考了知识库
- 参考了哪些产品文档

---

## 6. 任务状态查询流程

接口：

- `GET /rest/v1/testcases/ai-task/{task_id}/`

当前逻辑：

1. 优先读取 Redis 中保存的统一结果
2. 如果缓存存在，则直接返回结构化结果
3. 如果缓存不存在，则回退到 Celery `AsyncResult`

这样做的好处：

- 轮询接口也能拿到完整的知识库元数据
- 不再只依赖 WebSocket 中的临时文本
- 导出与查询共享同一结果来源

---

## 7. Excel 导出流程

导出接口：

- `GET /rest/v1/testcases/ai-export/{task_id}/`

当前导出逻辑：

1. 优先读取 Redis 中的统一结果缓存
2. 回退兼容 Celery `AsyncResult`
3. 提取：
   - `testcases`
   - `analysis`
   - `rag_summary.sources`
4. 调用 `AgentService.export_testcases_excel(...)`

当前导出的工作表包括：

- `Test Cases`
- `Analysis`
- `Knowledge Base`

其中 `Knowledge Base` sheet 会记录本次命中的产品文档来源。

---

## 8. 当前职责边界总结

### 8.1 Jira Skill 的职责

- 定义如何基于 Jira 需求做分析
- 定义如何设计测试覆盖
- 定义输出结构与字段要求
- 使用系统已提供的上下文进行测试设计

不负责：

- 决定是否执行 RAG
- 自己声明必须亲自执行知识库检索流程

### 8.2 Knowledge Skill 的职责

- 定义如何检索和引用知识库内容
- 定义缺失信息处理原则
- 定义知识库与 Jira 描述冲突时的处理方式

不负责：

- 决定 Jira 测试用例生成任务是否一定触发检索

### 8.3 Service 的职责

- 决定是否执行知识库检索
- 决定如何构造 query
- 决定如何将知识上下文注入模型
- 决定结果结构与可追溯信息

### 8.4 前端的职责

- 把生成过程展示给用户
- 把知识库参与情况展示给用户
- 提供导出入口

---

## 9. 当前流程的成果

相较于之前“代码里有 `query_kb`，但用户看不见”的状态，当前链路已经具备：

- 显式的知识库检索阶段
- 实时可见的 RAG 过程展示
- 生成完成后的知识来源持续展示
- 轮询接口可返回知识库参与信息
- Excel 可导出知识来源
- Prompt 层职责边界更清晰

简而言之，当前已经实现：

> 基于 Jira 主需求 + 历史需求 + 产品文档知识上下文 的测试用例生成链路。

---

## 10. 仍可继续优化的点

虽然当前流程已经比之前清晰很多，但后续仍有几个优化方向：

1. 给任务状态返回增加明确的 `stage` 字段，减少前端对文本内容的推断
2. 优化 RAG query 构造策略，不仅使用 `summary + description`
3. 在结果中增加更精细的知识片段摘要，而不仅是来源列表
4. 继续收紧 Prompt 与 Workflow 的边界，避免未来再次漂移
5. 为前端结果页补充更完整的知识来源说明与来源数量统计

---

## 11. 一句话总结

当前项目中“根据 Jira 需求生成测试用例”的流程，已经从“Jira + LLM 的黑盒生成”演进为“Jira 信息获取 + 历史需求补充 + 向量数据库检索产品文档 + 大模型生成 + 结构化展示/导出”的完整链路，并且知识库的参与过程已经具备可见性、可追溯性和可导出性。
