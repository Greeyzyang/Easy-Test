from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.models.function import Function
from typing import Any, Optional, List
import asyncio
import traceback
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
import inspect
import datetime

from app.utils.logger import get_logger

logger = get_logger(__name__)

class FunctionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_function(self, name: str) -> Optional[Function]:
        """获取函数定义
        
        Args:
            name: 函数名
            
        Returns:
            Function 对象或 None
        """
        result = await self.db.execute(
            select(Function).where(Function.name == name)
        )
        return result.scalar_one_or_none()

    async def get_function_by_id(self, function_id: str) -> Optional[Function]:
        """根据ID获取函数定义
        
        Args:
            function_id: 函数ID
            
        Returns:
            Function 对象或 None
        """
        result = await self.db.execute(
            select(Function).where(Function.id == function_id)
        )
        return result.scalar_one_or_none()

    async def list_functions(
        self, 
        skip: int = 0, 
        limit: int = 10, 
        name: Optional[str] = None
    ) -> tuple[List[Function], int]:
        """获取函数列表
        
        Args:
            skip: 跳过的记录数
            limit: 返回的记录数
            name: 函数名称过滤
            
        Returns:
            (Function 对象列表, 总记录数)
        """
        query = select(Function)
        count_query = select(func.count()).select_from(Function)
        
        if name:
            filter_stmt = Function.name.ilike(f"%{name}%")
            query = query.where(filter_stmt)
            count_query = count_query.where(filter_stmt)
            
        # 执行计数查询
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # 执行分页查询
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    def _get_safe_globals(self):
        """获取安全的全局执行环境"""
        # 1. 基础内置函数白名单
        allowed_builtins = {
            'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
            'bytearray': bytearray, 'bytes': bytes, 'chr': chr, 'dict': dict,
            'divmod': divmod, 'enumerate': enumerate, 'filter': filter,
            'float': float, 'format': format, 'frozenset': frozenset,
            'getattr': getattr, 'hasattr': hasattr, 'hash': hash, 'hex': hex,
            'id': id, 'int': int, 'isinstance': isinstance, 'issubclass': issubclass,
            'iter': iter, 'len': len, 'list': list, 'map': map, 'max': max,
            'min': min, 'next': next, 'object': object, 'oct': oct, 'ord': ord,
            'pow': pow, 'print': print, 'range': range, 'repr': repr,
            'reversed': reversed, 'round': round, 'set': set, 'slice': slice,
            'sorted': sorted, 'str': str, 'sum': sum, 'tuple': tuple,
            'type': type, 'zip': zip, 'Exception': Exception, 'ValueError': ValueError,
            'TypeError': TypeError, 'KeyError': KeyError, 'IndexError': IndexError
        }

        # 2. 预置安全模块
        import json, math, random, re, time, collections, itertools, hashlib, uuid
        
        safe_modules = {
            "json": json,
            "math": math,
            "random": random,
            "re": re,
            "time": time,
            "datetime": datetime,
            "collections": collections,
            "itertools": itertools,
            "hashlib": hashlib,
            "uuid": uuid
        }

        # 3. 自定义安全导入函数
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in safe_modules:
                return safe_modules[name]
            raise ImportError(f"Import of module '{name}' is not allowed")

        # 将 safe_import 添加到内置函数中
        allowed_builtins['__import__'] = safe_import

        # 定义全局命名空间，包含允许的内置函数和预置模块
        return {
            "__builtins__": allowed_builtins,
            **safe_modules
        }

    async def execute_function(self, name: str, args: list) -> tuple[bool, Any, str, str]:
        """执行函数
        
        Args:
            name: 函数名
            args: 函数参数列表
            
        Returns:
            tuple: (是否成功, 结果, 标准输出, 标准错误)
        """
        try:
            # 获取函数定义
            func = await self.get_function(name)
            if not func:
                return False, None, "", f"Function {name} not found"
            
            return await self.execute_code(func.code, name, args)
                    
        except Exception as e:
            error_msg = f"Error executing function {name}: {str(e)}\n{traceback.format_exc()}"
            logger.error(f"execute_function error: {error_msg}")
            return False, None, "", error_msg

    async def execute_code(self, code: str, entry_name: Optional[str], args: list) -> tuple[bool, Any, str, str]:
        """执行代码
        
        Args:
            code: 代码内容
            entry_name: 入口函数名
            args: 参数列表
            
        Returns:
            tuple: (是否成功, 结果, 标准输出, 标准错误)
        """
        try:
            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                local_vars = {}
                global_vars = self._get_safe_globals()
                
                try:
                    # 执行代码
                    exec(code, global_vars, local_vars)
                    
                    # 获取函数对象
                    func_obj = None
                    if entry_name:
                        func_obj = local_vars.get(entry_name)
                        if not func_obj:
                            return False, None, stdout.getvalue(), stderr.getvalue() + f"\nFunction {entry_name} not defined in code"
                    else:
                        # 如果未指定入口函数，尝试自动查找
                        callables = [(k, v) for k, v in local_vars.items() if callable(v) and not k.startswith('_')]
                        if len(callables) == 1:
                            func_obj = callables[0][1]
                            entry_name = callables[0][0]
                        elif len(callables) == 0:
                            return False, None, stdout.getvalue(), stderr.getvalue() + "\nNo callable found in code"
                        else:
                            names = ", ".join([k for k, _ in callables])
                            return False, None, stdout.getvalue(), stderr.getvalue() + f"\nMultiple callables found: {names}. Provide entry_name."

                    # 参数处理
                    processed_args = []
                    try:
                        signature = inspect.signature(func_obj)
                        params = list(signature.parameters.values())
                        
                        has_var_args = any(p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD) for p in params)
                        if not has_var_args and len(args) != len(params):
                             return False, None, stdout.getvalue(), stderr.getvalue() + f"\nFunction {entry_name} expected {len(params)} arguments, but received {len(args)}"

                        for i, arg_str in enumerate(args):
                            if i < len(params):
                                param = params[i]
                                annotation = param.annotation
                                try:
                                    if annotation is inspect.Parameter.empty or annotation is str:
                                        processed_args.append(arg_str)
                                    elif annotation is int:
                                        processed_args.append(int(arg_str))
                                    elif annotation is float:
                                        processed_args.append(float(arg_str))
                                    elif annotation is bool:
                                        processed_args.append(str(arg_str).lower() == 'true')
                                    elif annotation is list:
                                        import json
                                        processed_args.append(json.loads(arg_str) if isinstance(arg_str, str) else arg_str)
                                    elif annotation is dict:
                                        import json
                                        processed_args.append(json.loads(arg_str) if isinstance(arg_str, str) else arg_str)
                                    else:
                                        processed_args.append(arg_str)
                                except ValueError as ve:
                                    return False, None, stdout.getvalue(), stderr.getvalue() + f"\nInvalid argument type for parameter '{param.name}': Cannot convert '{arg_str}' to {getattr(annotation,'__name__',str(annotation))}. {ve}"
                            else:
                                processed_args.append(arg_str)
                    except Exception as e:
                        return False, None, stdout.getvalue(), stderr.getvalue() + f"\nError processing function parameters: {e}"

                    # 执行函数
                    if asyncio.iscoroutinefunction(func_obj):
                        result = await func_obj(*processed_args)
                    else:
                        result = func_obj(*processed_args)
                        
                    return True, result, stdout.getvalue(), stderr.getvalue()
                except Exception as e:
                    error_msg = f"Error executing code: {str(e)}\n{traceback.format_exc()}"
                    return False, None, stdout.getvalue(), stderr.getvalue() + "\n" + error_msg
        except Exception as e:
            error_msg = f"Error preparing execution: {str(e)}\n{traceback.format_exc()}"
            return False, None, "", error_msg

    async def create_function(self, name: str, code: str, description: str = "") -> Function:
        """创建新函数
        
        Args:
            name: 函数名
            code: 函数代码
            description: 函数描述
            
        Returns:
            Function 对象
        """
        # 检查函数名是否已存在
        existing = await self.get_function(name)
        if existing:
            raise ValueError(f"Function {name} already exists")
            
        # 创建新函数
        function = Function(
            name=name,
            code=code,
            description=description
        )
        self.db.add(function)
        await self.db.commit()
        await self.db.refresh(function)
        return function

    async def update_function(self, function_id: str, name: str = None, code: str = None, description: str = None) -> Function:
        """更新函数
        
        Args:
            function_id: 函数ID
            name: 新的函数名
            code: 新的函数代码
            description: 新的函数描述
            
        Returns:
            Function 对象
        """
        function = await self.get_function_by_id(function_id)
        if not function:
            raise ValueError(f"Function {function_id} not found")
            
        if name is not None:
            function.name = name
        if code is not None:
            function.code = code
        if description is not None:
            function.description = description
            
        await self.db.commit()
        await self.db.refresh(function)
        return function

    async def delete_function(self, function_id: str) -> bool:
        """删除函数
        
        Args:
            function_id: 函数ID
            
        Returns:
            bool: 是否成功删除
        """
        function = await self.get_function_by_id(function_id)
        if not function:
            return False
            
        await self.db.delete(function)
        await self.db.commit()
        return True 
