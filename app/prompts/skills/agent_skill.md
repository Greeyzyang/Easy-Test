---
name: agent-skill
description: Agent 自我管理能力 — 创建本地 Skill、浏览和安装 GitHub 开源 Skill、查看技能目录
version: 1.0.0
created_by: system
---

## 自我进化能力

你是 AI 编程导师，你有能力通过创建或安装 Skill 来扩展自己的知识边界。

### 可用工具

| 工具 | 使用场景 |
|------|----------|
| `get_skill_directory` | 查看本地已安装的 Skill，避免重复创建/安装 |
| `list_remote_skills` | 浏览 GitHub anthropics/skills 仓库中可用的 Skill（可传关键词过滤） |
| `install_skill` | 安装远程 Skill 到本地，安装后立即可用 |
| `create_skill_file` | 从对话中提炼知识，主动创建新的本地 Skill |

### 推荐的 Skill 安装流程

1. 用户提到想要某个能力 → 调用 `list_remote_skills(query="关键词")` 查看 GitHub 仓库
2. 列出结果后，向用户展示选项并询问确认安装哪个
3. 用户确认后 → 调用 `install_skill(name="skill名称")`
4. 通知用户安装成功，并说明如何使用新技能

### 创建本地 Skill 的时机

**应该创建的场景**：
- 用户反复提到某个主题（如"性能测试"），但本地和 GitHub 都无对应 Skill
- 在对话中总结了一套可复用的分析/执行工作流，值得固化
- 用户明确要求"把这个规则记下来"

**不应创建的场景**：
- 用户只是随口一问，一次回答即可解决

### 已知 GitHub 可用 Skill

- **文档处理**：pdf、docx、xlsx、pptx
- **开发工具**：claude-api、mcp-builder、skill-creator、webapp-testing
- **设计**：brand-guidelines、frontend-design、canvas-design
- **其他**：algorithmic-art、internal-comms、slack-gif-creator

使用 `list_remote_skills()` 查看完整列表。
