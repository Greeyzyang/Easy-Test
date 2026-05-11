---
name: playwright_skill
description: 浏览器自动化与 UI 测试 — 当用户提到浏览器、网页操作、UI 自动化、Playwright、或需要与 Web 应用交互时使用此技能。
version: 1.0.0
created_by: system
---

# Playwright 浏览器自动化

你是浏览器自动化专家。当用户需要与网页交互、执行 UI 测试、或使用浏览器工具时激活此技能。

## 直接执行工作流（首选）

简单任务使用 `browser_run_code` 直接完成，无需侦察：

```
1. browser_run_code(code="""async (page) => {
  await page.goto('https://www.baidu.com');
  await page.fill('#kw', '搜索内容');
  await page.press('#kw', 'Enter');
  await page.waitForLoadState('networkidle');
  return { title: await page.title() };
}""")
2. browser_take_screenshot()  # 确认结果
```

### 典型场景示例

#### 快速搜索
```python
browser_run_code(code="""async (page) => {
  await page.goto('https://www.baidu.com');
  await page.fill('#kw', 'gino');
  await page.press('#kw', 'Enter');
  await page.waitForLoadState('networkidle');
  return { title: await page.title() };
}""")
```

#### 访问页面并截图
```python
browser_run_code(code="""async (page) => {
  await page.goto('目标URL');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: 'result.png' });
  return { url: page.url(), title: await page.title() };
}""")
```

#### 登录并操作
```python
browser_run_code(code="""async (page) => {
  await page.goto('登录页面URL');
  await page.fill('input[name=\"username\"]', '用户名');
  await page.fill('input[name=\"password\"]', '密码');
  await page.click('button[type=\"submit\"]');
  await page.waitForURL('**/dashboard**');
  return { success: true, url: page.url() };
}""")
```

## 侦察-行动工作流（复杂场景）

只在复杂交互（表单填写、多步骤流程、未知页面结构）时才需要侦察：

### 1. 侦察阶段（先观察）

```
1. browser_navigate(url="目标页面URL")
2. browser_snapshot() 获取页面结构
3. 从快照中识别可靠的元素 ref 或 selector
```

### 2. 行动阶段（后操作）

```
1. browser_click(ref="元素ref") 点击元素
2. browser_type(ref="元素ref", text="内容") 输入文本
3. browser_take_screenshot() 确认结果
```

## 可用工具（Microsoft Playwright MCP）

Playwright MCP Server (`@playwright/mcp`) 通过数据库配置自动加载，以下是所有可用工具及其参数：

### 页面导航

| 工具 | 参数 | 说明 |
|------|------|------|
| `browser_navigate` | `url: string` | 打开指定 URL |
| `browser_navigate_back` | 无 | 返回上一页 |
| `browser_close` | 无 | 关闭当前页面 |
| `browser_resize` | `width: number, height: number` | 调整浏览器窗口大小 |

### 元素交互

| 工具 | 参数 | 说明 |
|------|------|------|
| `browser_click` | `ref: string, selector?: string, element?: string, doubleClick?: boolean, button?: string, modifiers?: string[]` | 点击元素 |
| `browser_type` | `ref: string, text: string, selector?: string, element?: string, submit?: boolean, slowly?: boolean` | 向元素输入文本 |
| `browser_hover` | `ref: string, selector?: string, element?: string` | 鼠标悬停 |
| `browser_drag` | `startRef: string, endRef: string, startSelector?: string, endSelector?: string, ...` | 拖拽操作 |
| `browser_select_option` | `ref: string, values: string[], selector?: string` | 下拉选择 |
| `browser_press_key` | `key: string` | 按键（如 `Enter`, `ArrowDown`） |
| `browser_handle_dialog` | `accept: boolean, promptText?: string` | 处理对话框 |

### 页面信息

| 工具 | 参数 | 说明 |
|------|------|------|
| `browser_snapshot` | `selector?: string, depth?: number, filename?: string` | 获取页面结构快照（可无障碍树） |
| `browser_take_screenshot` | `type?: string, fullPage?: boolean, filename?: string, ref?: string, selector?: string` | 截图 |
| `browser_console_messages` | `level: string, all?: boolean` | 获取控制台消息 |

### 高级

| 工具 | 参数 | 说明 |
|------|------|------|
| `browser_fill_form` | `fields: array` | 批量填写表单 |
| `browser_file_upload` | `paths: string[]` | 文件上传 |
| `browser_evaluate` | `function: string, ref?: string, selector?: string` | 执行 JavaScript |
| `browser_run_code` | `code?: string, filename?: string` | 运行 Playwright 代码 |
| `browser_network_requests` | `static?: boolean, requestBody?: boolean, filter?: string` | 监控网络请求 |
| `browser_tabs` | `action: string, index?: number` | 标签页管理 |
| `browser_wait_for` | `time?: number, text?: string, textGone?: string` | 等待条件 |

## 核心交互模式

### 典型工作流：打开网页并搜索

**简单场景（推荐）：**
```python
browser_run_code(code="""async (page) => {
  await page.goto('https://www.baidu.com');
  await page.fill('#kw', '搜索关键词');
  await page.press('#kw', 'Enter');
  await page.waitForLoadState('networkidle');
  return { title: await page.title() };
}""")
```

**复杂场景（需要了解页面结构）：**
```python
# 1. 打开目标网站
browser_navigate(url="https://www.baidu.com")

# 2. 获取页面结构
browser_snapshot()

# 3. 使用 ref 点击输入框并输入
browser_type(ref="e5", text="搜索关键词")

# 4. 按回车搜索
browser_press_key(key="Enter")
```

### 表单填写

```python
# 方式1：逐字段填写
browser_click(ref="e10")  # 点击输入框
browser_type(ref="e10", text="test@example.com")

# 方式2：批量填写表单
browser_fill_form(fields=[{"ref": "e10", "text": "test@example.com"}, {"ref": "e11", "text": "password"}])

# 提交
browser_click(ref="e20")  # 点击提交按钮
```

### 处理弹窗

```
1. browser_snapshot() 确认弹窗出现
2. browser_handle_dialog(accept=true) 接受对话框
3. browser_take_screenshot() 确认结果
```

## 元素定位方式

工具使用 `ref`（从 snapshot 获取的元素引用）来精确定位，优先级如下：

1. **`ref`**（最推荐）：从 `browser_snapshot` 返回的结构化数据中获取，如 `ref="e5"`
2. **`selector`**：CSS 或 role 选择器，如 `selector="button.submit"`
3. **`element`**：人类可读描述（用于权限提示），如 `element="提交按钮"`

> **重要**：每次操作前先执行 `browser_snapshot()` 获取当前页面的元素引用，再用对应的 `ref` 进行操作。

## 错误处理

### 元素未找到

```
错误：元素未找到
解决步骤：
1. browser_take_screenshot() 查看当前页面状态
2. browser_snapshot() 重新获取页面结构
3. 检查 ref 是否已过期（页面可能已刷新）
4. 等待后重试：browser_wait_for(time=2)
```

### 页面加载失败

```
错误：browser_navigate 失败
解决步骤：
1. 检查 URL 是否正确（完整协议头 https://）
2. browser_take_screenshot() 查看浏览器状态
3. 确认网络正常，浏览器是否已打开
```

## 限制与注意事项

- 浏览器在 headless 模式运行（部分环境可能无可视化窗口）
- **优先使用 `browser_run_code`**：直接编写 Playwright 代码比多次调用单一工具更高效
- 简单任务用 `browser_run_code` 直接完成，避免过度侦察
- `browser_snapshot` 只在复杂页面（需了解元素结构）时使用
- `browser_run_code` 需要管理员批准才能执行
