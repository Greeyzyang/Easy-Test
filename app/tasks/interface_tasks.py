from app.celery_app import celery_app
from app.database import async_session_maker
from app.models.interface import Interface
from app.models.module import Module
from app.models.project import Project
from app.utils.logger import get_logger
from app.utils.task_utils import update_celery_task_progress
import httpx
import asyncio
from datetime import datetime
from sqlalchemy import select, and_, or_

logger = get_logger(__name__)

def _get_ref_schema(ref_str, root_data):
    """通用 $ref 解析逻辑"""
    if not ref_str or not isinstance(ref_str, str):
        return None
    ref_path = ref_str.split("/")
    ref_obj = root_data
    try:
        for part in ref_path:
            if part == "#": continue
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(ref_obj, dict):
                ref_obj = ref_obj.get(part, {})
            else:
                return None
        return ref_obj
    except Exception as e:
        logger.error(f"Error resolving $ref {ref_str}: {str(e)}")
        return None

def check_file_fields(data):
    """递归检查数据中是否包含文件相关字段"""
    if isinstance(data, dict):
        for k, v in data.items():
            if any(kw in str(k).lower() for kw in ["file", "attachment", "image"]):
                return True
            if check_file_fields(v):
                return True
    elif isinstance(data, list):
        for item in data:
            if check_file_fields(item):
                return True
    return False

def normalize_url(u):
    """统一规范化 URL"""
    if not u: return ""
    u = u.strip()
    return u[:-1] if u.endswith("/") and u != "/" else u

def resolve_schema(schema, components, depth=0):
    """递归解析 OpenAPI Schema 中的 $ref, allOf, anyOf, oneOf 等"""
    if depth > 10:
        return {}
    if not schema or not isinstance(schema, dict):
        return schema
        
    # 1. 处理 $ref (优先级最高)
    if "$ref" in schema:
        ref_schema = _get_ref_schema(schema["$ref"], components)
        if ref_schema:
            if ref_schema == schema: return {}
            # 合并 $ref 指向的内容和当前层级的 example/default
            resolved = resolve_schema(ref_schema, components, depth + 1)
            if isinstance(resolved, dict) and "example" in schema:
                return schema["example"]
            return resolved
        else:
            return {}

    # 2. 优先检查 example 和 default
    if "example" in schema: return schema["example"]
    if "default" in schema: return schema["default"]

    # 3. 处理组合逻辑 (allOf)
    if "allOf" in schema and isinstance(schema["allOf"], list):
        merged = {}
        for sub in schema["allOf"]:
            resolved_val = resolve_schema(sub, components, depth + 1)
            if isinstance(resolved_val, dict):
                merged.update(resolved_val)
            elif resolved_val is not None and not merged:
                # 如果 allOf 中某一项直接解析出了非字典值（如数组），且当前还没有合并出字典，则以它为准
                return resolved_val
        
        # 将 merged 结果与当前层级的 properties 合并
        if "properties" in schema:
            for k, v in schema.get("properties", {}).items():
                merged[k] = resolve_schema(v, components, depth + 1)
        
        return merged if merged else {}

    # 处理 anyOf, oneOf (取第一个)
    elif "anyOf" in schema or "oneOf" in schema:
        key = "anyOf" if "anyOf" in schema else "oneOf"
        if isinstance(schema[key], list) and len(schema[key]) > 0:
            return resolve_schema(schema[key][0], components, depth + 1)

    # 4. 处理自身的属性
    schema_type = schema.get("type")
    # 隐含类型补偿
    if not schema_type:
        if "properties" in schema: schema_type = "object"
        elif "items" in schema: schema_type = "array"

    if schema_type == "object" or "properties" in schema:
        result = {}
        properties = schema.get("properties", {})
        for key, prop in properties.items():
            result[key] = resolve_schema(prop, components, depth + 1)
        
        # 如果有 additionalProperties，添加一个示例
        if "additionalProperties" in schema and schema["additionalProperties"]:
            add_prop = schema["additionalProperties"]
            if isinstance(add_prop, dict):
                result["additionalProp1"] = resolve_schema(add_prop, components, depth + 1)
            else:
                result["additionalProp1"] = "string"
        return result
    
    elif schema_type == "array" or "items" in schema:
        items = schema.get("items", {})
        res = resolve_schema(items, components, depth + 1)
        # 强制返回列表
        return [res] if not isinstance(res, list) else res

    # 5. 兜底逻辑
    type_defaults = {
        "string": "string",
        "integer": 0,
        "number": 0.0,
        "boolean": False,
        "null": None
    }
    return type_defaults.get(schema_type, "string" if not schema_type else {})

def get_schema_metadata(schema, components, depth=0):
    """递归获取 OpenAPI Schema 的元数据定义（类型、必填项、描述等）"""
    if depth > 10:
        return {"type": "recursive_limit"}
    if not schema or not isinstance(schema, dict):
        return {"type": "unknown"}

    if "$ref" in schema:
        ref_schema = _get_ref_schema(schema["$ref"], components)
        if ref_schema:
            if ref_schema == schema: return {"type": "circular_ref"}
            return get_schema_metadata(ref_schema, components, depth + 1)
        else:
            return {"type": "ref_error", "ref": schema["$ref"]}

    # 2. 处理组合逻辑 (allOf, anyOf, oneOf)
    if "allOf" in schema:
        combined = {"type": "object", "properties": {}, "required": []}
        for sub in schema["allOf"]:
            res = get_schema_metadata(sub, components, depth + 1)
            if isinstance(res, dict) and res.get("type") == "object":
                if "properties" not in combined:
                    combined["properties"] = {}
                combined["properties"].update(res.get("properties", {}))
                
                if "required" not in combined:
                    combined["required"] = []
                combined["required"].extend(res.get("required", []))
            elif isinstance(res, dict) and res.get("type") != "unknown":
                combined["type"] = res.get("type")
        return combined
    
    if "anyOf" in schema or "oneOf" in schema:
        key = "anyOf" if "anyOf" in schema else "oneOf"
        if isinstance(schema[key], list) and len(schema[key]) > 0:
            return get_schema_metadata(schema[key][0], components, depth + 1)

    # 3. 处理核心属性
    schema_type = schema.get("type")
    if not schema_type:
        if "properties" in schema: schema_type = "object"
        elif "items" in schema: schema_type = "array"
        else: schema_type = "object" # 默认

    res = {
        "type": schema_type,
        "description": schema.get("description", ""),
        "format": schema.get("format", ""),
        "example": schema.get("example"),
        "default": schema.get("default"),
    }

    # 约束提取
    constraints = [
        "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
        "minLength", "maxLength", "pattern",
        "minItems", "maxItems", "uniqueItems"
    ]
    for k in constraints:
        if k in schema:
            res[k] = schema[k]

    if res["type"] == "object" or "properties" in schema:
        res["type"] = "object"
        res["properties"] = {}
        res["required"] = schema.get("required", [])
        for key, prop in schema.get("properties", {}).items():
            res["properties"][key] = get_schema_metadata(prop, components, depth + 1)
    
    elif res["type"] == "array" or "items" in schema:
        res["type"] = "array"
        res["items"] = get_schema_metadata(schema.get("items", {}), components, depth + 1)

    return res

def get_method_str(m):
    """统一获取方法字符串"""
    if hasattr(m, 'value'): return str(m.value).upper()
    if hasattr(m, 'name'): return str(m.name).upper()
    return str(m).upper().replace("INTERFACEMETHOD.", "")

@celery_app.task(bind=True, name="app.tasks.interface_tasks.import_swagger_task")
async def import_swagger_task(self, project_id: str, url: str):
    """
    异步导入 Swagger 接口文档任务
    """
    task_id = self.request.id
    logger.info(f"Task {task_id} started: Importing Swagger from {url} to project {project_id}")
    await update_celery_task_progress(self, 5, "正在获取 Swagger 数据...", "PROGRESS")
    
    async with async_session_maker() as db:
        try:
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalars().first()
            if not project:
                error_msg = f"Project not found: {project_id}"
                await update_celery_task_progress(self, 0, error_msg, "FAILURE")
                return {"status": "error", "message": error_msg}

            # 获取 Swagger 数据
            try:
                input_url = url.strip()
                urls_to_try = []
                
                # 如果 URL 已经是以 .json 结尾，或者包含 openapi.json/v2/api-docs 等关键字，优先尝试
                is_json_url = any(k in input_url.lower() for k in [".json", "openapi.json", "v2/api-docs", "v3/api-docs", "swagger.json"])
                
                if is_json_url:
                    urls_to_try.append(input_url)
                
                # 自动构建可能的 JSON 地址
                if "/docs" in input_url:
                    base = input_url.split('/docs')[0].rstrip('/')
                    urls_to_try.append(f"{base}/openapi.json")
                    urls_to_try.append(f"{base}/docs/openapi.json")
                elif "/redoc" in input_url:
                    base = input_url.split('/redoc')[0].rstrip('/')
                    urls_to_try.append(f"{base}/openapi.json")
                elif "/swagger-ui" in input_url:
                    base = input_url.split('/swagger-ui')[0].rstrip('/')
                    urls_to_try.append(f"{base}/v2/api-docs")
                    urls_to_try.append(f"{base}/v3/api-docs")
                    urls_to_try.append(f"{base}/swagger.json")
                
                # 无论如何，都把原地址加进去（如果还没加的话）
                if input_url not in urls_to_try:
                    urls_to_try.append(input_url)
                    
                # 兜底常用路径
                base_origin = input_url.split('?')[0].rstrip('/')
                if base_origin not in [u.rstrip('/') for u in urls_to_try]:
                    urls_to_try.append(f"{base_origin}/openapi.json")
                    urls_to_try.append(f"{base_origin}/v2/api-docs")
                    urls_to_try.append(f"{base_origin}/swagger.json")

                # 去重
                seen = set()
                urls_to_try = [x for x in urls_to_try if not (x in seen or seen.add(x))]
                
                logger.info(f"[DEBUG] URLs to try: {urls_to_try}")
                
                swagger_data = None
                last_error = None
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": input_url
                }
                
                success_url = None
                for target_url in urls_to_try:
                    try:
                        logger.info(f"[DEBUG] Attempting to fetch Swagger from: {target_url}")
                        async with httpx.AsyncClient(follow_redirects=True, verify=False, headers=headers) as client:
                            response = await client.get(target_url, timeout=15.0)
                            logger.info(f"[DEBUG] URL {target_url} returned status: {response.status_code}")
                            
                            if response.status_code == 200:
                                try:
                                    data = response.json()
                                    if isinstance(data, dict) and ("swagger" in data or "openapi" in data or "paths" in data):
                                        swagger_data = data
                                        success_url = target_url
                                        logger.info(f"[DEBUG] Successfully fetched Swagger from: {target_url}")
                                        break
                                    else:
                                        last_error = f"URL {target_url} 返回了非法的 Swagger 格式"
                                except Exception as je:
                                    last_error = f"URL {target_url} 返回内容非 JSON 格式"
                            else:
                                last_error = f"HTTP {response.status_code} ({target_url})"
                    except Exception as e:
                        logger.warning(f"[DEBUG] Error fetching from {target_url}: {str(e)}")
                        last_error = f"连接失败: {str(e)}"

                if not swagger_data:
                    error_msg = f"导入失败：无法获取有效的 Swagger JSON。请检查地址是否正确或目标服务器是否允许访问。最后错误: {last_error}"
                    await update_celery_task_progress(self, 0, error_msg, "FAILURE")
                    return {"status": "error", "message": error_msg}
                    
            except Exception as e:
                error_msg = f"获取 Swagger 数据异常: {str(e)}"
                await update_celery_task_progress(self, 0, error_msg, "FAILURE")
                return {"status": "error", "message": error_msg}

            await update_celery_task_progress(self, 20, "正在解析接口数据...", "PROGRESS")

            # 获取项目中所有的接口，建立 (method, url) 映射
            # 使用 outerjoin 确保即使接口当前没有关联模块也能被查出来并更新
            stmt = select(Interface).join(Module, Interface.module_id == Module.id, isouter=True).where(Module.project_id == project_id)
            result = await db.execute(stmt)
            existing_interfaces = result.scalars().all()
            
            interface_map = {}
            for i in existing_interfaces:
                m_str = get_method_str(i.method)
                u_str = normalize_url(i.url)
                interface_map[(m_str, u_str)] = i

            # 获取/创建模块
            stmt_modules = select(Module).where(Module.project_id == project_id)
            result_modules = await db.execute(stmt_modules)
            existing_modules = result_modules.scalars().all()
            module_map = {m.name: m for m in existing_modules}

            interfaces_created = []
            interfaces_updated = []
            modules_created = []
            
            paths = swagger_data.get("paths", {})
            root_data = swagger_data
            swagger_version = swagger_data.get("info", {}).get("version", "v1")
            
            total = sum(len(methods) for methods in paths.values())
            count = 0

            for path, methods in paths.items():
                for method, details in methods.items():
                    count += 1
                    method_upper = method.upper()
                    if method_upper not in ["GET", "POST", "PUT", "DELETE", "PATCH"]: continue
                    
                    tags = details.get("tags", [])
                    module_name = tags[0] if tags else "Default"
                    if module_name not in module_map:
                        new_mod = Module(name=module_name, project_id=project_id)
                        db.add(new_mod)
                        await db.flush()
                        module_map[module_name] = new_mod
                        modules_created.append(module_name)
                    
                    target_mod = module_map[module_name]
                    
                    # 解析参数
                    headers, params, body, body_schema = {}, {}, {}, {}
                    
                    # 默认注入 X-Auth-Token 全局变量头（引用变量）
                    headers["X-Auth-Token"] = "${X-Auth-Token}"
                    
                    request_type = "JSON"
                    
                    parameters = details.get("parameters", [])
                    for p in parameters:
                        p_in, p_name = p.get("in"), p.get("name")
                        schema = p.get("schema", p)
                        val = resolve_schema(schema, root_data)
                        if p_in == "header": 
                            headers[p_name] = str(val)
                        elif p_in in ["query", "path"]: 
                            params[p_name] = str(val)
                        elif p_in == "formData":
                            request_type = "FORM"
                            body[p_name] = str(val)
                        elif p_in == "body": 
                            body_data = resolve_schema(p.get("schema"), root_data)
                            body_schema_data = get_schema_metadata(p.get("schema"), root_data)
                            
                            if check_file_fields(body_data):
                                request_type = "FORM"
                                logger.info(f"[DEBUG] Detected file-related fields in {path} (v2 recursive), forcing request_type to FORM")
                            
                            body = body_data
                            body_schema = body_schema_data or {}
                            logger.info(f"[DEBUG] Extracted body from parameters (Swagger 2.0): {path}, Body: {body}")
                    
                    req_body = details.get("requestBody", {})
                    if req_body:
                        if "$ref" in req_body:
                            logger.info(f"[DEBUG] requestBody is a $ref: {req_body['$ref']}")
                            req_body = _get_ref_schema(req_body["$ref"], root_data) or {}
                        
                        if isinstance(req_body, dict):
                            content = req_body.get("content", {})
                            if not content:
                                logger.warning(f"[DEBUG] requestBody content is empty for {path}")
                            else:
                                # 优先查找表单类型
                                target_c_type = None
                                for c_type in content.keys():
                                    if "multipart/form-data" in c_type or "x-www-form-urlencoded" in c_type:
                                        target_c_type = c_type
                                        request_type = "FORM"
                                        break
                                
                                # 如果没找到表单类型，再找 JSON
                                if not target_c_type:
                                    for c_type in content.keys():
                                        if "json" in c_type:
                                            target_c_type = c_type
                                            request_type = "JSON"
                                            break
                                
                                # 如果还是没找到，取第一个
                                if not target_c_type and content:
                                    target_c_type = next(iter(content))
                                    request_type = "JSON" # 默认 JSON
                                
                                if target_c_type:
                                    c_details = content[target_c_type]
                                    schema = c_details.get("schema")
                                    if schema:
                                        body_data = resolve_schema(schema, root_data)
                                        body_schema_data = get_schema_metadata(schema, root_data)
                                        
                                        if check_file_fields(body_data):
                                            request_type = "FORM"
                                            logger.info(f"[DEBUG] Detected file-related fields in {path} (recursive), forcing request_type to FORM")

                                        # 修复：直接赋值，不再做复杂的类型校验，由 resolve_schema 保证格式
                                        body = body_data
                                        body_schema = body_schema_data or {}
                                        logger.info(f"[DEBUG] Extracted body from requestBody (OpenAPI 3.0): {path}, Content-Type: {target_c_type}, Body: {body}")
                                    else:
                                        logger.warning(f"[DEBUG] No schema found in requestBody content for {path}, {target_c_type}")
                        else:
                            logger.warning(f"[DEBUG] requestBody resolved to non-dict: {type(req_body)}")

                    if not body and method_upper in ["POST", "PUT", "PATCH"]:
                        logger.warning(f"[DEBUG] Body is still empty for {method_upper} {path}. Check details: {details}")

                    # 最终确保 body_schema 不为 None (针对 POST/PUT/PATCH)
                    if method_upper in ["POST", "PUT", "PATCH"] and body_schema is None:
                        body_schema = {}

                    # 匹配更新逻辑
                    match_key = (method_upper, normalize_url(path))
                    inf = interface_map.get(match_key)
                    
                    if inf:
                        inf.name = details.get("summary") or details.get("operationId") or inf.name
                        inf.description = details.get("description") or details.get("summary") or inf.description
                        inf.request_type = request_type
                        inf.headers = headers
                        inf.params = params
                        inf.body = body
                        if body_schema:
                            inf.body_schema = body_schema
                        
                        inf.module_id = target_mod.id
                        inf.version = swagger_version
                        inf.updated_time = datetime.now()
                        interfaces_updated.append(inf.name)
                    else:
                        new_inf = Interface(
                            name=details.get("summary") or details.get("operationId") or f"{method_upper} {path}",
                            url=path.strip(),
                            method=method_upper,
                            description=details.get("description") or details.get("summary"),
                            module_id=target_mod.id,
                            request_type=request_type,
                            headers=headers,
                            params=params,
                            body=body,
                            body_schema=body_schema,
                            version=swagger_version
                        )
                        db.add(new_inf)
                        interfaces_created.append(new_inf.name)
                    
                    progress = int(20 + (count / total) * 75)
                    await update_celery_task_progress(self, progress, f"正在导入接口: {count}/{total}", "PROGRESS", current=count, total=total)

            await db.commit()
            result_msg = f"导入完成！新增 {len(interfaces_created)}，更新 {len(interfaces_updated)}"
            await update_celery_task_progress(self, 100, result_msg, "SUCCESS")
            return {
                "status": "success",
                "message": result_msg,
                "data": {"created": len(interfaces_created), "updated": len(interfaces_updated)}
            }
        except Exception as e:
            await db.rollback()
            error_msg = f"Task failed: {str(e)}"
            await update_celery_task_progress(self, 0, error_msg, "FAILURE")
            return {"status": "error", "message": error_msg}
