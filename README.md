# 自动化测试平台（FastAPI + Vue2 + Element UI）

## 项目简介

本项目是一套企业级接口自动化测试平台，后端基于 FastAPI + SQLAlchemy + Celery，前端基于 Vue2 + Element UI。平台支持项目、模块、接口、用例、测试套件、测试报告、变量、自定义函数等全流程管理，适用于接口自动化测试、持续集成、团队协作等场景。

---

## 目录结构

```
fastapi_project/
  ├── app/                # 后端FastAPI主应用
  │   ├── models/         # ORM数据模型
  │   ├── routers/        # API路由（项目、模块、接口、用例、套件、报告、变量、函数等）
  │   ├── schemas/        # Pydantic数据校验与序列化
  │   ├── services/       # 业务逻辑与LLM模型
  │   ├── utils/          # 工具类与异常处理
  │   ├── tasks/          # Celery异步任务
  │   ├── main.py         # FastAPI入口
  │   ├── config.py       # 配置文件
  │   ├── celery_app.py   # Celery配置
  │   └── database.py     # 数据库连接与初始化
  └── vue-admin-template/ # 前端Vue2+ElementUI管理后台
      ├── src/
      │   ├── api/        # 前端API接口封装
      │   ├── views/      # 页面视图（项目、模块、接口、用例、套件、报告、变量、函数等）
      │   ├── components/ # 通用组件
      │   ├── utils/      # 工具函数
      │   ├── store/      # Vuex状态管理
      │   ├── router/     # 路由配置
      │   └── App.vue     # 入口组件
      └── package.json    # 前端依赖与脚本
```

---

## 技术栈

- **后端**：FastAPI、SQLAlchemy、Alembic、MySQL、Redis、Celery、Pydantic
- **前端**：Vue2、Element UI、Vuex、Vue Router、Axios
- **其他**：支持自定义函数、变量、LLM模型（如sentence-transformers）

---

## 环境依赖

### 后端

- Python 3.10+
- MySQL 5.7+/8.0+（或兼容数据库，默认配置为本地 test_platform）
- Redis 5+（用于Celery消息队列）
- 依赖包见 `pyproject.toml` 或 `requirements.txt`

### 前端

- Node.js 8.9+
- npm 3.0.0+
- 依赖包见 `vue-admin-template/package.json`

---

## 启动方式

### 后端 FastAPI

1. 安装依赖  
   ```bash
   pip install -r requirements.txt
   ```
2. 配置数据库与Redis（见 `app/config.py`，默认本地MySQL/Redis）
3. 初始化数据库表  
   ```bash
   # 启动时自动创建表和管理员账号（admin@qq.com/admin1234）
   ```
4. 启动 FastAPI 服务  
   ```bash
   uvicorn app.main:app --reload
   ```
5. 启动 Celery Worker（异步任务/定时任务）  
   ```bash
   celery -A app.celery_app.celery_app worker --loglevel=info
   ```

### 前端 Vue2

1. 安装依赖  
   ```bash
   cd vue-admin-template
   npm install
   ```
2. 启动开发环境  
   ```bash
   npm run dev
   ```
   访问 [http://localhost:9528](http://localhost:9528)

3. 构建生产环境  
   ```bash
   npm run build:prod
   ```

---

## 详细功能说明

### 1. 项目管理
- 支持项目的创建、编辑、删除、查询
- 支持项目下模块、接口、用例、套件的统一管理
- 支持项目描述、时间戳、批量删除等

### 2. 模块管理
- 支持模块的增删改查，归属于具体项目
- 支持模块描述、批量操作

### 3. 接口管理
- 支持接口的增删改查，归属于具体模块
- 支持接口请求方法、地址、版本、参数、断言等配置
- 支持接口复制、快速编辑

### 4. 用例管理
- 支持测试用例的增删改查
- 用例可关联接口、变量、前后置操作
- 支持用例标签、优先级、批量复制、执行

### 5. 测试套件管理
- 支持测试套件的增删改查
- 套件可批量管理用例，支持一键执行、定时执行（集成Celery）
- 支持执行进度、历史记录、定时任务配置

### 6. 测试报告
- 自动生成测试报告，展示用例执行结果、通过率、耗时等
- 支持报告详情查看、删除

### 7. 变量管理
- 支持全局变量、环境变量的增删改查
- 变量可用于用例、接口参数化

### 8. 自定义函数
- 支持自定义Python函数，供用例/接口/变量提取等场景调用
- 支持函数的增删改查、在线运行、结果查看

### 9. 用户与权限
- 支持用户注册、登录（JWT+Cookie）、权限校验
- 默认管理员账号：`admin@qq.com` / `admin1234`

### 10. 其他特色
- 支持LLM模型（如sentence-transformers）集成，便于智能用例生成、语义搜索等
- 支持API统一异常处理、日志记录
- 支持API接口RESTful风格，前后端分离

---

## 主要接口与页面说明

### 后端API（部分）
- `/rest/v1/projects/` 项目管理（增删改查）
- `/rest/v1/modules/` 模块管理
- `/rest/v1/interfaces/` 接口管理
- `/rest/v1/testcases/` 用例管理
- `/rest/v1/testsuites/` 测试套件管理
- `/rest/v1/testreports/` 测试报告
- `/rest/v1/variables/` 变量管理
- `/rest/v1/functions/` 自定义函数
- `/auth/jwt/login` 登录认证（JWT+Cookie）

### 前端页面
- 仪表盘首页：展示平台欢迎信息、用户信息
- 项目管理：项目列表、创建、编辑、删除、批量操作
- 模块管理：模块列表、创建、编辑、删除、批量操作
- 接口管理：接口列表、创建、编辑、复制、删除、参数配置
- 用例管理：用例列表、创建、编辑、复制、删除、执行、标签
- 测试套件：套件列表、创建、编辑、删除、执行、定时任务
- 测试报告：报告列表、详情、删除、统计
- 变量管理：变量列表、创建、编辑、删除、参数化
- 自定义函数：函数列表、创建、编辑、删除、在线运行
- 登录页面：支持邮箱+密码登录，登录后进入主界面

---

## 常见问题

- **数据库连接失败**：请检查 `app/config.py` 中的 `DATABASE_URL` 配置，确保MySQL已启动并有对应库。
- **Redis连接失败**：请检查 `REDIS_URL` 配置，确保Redis服务已启动。
- **前端接口404**：请确认后端服务已启动，且前端 `.env` 配置了正确的API地址。
- **登录失败**：默认管理员账号为 `admin@qq.com`，密码 `admin1234`，可在首次启动后自行修改。
- **Celery任务不执行**：请确认已正确启动Celery worker，并配置好Redis。
- **模型相关依赖问题**：如需使用LLM相关功能，请确保已安装 `sentence-transformers` 及相关模型文件。

---

## 参考/致谢

- 前端基于 [vue-admin-template](https://github.com/PanJiaChen/vue-admin-template)
- Element UI 组件库
- FastAPI 官方文档
- sentence-transformers 相关模型

---

## License

MIT

---

如需详细二次开发文档或接口文档，请参考代码注释或联系项目维护者。 