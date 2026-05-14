# MCP 集成规范

## 1. MCPServer 配置字段

存储在 `app/models/mcp_server.py`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | String | 服务器显示名称 |
| `description` | String | 功能描述 |
| `transport` | String | 传输类型：`stdio` / `http` / `sse` |
| `command` | String | stdio 模式启动命令 |
| `args` | JSON | 启动参数列表 |
| `env` | JSON | 环境变量 |
| `url` | String | http/sse 模式服务器 URL |
| `enabled` | Boolean | 是否启用 |

---

## 2. 加载机制

`app/services/mcp_browser_service.py` 中 `get_mcp_tools()` 从 DB 读取所有 `enabled=True` 的 Server，通过 `langchain_mcp_adapters` 加载工具。

**规则**：
- `enabled=True` 的 Server 自动加载到 Agent 工具列表
- 新增/修改 Server 后需重启 FastAPI 服务生效
- 运行时切换 `enabled` 状态不会动态更新

---

## 3. 新增 MCP Server 流程

1. 前端 `MCPServers` 管理页面添加配置
2. 保存到数据库 `mcp_servers` 表
3. 重启 FastAPI 服务
4. 服务启动时 `get_mcp_tools()` 自动加载
