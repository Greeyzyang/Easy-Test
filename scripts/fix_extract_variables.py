import asyncio
import json
import re
from sqlalchemy import select, update
from app.db.session import async_session
from app.models.testcase import Testcase
from app.models.teststep import TestStep

def generate_valid_name(path: str) -> str:
    """从 path 生成有效的变量名"""
    # 如果是 JSONPath，提取最后一个部分
    if path.startswith('$'):
        parts = path.split('.')
        last_part = parts[-1]
        # 移除数组索引和特殊字符
        name = re.sub(r'[\[\]\{\}\(\)]', '', last_part)
    else:
        # 如果不是 JSONPath，直接使用 path
        name = path
    
    # 确保变量名是有效的
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # 确保不以数字开头
    if name[0].isdigit():
        name = 'var_' + name
    return name

async def fix_extract_variables():
    """修复测试步骤中 extract_variables 缺失 name 字段的问题"""
    async with async_session() as session:
        # 1. 获取所有测试步骤
        result = await session.execute(select(TestStep))
        steps = result.scalars().all()
        
        fixed_count = 0
        error_count = 0
        logger.info(f"Found {len(steps)} steps to process")
        
        for step in steps:
            if not step.extract_variables:
                continue
                
            # 2. 解析 extract_variables
            try:
                variables = json.loads(step.extract_variables)
                if not isinstance(variables, list):
                    logger.warning(f"Step {step.id}: extract_variables is not a list")
                    continue
                    
                # 3. 修复每个变量配置
                fixed_variables = []
                for var in variables:
                    if isinstance(var, dict):
                        # 如果已经有 name 字段，保持不变
                        if 'name' in var and var['name']:
                            fixed_variables.append(var)
                            continue
                            
                        # 如果没有 name 字段，从 path 生成
                        fixed_var = var.copy()
                        path = var.get('path', '')
                        if not path:
                            logger.warning(f"Step {step.id}: Missing path in variable config")
                            continue
                            
                        fixed_var['name'] = generate_valid_name(path)
                        fixed_variables.append(fixed_var)
                        logger.info(f"Step {step.id}: Generated name '{fixed_var['name']}' from path '{path}'")
                    else:
                        logger.warning(f"Step {step.id}: Invalid variable format")
                        continue
                
                # 4. 更新数据库
                if fixed_variables:
                    await session.execute(
                        update(TestStep)
                        .where(TestStep.id == step.id)
                        .values(extract_variables=json.dumps(fixed_variables))
                    )
                    fixed_count += 1
                    logger.info(f"Step {step.id}: Updated {len(fixed_variables)} variables")
                    
            except json.JSONDecodeError:
                logger.error(f"Step {step.id}: Invalid JSON format")
                error_count += 1
                continue
            except Exception as e:
                logger.error(f"Step {step.id}: Error: {str(e)}")
                error_count += 1
                continue
        
        # 5. 提交更改
        await session.commit()
        logger.info("\nSummary:")
        logger.info(f"- Fixed {fixed_count} steps")
        logger.info(f"- Encountered {error_count} errors")

if __name__ == "__main__":
    asyncio.run(fix_extract_variables()) 