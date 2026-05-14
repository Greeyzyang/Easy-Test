# 自动化测试平台 — Cursor AI 编码规范

> 本文件是 Cursor AI 在此项目中编写代码的最高参考标准。所有代码必须严格遵循本规范。

## 两条最高原则

1. **统一响应格式**：所有 API 必须用 `ResponseModel` 封装 `{code: "0", data: {...}, msg: "success"}`
2. **严格按开发顺序**：Model -> Schema -> Router -> 前端 API -> 前端页面

---

## 统一响应格式（必须遵循）

后端：

```python
from app.utils.response import create_response, ResponseModel

@router.post("/", response_model=ResponseModel)
async def create_resource(...):
    return await create_response(data={"id": resource.id})
```

错误响应：`raise HTTPException(status_code=404, detail="...")`，不要自己封装。

前端必须检查：

```javascript
if (response && response.code === '0' && response.data) {
  const { items, total } = response.data
  this.list = items || []
  this.total = total || 0
}
```

---

## 开发顺序（必须按此顺序）

```
数据库 Model (app/models/)
        ↓
Pydantic Schema (app/schemas/)
        ↓
Router (app/routers/)
        ↓
前端 API (src/api/)
        ↓
前端页面 (src/views/)
```

每一层的接口稳定后再开发下一层。

---

## 规则文件索引

| 规范 | 文件 |
|------|------|
| 后端完整规范（Router/Schema/Model/日志/异步/分页/错误处理） | [.cursor/rules/backend.md](./.cursor/rules/backend.md) |
| 前端完整规范（API/列表页/编辑页/组件/Element UI/样式） | [.cursor/rules/frontend.md](./.cursor/rules/frontend.md) |
| MCP 集成规范 | [.cursor/rules/mcp.md](./.cursor/rules/mcp.md) |
| 常用代码模板 | [.cursor/rules/patterns.md](./.cursor/rules/patterns.md) |

---

## 项目结构

**后端**：`app/models/` · `app/schemas/` · `app/routers/` · `app/services/` · `app/tasks/` · `app/utils/`
**前端**：`vue-admin-template/src/api/` · `vue-admin-template/src/views/` · `vue-admin-template/src/components/` · `vue-admin-template/src/utils/`

### 前端组件目录结构

```
src/components/
├── Common/           # 通用业务组件（跨视图复用）
│   ├── ParamTable.vue           # 参数表格（请求头/参数/表单）
│   ├── EllipsisCell.vue         # 文本省略单元格
│   └── VariableExtract.vue      # 变量提取配置
├── Charts/           # 图表组件
│   ├── PieChart.vue
│   └── RingProgress.vue
├── Layout/           # 布局相关组件
│   ├── Breadcrumb.vue           # 面包屑导航
│   ├── Hamburger.vue            # 侧边栏收缩按钮
│   ├── PageHeader.vue           # 页面头部
│   └── Pagination.vue           # 分页组件
├── Editor/           # 编辑器相关
│   ├── MonacoEditor.vue          # Monaco 代码编辑器
│   └── SvgIcon.vue              # SVG 图标组件
└── Assistant/        # AI 助手相关
    └── GlobalAssistant.vue     # 全局 AI 助手浮窗
```

**规范**：
- 通用业务组件放在 `Common/`，视图专用组件放在 `views/{module}/components/`
- 组件引用路径统一使用 `@/components/` 前缀
- 组件必须添加 JSDoc 注释说明用途和示例

---

## 常见问题

**Q: 列表页数据不更新？**
A: 检查 `this.list = items || []` 是否正确，确认 `response.code === '0'` 通过。

**Q: 表单验证失败？**
A: `const valid = await this.$refs.form.validate().catch(() => false)`

**Q: 拖拽排序不生效？**
A: 确保 `this.$nextTick()` 包裹初始化代码。

**Q: API 报 401？**
A: 检查 `request.js` 拦截器是否注入 `Authorization: Bearer {token}`。

**Q: 后端枚举值如何映射到前端？**
A: 在 `app/schemas/base_schemas.py` 中定义枚举，前端通过 API 获取或在代码中写死常量。
