from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.function import Function
from typing import Any, Optional, List
import asyncio
import traceback
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
import inspect
import datetime

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
    ) -> List[Function]:
        """获取函数列表
        
        Args:
            skip: 跳过的记录数
            limit: 返回的记录数
            name: 函数名称过滤
            
        Returns:
            Function 对象列表
        """
        query = select(Function)
        
        if name:
            query = query.where(Function.name.ilike(f"%{name}%"))
            
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()

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

            # 捕获标准输出和标准错误
            stdout = StringIO()
            stderr = StringIO()
            
            with redirect_stdout(stdout), redirect_stderr(stderr):
                # 创建安全的执行环境
                local_vars = {}
                # 允许访问一些常用的内置函数和类型
                allowed_builtins = {
                    'int': int,
                    'str': str,
                    'float': float,
                    'list': list,
                    'dict': dict,
                    'len': len,
                    'print': print,
                    'sum': sum,
                    'max': max,
                    'min': min,
                    'range': range,
                    'isinstance': isinstance,
                    'Exception': Exception,
                    '__import__': __import__,
                    # 可以根据需要添加其他内置项
                }

                # 定义全局命名空间，包含允许的内置函数和需要的模块
                # 将 datetime 模块本身传递给 exec 的全局命名空间
                # 这样用户函数中的 'from datetime import datetime' 才能正确工作
                global_vars = {
                    "__builtins__": allowed_builtins,
                    "datetime": datetime,
                }
                try:
                    # 执行函数代码
                    exec(func.code, global_vars, local_vars)
                    print(f"DEBUG: local_vars after exec: {local_vars}")
                    # 获取函数对象
                    func_obj = local_vars.get(name)
                    if not func_obj:
                        return False, None, stdout.getvalue(), stderr.getvalue() + f"\nFunction {name} not defined in code"
                    
                    # 尝试根据函数签名进行参数类型转换
                    processed_args = []
                    try:
                        signature = inspect.signature(func_obj)
                        params = list(signature.parameters.values())
                        if len(args) != len(params):
                            return False, None, stdout.getvalue(), stderr.getvalue() + f"\nFunction {name} expected {len(params)} arguments, but received {len(args)}"

                        for i, arg_str in enumerate(args):
                            param = params[i]
                            annotation = param.annotation
                            # 尝试根据类型提示转换参数
                            try:
                                if annotation is inspect.Parameter.empty or annotation is str:
                                    # 没有类型提示或指定为 str，直接使用字符串
                                    processed_args.append(arg_str)
                                elif annotation is int:
                                    processed_args.append(int(arg_str))
                                elif annotation is float:
                                    processed_args.append(float(arg_str))
                                elif annotation is bool:
                                    # 简单的布尔转换，例如 'true' -> True, 'false' -> False
                                    processed_args.append(arg_str.lower() == 'true')
                                # TODO: 支持更多复杂类型，如 list, dict 等
                                else:
                                    # 对于其他未处理的类型，暂时保留原始字符串
                                    print(f"Warning: Unhandled parameter type {annotation} for function {name}")
                                    processed_args.append(arg_str)
                            except ValueError as ve:
                                return False, None, stdout.getvalue(), stderr.getvalue() + f"\nInvalid argument type for parameter '{param.name}' in function {name}: Cannot convert '{arg_str}' to {annotation.__name__}. {ve}"

                    except Exception as e:
                        return False, None, stdout.getvalue(), stderr.getvalue() + f"\nError processing function parameters for {name}: {e}"
                    
                    # 执行函数
                    if asyncio.iscoroutinefunction(func_obj):
                        result = await func_obj(*processed_args) # 使用转换后的参数
                    else:
                        result = func_obj(*processed_args) # 使用转换后的参数
                        
                    return True, result, stdout.getvalue(), stderr.getvalue()
                    
                except Exception as e:
                    error_msg = f"Error executing function {name}: {str(e)}\n{traceback.format_exc()}"
                    print(f"DEBUG: execute_function error: {error_msg}")
                    return False, None, stdout.getvalue(), stderr.getvalue() + "\n" + error_msg
                    
        except Exception as e:
            error_msg = f"Error getting function {name}: {str(e)}\n{traceback.format_exc()}"
            print(f"DEBUG: get_function error: {error_msg}")
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