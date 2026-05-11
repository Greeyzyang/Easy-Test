import httpx
import json
import base64
import io
from fastapi import HTTPException
from app.models import TestStep, Interface
import time
from jsonpath_rw import parse
from typing import Dict, Optional
from app.schemas.base_schemas import RequestType, VariableSource
from app.services.function_service import FunctionService
from app.schemas.teststep import JsonValueAssertionRule
import re
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models import TestStep, Interface, Project, Module

from app.utils.execution_context import BaseExecutionContext
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TestContext(BaseExecutionContext):
    """测试上下文管理类（单例模式），继承自 BaseExecutionContext"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.db = None
        return cls._instance

    def set_db(self, db):
        self.db = db
        logger.info(f"数据库会话已设置: {db}")

    async def process_template_string(self, template_str: str) -> str:
        """在父类基础上增加函数调用 ${funcName(args)} 支持"""
        if not template_str or not isinstance(template_str, str):
            return template_str

        result_str = template_str
        matches = list(re.finditer(r'\$\{([^}]+)}', template_str))
        for match in reversed(matches):
            content = match.group(1).strip()
            if '(' in content and content.endswith(')'):
                func_part = content[content.index('(') + 1:-1]
                func_name = content[:content.index('(')]
                func_args = [arg.strip() for arg in func_part.split(',')] if func_part else []
                replacement = await self._execute_function(func_name, func_args)
            else:
                var_value = await self.get_variable(content)
                if var_value is None:
                    logger.warning(f"变量 '{content}' 未在上下文中找到")
                    return match.group(0)
                replacement = str(var_value)
            result_str = result_str[:match.start()] + replacement + result_str[match.end():]
        return result_str

    async def _execute_function(self, func_name: str, args: list) -> str:
        """执行自定义函数"""
        try:
            if not self.db:
                raise ValueError("数据库会话未设置")
            function_service = FunctionService(self.db)
            success, result, stdout, stderr = await function_service.execute_function(func_name, args)
            if not success:
                logger.error(f"执行函数 {func_name} 失败")
                return ''
            return str(result)
        except Exception as e:
            logger.error(f"执行函数 {func_name} 时出错: {str(e)}")
            return ''

class HttpClient:
    """HTTP 客户端类，负责处理 HTTP 请求和响应"""
    _context = TestContext()
    _client = None

    @classmethod
    async def init_client(cls):
        """初始化 HTTP client"""
        if cls._client is None:
            cookies = httpx.Cookies()
            cls._client = httpx.AsyncClient(cookies=cookies, verify=False, follow_redirects=True)
        return cls._client

    @classmethod
    async def close_client(cls):
        """关闭 HTTP client"""
        if cls._client:
            await cls._client.aclose()
            cls._client = None

    @staticmethod
    async def _process_url_variables(path: str) -> str:
        """处理 URL 中的变量替换"""
        logger.debug(f"处理 URL 中的变量替换: {path}")
        logger.debug(f"当前上下文变量: {HttpClient._context.variables}")
        
        pattern = r'\${([^}]+)}'
        
        async def replace_var(match):
            var_name = match.group(1)
            var_value = await HttpClient._context.get_variable(var_name)
            logger.debug(f"替换 URL 变量 {var_name}: ${{{var_name}}} -> {var_value}")
            return str(var_value) if var_value is not None else match.group(0)
        
        # 由于 re.sub 不支持异步函数，我们需要手动处理替换
        result = path
        for match in re.finditer(pattern, path):
            replacement = await replace_var(match)
            result = result.replace(match.group(0), replacement)
        return result

    @staticmethod
    async def _build_url(interface) -> str:
        """
        构建完整的请求 URL
        
        构建逻辑：
        1. 从测试上下文中获取 base_url（在 TestreportService 中已设置）
        2. 获取接口的 URL 路径
        3. 处理路径中的变量替换（如果有 ${...} 占位符）
        4. 拼接 base_url 和路径，形成完整的 URL
        
        示例：
        - base_url: "http://127.0.0.1:8000"
        - interface.url: "/api/users/${user_id}"
        - 假设上下文中有 user_id=123
        - 最终URL: "http://127.0.0.1:8000/api/users/123"
        
        Args:
            interface: 接口对象，包含 URL 路径信息
            
        Returns:
            str: 完整的请求 URL
        """
        # 1. 从全局变量获取 base_url
        # base_url 在 TestreportService._initialize_test_context 中已设置
        base_url = HttpClient._context.variables.get('base_url', '').rstrip('/')
        if not base_url:
            logger.warning("base_url 未设置，可能导致请求失败")
        
        # 2. 获取接口的 URL 路径，并去除开头的斜杠
        path = interface.url.lstrip('/')
        
        # 3. 处理 URL 路径中的变量替换
        # 如果路径中包含 ${...} 占位符，会从上下文中获取对应的变量值进行替换
        if '${' in path and '}' in path:
            logger.debug(f"检测到路径中的变量占位符: {path}")
            path = await HttpClient._process_url_variables(path)
            logger.debug(f"变量替换后的路径: {path}")
        
        # 4. 拼接 base_url 和路径，形成完整的 URL
        full_url = f"{base_url}/{path}"
        logger.debug(f"构建完整URL: {full_url}")
        
        return full_url

    @staticmethod
    async def execute(teststep: TestStep, db=None):
        """
        执行单个测试步骤的 HTTP 请求
        
        执行流程：
        1. 数据准备：从数据库获取接口信息
        2. 客户端初始化：确保 HTTP 客户端可用
        3. 模板处理：处理请求参数中的变量替换（已在 TestreportService 中完成）
        4. URL构建：构建完整的请求 URL
        5. 请求发送：根据请求类型发送 HTTP 请求
        6. 响应处理：处理响应数据、断言验证、变量提取
        7. 上下文更新：更新测试上下文中的响应数据
        
        Args:
            teststep: 测试步骤对象，包含请求配置
            db: 数据库会话，用于获取接口信息
            
        Returns:
            dict: 包含执行结果的字典
                {
                    "status": "passed/failed",
                    "error_message": "错误信息（如果有）",
                    "response": "响应数据",
                    "status_code": "HTTP状态码",
                    "duration": "执行耗时"
                }
        """
        start_time = time.time()
        try:
            # ==================== 数据准备阶段 ====================
            # 1. 验证数据库会话
            if not db:
                raise HTTPException(status_code=500, detail="数据库会话未提供")
            
            # 2. 从数据库获取关联的 Interface 对象
            # 接口对象包含了请求方法、URL路径等信息，同时加载所属模块和项目以获取公共配置
            result = await db.execute(
                select(Interface)
                .options(
                    selectinload(Interface.module).selectinload(Module.project)
                )
                .where(Interface.id == teststep.interface_id)
            )
            interface = result.scalar_one_or_none()

            if not interface:
                raise HTTPException(status_code=404, detail=f"接口 {teststep.interface_id} 未找到")
                
            logger.info(f"获取到接口: {interface.method} {interface.url}")

            # ==================== 项目公共配置加载 ====================
            # 加载项目级公共变量和请求头
            project_headers = {}
            if interface.module and interface.module.project:
                project = interface.module.project
                # 注入项目级变量到上下文
                if project.variables:
                    try:
                        p_vars = json.loads(project.variables) if isinstance(project.variables, str) else project.variables
                        if isinstance(p_vars, dict):
                            for k, v in p_vars.items():
                                if k not in HttpClient._context.variables: # 不覆盖已存在的（如环境/步骤变量）
                                    HttpClient._context.variables[k] = v
                    except Exception as e:
                        logger.error(f"解析项目公共变量失败: {str(e)}")
                
                # 准备项目级请求头
                if project.headers:
                    try:
                        project_headers = json.loads(project.headers) if isinstance(project.headers, str) else project.headers
                        if not isinstance(project_headers, dict):
                            project_headers = {}
                    except Exception as e:
                        logger.error(f"解析项目公共请求头失败: {str(e)}")
                
            # ==================== 客户端初始化阶段 ====================
            # 3. 初始化 HTTP 客户端
            # 客户端会维护 cookies 和连接池
            client = await HttpClient.init_client()
            
            # ==================== 模板处理阶段 ====================
            # 4. 处理请求参数中的模板字符串
            # 注意：这一步已经在 TestreportService 中完成，这里直接使用处理后的参数
            # 但为了确保一致性，我们再次处理一次
            
            # 处理请求体中的变量
            processed_body = await HttpClient._context.process_template_dict(teststep.body or {})
            
            # 处理请求头中的变量（合并项目级 Header）
            # 优先级：步骤 Header > 接口 Header > 项目 Header
            final_headers = project_headers.copy()
            # 这里先获取接口定义的默认 Header (如果有)
            if interface.headers:
                final_headers.update(interface.headers)
            # 再合并当前步骤的 Header
            if teststep.headers:
                final_headers.update(teststep.headers)
                
            # 关键日志：仅在未找到 Token 时进行提醒
            if 'X-Auth-Token' not in HttpClient._context.variables:
                logger.warning("X-Auth-Token NOT found in variables")

            # 如果上下文没有 X-Auth-Token，则尝试从客户端 Cookie 中回退填充
            if 'X-Auth-Token' not in HttpClient._context.variables and HttpClient._client:
                try:
                    c = dict(HttpClient._client.cookies)
                    if 'gin2_token' in c:
                        HttpClient._context.variables['X-Auth-Token'] = c['gin2_token']
                        logger.info(f"从Cookie回退填充 X-Auth-Token: {str(c['gin2_token'])[:10]}...")
                except Exception:
                    pass

            # 自动添加 X-Auth-Token (如果存在)
            if 'X-Auth-Token' in HttpClient._context.variables:
                final_headers['X-Auth-Token'] = HttpClient._context.variables['X-Auth-Token']
                logger.debug("已自动将 X-Auth-Token 添加到请求头")

            processed_headers = await HttpClient._context.process_template_dict(final_headers)
            logger.debug("请求头处理完成")
            
            # 处理查询参数中的变量
            processed_params = await HttpClient._context.process_template_dict(teststep.params or {})
            logger.debug("请求参数处理完成")

            # 保存请求体到上下文，便于后续变量提取
            HttpClient._context.last_request_body = processed_body.copy() if isinstance(processed_body, dict) else processed_body
            
            # ==================== URL构建阶段 ====================
            # 5. 构建完整的请求 URL
            # 这一步会：
            # - 从上下文中获取 base_url
            # - 拼接接口的 URL 路径
            # - 处理路径中的变量替换
            full_url = await HttpClient._build_url(interface)
            
            # ==================== 请求发送阶段 ====================
            # 6. 根据请求类型发送 HTTP 请求
            
            # 检查 Headers 中是否有未替换的变量，如果有，添加到错误信息中提示用户
            unresolved_vars = []
            headers_to_remove = []
            for k, v in processed_headers.items():
                if isinstance(v, str) and '${' in v and '}' in v:
                    warning_msg = f"Header '{k}' 包含未替换变量: {v}"
                    logger.warning(warning_msg)
                    unresolved_vars.append(warning_msg)
                    
                    # 特殊处理：如果 Auth Token 未替换，直接移除，避免发送无效 Token
                    # 这可以防止服务端因收到无效 Token 而产生异常行为（如设置错误的 Cookie）
                    if k in ['X-Auth-Token', 'Authorization']:
                        headers_to_remove.append(k)
            
            for k in headers_to_remove:
                logger.warning(f"移除未替换的 Header: {k}")
                processed_headers.pop(k)

            # 检查是否是登录请求（需要特殊处理）
            if await HttpClient._is_login_request(teststep):
                logger.info("开始登录")
                response = await HttpClient._handle_login_request(
                    client, full_url, processed_body, processed_headers
                )
            else:
                # 发送普通请求
                logger.info(f"发送 {interface.method} 请求到 {full_url}")
                response = await HttpClient._send_request(
                    client, 
                    interface.method,
                    full_url,
                    teststep.request_type,
                    processed_body,
                    processed_headers,
                    teststep.file_config,
                    processed_params
                )
            
            # ==================== 响应处理阶段 ====================
            # 7. 处理响应数据
            result = await HttpClient._process_response(response, teststep, start_time)
            
            # 如果有未替换的变量且请求失败（401/403），将警告添加到错误信息中
            if unresolved_vars and response.status_code in [401, 403]:
                extra_msg = "; ".join(unresolved_vars)
                if result.get("error_message"):
                    result["error_message"] += f"; 警告: {extra_msg}"
                else:
                    result["error_message"] = f"警告: {extra_msg}"

            
            # ==================== 上下文更新阶段 ====================
            # 8. 更新测试上下文
            # 将响应数据、响应头、cookies 保存到上下文中
            # 供后续的变量提取和模板处理使用
            await HttpClient._update_context(response)
            
            # ==================== 变量提取阶段 ====================
            # 9. 处理变量提取
            # 如果测试步骤配置了变量提取规则，会从响应中提取变量
            # 并保存到上下文中，供后续步骤使用
            await HttpClient._handle_variable_extraction(teststep)

            # 自动尝试从 Cookie 中提取 gin2_token 并设置为 X-Auth-Token (针对 OVH 环境)
            if HttpClient._client:
                cookies = dict(HttpClient._client.cookies)
                if 'gin2_token' in cookies:
                    token = cookies['gin2_token']
                    # 只有当变量中没有 X-Auth-Token 或者值不同时才更新
                    current_token = HttpClient._context.variables.get('X-Auth-Token')
                    if current_token != token:
                        logger.info(f"自动从 Cookie 更新 X-Auth-Token: {token[:10]}...")
                        HttpClient._context.variables['X-Auth-Token'] = token
                else:
                    # 登录接口请求后，如果没有 gin2_token，打印警告
                    if await HttpClient._is_login_request(teststep):
                        logger.warning("登录接口完成后，未在 Cookie 中找到 gin2_token")
            
            logger.info(f"请求执行完成，状态: {result['status']}, 耗时: {result['duration']:.2f}s")
            return result
                
        except Exception as e:
            # ==================== 异常处理阶段 ====================
            logger.error(f"请求执行失败: {str(e)}")
            return {
                "status": "failed",
                "error_message": str(e),
                "response": None,
                "status_code": None,
                "duration": time.time() - start_time
            }

    @staticmethod
    async def _send_request(client, method, url, request_type, body, headers, file_config=None, params=None):
        if headers is None:
            headers = {}
        if params is None:
            params = {}
            
        # 检查 Headers 中是否有未替换的变量
        for k, v in headers.items():
            if isinstance(v, str) and '${' in v and '}' in v:
                logger.warning(f"Header '{k}' 中包含未替换的变量: {v}，可能导致请求失败(如 401)")
        
        # 记录请求信息
        # 精简请求日志，仅保留必要信息
        logger.debug(f"发送请求: {method} {url}")
        
        # 统一处理 body，支持 dict 和 list[dict]
        data = {}
        files = {}
        
        if isinstance(body, list):
            # 处理列表形式的参数 (来自优化的表单)
            for item in body:
                if not isinstance(item, dict) or 'name' not in item:
                    continue
                name = item['name']
                value = item.get('value')
                param_type = item.get('type', 'string')
                
                if param_type == 'file':
                    if value:
                        # 检查是否是 Base64 格式
                        if isinstance(value, str) and value.startswith('base64:'):
                            try:
                                file_info = json.loads(value[7:])
                                filename = file_info.get('filename', 'unknown_file')
                                base64_str = file_info.get('data', '')
                                
                                # 处理 data:image/png;base64,... 这种格式
                                if ',' in base64_str:
                                    base64_str = base64_str.split(',')[1]
                                
                                file_content = base64.b64decode(base64_str)
                                files[name] = (filename, io.BytesIO(file_content))
                            except Exception as e:
                                logger.error(f"解析 Base64 文件失败: {str(e)}")
                        else:
                            # 传统的路径方式
                            try:
                                files[name] = open(value, 'rb')
                            except Exception as e:
                                logger.error(f"无法打开文件 {value}: {str(e)}")
                    # 只要有文件，就属于表单提交的一部分，不需要单独修改 request_type
                else:
                    data[name] = value
        else:
            data = body

        # 处理旧的文件配置
        if file_config and isinstance(file_config, dict):
            for field_name, file_path in file_config.items():
                try:
                    files[field_name] = open(file_path, 'rb')
                except Exception as e:
                    logger.error(f"无法打开文件 {file_path}: {str(e)}")

        # 根据不同的请求类型设置不同的参数
        try:
            if method.upper() in ["POST", "PUT", "PATCH"]:
                # 对于登录请求，强制使用表单提交
                if url.endswith('/user/login/'):
                    return await client.request(
                        method=method,
                        url=url,
                        data=data,
                        headers=headers,
                        params=params
                    )
                # 其他请求按照 request_type 处理
                elif request_type == RequestType.JSON:
                    if 'Content-Type' not in headers:
                        headers['Content-Type'] = 'application/json'
                    return await client.request(
                        method=method,
                        url=url,
                        json=data,
                        headers=headers,
                        params=params
                    )
                elif request_type == RequestType.FORM:
                    # 如果有文件，httpx 会自动处理为 multipart/form-data
                    # 如果没有文件，且未指定 Content-Type，则默认为 x-www-form-urlencoded
                    if not files and 'Content-Type' not in headers:
                        headers['Content-Type'] = 'application/x-www-form-urlencoded'
                    
                    return await client.request(
                        method=method,
                        url=url,
                        data=data,
                        files=files if files else None,
                        headers=headers,
                        params=params
                    )
            else:
                # GET/DELETE 等请求
                return await client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers
                )
        finally:
            # 关闭所有打开的文件
            for f in files.values():
                try:
                    if isinstance(f, tuple):
                        f[1].close()
                    else:
                        f.close()
                except Exception:
                    pass


    @staticmethod
    async def _process_response(response, teststep, start_time):
        try:
            response_json = response.json()
        except ValueError:
            # 如果不是 JSON 响应，返回文本内容
            response_json = {"text": response.text}

        status = "passed"
        error_messages = []

        # 检查状态码
        if teststep.expected_response_code:
            if response.status_code != teststep.expected_response_code:
                status = "failed"
                msg = f"预期状态码: {teststep.expected_response_code}, 实际状态码: {response.status_code}"
                
                # 尝试从响应中提取具体的错误信息
                if isinstance(response_json, dict):
                    details_list = []
                    
                    # 1. 提取 detail (FastAPI 默认)
                    if "detail" in response_json:
                        d = response_json["detail"]
                        if isinstance(d, list):
                            # 处理 [{"loc": ["body", "price"], "msg": "value is not a valid float", ...}]
                            for item in d:
                                if isinstance(item, dict) and "loc" in item and "msg" in item:
                                    # 简化 loc 显示，去掉 body/query 等前缀，只保留字段名
                                    loc_parts = [str(x) for x in item["loc"] if x not in ("body", "query", "path")]
                                    loc = ".".join(loc_parts)
                                    details_list.append(f"{loc}: {item['msg']}" if loc else item['msg'])
                                else:
                                    details_list.append(str(item))
                        else:
                            details_list.append(str(d))
                    
                    # 2. 提取 message / msg
                    if "message" in response_json:
                        details_list.append(str(response_json["message"]))
                    elif "msg" in response_json:
                        details_list.append(str(response_json["msg"]))
                    
                    # 3. 提取 errors / error
                    if "errors" in response_json:
                        details_list.append(str(response_json["errors"]))
                    if "error" in response_json:
                         # 避免 error 和 errors 重复 (有些框架同时返回)
                        if "errors" not in response_json or str(response_json["error"]) != str(response_json["errors"]):
                            details_list.append(str(response_json["error"]))
                    
                    # 4. 提取 code (有时有用)
                    if "code" in response_json:
                        details_list.append(f"Code: {response_json['code']}")

                    # 5. 提取 data (关键补充)
                    if "data" in response_json:
                        data_val = response_json["data"]
                        # 只提取字典或列表类型的 data，且不为空
                        if data_val and isinstance(data_val, (dict, list)):
                             details_list.append(f"Data: {str(data_val)}")

                    if details_list:
                        # 去重并拼接
                        unique_details = []
                        seen = set()
                        for item in details_list:
                            if item not in seen:
                                unique_details.append(item)
                                seen.add(item)
                        
                        detail_str = "; ".join(unique_details)
                        
                        # 智能兜底：如果提取出的信息太短（例如只有 "validation error"），
                        # 且原始响应体长度适中，则追加一部分原始响应体以防遗漏
                        if len(detail_str) < 30 and len(str(response_json)) < 500:
                             # 避免重复：如果 detail_str 已经是 response_json 的一部分，就不追加了
                             raw_resp = str(response_json)
                             if raw_resp not in detail_str:
                                 # 截取前 100 字符
                                 preview = raw_resp[:100] + "..." if len(raw_resp) > 100 else raw_resp
                                 detail_str += f"; 原文: {preview}"

                        # 最终长度控制
                        if len(detail_str) > 200:
                            detail_str = detail_str[:197] + "..."
                        msg += f", 详情: {detail_str}"
                    else:
                        # 如果没有标准错误字段，截取部分响应体
                        resp_str = str(response_json)
                        if len(resp_str) > 100:
                            resp_str = resp_str[:100] + "..."
                        msg += f", 响应: {resp_str}"
                elif response_json:
                    # 如果响应不是字典（例如列表或纯字符串）
                    resp_str = str(response_json)
                    if len(resp_str) > 100:
                        resp_str = resp_str[:100] + "..."
                    msg += f", 响应: {resp_str}"
                
                error_messages.append(msg)

        # 检查响应内容断言列表
        if teststep.assertions:
            for assertion_dict in teststep.assertions:
                try:
                    # 将字典转换为 JsonValueAssertionRule 对象
                    assertion = JsonValueAssertionRule(**assertion_dict)

                    matches = []
                    path_desc = assertion.path if assertion.path else assertion.source.value

                    if assertion.source == VariableSource.STATUS:
                        matches = [response.status_code]
                    elif assertion.source == VariableSource.HEADERS:
                        if assertion.path:
                            val = response.headers.get(assertion.path)
                            if val is not None:
                                matches = [val]
                    elif assertion.source == VariableSource.RESPONSE_TIME:
                        matches = [response.elapsed.total_seconds() * 1000]
                    else:
                        # RESPONSE or BODY (for compatibility, treat BODY as RESPONSE if dealing with response content)
                        # But wait, VariableSource.BODY means Request Body. 
                        # However, for assertions we usually mean Response Body.
                        # If user set source=BODY in old logic (AssertionSource.BODY), it meant response body.
                        # Now VariableSource.RESPONSE is the correct one for response body.
                        
                        target_json = response_json
                        if assertion.source == VariableSource.BODY:
                            # If it explicitly says BODY (Request Body in VariableSource), do we support asserting on request body?
                            # Usually we don't. But assuming legacy data might have "BODY" meaning "RESPONSE".
                            # Let's check if we should migrate data.
                            # For now, let's assume default is RESPONSE.
                            pass
                            
                        if assertion.path:
                            # 兼容性处理：如果 path 是 STATUS 且 source 是 RESPONSE/BODY（默认），修正为 STATUS
                            if assertion.path == "STATUS":
                                matches = [response.status_code]
                            else:
                                try:
                                    jsonpath_expr = parse(assertion.path)
                                    matches = [match.value for match in jsonpath_expr.find(target_json)]
                                except Exception as e:
                                    logger.warning(f"JSONPath 解析失败: {assertion.path}, error: {e}")
                        else:
                            matches = [target_json]

                    # 根据操作符进行验证
                    is_passed = False
                    error_detail = f"路径 '{path_desc}' 查找失败或无匹配"

                    if assertion.operator in ["equal", "not_equal", "contains", "not_contains", "greater_than", "less_than", "greater_or_equal", "less_or_equal"]:
                        if not matches:
                            is_passed = False # 无匹配则断言失败
                            error_detail = f"路径 '{path_desc}' 未找到匹配项"
                        else:
                            actual_value = matches[0] # 通常我们只关心第一个匹配项
                            error_detail = f"路径 '{path_desc}': 预期值 {assertion.value}, 实际值 {actual_value}"
                            
                            if assertion.operator == "equal":
                                is_passed = str(actual_value) == str(assertion.value)
                            elif assertion.operator == "not_equal":
                                is_passed = str(actual_value) != str(assertion.value)
                            elif assertion.operator == "contains":
                                is_passed = str(assertion.value) in str(actual_value)
                            elif assertion.operator == "not_contains":
                                is_passed = str(assertion.value) not in str(actual_value)
                            elif assertion.operator in ["greater_than", "less_than", "greater_or_equal", "less_or_equal"]:
                                # 尝试将值转换为数字进行比较
                                try:
                                    act_f = float(actual_value)
                                    exp_f = float(assertion.value)
                                    if assertion.operator == "greater_than":
                                        is_passed = act_f > exp_f
                                    elif assertion.operator == "less_than":
                                        is_passed = act_f < exp_f
                                    elif assertion.operator == "greater_or_equal":
                                        is_passed = act_f >= exp_f
                                    elif assertion.operator == "less_or_equal":
                                        is_passed = act_f <= exp_f
                                except (ValueError, TypeError):
                                    is_passed = False # 无法转换为数字则断言失败
                                    error_detail += " (无法进行数值比较)"

                    elif assertion.operator.startswith("length_"):
                        if not matches:
                            is_passed = False
                            error_detail = f"路径 '{path_desc}' 未找到匹配项，无法计算长度"
                        else:
                            actual_value = matches[0]
                            try:
                                actual_length = len(actual_value)
                                expected_length = int(assertion.value)
                                error_detail = f"路径 '{path_desc}' 长度: 预期 {expected_length}, 实际 {actual_length}"
                                
                                if assertion.operator == "length_equal":
                                    is_passed = actual_length == expected_length
                                elif assertion.operator == "length_not_equal":
                                    is_passed = actual_length != expected_length
                                elif assertion.operator == "length_greater_than":
                                    is_passed = actual_length > expected_length
                                elif assertion.operator == "length_less_than":
                                    is_passed = actual_length < expected_length
                                elif assertion.operator == "length_greater_or_equal":
                                    is_passed = actual_length >= expected_length
                                elif assertion.operator == "length_less_or_equal":
                                    is_passed = actual_length <= expected_length
                            except (TypeError, ValueError):
                                is_passed = False
                                error_detail = f"路径 '{path_desc}' 的值无法计算长度或预期值不是整数"

                    elif assertion.operator == "exists":
                        is_passed = bool(matches)
                        error_detail = f"路径 '{path_desc}' {'预期存在但未找到' if not is_passed else '存在'}"
                    elif assertion.operator == "not_exists":
                        is_passed = not bool(matches)
                        error_detail = f"路径 '{path_desc}' {'预期不存在但找到' if not is_passed else '不存在'}"

                    elif assertion.operator.startswith("is_") or assertion.operator == "not_null":
                        if not matches:
                            is_passed = False
                            error_detail = f"路径 '{path_desc}' 未找到匹配项，无法进行类型校验"
                        else:
                            actual_value = matches[0]
                            if assertion.operator == "is_array":
                                is_passed = isinstance(actual_value, list)
                                type_name = "Array"
                            elif assertion.operator == "is_dict":
                                is_passed = isinstance(actual_value, dict)
                                type_name = "Object/Dict"
                            elif assertion.operator == "is_string":
                                is_passed = isinstance(actual_value, str)
                                type_name = "String"
                            elif assertion.operator == "is_number":
                                is_passed = isinstance(actual_value, (int, float)) and not isinstance(actual_value, bool)
                                type_name = "Number"
                            elif assertion.operator == "is_boolean":
                                is_passed = isinstance(actual_value, bool)
                                type_name = "Boolean"
                            elif assertion.operator == "is_null":
                                is_passed = actual_value is None
                                type_name = "Null"
                            elif assertion.operator == "not_null":
                                is_passed = actual_value is not None
                                type_name = "Not Null"
                            
                            actual_type = type(actual_value).__name__
                            error_detail = f"路径 '{assertion.path}': 预期类型 {type_name}, 实际类型 {actual_type}"

                    # 如果断言失败，更新总体状态和错误信息
                    if not is_passed:
                        status = "failed"
                        error_messages.append(f"断言失败 ({assertion.operator}): {error_detail}")
                except Exception as e:
                    status = "failed"
                    error_messages.append(f"断言执行异常 ({assertion.operator}, 路径: {assertion.path}): {str(e)}")

        # 合并所有错误信息
        error_message = "; ".join(error_messages) if error_messages else None
        
        # 确保错误信息不超过数据库字段限制 (255字符)
        if error_message and len(error_message) > 255:
            error_message = error_message[:252] + "..."

        duration = time.time() - start_time
        return {
            "status": status,
            "error_message": error_message,
            "response": response_json,
            "status_code": response.status_code,
            "duration": duration
        }

    @staticmethod
    async def _is_login_request(teststep: TestStep) -> bool:
        return teststep.interface.url.endswith('/user/login/') and teststep.interface.method.upper() == 'POST'

    @staticmethod
    async def _handle_login_request(client, url, body, headers):
        logger.info("开始登录")
        
        # 0. 清除现有 Cookies，模拟一个新的 Session
        client.cookies.clear()

        # 1. 发送GET请求获取登录页面和CSRF token
        logger.debug(f"获取登录页面: {url}")
        await client.get(url)
        
        # 2. 从cookie中提取CSRF token
        if '__Host_csrftoken' in client.cookies:
            csrftoken = client.cookies['__Host_csrftoken']
            logger.info(f"获取到CSRF token")
            
            # 3. 设置token到payload和headers
            body['csrfmiddlewaretoken'] = csrftoken
            if not headers:
                headers = {}
            headers['Referer'] = url
            # 不需要设置 X-CSRFToken，因为表单提交只需要 csrfmiddlewaretoken
            
            logger.debug(f"准备发送登录请求: {headers}")
        else:
            logger.warning("未获取到CSRF token，登录可能会失败")

        # 4. 发送登录请求
        # 显式启用重定向跟踪，确保获取到最终页面的 Cookies
        response = await client.request(
            method='POST',
            url=url,
            data=body,
            headers=headers,
            follow_redirects=True
        )

        logger.info(f"登录请求完成，状态码: {response.status_code}")
        logger.debug(f"登录响应 URL: {response.url}")
        
        # 详细打印 Cookie 信息用于调试
        logger.info(f"登录后 Client Cookie Jar: {dict(client.cookies)}")
        for cookie in client.cookies.jar:
            logger.info(f"Cookie详情: name={cookie.name}, value={cookie.value}, domain={cookie.domain}, path={cookie.path}")
            
        if 'gin2_token' not in client.cookies:
            logger.error("严重错误: 登录后未在 Cookie Jar 中找到 gin2_token！")
            logger.error(f"响应头 Set-Cookie: {response.headers.get_list('set-cookie')}")
            logger.error(f"响应体预览: {response.text}")
        else:
            logger.info("成功获取到 gin2_token")

        return response

    @staticmethod
    async def _update_context(response):
        """更新上下文数据"""
        response_data = {}
        content_type = response.headers.get('Content-Type', '')

        if 'application/json' in content_type:
            try:
                response_data = response.json()
            except ValueError:
                logger.warning(f"_update_context 中尝试解析JSON失败，响应内容为: {response.text[:200]}...")
                response_data = {"_parse_error": "Invalid JSON response", "text_content": response.text}
        else:
            response_data = {"text_content": response.text}

        # 使用 client.cookies 获取完整的 cookie jar (包含重定向过程中的 cookies)
        # 如果仅使用 response.cookies，可能会丢失重定向过程中设置的 cookies
        cookies = dict(response.cookies)
        if HttpClient._client:
            cookies = dict(HttpClient._client.cookies)

        await HttpClient._context.update_context(
            response_data,
            dict(response.headers),
            cookies
        )

    @staticmethod
    async def _handle_variable_extraction(teststep):
        """处理变量提取"""
        if teststep.extract_variables:
            if isinstance(teststep.extract_variables, dict):
                for var_name, config in teststep.extract_variables.items():
                    await HttpClient._context.extract_variable(var_name, config)
            elif isinstance(teststep.extract_variables, list):
                for item in teststep.extract_variables:
                    var_name = item.get("name")
                    config = {k: v for k, v in item.items() if k != "name"}
                    if var_name:
                        await HttpClient._context.extract_variable(var_name, config)
