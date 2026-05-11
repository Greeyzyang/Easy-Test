import json
import asyncio
import hashlib
import re
from typing import Any, Dict, List
import redis
from app.config import REDIS_URL
from app.services.ai_service import ai_service, JIRA_BUG_TYPES
from app.utils.logger import get_logger
from app.utils.task_utils import publish_task_progress
from app.utils.llm_parsing import extract_json_from_llm_output, normalize_testcase_output

logger = get_logger(__name__)

class TestcaseGenerationService:
    def __init__(self):
        self.redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

    def _build_jira_testcase_cache_key(self, jira_key: str, linked_req_keys: list[str] | None = None) -> str:
        normalized = sorted({key.strip() for key in (linked_req_keys or []) if isinstance(key, str) and key.strip()})
        cache_payload = {
            "jira_key": jira_key,
            "linked_req_keys": normalized,
            "prompt_version": "jira_testcase_v2",
        }
        fingerprint = hashlib.sha256(json.dumps(cache_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        return f"ai:testcases:{jira_key}:{fingerprint}"

    def _normalize_jira_testcase(self, testcase: dict, index: int, jira_key: str) -> dict:
        normalized = dict(testcase) if isinstance(testcase, dict) else {}
        normalized["id"] = f"{jira_key}-{index:03d}"

        if not normalized.get("task"):
            normalized["task"] = jira_key
        if not normalized.get("module"):
            normalized["module"] = "General"
        if not normalized.get("priority"):
            normalized["priority"] = "P1"
        if not normalized.get("type"):
            normalized["type"] = "functional"

        steps = normalized.get("steps", [])
        if isinstance(steps, str):
            steps = [line.strip() for line in re.split(r"\r?\n", steps) if line.strip()]
        elif not isinstance(steps, list):
            steps = []
        normalized["steps"] = [str(step).strip() for step in steps if str(step).strip()]

        if "expected_results" in normalized and "expected_result" not in normalized:
            expected_results = normalized.get("expected_results")
            if isinstance(expected_results, list):
                normalized["expected_result"] = "\n".join(str(item).strip() for item in expected_results if str(item).strip())
            elif expected_results is not None:
                normalized["expected_result"] = str(expected_results).strip()

        if not normalized.get("expected_result"):
            normalized["expected_result"] = "Expected result not provided."

        if normalized.get("preconditions") and not normalized.get("precondition"):
            normalized["precondition"] = normalized.get("preconditions")

        normalized.setdefault("precondition", "")
        normalized["title"] = str(normalized.get("title", "")).strip() or normalized["id"]
        return normalized

    def _recover_testcases_from_raw_output(self, llm_response: str, jira_key: str) -> list[dict]:
        if not isinstance(llm_response, str) or not llm_response.strip():
            return []

        block_match = re.search(
            r"SECTION\s*2\s*:\s*TEST CASES.*?```json\s*(.*?)\s*```",
            llm_response,
            re.DOTALL | re.IGNORECASE,
        )
        candidate = block_match.group(1).strip() if block_match else llm_response.strip()

        repaired = candidate
        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)

        testcases_match = re.search(r'"testcases"\s*:\s*(\[.*\])', repaired, re.DOTALL)
        if testcases_match:
            array_candidate = testcases_match.group(1)
            try:
                parsed_array = json.loads(array_candidate)
                if isinstance(parsed_array, list):
                    return [
                        self._normalize_jira_testcase(tc, i, jira_key)
                        for i, tc in enumerate(parsed_array, 1)
                        if isinstance(tc, dict)
                    ]
            except Exception:
                pass

        list_match = re.search(r'\[(\s*{.*}\s*)\]', repaired, re.DOTALL)
        if list_match:
            list_candidate = f"[{list_match.group(1)}]"
            try:
                parsed_list = json.loads(list_candidate)
                if isinstance(parsed_list, list):
                    return [
                        self._normalize_jira_testcase(tc, i, jira_key)
                        for i, tc in enumerate(parsed_list, 1)
                        if isinstance(tc, dict)
                    ]
            except Exception:
                pass

        object_candidates = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', repaired, re.DOTALL)
        recovered = []
        for raw_obj in object_candidates:
            try:
                parsed = json.loads(re.sub(r',\s*([}\]])', r'\1', raw_obj))
            except Exception:
                continue
            if isinstance(parsed, dict) and (parsed.get("title") or parsed.get("steps") or parsed.get("expected_result") or parsed.get("expected_results")):
                recovered.append(parsed)

        return [
            self._normalize_jira_testcase(tc, i, jira_key)
            for i, tc in enumerate(recovered, 1)
        ]

    async def _update_progress(self, task_id: str, progress: int, text: str, status: str = "PROGRESS", celery_task=None, **kwargs):
        """Updates progress via WS and optionally Celery state."""
        if not task_id:
            return

        # 1. Update Celery State if provided (for compatibility)
        if celery_task and hasattr(celery_task, 'update_state'):
            try:
                update_result = celery_task.update_state(
                    state='PROGRESS',
                    meta={'status': status, 'message': text, 'progress': progress, **kwargs}
                )
                if hasattr(update_result, '__await__'):
                    await update_result
            except Exception as e:
                logger.error(f"Failed to update celery state: {e}")

        # 2. Push WebSocket message
        await publish_task_progress(
            task_id=task_id,
            status=status,
            progress=progress,
            text=text,
            **kwargs
        )
        
        # 3. Cache the final result independently
        if status in ['SUCCESS', 'FAILURE']:
            result_payload = {
                'status': status,
                'error': kwargs.get('error'),
                'result': kwargs.get('result')
            }
            try:
                self.redis_client.setex(
                    f"ai:task:result:{task_id}", 
                    86400, 
                    json.dumps(result_payload, ensure_ascii=False)
                )
            except Exception as e:
                logger.error(f"Failed to save task result to redis: {e}")

    async def generate_from_jira(self, jira_key: str, linked_req_keys: list[str] = None, task_id: str = None, celery_task=None) -> dict:
        """
        [Core Logic] Generate test cases from Jira issue.
        """
        try:
            current_model = ai_service._get_model_name()
        except Exception:
            current_model = "AI"

        try:
            # 1. Cache Check
            try:
                cache_key = self._build_jira_testcase_cache_key(jira_key, linked_req_keys)
                cached = self.redis_client.get(cache_key)
                if cached:
                    try:
                        structured_result: Dict[str, Any] = json.loads(cached if isinstance(cached, str) else str(cached))
                        if isinstance(structured_result, dict) and "testcases" in structured_result:
                            await self._update_progress(task_id, 100, f'命中缓存，直接返回生成结果（{current_model}）', status='SUCCESS', celery_task=celery_task, result=structured_result)
                            return {'status': 'SUCCESS', 'result': structured_result}
                    except Exception:
                        pass
            except Exception:
                pass
            
            await self._update_progress(task_id, 10, f'获取 Jira issue...（{current_model}）', celery_task=celery_task)
            
            # 2. Fetch Jira Issue (with Retry)
            logger.info(f"开始获取核心需求: {jira_key}")
            issue_details = None
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    issue_details = ai_service.get_jira_issue_details(jira_key)
                    if issue_details:
                        await self._update_progress(task_id, 20, f'核心需求获取成功（{current_model}）', celery_task=celery_task)
                        break
                    else:
                        break
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        # 指数退避: 2, 4, 8 秒
                        backoff = 2 ** retry_count
                        await asyncio.sleep(backoff)
                        await self._update_progress(task_id, 15, f'重试获取Jira issue (第{retry_count}次, 等待{backoff}s)...', celery_task=celery_task)
                    else:
                        logger.error(f"核心需求 {jira_key} 获取失败: {e}")

            if not issue_details:
                error_msg = f"无法获取 Jira issue: {jira_key}"
                await self._update_progress(task_id, 100, error_msg, status='FAILURE', celery_task=celery_task, error=error_msg)
                return {'status': 'FAILURE', 'error': error_msg}

            # 3. Fetch / Derive Linked Requirement Keys from Linked Issues
            linked_req_details = []
            if linked_req_keys:
                await self._update_progress(task_id, 30, f'正在获取关联需求...（{len(linked_req_keys)}个）', celery_task=celery_task)
            else:
                # 自动从 linked_issues 中提取非 Bug 的关联需求 key
                linked = issue_details.get('linked_issues') or []
                derived_keys = []
                for li in linked:
                    if not isinstance(li, dict):
                        continue
                    it = (li.get('issuetype') or '').strip()
                    if it in JIRA_BUG_TYPES:
                        continue
                    key = li.get('key')
                    if key:
                        derived_keys.append(key)
                if derived_keys:
                    logger.info(f"自动从 linked_issues 提取关联需求: {derived_keys}")
                    linked_req_keys = derived_keys

            if linked_req_keys:
                for h_key in linked_req_keys:
                    try:
                        h_info = ai_service.get_jira_issue_details(h_key)
                        if h_info:
                            linked_req_details.append(h_info)
                    except Exception as e:
                        logger.warning(f"获取关联需求 {h_key} 失败: {e}")

            # 3.5 RAG Retrieval
            kb_context = None
            rag_status_msg = "未执行"
            kb_query = None
            kb_sources = []
            kb_used = False
            try:
                summary = issue_details.get('summary', '')
                description = issue_details.get('description', '')

                # 构建 RAG 查询：主需求 + 关联需求（已从 linked_issues 提取并完整获取）
                kb_query_parts = []

                # 主需求
                kb_query_parts.append(f"[主需求] {summary}")
                if description:
                    kb_query_parts.append(f"[描述] {description}")

                # 关联需求上下文（linked_req_details 已包含 linked_issues 中非 Bug 类型的完整信息）
                for hist in linked_req_details[:3]:
                    h_summary = hist.get('summary', '')
                    h_desc = hist.get('description', '')
                    h_type = hist.get('issuetype', '')

                    if h_summary:
                        kb_query_parts.append(f"[关联需求 {h_type}] {h_summary}")
                    if h_desc:
                        # 描述较长，按需截断避免 query 过长
                        kb_query_parts.append(f"[关联需求描述] {h_desc[:500]}" if len(h_desc) > 500 else f"[关联需求描述] {h_desc}")

                # 合并并限制总长度（2048 字符，FAISS 检索的合理范围）
                kb_query = "\n".join(filter(None, kb_query_parts))
                if len(kb_query) > 2048:
                    kb_query = kb_query[:2048]


                if kb_query:
                    await self._update_progress(task_id, 40, f'正在调用向量数据库检索产品文档...（{current_model}）', celery_task=celery_task)
                    
                    kb_result = ai_service.query_kb(kb_query, top_k=2)
                    if kb_result and "sources" in kb_result and kb_result["sources"]:
                        sources: List[Dict[str, Any]] = kb_result.get("sources", [])
                        kb_sources = []
                        for source in sources:
                            metadata = source.get("metadata", {}) if isinstance(source, dict) else {}
                            kb_sources.append({
                                "source": metadata.get("source", "Unknown"),
                                "page": metadata.get("page"),
                            })
                        context_texts = [s.get("content", "") for s in sources]
                        kb_context = "\n".join(context_texts)
                        kb_used = True
                        logger.info(f"RAG retrieved context length: {len(kb_context)}")
                        rag_status_msg = f"成功命中 {len(sources)} 条相关知识库文档"
                        source_names = []
                        for item in kb_sources:
                            name = item.get("source") or "Unknown"
                            page = item.get("page")
                            source_names.append(f"{name} (Page {page})" if page is not None else str(name))
                        await self._update_progress(
                            task_id,
                            45,
                            f'✅ {rag_status_msg}',
                            celery_task=celery_task,
                            kb_used=True,
                            kb_query=kb_query,
                            kb_sources=kb_sources,
                            kb_source_count=len(kb_sources),
                            kb_source_labels=source_names,
                        )
                    else:
                        rag_status_msg = "知识库未命中相关业务规则"
                        await self._update_progress(
                            task_id,
                            45,
                            f'⚠️ {rag_status_msg}',
                            celery_task=celery_task,
                            kb_used=False,
                            kb_query=kb_query,
                            kb_sources=[],
                            kb_source_count=0,
                        )
                else:
                    # 无可检索内容，跳过 RAG
                    rag_status_msg = "无检索内容"
                    await self._update_progress(
                        task_id, 45,
                        f'⚠️ {rag_status_msg}',
                        celery_task=celery_task,
                        kb_used=False,
                        kb_query=kb_query,
                        kb_sources=[],
                        kb_source_count=0,
                    )
            except Exception as e:
                rag_status_msg = f"检索失败 ({str(e)})"
                logger.warning(f"RAG Retrieval failed: {e}")
                await self._update_progress(
                    task_id,
                    45,
                    f'❌ 知识库检索异常，降级为纯大模型生成',
                    celery_task=celery_task,
                    kb_used=False,
                    kb_query=kb_query,
                    kb_sources=[],
                    kb_source_count=0,
                )

            # 4. Generate Test Cases
            await self._update_progress(task_id, 50, f'AI 正在生成测试用例...（{current_model}）', celery_task=celery_task)
            
            llm_response = ai_service.generate_testcases_from_jira(
                issue_details=issue_details,
                linked_req_details=linked_req_details,
                jira_key=jira_key,
                kb_context=kb_context
            ) or ""
            
            # 5. Parse Result (提取 + 归一化 + 去重 + 质量评估)
            await self._update_progress(task_id, 80, '正在解析生成结果...', celery_task=celery_task)

            # 使用新的完整处理链：提取 JSON → Doubao 修复 → 归一化 → 去重 → 质检
            structured_result = normalize_testcase_output(llm_response or "", jira_key)
            raw_testcases = structured_result.get("testcases", [])

            # 如果处理链返回空（解析失败），尝试正则回退
            if not raw_testcases:
                recovered_testcases = self._recover_testcases_from_raw_output(llm_response or "", jira_key)
                if recovered_testcases:
                    structured_result = normalize_testcase_output({"testcases": recovered_testcases}, jira_key)
                    structured_result["raw"] = llm_response
                else:
                    error_msg = "AI 响应格式无法解析"
                    await self._update_progress(task_id, 100, error_msg, status='FAILURE', celery_task=celery_task, error=error_msg)
                    return {'status': 'FAILURE', 'error': error_msg}

            testcases = structured_result.get("testcases", [])
            statistics = structured_result.get("statistics", {})
            quality_issues = structured_result.get("quality_issues", [])
            distribution_issues = structured_result.get("distribution_issues", [])

            # 5.1 Preserve optional analysis metadata
            if isinstance(structured_result, dict):
                analysis_lines: List[str] = []
                
                analysis = structured_result.get("analysis")
                if isinstance(analysis, list):
                    analysis_lines.extend(str(item).strip() for item in analysis if str(item).strip())
                elif isinstance(analysis, str) and analysis.strip():
                    analysis_lines.append(analysis.strip())

                if not analysis_lines and isinstance(llm_response, str):
                    analysis_match = re.search(
                        r"SECTION\s*1\s*:\s*ANALYSIS(.*?)(SECTION\s*2\s*:\s*TEST CASES|```json)",
                        llm_response,
                        re.DOTALL | re.IGNORECASE,
                    )
                    if analysis_match:
                        raw_analysis = analysis_match.group(1)
                        for line in raw_analysis.splitlines():
                            cleaned = re.sub(r"^\s*[-*\d.]+\s*", "", line).strip()
                            if cleaned:
                                analysis_lines.append(cleaned)

                if analysis_lines:
                    structured_result["analysis"] = analysis_lines

                structured_result["rag_summary"] = {
                    "status": rag_status_msg,
                    "query": kb_query or "",
                    "sources": kb_sources,
                    "quality": {
                        "issues": quality_issues,
                        "distribution_issues": distribution_issues,
                        "statistics": statistics,
                    }
                }

            # 6. Attach jira_key and quality metadata to structured_result
            try:
                if isinstance(structured_result, dict):
                    structured_result["jira_key"] = jira_key
                    structured_result["kb_used"] = kb_used
                    structured_result["kb_query"] = kb_query or ""
                    structured_result["kb_sources"] = kb_sources
                    # 补全统计和质量信息到顶层（与旧版行为一致）
                    structured_result["statistics"] = statistics
                    if quality_issues:
                        structured_result["quality_issues"] = quality_issues
                    if distribution_issues:
                        structured_result["distribution_issues"] = distribution_issues
            except Exception:
                pass

            # 7. Save to Result Cache
            try:
                self.redis_client.setex(cache_key, 86400, json.dumps(structured_result, ensure_ascii=False)) # 24h
            except Exception as e:
                logger.error(f"Cache save failed: {e}")

            await self._update_progress(task_id, 100, '生成完成', status='SUCCESS', celery_task=celery_task, result=structured_result)
            return {'status': 'SUCCESS', 'result': structured_result}

        except Exception as e:
            logger.error(f"Task failed: {e}")
            await self._update_progress(task_id, 100, f'任务执行失败: {str(e)}', status='FAILURE', celery_task=celery_task, error=str(e))
            return {'status': 'FAILURE', 'error': str(e)}


    def generate_from_jira_sync(self, jira_key: str, linked_req_keys: list[str] = None, task_id: str = None) -> dict:
        """
        同步入口，供 AgentService (非 async 上下文) 调用。
        避免 event loop 混用问题：
        - 若已在 async 上下文中（get_running_loop 存在），直接 await
        - 若无 event loop（Celery 同步 worker），创建新 loop 并 run
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 无运行中的 event loop（同步环境，如 Celery worker）
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    self.generate_from_jira(jira_key=jira_key, linked_req_keys=linked_req_keys, task_id=task_id)
                )
            finally:
                loop.close()

        # 已在 async 上下文中，直接 await
        return asyncio.run(
            self.generate_from_jira(jira_key=jira_key, linked_req_keys=linked_req_keys, task_id=task_id)
        )


testcase_generation_service = TestcaseGenerationService()
