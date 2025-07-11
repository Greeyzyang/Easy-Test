import httpx
from fastapi import HTTPException
from app.models import TestStep, Interface
import time
from jsonpath_rw import parse
from typing import Dict, Any, Union, Optional
from app.schemas.base_schemas import RequestType
from app.services.function_service import FunctionService
from app.schemas.teststep import JsonValueAssertionRule
import re
from sqlalchemy import select



class TestContext:
    """测试上下文管理类，负责管理测试过程中的变量和状态"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.variables = {}
            cls._instance.last_response = {}
            cls._instance.last_headers = {}
            cls._instance.cookies = {}
            cls._instance.db = None
            cls._instance.last_request_body = {}  # 保存最近一次请求体
        return cls._instance

    def set_db(self, db):
        """设置数据库会话"""
        self.db = db
        print(f"数据库会话已设置: {db}")

    async def process_template_string(self, template_str: str) -> str:
        """
        处理包含 ${} 标记的字符串，支持变量替换和函数调用
        
        处理逻辑：
        1. 检查输入字符串是否包含 ${...} 占位符
        2. 对于每个占位符：
           - 如果是函数调用（包含括号），执行函数并返回结果
           - 如果是变量，从上下文中获取变量值
        3. 替换所有占位符，返回处理后的字符串
        
        支持的语法：
        - 变量替换：${variable_name}
        - 函数调用：${function_name(arg1, arg2)}
        
        示例：
        - 输入：template_str = "Hello ${name}, your age is ${get_age()}"
        - 假设上下文中有 name="Alice"，get_age() 函数返回 25
        - 输出：result = "Hello Alice, your age is 25"
        
        Args:
            template_str: 可能包含 ${} 标记的字符串
            
        Returns:
            str: 处理后的字符串，所有 ${} 占位符都被替换为实际值
        """
        # 1. 输入验证：检查字符串是否为空或非字符串类型
        if not template_str or not isinstance(template_str, str):
            return template_str
            
        # 2. 定义内部函数，用于处理每个 ${...} 占位符
        async def replace_func(match):
            content = match.group(1)  # 提取 ${} 内的内容
            try:
                # 3. 检查是否是函数调用（包含括号）
                if '(' in content and content.endswith(')'):
                    # 函数调用处理
                    func_part = content[content.index('(')+1:-1]  # 提取括号内的参数
                    func_name = content[:content.index('(')]      # 提取函数名
                    
                    # 解析函数参数
                    if func_part:  # 如果有实际的参数内容
                        func_args = [arg.strip() for arg in func_part.split(',')]
                    else:  # 没有参数
                        func_args = []
                    
                    print(f"执行函数调用: {func_name}({func_args})")
                    # 执行函数并返回结果
                    return await self._execute_function(func_name, func_args)
                else:
                    # 4. 变量处理：从上下文中获取变量值
                    var_value = await self.get_variable(content)
                    print(f"获取变量 {content}: {var_value}")
                    return str(var_value) if var_value is not None else content
            except Exception as e:
                # 5. 异常处理：如果处理失败，返回原始占位符
                print(f"处理模板 '{content}' 时出错: {str(e)}")
                return match.group(0)  # 失败时返回原始匹配字符串
                
        # 6. 执行模板替换
        # 由于 re.sub 不支持异步函数，我们需要手动处理替换
        # 先收集所有匹配项，然后倒序处理，避免替换操作改变后续匹配项的索引
        result_str = template_str
        
        # 使用正则表达式查找所有 ${...} 占位符
        # re.finditer 返回迭代器，需要转换为列表才能倒序
        matches = list(re.finditer(r'\${([^}]+)}', template_str))
        
        # 倒序处理，避免替换操作影响后续匹配项的索引
        for match in reversed(matches):
            replacement = await replace_func(match)
            # 使用切片进行替换，确保准确性
            result_str = result_str[:match.start()] + replacement + result_str[match.end():]
        
        print(f"模板处理完成: '{template_str}' -> '{result_str}'")
        return result_str

    async def process_template_dict(self, data: dict) -> dict:
        """处理字典中所有字符串类型的值
        
        Args:
            data: 需要处理的字典
            
        Returns:
            处理后的字典
        """
        if not data:
            return data
            
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = await self.process_template_string(value)
            elif isinstance(value, dict):
                result[key] = await self.process_template_dict(value)
            elif isinstance(value, list):
                result[key] = await self.process_template_list(value)
            else:
                result[key] = value
        return result

    async def process_template_list(self, data: list) -> list:
        """处理列表中所有字符串类型的值
        
        Args:
            data: 需要处理的列表
            
        Returns:
            处理后的列表
        """
        if not data:
            return data
            
        result = []
        for item in data:
            if isinstance(item, str):
                result.append(await self.process_template_string(item))
            elif isinstance(item, dict):
                result.append(await self.process_template_dict(item))
            elif isinstance(item, list):
                result.append(await self.process_template_list(item))
            else:
                result.append(item)
        return result

    async def _execute_function(self, func_name: str, args: list) -> str:
        """执行函数并返回结果
        
        Args:
            func_name: 函数名
            args: 函数参数列表
            
        Returns:
            函数执行结果
        """
        try:

            if not self.db:
                raise ValueError("数据库会话未设置")

            function_service = FunctionService(self.db)
            success, result, stdout, stderr = await function_service.execute_function(func_name, args)
            
            if not success:
                print(f"执行函数 {func_name} 失败:")
                if stdout:
                    print(f"标准输出: {stdout}")
                if stderr:
                    print(f"标准错误: {stderr}")
                return ''
                
            return str(result)
                
        except Exception as e:
            print(f"执行函数 {func_name} 时出错: {str(e)}")
            return ''

    async def extract_variable(self, name: str, config: Union[str, dict]):
        """提取变量
        
        Args:
            name: 变量名
            config: 提取配置, 可以是:
                   - 字符串: 默认从response提取的jsonpath
                   - 字典: 包含source和path的配置，如 {"source": "headers", "path": "Content-Type"}
        """
        try:
            # 解析配置
            path, source = await self._parse_extract_config(config)
            if not source:
                raise ValueError(f"未指定数据源")

            # 打印调试信息
            await self._print_debug_info(name, source, path)

            # 根据数据源提取变量
            value = await self._extract_value_from_source(source, path)
            if value is not None:
                self.variables[name] = value
                print(f"提取到的变量值: {name} = {value}")
            else:
                print(f"未找到匹配的值: {path}")
                
        except Exception as e:
            print(f"变量提取失败: {str(e)}")
            return None

    async def _parse_extract_config(self, config: Union[str, dict]) -> tuple:
        """解析提取配置
        
        Args:
            config: 提取配置
            
        Returns:
            tuple: (path, source)
        """
        if isinstance(config, str):
            return config, "response"
        return config.get("path"), config.get("source", "").lower()

    async def _print_debug_info(self, name: str, source: str, path: str):
        """打印调试信息"""
        print(f"正在提取变量 {name}，从 {source} 中获取 {path}")
        print(f"当前 cookies: {self.cookies}")
        print(f"当前 headers: {self.last_headers}")
        print(f"当前 response: {self.last_response}")

    async def _extract_value_from_source(self, source: str, path: str) -> Any:
        """从指定数据源提取值
        
        Args:
            source: 数据源
            path: 提取路径
            
        Returns:
            提取的值
        """
        if source == "response":
            jsonpath_expr = parse(path)
            matches = [match.value for match in jsonpath_expr.find(self.last_response)]
            return matches[0] if matches else None
        elif source == "headers":
            return self.last_headers.get(path)
        elif source == "cookies":
            return self.cookies.get(path)
        elif source == "body":  # 支持从请求体提取变量
            jsonpath_expr = parse(path)
            matches = [match.value for match in jsonpath_expr.find(self.last_request_body)]
            return matches[0] if matches else None
        else:
            raise ValueError(f"不支持的数据源: {source}")

    async def get_variable(self, name: str) -> Any:
        """获取变量值，并递归处理其中的占位符"""
        value = self.variables.get(name)
        # 如果值是字符串且包含 ${}，递归处理
        if isinstance(value, str) and '${' in value and '}' in value:
            prev_value = None
            # 防止死循环，只有值发生变化时才继续递归
            while isinstance(value, str) and '${' in value and '}' in value and value != prev_value:
                prev_value = value
                value = await self.process_template_string(value)
        return value

    async def update_context(self, response_data: dict, headers: dict, cookies: dict):
        """更新上下文数据"""
        # 保证所有属性都是dict类型
        if not isinstance(response_data, dict):
            response_data = {'text': response_data}
        if not isinstance(headers, dict):
            headers = {}
        if not isinstance(cookies, dict):
            cookies = {}
        self.last_response = response_data
        self.last_headers = headers
        self.cookies = cookies

    async def clear(self):
        """清除上下文数据"""
        self.variables.clear()
        if isinstance(self.last_response, dict):
            self.last_response.clear()
        else:
            self.last_response = {}
        if isinstance(self.last_headers, dict):
            self.last_headers.clear()
        else:
            self.last_headers = {}
        if isinstance(self.cookies, dict):
            self.cookies.clear()
        else:
            self.cookies = {}
        if isinstance(self.last_request_body, dict):
            self.last_request_body.clear()
        else:
            self.last_request_body = {}
        # 注意：不清除 db，因为它在整个测试套件执行期间都需要使用
        print("上下文数据已清除，保留数据库会话")

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
        print(f"处理 URL 中的变量替换: {path}")
        print(f"当前上下文变量: {HttpClient._context.variables}")
        
        pattern = r'\${([^}]+)}'
        
        async def replace_var(match):
            var_name = match.group(1)
            var_value = await HttpClient._context.get_variable(var_name)
            print(f"替换 URL 变量 {var_name}: ${{{var_name}}} -> {var_value}")
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
            print("警告: base_url 未设置，可能导致请求失败")
        
        # 2. 获取接口的 URL 路径，并去除开头的斜杠
        path = interface.url.lstrip('/')
        
        # 3. 处理 URL 路径中的变量替换
        # 如果路径中包含 ${...} 占位符，会从上下文中获取对应的变量值进行替换
        if '${' in path and '}' in path:
            print(f"检测到路径中的变量占位符: {path}")
            path = await HttpClient._process_url_variables(path)
            print(f"变量替换后的路径: {path}")
        
        # 4. 拼接 base_url 和路径，形成完整的 URL
        full_url = f"{base_url}/{path}"
        print(f"构建完整URL: {full_url}")
        
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
            # 接口对象包含了请求方法、URL路径等信息
            result = await db.execute(
                select(Interface).where(Interface.id == teststep.interface_id)
            )
            interface = result.scalar_one_or_none()

            if not interface:
                raise HTTPException(status_code=404, detail=f"接口 {teststep.interface_id} 未找到")
                
            print(f"获取到接口: {interface.method} {interface.url}")
                
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
            # 处理请求头中的变量
            processed_headers = await HttpClient._context.process_template_dict(teststep.headers or {})
            # 处理查询参数中的变量
            processed_params = await HttpClient._context.process_template_dict(teststep.params or {})
            
            print(f"请求参数处理完成 - Body: {len(processed_body)}, Headers: {len(processed_headers)}, Params: {len(processed_params)}")

            # 保存请求体到上下文，便于后续变量提取
            HttpClient._context.last_request_body = processed_body.copy() if isinstance(processed_body, dict) else processed_body
            
            # ==================== URL构建阶段 ====================
            # 5. 构建完整的请求 URL
            # 这一步会：
            # - 从上下文中获取 base_url
            # - 拼接接口的 URL 路径
            # - 处理路径中的变量替换
            full_url = await HttpClient._build_url(interface)
            print(f"构建完整URL: {full_url}")
            
            # ==================== 请求发送阶段 ====================
            # 6. 根据请求类型发送 HTTP 请求
            
            # 检查是否是登录请求（需要特殊处理）
            if await HttpClient._is_login_request(teststep):
                print("检测到登录请求，使用特殊处理逻辑")
                response = await HttpClient._handle_login_request(
                    client, full_url, processed_body, processed_headers
                )
            else:
                # 发送普通请求
                print(f"发送 {interface.method} 请求到 {full_url}")
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
            # 这一步会：
            # - 解析响应内容
            # - 执行断言验证
            # - 检查状态码
            # - 计算执行耗时
            result = await HttpClient._process_response(response, teststep, start_time)
            
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
            
            print(f"请求执行完成，状态: {result['status']}, 耗时: {result['duration']:.2f}s")
            return result
                
        except Exception as e:
            # ==================== 异常处理阶段 ====================
            print(f"请求执行失败: {str(e)}")
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
        # 记录请求信息
        print(f"发送请求: {method} {url}")
        print(f"请求headers: {headers}")
        print(f"请求payload: {body}")
        print(f"请求params: {params}")
        print(f"客户端cookies: {dict(client.cookies)}")
        
        # 根据不同的请求类型设置不同的参数
        if method.upper() == "POST":
            # 对于登录请求，强制使用表单提交
            if url.endswith('/user/login/'):
                return await client.request(
                    method=method,
                    url=url,
                    data=body,  # 使用 data 而不是 json
                    headers=headers,
                    params=params
                )
            # 其他请求按照 request_type 处理
            elif request_type == RequestType.JSON:
                headers['Content-Type'] = 'application/json'
                return await client.request(
                    method=method,
                    url=url,
                    json=body,
                    headers=headers,
                    params=params
                )
            elif request_type == RequestType.FORM:
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                return await client.request(
                    method=method,
                    url=url,
                    data=body,
                    headers=headers,
                    params=params
                )
            elif request_type == RequestType.FILE and file_config:
                return await HttpClient._send_file_request(client, method, url, body, headers, file_config)
        else:
            # GET 请求参数使用 params
            return await client.request(
                method=method,
                url=url,
                params=params,
                headers=headers
            )

    @staticmethod
    async def _send_file_request(client, method, url, payload, headers, file_config):
        files = {}
        try:
            for field_name, file_path in file_config.items():
                try:
                    files[field_name] = open(file_path, 'rb')
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"无法打开文件 {file_path}: {str(e)}"
                    )
            
            return await client.request(
                method,
                url,
                files=files,
                data=payload,
                headers=headers
            )
        finally:
            for file in files.values():
                file.close()

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
                error_messages.append(f"预期状态码: {teststep.expected_response_code}, 实际状态码: {response.status_code}")

        # 检查响应内容断言列表
        if teststep.assertions:
            for assertion_dict in teststep.assertions:
                try:
                    # 将字典转换为 JsonValueAssertionRule 对象
                    assertion = JsonValueAssertionRule(**assertion_dict)

                    jsonpath_expr = parse(assertion.path)
                    matches = [match.value for match in jsonpath_expr.find(response_json)]

                    # 根据操作符进行验证
                    is_passed = False
                    error_detail = f"路径 '{assertion.path}' 查找失败或无匹配"

                    if assertion.operator in ["equal", "not_equal", "contains", "not_contains", "greater_than", "less_than"]:
                        if not matches:
                            is_passed = False # 无匹配则断言失败
                            error_detail = f"路径 '{assertion.path}' 未找到匹配项"
                        else:
                            actual_value = matches[0] # 通常我们只关心第一个匹配项
                            error_detail = f"路径 '{assertion.path}': 预期值 {assertion.value}, 实际值 {actual_value}"
                            
                            if assertion.operator == "equal":
                                is_passed = str(actual_value) == str(assertion.value)
                            elif assertion.operator == "not_equal":
                                is_passed = str(actual_value) != str(assertion.value)
                            elif assertion.operator == "contains":
                                is_passed = str(assertion.value) in str(actual_value)
                            elif assertion.operator == "not_contains":
                                is_passed = str(assertion.value) not in str(actual_value)
                            elif assertion.operator == "greater_than":
                                # 尝试将值转换为数字进行比较
                                try:
                                    is_passed = float(actual_value) > float(assertion.value)
                                except (ValueError, TypeError):
                                    is_passed = False # 无法转换为数字则断言失败
                                    error_detail += " (无法进行数值比较)"
                            elif assertion.operator == "less_than":
                                # 尝试将值转换为数字进行比较
                                try:
                                    is_passed = float(actual_value) < float(assertion.value)
                                except (ValueError, TypeError):
                                    is_passed = False # 无法转换为数字则断言失败
                                    error_detail += " (无法进行数值比较)"

                    elif assertion.operator == "exists":
                        is_passed = bool(matches)
                        error_detail = f"路径 '{assertion.path}' {'预期存在但未找到' if not is_passed else '存在'}"
                    elif assertion.operator == "not_exists":
                        is_passed = not bool(matches)
                        error_detail = f"路径 '{assertion.path}' {'预期不存在但找到' if not is_passed else '不存在'}"

                    # 如果断言失败，更新总体状态和错误信息
                    if not is_passed:
                        status = "failed"
                        error_messages.append(f"断言失败 ({assertion.operator}): {error_detail}")
                except Exception as e:
                    status = "failed"
                    error_messages.append(f"断言执行异常 ({assertion.operator}, 路径: {assertion.path}): {str(e)}")

        # 合并所有错误信息
        error_message = "; ".join(error_messages) if error_messages else None

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
        print("检测到登录请求，使用Session模式处理")
        # 1. 发送GET请求获取登录页面和CSRF token
        print(f"Step 1: 获取登录页面 {url}")
        await client.get(url)
        
        # 2. 从cookie中提取CSRF token
        if '__Host_csrftoken' in client.cookies:
            csrftoken = client.cookies['__Host_csrftoken']
            print(f"Step 2: 获取到CSRF token: {csrftoken}")
            
            # 3. 设置token到payload和headers
            body['csrfmiddlewaretoken'] = csrftoken
            if not headers:
                headers = {}
            headers['Referer'] = url
            # 不需要设置 X-CSRFToken，因为表单提交只需要 csrfmiddlewaretoken
            
            print(f"Step 3: 准备发送登录请求")
            print(f"- URL: {url}")
            print(f"- Headers: {headers}")
            print(f"- Payload: {body}")
            print(f"- Cookies: {dict(client.cookies)}")
        else:
            print("警告: 未获取到CSRF token，登录可能会失败")

        # 4. 发送登录请求
        response = await client.request(
            method='POST',
            url=url,
            data=body,
            headers=headers
        )

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
                print(f"警告: _update_context 中尝试解析JSON失败，响应内容为: {response.text[:200]}...")
                response_data = {"_parse_error": "Invalid JSON response", "text_content": response.text}
        else:
            response_data = {"text_content": response.text}

        await HttpClient._context.update_context(
            response_data,
            dict(response.headers),
            dict(response.cookies)
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
