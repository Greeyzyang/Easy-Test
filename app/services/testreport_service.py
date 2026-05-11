from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from app.models import (
    Testreport, 
    Testsuite, 
    Testcase,
    ExecutionDetail, 
    TestStep, Variable,
    TestSuiteTestCase
)
from app.schemas.base_schemas import TestStatus
from datetime import datetime
import time
import copy
from fastapi import HTTPException
from app.utils.http_client import HttpClient, TestContext
from typing import List, Dict, Any, Optional
from app.utils.pdf_generator import generate_test_report_pdf
from app.schemas.testreport import (
    StepResult,
    TestcaseResult,
    TestreportDetail,
    TestreportListRead
)

from app.utils.logger import get_logger
from app.utils.task_utils import publish_task_progress

logger = get_logger(__name__)

class TestreportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.http_client = HttpClient()

    async def generate_report(self, testsuite_id: str, env_name: str, websocket_list: List = None, task_id: str = None) -> Testreport:
        """
        生成测试报告的核心方法
        
        Args:
            testsuite_id: 测试套件ID
            env_name: 环境变量模板
            websocket_list: WebSocket连接列表
            task_id: Celery 任务 ID，用于进度推送
        """
        try:
            # ==================== 第一阶段：环境准备和上下文初始化 ====================
            logger.info(f"开始执行测试套件 {testsuite_id}，环境模板: {env_name}")
            if task_id:
                await publish_task_progress(task_id, "PROGRESS", 5, "正在初始化测试环境...")
            
            # 1. 解析环境变量模板
            final_base_url = await self._resolve_base_url_and_init_context(env_name)
            
            # ==================== 第二阶段：测试执行 ====================
            # 2. 从数据库获取测试套件
            testsuite = await self._get_testsuite(testsuite_id)
            if task_id:
                await publish_task_progress(task_id, "PROGRESS", 10, f"已获取测试套件: {testsuite.name}")
            
            suite_start_time = time.time()
            
            # 3. 执行所有测试用例
            report_details = await self._execute_test_cases(
                testcases=testsuite.testcases, 
                websocket_list=websocket_list, 
                task_id=task_id,
                suite_headers=testsuite.headers
            )
            
            # ==================== 第三阶段：报告生成 ====================
            # 4. 创建测试报告记录
            db_testreport = await self._create_testreport(
                testsuite_id, 
                report_details, 
                suite_start_time
            )
            
            # 5. 创建详细的执行记录
            await self._create_execution_details(db_testreport.id, report_details)
            
            logger.info(f"测试套件 {testsuite_id} 执行完成，生成报告: {db_testreport.id}")
            return db_testreport
            
        except Exception as e:
            logger.error(f"测试执行过程中发生错误: {str(e)}")
            raise
        finally:
            # ==================== 第四阶段：资源清理 ====================
            # 6. 确保在测试套件执行完成后关闭 HTTP 客户端连接
            await self.http_client.close_client()
            # 7. 清理测试上下文，避免影响后续测试
            await self._cleanup_test_context()
            logger.info("测试资源清理完成")

    async def _resolve_base_url_and_init_context(self, env_name_template: str) -> str:
        """
        解析 URL 模板并初始化测试上下文
        
        这个方法的作用：
        1. 从数据库获取所有全局变量
        2. 使用这些变量解析 env_name 模板，得到 base_url
        3. 初始化 HttpClient 的上下文，注入所有变量和 base_url
        4. 设置数据库会话
        
        示例：
        - 输入：env_name_template = "${protocol}://${host}:${port}"
        - 假设数据库中有：protocol=http, host=127.0.0.1, port=8000
        - 输出：final_base_url = "http://127.0.0.1:8000"
        - 同时初始化 HttpClient 上下文，包含所有变量和 base_url
        
        Args:
            env_name_template: URL模板字符串，支持 ${...} 语法
            
        Returns:
            str: 解析后的完整 base_url
            
        Raises:
            HTTPException: 当模板解析失败或包含未解析的变量时
        """
        # 1. 从数据库获取所有全局变量（只查询一次）
        all_variables = await self._get_all_variables()
        logger.info(f"从数据库获取到 {len(all_variables)} 个全局变量")
        
        # 补充：尝试从系统环境变量获取缺失的变量
        import os
        import re
        env_vars = re.findall(r'\${(.*?)}', env_name_template)
        for var in env_vars:
            if var not in all_variables:
                sys_val = os.getenv(var)
                if sys_val:
                    all_variables[var] = sys_val
                    logger.info(f"从系统环境变量获取: {var}={sys_val}")

        logger.debug(f"准备解析模板 '{env_name_template}'，可用变量: {list(all_variables.keys())}")
        
        # 2. 获取 HttpClient 的共享上下文实例
        context = HttpClient._context
        
        # 3. 清理上下文，避免之前的测试数据污染
        await context.clear()
        
        # 4. 设置所有全局变量到上下文中
        context.variables = all_variables
        
        # 5. 使用上下文解析模板，得到 base_url
        final_base_url = await context.process_template_string(env_name_template)
        
        # 6. 验证解析结果
        if not final_base_url or '${' in final_base_url:
            raise HTTPException(
                status_code=400, 
                detail=f"环境变量模板 '{env_name_template}' 解析失败或包含未解析的变量，"
                       f"解析结果: '{final_base_url}'"
            )
        
        # 7. 将解析后的 base_url 添加到上下文中
        context.variables["base_url"] = final_base_url
        
        # 8. 设置数据库会话，供后续函数调用使用
        context.set_db(self.db)
        
        logger.info(f"模板解析成功: '{env_name_template}' -> '{final_base_url}'")
        logger.debug(f"测试上下文初始化完成，base_url: {final_base_url}")
        logger.debug(f"可用变量: {list(context.variables.keys())}")
        
        return final_base_url

    async def _cleanup_test_context(self):
        """
        清理测试上下文
        
        这个方法的作用：
        1. 清除所有测试过程中产生的变量
        2. 清除响应数据和 cookies
        3. 为下一次测试做准备
        """
        from app.utils.http_client import HttpClient
        await HttpClient._context.clear()
        logger.info("测试上下文已清理")

    async def _get_testsuite(self, testsuite_id: str) -> Testsuite:
        result = await self.db.execute(
            select(Testsuite)
            .options(
                selectinload(Testsuite.testcase_associations)
                .selectinload(TestSuiteTestCase.testcase)
                .selectinload(Testcase.steps)
                .selectinload(TestStep.interface)
            )
            .where(Testsuite.id == testsuite_id)
        )
        testsuite = result.scalar_one_or_none()
        if not testsuite:
            raise HTTPException(status_code=404, detail="测试套件未找到")
        return testsuite

    async def _execute_test_cases(self, testcases: List[Testcase], websocket_list: List = None, task_id: str = None, suite_headers: Dict = None):
        """
        执行所有测试用例，返回测试结果列表（支持并行执行）
        
        执行流程：
        1. 预处理：统计所有测试步骤，建立测试用例映射
        2. 并行控制：使用 Semaphore 限制最大并发数为 5，防止压垮服务器
        3. 并发执行：使用 asyncio.gather 并发执行所有测试用例
        4. 进度推送：通过回调函数实时推送执行进度
        
        Args:
            testcases: 测试用例列表
            websocket_list: WebSocket连接列表，用于实时推送进度
            task_id: Celery 任务 ID，用于进度推送
            suite_headers: 测试套件公共请求头
            
        Returns:
            List[TestcaseResult]: 测试用例执行结果列表
        """
        import asyncio

        # ==================== 预处理阶段 ====================
        testcase_results = []
        all_steps = []
        testcase_map = {}
        
        # 1. 遍历所有测试用例，获取完整的测试步骤信息
        for testcase in testcases:
            # 从数据库获取测试用例的完整信息（包括关联的测试步骤和接口）
            tc = await self._get_testcase(testcase.id)
            testcase_map[testcase.id] = tc
            # 收集所有测试步骤，用于计算总进度
            all_steps.extend(list(tc.steps))
        
        total_steps = len(all_steps)
        # 使用 shared_state 字典在闭包中共享状态，因为 int 是不可变的
        shared_state = {"current_progress": 0}
        
        logger.info(f"开始执行 {len(testcases)} 个测试用例，共 {total_steps} 个测试步骤")

        # 2. 检查是否有可执行的测试步骤
        if total_steps == 0:
            logger.warning("没有找到可执行的测试步骤")
            if websocket_list:
                # 推送开始和完成消息
                msg0 = {"progress": 0, "text": "无可执行步骤", "status": TestStatus.SKIPPED}
                msg100 = {"progress": 100, "text": "无可执行步骤，直接完成", "status": TestStatus.COMPLETED}
                for ws in websocket_list:
                    try:
                        await ws.send_json(msg0)
                        await ws.send_json(msg100)
                    except:
                        pass
            return []

        # 3. 获取已初始化的 HttpClient 上下文
        # 这个上下文包含了所有环境变量，用于模板处理
        from app.utils.http_client import HttpClient
        context = HttpClient._context
        logger.debug(f"使用已初始化的测试上下文，可用变量: {list(context.variables.keys())}")

        # ==================== 并行执行配置 ====================
        # 设置最大并发数为 5，避免过多并发导致资源耗尽或触发限流
        concurrency_limit = 5
        semaphore = asyncio.Semaphore(concurrency_limit)

        async def execute_single_testcase(testcase_id):
            async with semaphore:
                tc = testcase_map[testcase_id]
                step_results = []
                
                logger.info(f"开始执行测试用例: {tc.name}")
                
                # 4. 遍历测试用例中的每个测试步骤
                for step in list(tc.steps):
                    if not step.interface:
                        logger.warning(f"跳过步骤 {step.name}：未关联接口")
                        continue
                        
                    logger.info(f"执行测试步骤: {step.name}")
                    
                    # ==================== 模板处理阶段 ====================
                    # 5. 使用已初始化的上下文处理请求参数中的模板字符串
                    # 这一步会将 ${...} 占位符替换为实际的变量值
                    
                    # 处理请求头中的变量
                    # 5.1 处理公共请求头
                    processed_suite_headers = await context.process_template_dict(suite_headers) if suite_headers else {}
                    
                    # 5.2 处理步骤请求头
                    processed_step_headers = await context.process_template_dict(step.headers) if step.headers else {}
                    
                    # 5.3 合并请求头（公共请求头 < 步骤请求头）
                    processed_headers = processed_suite_headers.copy()
                    processed_headers.update(processed_step_headers)
                    
                    # 处理查询参数中的变量
                    processed_params = await context.process_template_dict(step.params) if step.params else {}
                    
                    # 处理请求体中的变量
                    processed_body = await context.process_template_dict(step.body) if step.body else {}
                    
                    # 处理文件配置中的变量
                    processed_file_config = await context.process_template_dict(step.file_config) if step.file_config else {}
                    
                    logger.debug(f"模板处理完成 - Headers: {len(processed_headers)}, Params: {len(processed_params)}, Body: {len(processed_body)}")
                    
                    # ==================== 请求执行阶段 ====================
                    # 6. 创建处理后的步骤副本，避免修改原始数据
                    processed_step = copy.deepcopy(step)
                    processed_step.headers = processed_headers
                    processed_step.params = processed_params
                    processed_step.body = processed_body
                    processed_step.file_config = processed_file_config
                    
                    # 7. 调用 HttpClient 执行实际的 HTTP 请求
                    # 这一步会：
                    # - 构建完整的请求 URL（base_url + 接口路径）
                    # - 发送 HTTP 请求
                    # - 处理响应和断言
                    # - 提取变量（如果有配置）
                    result = await self.http_client.execute(processed_step, self.db)
                    
                    # 8. 解析执行状态
                    status = TestStatus(result["status"].upper())
                    
                    # ==================== 结果收集阶段 ====================
                    # 9. 创建步骤执行结果
                    response_data = result["response"]
                    if not isinstance(response_data, dict):
                        response_data = {"text": response_data}
                    step_result = StepResult(
                        id=step.id,
                        step_id=step.id,
                        step_name=step.name,
                        status=status,
                        start_time=datetime.utcnow(),
                        end_time=datetime.utcnow(),
                        duration=result["duration"],
                        request_data={
                            "headers": processed_headers,
                            "params": processed_params,
                            "body": processed_body,
                            "request_type": step.request_type.value if hasattr(step.request_type, 'value') else str(step.request_type),
                            "file_config": processed_file_config
                        },
                        response_data=response_data,
                        error_message=result["error_message"]
                    )
                    step_results.append(step_result)
                    
                    # 10. 更新进度计数器 (线程安全操作)
                    shared_state["current_progress"] += 1
                    current = shared_state["current_progress"]
                    
                    # ==================== 进度推送阶段 ====================
                    # 11. 通过 WebSocket 实时推送执行进度
                    progress = int(current / total_steps * 100) if total_steps > 0 else 100
                    progress_text = f"正在执行: {tc.name} - {step.name}"
                    
                    if websocket_list:
                        msg = {
                            "progress": progress, 
                            "text": progress_text, 
                            "status": status
                        }
                        for ws in websocket_list:
                            try:
                                await ws.send_json(msg)
                            except:
                                pass
                    
                    if task_id:
                        await publish_task_progress(
                            task_id=task_id,
                            status="PROGRESS",
                            progress=progress,
                            text=progress_text,
                            step_status=status
                        )
                    
                    logger.info(f"步骤 {step.name} 执行完成，状态: {status}")
                
                # ==================== 用例结果汇总阶段 ====================
                # 12. 汇总测试用例的整体执行结果
                if step_results:
                    # 判断用例整体状态：只有当所有步骤都通过时，用例才算通过
                    case_status = TestStatus.PASSED if all(s.status == TestStatus.PASSED for s in step_results) else TestStatus.FAILED
                    # 计算用例总耗时
                    case_duration = sum(s.duration for s in step_results)
                    
                    # 创建用例执行结果
                    testcase_result = TestcaseResult(
                        id=tc.id,
                        name=tc.name,
                        description=tc.description,
                        status=case_status,
                        duration=case_duration,
                        steps=step_results
                    )
                    
                    logger.info(f"测试用例 {tc.name} 执行完成，状态: {case_status}，耗时: {case_duration:.2f}s")
                    return testcase_result
                return None

        # ==================== 并发任务启动 ====================
        logger.info(f"启动并发执行，最大并发数: {concurrency_limit}")
        tasks = [execute_single_testcase(testcase.id) for testcase in testcases]
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks)
        
        # 过滤掉 None 结果 (没有步骤的用例)
        testcase_results = [r for r in results if r is not None]

        # ==================== 执行完成阶段 ====================
        # 13. 确保推送100%完成消息
        current = shared_state["current_progress"]
        if websocket_list and current == total_steps:
            msg = {"progress": 100, "text": "测试执行完成", "status": TestStatus.COMPLETED}
            for ws in websocket_list:
                try:
                    await ws.send_json(msg)
                except:
                    pass
        
        logger.info(f"所有测试用例执行完成，共执行 {len(testcase_results)} 个用例")
        return testcase_results

    async def _get_testcase(self, testcase_id: str):
        result = await self.db.execute(
            select(Testcase)
            .options(selectinload(Testcase.steps).selectinload(TestStep.interface))
            .where(Testcase.id == testcase_id)
        )
        return result.scalar_one_or_none()

    async def _create_testreport(self, testsuite_id: str, testcase_results: List[TestcaseResult], start_time: float):
        """创建测试报告"""
        # 统计用例状态
        total_cases = len(testcase_results)
        passed_cases = sum(1 for tc in testcase_results if tc.status == TestStatus.PASSED)
        failed_cases = sum(1 for tc in testcase_results if tc.status == TestStatus.FAILED)
        skipped_cases = sum(1 for tc in testcase_results if tc.status == TestStatus.SKIPPED)
        pass_rate = (passed_cases / total_cases * 100) if total_cases > 0 else 0

        # 确定报告状态
        if total_cases == 0:
            status = TestStatus.PENDING
        elif failed_cases > 0:
            status = TestStatus.FAILED
        else:
            status = TestStatus.COMPLETED

        # 获取测试套件名称
        suite_name = ""
        suite = await self._get_testsuite(testsuite_id)
        if suite:
            suite_name = suite.name or "测试套件"

        # 生成报告名称
        today_str = datetime.now().strftime("%Y-%m-%d-%H-%M")
        report_name = f"{suite_name}_{today_str}"

        # 创建报告记录
        db_testreport = Testreport(
            testsuite_id=testsuite_id,
            name=report_name,
            status=status,
            duration=time.time() - start_time,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            pass_rate=pass_rate,
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            skipped_cases=skipped_cases
        )
        self.db.add(db_testreport)
        await self.db.commit()
        await self.db.refresh(db_testreport)
        return db_testreport

    async def _create_execution_details(self, testreport_id: str, testcase_results: List[TestcaseResult]):
        """创建执行详情记录"""
        for testcase in testcase_results:
            for step in testcase.steps:
                execution_detail = ExecutionDetail(
                    testreport_id=testreport_id,
                    testcase_id=testcase.id,
                    step_id=step.step_id,
                    step_name=step.step_name,
                    status=step.status,
                    start_time=step.start_time,
                    end_time=step.end_time,
                    duration=step.duration,
                    request_data=step.request_data,
                    response_data=step.response_data,
                    error_message=step.error_message,
                    order=step.order
                )
                self.db.add(execution_detail)
        await self.db.commit()

    async def get_report(self, report_id: str):
        """获取测试报告详情"""
        # 查询报告本身
        query = (
            select(Testreport)
            .options(selectinload(Testreport.testsuite))
            .where(Testreport.id == report_id)
        )
        result = await self.db.execute(query)
        report = result.scalar_one_or_none()
        if not report:
            raise ValueError(f"测试报告 {report_id} 不存在")

        # 查询该报告下所有用例执行详情
        detail_result = await self.db.execute(
            select(ExecutionDetail).where(ExecutionDetail.testreport_id == report.id)
        )
        execution_details = detail_result.scalars().all()

        # 按用例ID分组
        testcase_groups = {}
        for detail in execution_details:
            if detail.testcase_id not in testcase_groups:
                testcase_groups[detail.testcase_id] = []
            testcase_groups[detail.testcase_id].append(detail)

        # 构建用例结果列表（用 schema）
        case_results = []
        for testcase_id, details in testcase_groups.items():
            testcase = await self._get_testcase(testcase_id)
            if not testcase:
                continue

            # 步骤结果（用 schema）
            steps = [StepResult.from_orm(d) for d in sorted(details, key=lambda x: x.start_time, reverse=True)]

            # 用例整体状态和总耗时
            case_status = (
                "PASSED" if all(s.status == "PASSED" for s in steps) else "FAILED"
            )
            total_duration = sum(s.duration or 0 for s in steps)

            # 用 TestcaseResult schema
            case_results.append(
                TestcaseResult(
                    id=testcase.id,
                    name=testcase.name,
                    description=testcase.description,
                    status=case_status,
                    duration=total_duration,
                    steps=steps
                )
            )

        # 用 TestreportDetail schema 返回
        return TestreportDetail(
            id=report.id,
            name=report.name,
            description=getattr(report, "description", None),
            testsuite_id=report.testsuite_id,
            testsuite_name=report.testsuite.name if report.testsuite else "",
            status=report.status,
            start_time=report.start_time,
            end_time=report.end_time,
            duration=report.duration,
            total_cases=report.total_cases,
            passed_cases=report.passed_cases,
            failed_cases=report.failed_cases,
            skipped_cases=report.skipped_cases,
            pass_rate=report.pass_rate,
            case_results=case_results
        )

    async def list_reports(self, skip: int = 0, limit: int = 10, status: TestStatus | None = None, project_id: str | None = None):
        """获取测试报告列表"""
        query = select(Testreport).options(
            selectinload(Testreport.testsuite)
        )
        
        # 计数查询
        count_query = select(func.count()).select_from(Testreport)

        if status:
            query = query.where(Testreport.status == status)
            count_query = count_query.where(Testreport.status == status)

        if project_id:
            # 需要通过 testsuite 关联 project
            join_stmt = query.join(Testsuite)
            query = join_stmt.where(Testsuite.project_id == project_id)
            count_query = count_query.join(Testsuite).where(Testsuite.project_id == project_id)
            
        # 按创建时间倒序排列，最近的在前面
        query = query.order_by(Testreport.created_time.desc())

        # 执行计数查询
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # 执行分页查询
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        testreports = result.scalars().all()
        
        # 转换为 Pydantic 模型
        reports_data = []
        for report in testreports:
            reports_data.append(
                TestreportListRead(
                    id=report.id,
                    name=report.name, 
                    testsuite_id=report.testsuite_id,
                    testsuite_name=report.testsuite.name if report.testsuite else "",
                    status=report.status,
                    start_time=report.start_time,
                    end_time=report.end_time,
                    duration=report.duration,
                    pass_rate=report.pass_rate,
                    total_cases=report.total_cases,
                    passed_cases=report.passed_cases,
                    failed_cases=report.failed_cases,
                    skipped_cases=report.skipped_cases,
                )
            )
        return reports_data, total

    async def delete_all_reports(self):
        """删除所有测试报告"""
        query = select(Testreport)
        result = await self.db.execute(query)
        reports = result.scalars().all()
        
        for report in reports:
            await self.db.delete(report)
            
        await self.db.commit()

    async def delete_report(self, report_id: str):
        """删除测试报告"""
        query = select(Testreport).where(Testreport.id == report_id)
        result = await self.db.execute(query)
        report = result.scalar_one_or_none()
        
        if not report:
            raise ValueError(f"测试报告 {report_id} 不存在")
            
        await self.db.delete(report)
        await self.db.commit()

    async def generate_pdf_report(self, report_id: str) -> bytes:
        """生成测试报告PDF"""
        report_data = await self.get_report(report_id)
        pdf_content = generate_test_report_pdf(report_data)
        return pdf_content

    async def _get_testreport(self, report_id: str):
        """获取测试报告详情"""
        # 查询报告本身
        query = (
            select(Testreport)
            .options(selectinload(Testreport.testsuite))
            .options(selectinload(Testreport.execution_details))
            .where(Testreport.id == report_id)
        )
        result = await self.db.execute(query)
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(status_code=404, detail="测试报告未找到")

        # 按用例ID分组执行详情
        testcase_groups = {}
        for detail in report.execution_details:
            if detail.testcase_id not in testcase_groups:
                testcase_groups[detail.testcase_id] = []
            testcase_groups[detail.testcase_id].append(detail)

        # 构建用例结果列表
        case_results = []
        for testcase_id, details in testcase_groups.items():
            # 获取用例信息
            testcase = await self._get_testcase(testcase_id)
            if not testcase:
                continue

            # 构建步骤结果列表
            step_results = []
            for detail in sorted(details, key=lambda x: x.order):
                step_result = StepResult(
                    id=detail.id,
                    step_id=detail.step_id,
                    step_name=detail.step_name,
                    status=detail.status,
                    start_time=detail.start_time,
                    end_time=detail.end_time,
                    duration=detail.duration,
                    request_data=detail.request_data,
                    response_data=detail.response_data,
                    error_message=detail.error_message,
                    order=detail.order
                )
                step_results.append(step_result)

            # 计算用例整体状态和总耗时
            case_status = TestStatus.PASSED if all(s.status == TestStatus.PASSED for s in step_results) else TestStatus.FAILED
            case_duration = sum(s.duration for s in step_results)

            # 构建用例结果
            testcase_result = TestcaseResult(
                id=testcase.id,
                name=testcase.name,
                description=testcase.description,
                status=case_status,
                duration=case_duration,
                steps=step_results
            )
            case_results.append(testcase_result)

        # 使用 TestreportDetail schema 构建报告数据
        report_data = TestreportDetail(
            id=report.id,
            name=report.name,
            description=report.description,
            testsuite_id=report.testsuite_id,
            testsuite_name=report.testsuite.name if report.testsuite else "",
            status=report.status,
            start_time=report.start_time,
            end_time=report.end_time,
            duration=report.duration,
            total_cases=report.total_cases,
            passed_cases=report.passed_cases,
            failed_cases=report.failed_cases,
            skipped_cases=report.skipped_cases,
            pass_rate=report.pass_rate,
            case_results=case_results
        )

        return report_data

    async def _get_all_variables(self) -> dict:
        result = await self.db.execute(select(Variable))
        variables = result.scalars().all()
        return {var.key: var.value for var in variables}



