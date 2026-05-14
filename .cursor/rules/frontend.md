# 前端规范 (Vue 2 + Element UI)

> 详细代码模板见 [patterns.md](./patterns.md)

## 1. 技术栈

- Vue 2（Options API，非 Composition API）
- Element UI 2.x
- Axios（通过 `@/utils/request.js` 封装，禁止直接用 axios）
- Vuex + Vue Router 3
- SCSS（样式预处理器）
- 中文 UI（所有按钮、标签、提示使用中文）

---

## 2. 统一响应格式（必须遵循）

后端响应：`{code: "0", data: {items: [...], total: 100}, msg: "success"}`

**必须检查**：
```javascript
const response = await getTestCases(this.listQuery)
if (response && response.code === '0' && response.data) {
  const { items, total } = response.data
  this.list = items || []
  this.total = total || 0
} else {
  this.$message.error('数据格式错误')
}
```

**规则**：
- 成功判断：`response.code === '0'`（字符串，非数字）
- 文件下载：`responseType: 'blob'`

---

## 3. HTTP 客户端规范

使用 `@/utils/request.js` 封装的实例，禁止直接使用 axios。

```javascript
import request from '@/utils/request'  // 必须从 utils 导入
```

---

## 4. API 层规范

每个 API 文件对应一个后端 Router（如 `src/api/testcase.js` 对应 `app/routers/testcases.py`）。

```javascript
// 命名：动词前缀 + 资源名
// URL：/rest/v1/{resource}/ 或 /rest/v1/{resource}/{id}/
// 列表参数：skip = (page - 1) * limit，URL 统一以 / 结尾

export function getTestCases(listQueryParams) {
  const params = {
    skip: Math.max((listQueryParams.page - 1) * listQueryParams.limit, 0),
    limit: listQueryParams.limit,
    name: listQueryParams.name,
    module_id: listQueryParams.module_id
  }
  return request({ url: '/rest/v1/testcases/', method: 'get', params })
}

export function getTestCase(id) {
  return request({ url: `/rest/v1/testcases/${id}/`, method: 'get' })
}

export function createTestCase(data) {
  return request({ url: '/rest/v1/testcases/', method: 'post', data })
}

export function updateTestCase(id, data) {
  return request({ url: `/rest/v1/testcases/${id}/`, method: 'put', data })
}

export function deleteTestCase(id) {
  return request({ url: `/rest/v1/testcases/${id}/`, method: 'delete' })
}
```

---

## 5. 列表页规范

**文件**：`src/views/{resource}/index.vue`

必须元素：
- `listLoading` 控制加载状态
- `listQuery` 包含 `page`、`limit`（必选）及其他查询参数
- 方法用 `handle` 前缀（如 `handleFilter`、`handleDelete`）
- 搜索按钮加 `v-waves` 指令
- 搜索条件变化时重置 `page = 1`
- 删除用 `this.$confirm()` 确认
- 操作列固定右侧：`fixed="right"`

```javascript
// 标准列表页 data
data() {
  return {
    list: null,        // null 表示未加载
    total: 0,
    listLoading: true,
    listQuery: { page: 1, limit: 20, name: undefined, module_id: undefined }
  }
}

// 标准 getList
async getList() {
  this.listLoading = true
  try {
    const response = await getTestCases(this.listQuery)
    if (response && response.code === '0' && response.data) {
      this.list = response.data.items || []
      this.total = response.data.total || 0
    }
  } catch (error) {
    this.$message.error('获取数据失败')
  } finally {
    this.listLoading = false
  }
}
```

---

## 6. 编辑页规范

**文件**：`src/views/{resource}/edit.vue`（编辑和创建共用，通过 `$route.params.id` 判断）

```javascript
// 并行加载多个数据源
const [res1, res2] = await Promise.all([api1(params1), api2(params2)])

// 表单验证
const valid = await this.$refs.form.validate().catch(() => false)

// 响应式更新（Vue 2 必须用 $set）
this.$set(this.form.steps, index, newData)

// DOM 更新后执行
this.$nextTick(() => { ... })

// 保存逻辑
const api = this.form.id ? updateXxx : createXxx
await api(...args)
this.$message.success('保存成功')
this.$router.push('/xxx')
```

---

## 7. 组件规范

**选项顺序**：`name -> components -> directives -> props -> data -> computed -> watch -> created -> mounted -> methods`

**命名规范**：

| 类型 | 规范 | 示例 |
|------|------|------|
| 组件名 | PascalCase | `TestcaseList` |
| 文件名 | kebab-case | `testcase-list.vue` |
| 方法名 | camelCase + handle 前缀 | `handleFilter` |
| 变量名 | camelCase | `listLoading` |
| CSS 类名 | kebab-case | `.filter-container` |

---

## 8. Element UI 使用规范

**表单**：`<el-form :model="form" :rules="rules">`
**表格**：`v-loading="listLoading"`，操作列 `fixed="right"`
**按钮**：主要操作 `type="primary"`，危险操作 `type="danger"`，搜索按钮加 `v-waves`

---

## 9. 样式规范

- 使用 SCSS，添加 `scoped`
- 布局容器：`padding: 20px; background: #fff`
- Element UI 深度选择器：`:deep()` 或 `::v-deep`
