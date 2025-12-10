import json
import re
from app.celery_app import celery_app
from app.services.ai_service import ai_service
# 新增：Redis 发布用于 WebSocket 推送
from app.config import REDIS_URL
try:
    import redis
except Exception:
    redis = None


def extract_json_from_llm_output(llm_output: str) -> dict:
    """
    从大模型输出中提取JSON数据（增强版）
    - 支持顶层为数组的输出，自动包装为 {"testcases": [...]}。
    - 更健壮地处理 markdown 代码块（```json）与混杂文本。
    - 对单引号、尾随逗号等常见问题进行宽松修复。
    """
    if not llm_output:
        return {"error": "Empty LLM output", "raw_output": str(llm_output)}

    if isinstance(llm_output, dict):
        if not llm_output:
            return {"error": "Empty JSON object", "raw_output": str(llm_output)}
        return llm_output

    if not isinstance(llm_output, str):
        return {"error": f"Invalid LLM output type: {type(llm_output)}", "raw_output": str(llm_output)}

    # 清理控制字符
    cleaned_output = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', llm_output)

    # 尝试直接解析
    try:
        data = json.loads(cleaned_output)
        if isinstance(data, dict):
            if not data:
                return {"error": "Empty JSON object", "raw_output": str(llm_output)}
            return data
        if isinstance(data, list):
            return {"testcases": data}
    except json.JSONDecodeError:
        pass

    # 从代码块或文本中提取 JSON（对象或数组）
    patterns = [
        r"```(?:json)?\s*([\s\S]*?)```",  # markdown 代码块
        r'({[\s\S]*})',                    # JSON 对象
        r'(\[[\s\S]*\])'                 # JSON 数组
    ]

    for pattern in patterns:
        matches = re.findall(pattern, cleaned_output)
        for match in matches:
            match_str = match.strip()
            try:
                if match_str.startswith('{') and match_str.endswith('}'):
                    data = json.loads(match_str)
                    if isinstance(data, dict):
                        return data
                if match_str.startswith('[') and match_str.endswith(']'):
                    data = json.loads(match_str)
                    if isinstance(data, list):
                        return {"testcases": data}
            except json.JSONDecodeError:
                # 宽松修复：替换单引号、移除尾随逗号
                try:
                    fixed = match_str.replace("'", '"')
                    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
                    data = json.loads(fixed)
                    if isinstance(data, dict):
                        return data
                    if isinstance(data, list):
                        return {"testcases": data}
                except Exception:
                    continue

    # 退路：截取第一个 { 到最后一个 } 或第一个 [ 到最后一个 ]
    # 对象
    obj_start = cleaned_output.find('{')
    obj_end = cleaned_output.rfind('}')
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        json_str = cleaned_output[obj_start:obj_end + 1]
        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # 数组
    arr_start = cleaned_output.find('[')
    arr_end = cleaned_output.rfind(']')
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        json_str = cleaned_output[arr_start:arr_end + 1]
        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                return {"testcases": data}
        except json.JSONDecodeError:
            pass

    return {"error": "Could not extract valid JSON", "raw_output": cleaned_output[:500]}


def _publish_ws(task_id: str, payload: dict):
    """通过 Redis Pub/Sub 推送进度到 WebSocket 订阅者"""
    try:
        if redis is None:
            return
        r = redis.Redis.from_url(REDIS_URL)
        channel = f"ai:progress:{task_id}"
        r.publish(channel, json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        # 推送失败不影响主流程
        print(f"[WS Publish Error] {e}")

@celery_app.task(bind=True)
def generate_testcases_task(self, jira_key: str, history_keys: list[str] | None = None):
    """
    Asynchronous Celery task to generate test cases from Jira issues
    默认生成英文测试用例
    优化：使用更高的温度和更简洁的prompt提升生成质量
    """
    try:
        # 缓存命中检查：若最近24小时已有生成结果，直接返回
        if redis is not None:
            try:
                r = redis.Redis.from_url(REDIS_URL)
                cache_key = f"ai:testcases:{jira_key}"
                cached = r.get(cache_key)
                if cached:
                    try:
                        structured_result = json.loads(cached)
                        _publish_ws(self.request.id, {'status': 'SUCCESS', 'result': structured_result, 'progress': 100, 'text': '命中缓存，直接返回生成结果'})
                        return {'status': 'SUCCESS', 'result': structured_result}
                    except Exception:
                        pass
            except Exception:
                pass
        self.update_state(state='PROGRESS', meta={'status': '获取 Jira issue...', 'progress': 10})
        
        # 1. Fetch core requirement information with retry mechanism (优化：增强附件处理和多模态分析)
        print(f"开始获取核心需求: {jira_key} (已优化：支持多模态分析)")
        issue_details = None
        max_retries = 3
        retry_count = 0
        
        # 在获取Jira信息时添加状态更新
        self.update_state(state='PROGRESS', meta={'status': '正在获取Jira需求信息...', 'progress': 10})
        _publish_ws(self.request.id, {"status": "PROGRESS", "text": "正在获取Jira需求信息...", "progress": 10})
        
        # 重试机制：最多重试3次
        while retry_count < max_retries:
            try:
                issue_details = ai_service.get_jira_issue_details(jira_key)
                if issue_details:
                    print(f"✓ 成功获取核心需求: {jira_key}")
                    self.update_state(state='PROGRESS', meta={'status': '核心需求获取成功', 'progress': 20})
                    _publish_ws(self.request.id, {"status": "PROGRESS", "text": "核心需求获取成功", "progress": 20})
                    break
                else:
                    # 获取失败，但API调用成功（返回None）
                    print(f"⚠ 核心需求 {jira_key} 不存在或无访问权限")
                    break
            except Exception as e:
                retry_count += 1
                print(f"✗ 获取核心需求 {jira_key} 第 {retry_count} 次尝试失败: {e}")
                
                if retry_count < max_retries:
                    import time
                    time.sleep(2)  # 等待2秒后重试
                    print(f"  等待2秒后重试...")
                    self.update_state(state='PROGRESS', meta={'status': f'重试获取Jira issue (第{retry_count}次)...', 'progress': 15}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": f"重试获取Jira issue (第{retry_count}次)...", "progress": 15})
                else:
                    print(f"✗ 核心需求 {jira_key} 获取失败，已重试{max_retries}次")
        
        if not issue_details:
            raise ValueError(f"无法获取Jira issue详情: {jira_key} (已重试{max_retries}次)")

        # 记录需求信息统计（已优化：支持多模态分析，包括图片和文本附件）
        core_attachments_count = issue_details.get('attachment_count', 0)
        print(f"核心需求附件数: {core_attachments_count}（已优化：支持多模态分析）")
        self.update_state(state='PROGRESS', meta={'status': f'核心需求附件数: {core_attachments_count}', 'progress': 25}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": f"核心需求附件数: {core_attachments_count}", "progress": 25})
        

        # 2. Fetch history requirement information with enhanced logging and retry (优化：支持多模态分析)
        history_details = []
        total_history_attachments = 0
        
        if history_keys:
            # 在处理历史需求时添加状态更新
            self.update_state(state='PROGRESS', meta={'status': f'获取 {len(history_keys)} 个历史需求信息 (已优化：支持多模态分析)...', 'progress': 30}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": f"获取 {len(history_keys)} 个历史需求信息 (已优化：支持多模态分析)...", "progress": 30})
            
            for idx, key in enumerate(history_keys, 1):
                print(f"开始获取历史需求 {idx}/{len(history_keys)}: {key}")
                progress = 30 + int(idx / len(history_keys) * 15)
                self.update_state(state='PROGRESS', meta={'status': f'正在获取历史需求 {idx}/{len(history_keys)}: {key}', 'progress': progress}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": f"正在获取历史需求 {idx}/{len(history_keys)}: {key}", "progress": progress})
                retry_count = 0
                hist_detail = None
                
                # 重试机制：最多重试3次
                while retry_count < max_retries:
                    try:
                        hist_detail = ai_service.get_jira_issue_details(key)
                        if hist_detail:
                            # 成功获取历史需求
                            history_details.append(hist_detail)
                            hist_attachments = hist_detail.get('attachment_count', 0)
                            total_history_attachments += hist_attachments
                            print(f"✓ 成功获取历史需求 {idx}/{len(history_keys)}: {key} (附件数: {hist_attachments}，支持多模态分析)")
                            progress = 30 + int(idx / len(history_keys) * 15)
                            self.update_state(state='PROGRESS', meta={'status': f'成功获取历史需求 {idx}/{len(history_keys)}: {key}', 'progress': progress}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": f"成功获取历史需求 {idx}/{len(history_keys)}: {key}", "progress": progress})
                            break
                        else:
                            # 获取失败，但API调用成功（返回None）
                            print(f"⚠ 历史需求 {key} 不存在或无访问权限")
                            break
                    except Exception as e:
                        retry_count += 1
                        print(f"✗ 获取历史需求 {key} 第 {retry_count} 次尝试失败: {e}")
                        
                        if retry_count < max_retries:
                            import time
                            time.sleep(1)  # 等待1秒后重试
                            print(f"  等待1秒后重试...")
                        else:
                            print(f"✗ 历史需求 {key} 获取失败，已重试{max_retries}次，跳过该需求")
                            # 继续处理其他历史需求，不中断整个流程
                
                # 如果所有重试都失败，记录失败信息
                if hist_detail is None and retry_count >= max_retries:
                    print(f"⚠ 历史需求 {key} 最终获取失败，将跳过该需求")
        
        print(f"历史需求处理完成 (优化：支持多模态分析):")
        print(f"  - 成功获取: {len(history_details)} 个")
        print(f"  - 失败跳过: {len(history_keys) - len(history_details) if history_keys else 0} 个")
        print(f"  - 附件总数: {total_history_attachments}（支持多模态分析）")
        print(f"  - 总附件数: {core_attachments_count + total_history_attachments}（支持多模态分析）")
        print(f"  - 历史需求将被传递给LLM用于参考（已恢复功能）")
        self.update_state(state='PROGRESS', meta={'status': f'历史需求处理完成，成功 {len(history_details)}，失败 {len(history_keys) - len(history_details) if history_keys else 0}', 'progress': 50})
        
        # 在调用大模型之前添加状态更新
        self.update_state(state='PROGRESS', meta={'status': '准备调用大模型生成测试用例...', 'progress': 50}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": "准备调用大模型生成测试用例...", "progress": 50})
        # 新增：提示词与上下文构建阶段
        self.update_state(state='PROGRESS', meta={'status': '正在构建提示词与上下文...', 'progress': 60}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": "正在构建提示词与上下文...", "progress": 60})
        
        # 3. Call large model to generate test cases (激进优化：大幅简化生成策略)
        max_llm_retries = 0
        llm_retry_count = 0
        llm_output = None
        
        while llm_retry_count <= max_llm_retries:
            try:
                print(f"LLM调用尝试 {llm_retry_count + 1}/{max_llm_retries + 1}")
                self.update_state(state='PROGRESS', meta={'status': f'调用LLM生成测试用例 (第{llm_retry_count + 1}次尝试)...', 'progress': 70}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": f"调用LLM生成测试用例 (第{llm_retry_count + 1}次尝试)...", "progress": 70})
                
                llm_output = ai_service.generate_testcases_from_jira(issue_details, history_details, jira_key)
                
                # 检查输出是否有效
                if llm_output and isinstance(llm_output, str) and len(llm_output.strip()) > 0:
                    print(f"✓ LLM调用成功 (第{llm_retry_count + 1}次尝试)")
                    # 新增：LLM输出获取成功，进入解析阶段
                    self.update_state(state='PROGRESS', meta={'status': 'LLM 输出获取成功，正在进行数据抽取...', 'progress': 85}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": "LLM 输出获取成功，正在进行数据抽取...", "progress": 85})
                    break
                else:
                    raise ValueError("LLM返回空响应")
                    
            except Exception as e:
                llm_retry_count += 1
                error_msg = str(e)
                print(f"✗ LLM调用失败 (第{llm_retry_count}次): {error_msg}")
                
                # 如果还有重试机会且是超时错误
                if llm_retry_count <= max_llm_retries and ("timeout" in error_msg.lower() or "timed out" in error_msg.lower()):
                    wait_time = min(20, 5 * llm_retry_count)  # 5秒、10秒、15秒
                    print(f"检测到超时错误，等待{wait_time}秒后重试...")
                    self.update_state(state='PROGRESS', meta={'status': f'LLM超时，等待{wait_time}秒后第{llm_retry_count + 1}次重试...', 'progress': 75}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": f"LLM超时，等待{wait_time}秒后第{llm_retry_count + 1}次重试...", "progress": 75})
                    import time
                    time.sleep(wait_time)
                else:
                    # 达到最大重试次数或非超时错误
                    if llm_retry_count > max_llm_retries:
                        print(f"LLM超时重试已达到最大次数({max_llm_retries + 1})，任务失败")
                        return {
                            'status': 'FAILURE', 
                            'result': f"LLM API连续超时{max_llm_retries + 1}次，可能的原因：1) 网络连接不稳定 2) LLM服务高负载 3) 需求过于复杂。建议：稍后重试或简化需求描述。", 
                            'details': {
                                'error': f"LLM API连续超时{max_llm_retries + 1}次",
                                'core_attachments': core_attachments_count,
                                'history_attachments': total_history_attachments,
                                'error_type': 'llm_persistent_timeout',
                                'retry_count': llm_retry_count
                            }
                        }
                    else:
                        # 非超时错误，直接抛出
                        print(f"LLM调用遇到非超时错误: {error_msg}")
                        return {
                            'status': 'FAILURE', 
                            'result': f"LLM调用失败: {error_msg}", 
                            'details': {
                                'error': error_msg,
                                'core_attachments': core_attachments_count,
                                'history_attachments': total_history_attachments,
                                'error_type': 'llm_api_failure'
                            }
                        }

        if not llm_output:
            return {
                'status': 'FAILURE', 
                'result': "LLM未能生成任何内容，请检查API连接和参数设置", 
                'details': {
                    'error': "Empty LLM output",
                    'core_attachments': core_attachments_count,
                    'history_attachments': total_history_attachments,
                    'error_type': 'llm_empty_output'
                }
            }

        # 检查是否是错误响应
        try:
            # 尝试解析为JSON以检查是否包含错误信息
            temp_result = json.loads(llm_output)
            if "error" in temp_result:
                # 如果LLM API调用失败，直接返回错误
                error_message = temp_result["error"]
                print(f"LLM API调用失败: {error_message}")
                return {
                    'status': 'FAILURE', 
                    'result': f"LLM API调用失败: {error_message}", 
                    'details': {
                        'error': error_message,
                        'core_attachments': core_attachments_count,
                        'history_attachments': total_history_attachments,
                        'error_type': 'llm_api_failure'
                    }
                }
        except json.JSONDecodeError:
            # 如果不是JSON格式，继续正常处理流程
            pass

        # 4. Parse and clean the output (优化：简化解析逻辑)
        # 在解析输出时添加状态更新
        print(f"开始解析大模型输出，输出长度: {len(llm_output) if isinstance(llm_output, str) else '非字符串'}")
        self.update_state(state='PROGRESS', meta={'status': '正在解析大模型输出...', 'progress': 90}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": "正在解析大模型输出...", "progress": 90})
        structured_result = extract_json_from_llm_output(llm_output)
        
        if "error" in structured_result:
            # 记录详细的错误信息，包括原始输出
            error_message = structured_result["error"]
            raw_output = structured_result.get("raw_output", "无可用的原始输出")
            print(f"解析大模型输出时出错: {error_message}")
            print(f"原始大模型输出 (前200字符): {raw_output[:200]}..." if len(raw_output) > 200 else raw_output)
            
            # 针对空JSON对象提供更明确的错误信息
            if error_message == "Empty JSON object":
                return {
                    'status': 'FAILURE', 
                    'result': "大模型返回了空的JSON对象，未能生成任何测试用例。请重试或检查大模型配置。", 
                    'details': {
                        'error': error_message,
                        'raw_output': raw_output,
                        'core_attachments': core_attachments_count,
                        'history_attachments': total_history_attachments
                    }
                }
            
            # 尝试再次处理，使用更宽松的解析方式（优化：直接使用ai_service的处理方法）
            self.update_state(state='PROGRESS', meta={'status': '尝试替代解析方法 (优化版本)...', 'progress': 95}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": "尝试替代解析方法 (优化版本)...", "progress": 95})
            
            # 如果原始输出是字符串，尝试直接从中提取测试用例结构
            if isinstance(llm_output, str):
                # 尝试提取测试用例结构
                import re
                # 同时支持中英文的测试用例模式
                testcase_patterns = [
                    r'\{\s*"id"\s*:\s*"[^"]*"\s*,\s*"module"\s*:\s*"[^"]*"\s*,\s*"title"\s*:\s*"[^"]*"',  # 标准格式
                    r'\{\s*"测试用例"\s*:\s*\[',  # 中文测试用例列表
                    r'\{\s*"testcases"\s*:\s*\['  # 英文测试用例列表
                ]
                
                for pattern in testcase_patterns:
                    if re.search(pattern, llm_output):
                        print(f"检测到可能的测试用例结构，尝试使用模式: {pattern}")
                        # 可能包含测试用例结构，尝试手动构建JSON
                        try:
                            # 优化：直接使用ai_service中的处理方法
                            processed_output = ai_service._process_llm_response(llm_output, jira_key)
                            structured_result = json.loads(processed_output)
                            if "testcases" in structured_result and isinstance(structured_result["testcases"], list):
                                testcase_count = len(structured_result["testcases"])
                                self.update_state(state='PROGRESS', meta={'status': f'成功使用替代方法提取了 {testcase_count} 个测试用例', 'progress': 100})
                                print(f"成功使用优化的替代解析方法提取了 {testcase_count} 个测试用例")
                                _publish_ws(self.request.id, {'status': 'SUCCESS', 'result': structured_result, 'progress': 100, 'text': '测试用例生成完成'})
                                # 写入缓存，TTL 24h
                                if redis is not None:
                                    try:
                                        r = redis.Redis.from_url(REDIS_URL)
                                        r.set(f"ai:testcases:{jira_key}", json.dumps(structured_result, ensure_ascii=False), ex=86400)
                                    except Exception:
                                        pass
                                return {'status': 'SUCCESS', 'result': structured_result}
                        except Exception as parsing_error:
                            import traceback
                            print(f"替代解析方法失败: {parsing_error}")
                            print(traceback.format_exc())
            
            # 如果所有解析尝试都失败，返回详细的错误信息
            _publish_ws(self.request.id, {'status': 'FAILURE', 'text': f"无法解析大模型输出: {error_message}", 'progress': 100, 'details': {
                    'error': error_message,
                    'raw_output_sample': raw_output[:500] + "..." if len(raw_output) > 500 else raw_output,
                    'core_attachments': core_attachments_count,
                    'history_attachments': total_history_attachments
                }})
            return {
                'status': 'FAILURE', 
                'result': f"无法解析大模型输出: {error_message}", 
                'details': {
                    'error': error_message,
                    'raw_output_sample': raw_output[:500] + "..." if len(raw_output) > 500 else raw_output,
                    'core_attachments': core_attachments_count,
                    'history_attachments': total_history_attachments
                }
            }
        
        # 5. 结果简单校验和统计
        if "testcases" in structured_result and isinstance(structured_result["testcases"], list):
            testcases = structured_result["testcases"]
            testcase_count = len(testcases)
            self.update_state(state='PROGRESS', meta={'status': f'成功生成 {testcase_count} 个测试用例', 'progress': 100}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": f"成功生成 {testcase_count} 个测试用例", "progress": 100})
            print(f"成功解析出 {testcase_count} 个测试用例")
            
            # 统计测试用例类型分布
            type_stats = {}
            priority_stats = {}
            module_stats = {}
            
            for testcase in testcases:
                # 类型统计
                test_type = testcase.get('type', 'other')
                type_stats[test_type] = type_stats.get(test_type, 0) + 1
                
                # 优先级统计
                priority = testcase.get('priority', 'P2')
                priority_stats[priority] = priority_stats.get(priority, 0) + 1
                
                # 模块统计
                module = testcase.get('module', '未指定')
                module_stats[module] = module_stats.get(module, 0) + 1
            
            print(f"测试用例类型分布: {type_stats}")
            print(f"测试用例优先级分布: {priority_stats}")
            print(f"测试用例模块分布: {module_stats}"); _publish_ws(self.request.id, {'status': 'SUCCESS', 'result': structured_result, 'progress': 100, 'text': '测试用例生成完成'})

        # 成功后写入缓存，TTL 24h
        if redis is not None:
            try:
                r = redis.Redis.from_url(REDIS_URL)
                r.set(f"ai:testcases:{jira_key}", json.dumps(structured_result, ensure_ascii=False), ex=86400)
            except Exception:
                pass

        return {'status': 'SUCCESS', 'result': structured_result}

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"测试用例生成任务出错: {e}\n{error_trace}")
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e), 'traceback': error_trace}); _publish_ws(self.request.id, {'status': 'FAILURE', 'text': f"测试用例生成失败: {str(e)}", 'progress': 100, 'traceback': error_trace})
        return {'status': 'FAILURE', 'result': f"测试用例生成失败: {str(e)}", 'traceback': error_trace}


@celery_app.task(bind=True)
def generate_kb_answer_task(self, question: str, top_k: int = 4):
    """
    异步知识库查询任务：检索 PDF 知识库并通过 LLM 生成答案
    返回结构与其他任务一致：{"status": "SUCCESS"|"FAILURE", "result": ...}
    """
    try:
        # 进度：开始
        self.update_state(state='PROGRESS', meta={'status': '准备检索知识库', 'progress': 10}); _publish_ws(self.request.id, {"status": "PROGRESS", "text": "准备检索知识库", "progress": 10})

        # 执行查询
        result = ai_service.query_kb(question, top_k=top_k)

        # 进度：完成
        self.update_state(state='PROGRESS', meta={'status': '知识库答案生成完成', 'progress': 100}); _publish_ws(self.request.id, {"status": "SUCCESS", "text": "知识库答案生成完成", "progress": 100, "result": result})
        return {'status': 'SUCCESS', 'result': result}
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        # 失败状态与推送
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e), 'traceback': error_trace}); _publish_ws(self.request.id, {"status": "FAILURE", "text": f"知识库查询失败: {str(e)}", "progress": 100, "traceback": error_trace})
        return {'status': 'FAILURE', 'result': f"知识库查询失败: {str(e)}", 'traceback': error_trace}
