import contextvars
import re
from typing import Any, Optional, Dict
from jsonpath_rw import parse as jsonpath_parse

from app.utils.logger import get_logger

logger = get_logger(__name__)

resolving_vars_context = contextvars.ContextVar("resolving_vars", default=frozenset())


class BaseExecutionContext:
    """压测与接口自动化共享的上下文基类，负责变量管理和模板替换"""

    def __init__(self):
        self.variables: Dict[str, Any] = {}
        self.last_response: Dict = {}
        self.last_headers: Dict = {}
        self.cookies: Dict = {}
        self.last_request_body: Dict = {}

    async def process_template_string(self, template_str: str) -> str:
        if not template_str or not isinstance(template_str, str):
            return template_str
        result_str = template_str
        matches = list(re.finditer(r'\$\{([^}]+)}', template_str))
        for match in reversed(matches):
            content = match.group(1).strip()
            value = await self.get_variable(content)
            if value is not None:
                result_str = result_str[:match.start()] + str(value) + result_str[match.end():]
        return result_str

    async def process_template_dict(self, data: Any) -> Any:
        if data is None:
            return None
        if isinstance(data, dict):
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
        elif isinstance(data, list):
            return await self.process_template_list(data)
        elif isinstance(data, str):
            return await self.process_template_string(data)
        return data

    async def process_template_list(self, data: list) -> list:
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

    async def get_variable(self, name: str) -> Any:
        resolving_vars = resolving_vars_context.get()
        if name in resolving_vars and name != 'X-Auth-Token':
            logger.debug(f"检测到变量循环引用: {name}")
            return f"${{{name}}}"
        token = resolving_vars_context.set(resolving_vars | {name})
        try:
            value = self.variables.get(name)
            if value is None:
                return None
            if isinstance(value, str) and value.strip() == f"${{{name}}}":
                return value
            if isinstance(value, str) and '${' in value and '}' in value:
                prev_value = None
                loop_count = 0
                while isinstance(value, str) and '${' in value and '}' in value and value != prev_value:
                    if loop_count > 10:
                        logger.warning(f"变量 {name} 解析超过最大深度，停止")
                        break
                    loop_count += 1
                    prev_value = value
                    value = await self.process_template_string(value)
            return value
        finally:
            resolving_vars_context.reset(token)

    def _extract_by_jsonpath(self, data: Any, path: str) -> Optional[Any]:
        try:
            jsonpath_expr = jsonpath_parse(path)
            matches = [m.value for m in jsonpath_expr.find(data)]
            return matches[0] if matches else None
        except Exception:
            return None

    async def extract_variable(self, name: str, config: Dict):
        if isinstance(config, str):
            source, path = "response", config
        else:
            source = config.get("source", "response")
            path = config.get("path", "")
        try:
            if source == "response":
                value = self._extract_by_jsonpath(self.last_response, path)
            elif source == "headers":
                value = self.last_headers.get(path)
            elif source == "cookies":
                value = self.cookies.get(path)
            elif source == "body":
                value = self._extract_by_jsonpath(self.last_request_body, path)
            else:
                value = None
            if value is not None:
                self.variables[name] = value
                logger.debug(f"提取变量: {name} = {value} (source={source})")
            else:
                logger.warning(f"未找到变量 '{name}' (source={source}, path={path})")
        except Exception as e:
            logger.error(f"变量提取失败 '{name}': {e}")

    def update_response(self, body: Dict, headers: Dict, cookies: Dict):
        self.last_response = body or {}
        self.last_headers = headers or {}
        if cookies:
            self.cookies = {k: (v.value if hasattr(v, 'value') else v) for k, v in cookies.items()}
        else:
            self.cookies = {}

    def clear(self):
        self.variables.clear()
        self.last_response.clear()
        self.last_headers.clear()
        self.cookies.clear()
        self.last_request_body.clear()
