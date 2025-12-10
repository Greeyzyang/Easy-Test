import json
import re
from jira import JIRA
from openai import OpenAI

# 第三方库集中导入（RAG相关），缺失时延迟错误在方法内抛出
try:
    from langchain_community.document_loaders import PyPDFLoader
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except Exception:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS
except Exception:
    PyPDFLoader = None
    RecursiveCharacterTextSplitter = None
    HuggingFaceEmbeddings = None
    FAISS = None

from app.config import Settings

settings = Settings()

class AIService:
    def __init__(self):
        # 使用 options + validate 控制初始化行为，避免不可达时的持续重试报警
        self.jira_client = JIRA(
            options={
                "server": settings.JIRA_URL,
                "verify": settings.JIRA_VERIFY
            },
            basic_auth=(settings.JIRA_USER, settings.JIRA_API_TOKEN),
            timeout=settings.JIRA_TIMEOUT,  # 使用配置中的超时时间
            max_retries=settings.MAX_RETRIES,  # 使用配置中的重试次数
            validate=settings.JIRA_VALIDATE  # 避免初始化时访问 serverInfo 导致重复告警
        )
        self.llm_client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            timeout=float(settings.LLM_TIMEOUT),  # 优化：使用配置中的超时时间，针对纯文本处理优化
            max_retries=1  # 减少重试次数，避免长时间等待
        )
        self._kb_store = None
        self._kb_path = settings.KB_PDF_PATH
        # KB（知识库）相关：RAG 使用的 PDF 路径与向量索引缓存
        # 说明：RAG = 检索增强生成。先“检索”与问题最相关的文档片段，再“生成”答案。
        # 其中“检索”依赖向量索引（FAISS），因此这里保存索引对象以便复用。

    def get_jira_issue_details(self, issue_key: str):
        """
        获取Jira issue的详细信息，包括附件处理
        """
        try:
            print(f"开始获取Jira issue: {issue_key}")
            issue = self.jira_client.issue(issue_key)
            print(f"成功获取Jira issue: {issue_key}")
            
            # 处理附件信息，供豆包多模态分析
            attachments_for_llm = []
            attachment_count = 0
            
            if hasattr(issue.fields, 'attachment') and issue.fields.attachment:
                attachment_count = len(issue.fields.attachment)
                print(f"发现 {attachment_count} 个附件")
                
                # 根据 ENABLE_IMAGE_PROCESSING 配置决定是否处理任何附件
                if settings.ENABLE_IMAGE_PROCESSING:
                    print("图片处理已启用，开始处理所有附件...")
                    
                    for attachment in issue.fields.attachment:
                        attachment_info = {
                            "filename": attachment.filename,
                            "mime_type": getattr(attachment, 'mimeType', 'unknown'),
                            "size": getattr(attachment, 'size', 0),
                            "created": getattr(attachment, 'created', None),
                            "content_url": attachment.content
                        }
                        
                        # 处理图片文件
                        if attachment_info["mime_type"].startswith('image/'):
                            try:
                                attachment_content = attachment.get()
                                if isinstance(attachment_content, bytes):
                                    import base64
                                    base64_content = base64.b64encode(attachment_content).decode('utf-8')
                                    attachment_info["type"] = "image"
                                    attachment_info["base64_content"] = base64_content
                                    attachment_info["description"] = f"图片文件：{attachment.filename}，可用于界面分析和功能测试"
                                    print(f"成功下载并处理图片附件: {attachment.filename} (大小: {len(attachment_content)} bytes)")
                                    attachments_for_llm.append(attachment_info)
                                else:
                                    print(f"图片附件获取失败: {attachment.filename}")
                            except Exception as e:
                                print(f"下载图片附件 {attachment.filename} 失败: {e}")
                        
                        # 处理文本文件
                        elif (attachment_info["mime_type"].startswith('text/') or 
                              attachment.filename.lower().endswith(('.txt', '.md', '.doc', '.docx', '.pdf', '.json', '.xml', '.csv'))):
                            try:
                                attachment_content = attachment.get()
                                if isinstance(attachment_content, bytes):
                                    for encoding in ['utf-8', 'gbk', 'gb2312', 'utf-16']:
                                        try:
                                            content_text = attachment_content.decode(encoding)
                                            break
                                        except UnicodeDecodeError:
                                            continue
                                    else:
                                        content_text = attachment_content.decode('utf-8', errors='ignore')
                                else:
                                    content_text = str(attachment_content)
                                
                                max_content_length = 5000
                                if len(content_text) > max_content_length:
                                    content_text = content_text[:max_content_length] + "...[内容过长，已截断]"
                                
                                attachment_info["type"] = "text"
                                attachment_info["text_content"] = content_text
                                attachment_info["description"] = f"文本文件：{attachment.filename}，包含重要测试信息"
                                
                                print(f"成功获取文本附件: {attachment.filename} (长度: {len(content_text)})")
                                attachments_for_llm.append(attachment_info)
                            except Exception as e:
                                print(f"获取文本附件 {attachment.filename} 失败: {e}")
                        
                        else:
                            print(f"跳过非支持文件: {attachment.filename} ({attachment_info['mime_type']})")
                    
                    print(f"成功准备 {len(attachments_for_llm)} 个附件供豆包分析 (图片处理: enabled)")
                else:
                    print("图片处理已禁用，跳过所有附件处理，使用纯文本模式")
                    # 当 ENABLE_IMAGE_PROCESSING = False 时，完全不处理任何附件
            
            return {
                "summary": issue.fields.summary,
                "description": issue.fields.description,
                "attachment_count": attachment_count,
                "attachments_for_llm": attachments_for_llm  # 供豆包多模态分析
            }
        except Exception as e:
            # 更详细的错误日志记录
            print(f"获取Jira issue {issue_key} 失败: {e}")
            print(f"错误类型: {type(e).__name__}")
            
            # 如果是超时错误，提供更具体的错误信息
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                print(f"Jira连接超时，请检查网络连接或Jira服务器状态")
                return None
            
            # 如果是认证错误
            if "unauthorized" in str(e).lower() or "401" in str(e):
                print(f"Jira认证失败，请检查用户名和API Token")
                return None
            
            # 如果是权限错误
            if "forbidden" in str(e).lower() or "403" in str(e):
                print(f"没有访问Jira issue {issue_key} 的权限")
                return None
            
            # 如果是issue不存在
            if "not found" in str(e).lower() or "404" in str(e):
                print(f"Jira issue {issue_key} 不存在")
                return None
            
            print(f"其他错误: {e}")
            return None

    def generate_testcases_from_jira(self, issue_details: dict, history_details: list | None = None, jira_key: str | None = None):
        """
        调用大模型生成测试用例 - 专门针对豆包模型优化
        保留完整的需求信息和历史需求内容，确保测试用例生成的全面性和准确性
        """
        # 1. 构造简洁prompt（保持稳定性）
        summary = issue_details.get('summary', 'N/A')
        description = issue_details.get('description', 'N/A')
        
        # 2. 构建历史需求参考信息（如果有的话）
        history_context = ""
        
        if history_details and isinstance(history_details, list) and len(history_details) > 0:
            history_summaries = []
            for idx, hist in enumerate(history_details[:3], 1):  # 最多3个历史需求
                hist_summary = hist.get('summary', 'N/A')
                hist_desc = hist.get('description', 'N/A')
                history_summaries.append(f"Historical Requirement {idx}: {hist_summary}\nDescription: {hist_desc}")
            
            history_context = f"\n\nHistorical Requirements Reference:\n{chr(10).join(history_summaries)}"
        
        # 优化后的动态Prompt - 根据需求复杂度生成更全面的测试用例
        prompt_text = f"""You are a senior test engineering expert. Generate comprehensive, high-quality test cases dynamically based on requirement complexity with full coverage of all testing dimensions.

### CRITICAL JSON FORMAT RULES (MUST FOLLOW EXACTLY):
1. OUTPUT ONLY VALID JSON — NO markdown, NO explanations, NO extra text, NO code fences (```), NO comments
2. OUTPUT MUST BE A SINGLE JSON OBJECT with ONE top-level key: "testcases". Do NOT include any other keys
3. STRUCTURE EXAMPLE: {{"testcases":[{{"id":"{jira_key}-001","module":"ModuleName","title":"Verify <objective>","priority":"P0","precondition":"Setup requirements","type":"functional","steps":["1. Action — Expected: Outcome","2. Next action — Expected: Outcome"],"expected_result":"Clear overall outcome"}}]}}
4. ID FORMAT: EXACTLY {jira_key}-001, {jira_key}-002 (sequential numbers, 3 digits)
5. PRIORITY: ONLY "P0", "P1", "P2" (no other values)
6. STEPS: Array of strings with numbered actions AND expected outcomes for EACH step
7. MODULE: Brief functional area name
8. TYPE: One of: functional, boundary, negative, security, integration, performance, concurrency, data-validation, network, compatibility
9. ALL fields are REQUIRED and MUST be present for EVERY test case
10. DO NOT include trailing commas or special characters; use plain ASCII quotes

### COMPREHENSIVE TESTING DIMENSIONS (ENSURE COVERAGE OF ALL):
1. **FUNCTIONAL TESTING**: Core feature functionality and main user workflows
2. **BOUNDARY TESTING**: Edge cases, input limits, boundary values
3. **NEGATIVE TESTING**: Error handling, invalid inputs, exception scenarios
4. **SECURITY TESTING**: Permission checks, data validation, access control
5. **PERFORMANCE TESTING**: Response time, load handling, resource consumption
6. **INTEGRATION TESTING**: Cross-module interactions, data flow validation
7. **CONCURRENCY TESTING**: Multi-user scenarios, race conditions
8. **DATA VALIDATION TESTING**: Input sanitization, data integrity
9. **NETWORK/INFRASTRUCTURE TESTING**: Connectivity, timeout handling
10. **COMPATIBILITY TESTING**: Browser/device compatibility

### REQUIREMENT COMPLEXITY ASSESSMENT:
**Summary**: {summary}
**Description**: {description}{history_context}

### GENERATION INSTRUCTIONS:
1. ASSESS requirement complexity and generate appropriate number of test cases:
   - Simple requirements (1-2 features): 6-10 comprehensive test cases
   - Moderate requirements (3-5 features): 10-15 comprehensive test cases
   - Complex requirements (6+ features): 20-30 comprehensive test cases
2. Each test case must have:
   - Unique ID: {jira_key}-001, {jira_key}-002, etc.
   - Module name (brief but descriptive)
   - Clear title starting with "Verify..."
   - Priority (P0/P1/P2) based on business impact
   - Detailed precondition (specific setup requirements)
   - Test type (one of the 10 types listed above)
   - 3-6 numbered steps with action AND expected outcome for each step
   - Clear overall expected result
3. Ensure comprehensive coverage of ALL 10 testing dimensions listed above
4. Include both positive and negative test scenarios
5. Consider real-world usage patterns and edge cases
6. Focus on detailed scenarios such as:
   - Multi-user concurrent operations
   - Permission and access control scenarios
   - Data consistency and integrity validation
   - Recovery and failover scenarios
   - Detailed performance benchmarks
   - Load and stress testing scenarios
   - Complex data flow validations
7. Avoid special characters, escape sequences, and complex JSON structures
8. Keep responses concise, well-formed, and single-line JSON format
9. Each step MUST include "- Expected:" with specific outcome

        Return ONLY the JSON object with test cases."""

        # 2. 构造多模态消息体（豆包支持图片+文本）
        content_parts: list[dict[str, str | dict[str, str]]] = [{"type": "text", "text": prompt_text}]
        
        # 添加附件内容到消息中
        attachments_for_llm = issue_details.get('attachments_for_llm', [])
        if attachments_for_llm:
            print(f"准备将 {len(attachments_for_llm)} 个附件传递给豆包 (ENABLE_IMAGE_PROCESSING={settings.ENABLE_IMAGE_PROCESSING})")
            
            for attachment in attachments_for_llm:
                if attachment.get('type') == 'image' and attachment.get('base64_content'):
                    # 添加base64编码的图片到消息中
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{attachment.get('mime_type', 'image/png')};base64,{attachment['base64_content']}"
                        }
                    })
                    print(f"添加图片附件到多模态消息: {attachment['filename']}")
                
                elif attachment.get('type') == 'text' and attachment.get('text_content'):
                    # 添加文本内容到消息中
                    content_parts.append({
                        "type": "text",
                        "text": f"\n\n【附件内容：{attachment['filename']}】\n{attachment['text_content']}"
                    })
                    print(f"添加文本附件内容到多模态消息: {attachment['filename']}")
        else:
            print("使用纯文本模式，没有附件内容")
        
        # 3. 调用豆包多模态模型
        try:
            attachment_count = len(attachments_for_llm) if attachments_for_llm else 0
            history_count = len(history_details) if history_details else 0
            status_info = []
            if history_count > 0:
                status_info.append(f"{history_count}个历史需求")
            if attachment_count > 0:
                status_info.append(f"{attachment_count}个附件(已下载)")
            
            status_text = ", ".join(status_info) if status_info else "无历史需求参考"
            print(f"调用豆包多模态生成测试用例，Jira Key: {jira_key}，{status_text}")
            
            response = self.llm_client.chat.completions.create(
                model=settings.LLM_MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an expert test case generator focused on comprehensive coverage based on requirement complexity.

CRITICAL FORMAT REQUIREMENTS:
1. OUTPUT: Return ONLY valid JSON object, NO markdown, NO code blocks, NO extra text
2. STRUCTURE: {{"testcases": [array_of_testcase_objects]}}
3. ID FORMAT: Use {jira_key}-001, {jira_key}-002, {jira_key}-003 (REAL sequential numbers, NOT placeholders)
4. PRIORITY: ONLY "P0", "P1", "P2" (NEVER use "P", "p", "High", "Medium", "Low")
5. STEPS: Array of numbered strings like ["1. Action - Expected: Outcome", "2. Next action - Expected: Outcome"]
6. TYPES: Use functional, boundary, negative, security, integration, performance, concurrency, data-validation, network, compatibility
7. DYNAMIC QUANTITY: Generate appropriate number based on requirement complexity
   - Simple requirements (1-2 features): 6-10 comprehensive test cases
   - Moderate requirements (3-5 features): 10-15 comprehensive test cases  
   - Complex requirements (6+ features): 20-30 comprehensive test cases
8. DETAILED SCENARIOS: Include multi-user, permission, data consistency, recovery, performance, load, and complex data flow scenarios

QUALITY FOCUS:
- Comprehensive coverage of all 10 testing dimensions
- Detailed, actionable test steps with specific expected outcomes
- Clear, measurable expected results
- Realistic test scenarios
- Proper risk-based prioritization

JSON VALIDATION:
- All strings must be properly quoted
- No trailing commas
- Proper array and object syntax
- All required fields present

IMPORTANT: Generate based on requirement complexity, prioritize comprehensive coverage over fixed quantity."""
                    },
                    {"role": "user", "content": content_parts}  # type: ignore
                ],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,  # 适中的温度确保质量和多样性
                presence_penalty=0.0,
                frequency_penalty=0.0,
                top_p=0.85,
                response_format={"type": "json_object"}
            )
            
            # 获取原始响应
            raw_response = response.choices[0].message.content
            print(f"豆包模型响应长度: {len(raw_response) if raw_response else 0} 字符")
            
            # 检查响应是否被截断（对数组和对象的更精准检查）
            is_truncated = False
            if raw_response:
                # 检查是否以完整的JSON结束
                if not raw_response.strip().endswith('}'):
                    is_truncated = True
                    print(f"警告：检测到响应可能被截断，最后字符: '{raw_response[-10:] if len(raw_response) >= 10 else raw_response}'")
                
                # 检查是否有损坏的字段名（如"_module_"）
                if '"_' in raw_response or '_"' in raw_response:
                    is_truncated = True
                    print("警告：检测到损坏的字段名（包含下划线），可能被截断")
                
                # 尝试自动修复被截断的JSON
                if is_truncated:
                    # 移除损坏的字段名
                    raw_response = re.sub(r',\s*{[^}]*"_[^"]*":[^}]*$', '', raw_response)
                    
                    # 修复缺少的括号
                    if raw_response.count('{') > raw_response.count('}'):
                        missing_braces = raw_response.count('{') - raw_response.count('}')
                        raw_response += '}' * missing_braces
                        print(f"尝试修复被截断的JSON，添加 {missing_braces} 个右花括号")
                    
                    # 修复缺少的方括号
                    if raw_response.count('[') > raw_response.count(']'):
                        missing_brackets = raw_response.count('[') - raw_response.count(']')
                        raw_response += ']' * missing_brackets
                        print(f"添加 {missing_brackets} 个右方括号")
            
            # 优化：修复调试文件保存逻辑
            try:
                import os
                import datetime
                debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug")
                os.makedirs(debug_dir, exist_ok=True)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_file = os.path.join(debug_dir, f"doubau_response_{jira_key}_{timestamp}.txt")
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(f"Jira Key: {jira_key}\n")
                    f.write(f"Response Length: {len(raw_response) if raw_response else 0}\n")
                    f.write(f"History Details Count: {len(history_details) if history_details else 0}\n")
                    f.write(f"History Status: {'With Historical Requirements' if history_details else 'No Historical Requirements'}\n")
                    
                    # 附件信息记录
                    f.write(f"Attachments Count: {attachment_count}\n")
                    if attachments_for_llm:
                        f.write("Attachment Content Details:\n")
                        for i, attachment in enumerate(attachments_for_llm, 1):
                            f.write(f"  {i}. {attachment['filename']} ({attachment['type']})\n")
                            if attachment['type'] == 'image':
                                has_content = 'base64_content' in attachment
                                f.write(f"     - Image content downloaded: {has_content}\n")
                            elif attachment['type'] == 'text':
                                has_content = 'text_content' in attachment
                                content_len = len(attachment.get('text_content', '')) if has_content else 0
                                f.write(f"     - Text content downloaded: {has_content}, length: {content_len}\n")
                    else:
                        f.write("Attachment Content: None (text-only prompt)\n")
                    
                    if settings.ENABLE_IMAGE_PROCESSING:
                        f.write(f"Attachment Processing: All attachments processed (images as base64, text as content)\n")
                    else:
                        f.write(f"Attachment Processing: No attachments processed (pure text mode)\n")
                    f.write(f"Optimized: Complete requirement content with downloaded attachments\n")
                    f.write(f"Timestamp: {datetime.datetime.now()}\n")
                    f.write("="*50 + "\n")
                    f.write(raw_response if raw_response else "")
                print(f"已保存豆包模型调试响应到: {debug_file}")
            except Exception as debug_error:
                print(f"保存调试文件失败: {debug_error}")
            
            # 处理响应并返回
            processed_response = self._process_llm_response(raw_response, jira_key)
            print(f"成功处理豆包模型响应，生成测试用例完成")
            
            # 检查处理后的响应是否包含错误
            try:
                result = json.loads(processed_response)
                if "error" in result:
                    print(f"处理响应时发生错误: {result['error']}")
                else:
                    print(f"成功生成 {len(result.get('testcases', []))} 个测试用例")
                    # 记录优化效果
                    if not settings.ENABLE_IMAGE_PROCESSING:
                        # 如果图片处理被禁用，说明使用了纯文本模式，没有处理任何附件
                        print(f"优化效果: 使用纯文本模式，跳过所有附件处理，提升响应稳定性")
            except json.JSONDecodeError:
                print("无法解析处理后的响应为JSON")
                
            return processed_response
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"调用豆包模型API失败: {e}\n{error_trace}")
            return json.dumps({
                "error": f"调用豆包模型API失败（已优化：极简prompt）: {str(e)}", 
                "traceback": error_trace,
                "optimization_note": "Doubao-specific optimization applied"
            })

    def _extract_json_from_response(self, raw_response: str | None, jira_key: str | None = None) -> dict:
        """
        从大模型响应中提取JSON数据，增强的JSON提取和修复逻辑
        专门处理豆包模型生成的不完整JSON
        """
        import json
        import re
        
        if not raw_response or not isinstance(raw_response, str):
            return {"error": "Invalid response format", "raw_output": str(raw_response)}
        
        print(f"开始解析响应，原始长度: {len(raw_response)}")
        
        # 检查响应长度是否异常（豆包模型失控检测）
        if len(raw_response) > 50000:  # 超过50KB认为异常
            print(f"警告：响应长度异常 ({len(raw_response)} 字符)，可能是豆包模型失控")
            # 尝试截取前部分内容
            raw_response = raw_response[:10000]
            print("已截取响应到前10000字符进行处理")
        
        # 首先尝试直接解析整个响应
        try:
            data = json.loads(raw_response)
            if isinstance(data, dict) and "testcases" in data:
                print(f"✓ 直接解析成功，包含 {len(data.get('testcases', []))} 个测试用例")
                return data
        except json.JSONDecodeError as e:
            print(f"直接解析失败: {e}")
        
        # 如果直接解析失败，尝试从响应中提取JSON部分
        json_start = raw_response.find('{')
        if json_start != -1:
            json_content = raw_response[json_start:]
            print(f"提取JSON部分，长度: {len(json_content)}")
            
            # 尝试解析提取的JSON
            try:
                data = json.loads(json_content)
                if isinstance(data, dict) and "testcases" in data:
                    print(f"✓ 提取解析成功，包含 {len(data.get('testcases', []))} 个测试用例")
                    return data
            except json.JSONDecodeError as e:
                print(f"提取解析失败: {e}")
        else:
            print("未找到JSON开始标记")
        
        # 清理控制字符和大量空白
        cleaned_response = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', raw_response)
        # 移除末尾的大量空白字符
        cleaned_response = re.sub(r'\s+$', '', cleaned_response)
        
        # 应用豆包特有修复 - 必须在JSON解析前修复ID和优先级格式
        id_counter = 1
        
        def fix_doubau_specific_issues(text):
            """修复豆包模型特定的格式问题 - 2025-09-28增强版本"""
            nonlocal id_counter
            if not text:
                return text
                
            print(f"开始豆包修复，文本长度: {len(text)}")
            
            # 0. 预处理：修复下划线替代逗号和引号的问题（2025-09-28新发现）
            print("修复下划线格式异常")
            
            # 修复 testcases_ 应该是 testcases"
            text = re.sub(r'"testcases_', '"testcases"', text)
            
            # 修复 {_field 应该是 {"field  
            text = re.sub(r'\{_([^_"]+)', r'{"\1', text)
            
            # 修复 value_,_ 应该是 value","
            text = re.sub(r'([^_"]+)_,_', r'\1","', text)
            
            # 修复 value_ 应该是 value"
            text = re.sub(r'([^_"]+)_([,\}\]])', r'\1"\2', text)
            
            # 修复 :_ 应该是 :"
            text = re.sub(r':\s*_([^_,\}\]]+)', r': "\1', text)
            
            # 修复 }: 和 ]: 后面的下划线问题
            text = re.sub(r'\}\s*_', '},', text)
            text = re.sub(r'\]\s*_', '],', text)
            
            # 2025-09-28新增：修复双重花括号问题
            text = re.sub(r'\{\{', '{', text)
            text = re.sub(r'\}\}', '}', text)
            
            # 2025-09-28新增：修复损坏的字段名（如 {"_module"）
            text = re.sub(r'"\{_\s*([^"]+)"', r'"\1"', text)
            
            # 2025-09-28新增：修复损坏的字段名（如 ""_id"）
            text = re.sub(r'""_([^"]+)"', r'"\1"', text)
            
            print(f"下划线修复后预览: {text[:200]}...")
            
            # 2025-09-28新增：增强的JSON完整性检查和修复
            try:
                # 尝试直接解析
                json.loads(text)
                # 如果能解析，直接返回
                return text
            except json.JSONDecodeError:
                # 如果不能直接解析，采用更全面的修复策略
                print("直接解析失败，采用增强修复策略")
                
                # 1. 修复转义字符问题
                text = text.replace('\\"', '"')
                text = text.replace('\\\\', '\\')
                
                # 2. 修复缺少的闭合符号
                open_braces = text.count('{')
                close_braces = text.count('}')
                if open_braces > close_braces:
                    text += '}' * (open_braces - close_braces)
                    print(f"添加了 {open_braces - close_braces} 个右花括号")
                
                open_brackets = text.count('[')
                close_brackets = text.count(']')
                if open_brackets > close_brackets:
                    text += ']' * (open_brackets - close_brackets)
                    print(f"添加了 {open_brackets - close_brackets} 个右方括号")
                
                # 3. 修复尾随逗号
                text = re.sub(r',\s*([}\]])', r'\1', text)
                
                # 4. 修复缺少逗号的问题
                text = re.sub(r'}\s*{', '},{', text)
                text = re.sub(r'\]\s*{', '],{', text)
                text = re.sub(r'}\s*\[', '},[', text)
                
                # 5. 尝试再次解析
                try:
                    json.loads(text)
                    return text
                except json.JSONDecodeError:
                    # 6. 如果仍然失败，采用应急策略
                    print("增强修复策略也失败，采用应急策略")
                    
                    # 应急策略：手动构造一个基本的JSON结构
                    try:
                        # 尝试提取关键信息并构造简单的测试用例
                        testcases = []
                        
                        # 提取testcases数组内容
                        testcases_match = re.search(r'"testcases"\s*:\s*$', text)
                        if testcases_match:
                            # 如果找到了testcases但数组不完整，构造一个简单的数组
                            testcases.append({
                                "id": f"{jira_key}-001" if jira_key else "FIXED-001",
                                "module": "Fixed Module",
                                "title": "Fixed Test Case",
                                "priority": "P1",
                                "precondition": "Fixed by repair logic",
                                "type": "functional",
                                "steps": ["1. This test case was automatically repaired"],
                                "expected_result": "Successful repair"
                            })
                        else:
                            # 尝试提取ID、标题等关键信息
                            id_matches = re.findall(r'"id":\s*"([^"]+)"', text)
                            title_matches = re.findall(r'"title":\s*"([^"]+)"', text)
                            priority_matches = re.findall(r'"priority":\s*"([^"]+)"', text)
                            
                            # 如果找到了多个测试用例的信息
                            max_cases = min(len(id_matches), len(title_matches), 3)  # 最多处理3个
                            if max_cases > 0:
                                for i in range(max_cases):
                                    testcase = {
                                        "id": id_matches[i] if i < len(id_matches) else f"{jira_key}-{i+1:03d}" if jira_key else f"FIXED-{i+1:03d}",
                                        "module": "Fixed Module",
                                        "title": title_matches[i] if i < len(title_matches) else f"Fixed Test Case {i+1}",
                                        "priority": priority_matches[i] if i < len(priority_matches) else "P1",
                                        "precondition": "Fixed by repair logic",
                                        "type": "functional",
                                        "steps": ["1. This test case was automatically repaired"],
                                        "expected_result": "Successful repair"
                                    }
                                    testcases.append(testcase)
                            else:
                                # 如果没有找到任何信息，构造一个默认的测试用例
                                testcases.append({
                                    "id": f"{jira_key}-001" if jira_key else "FIXED-001",
                                    "module": "Fixed Module",
                                    "title": "Fixed Test Case",
                                    "priority": "P1",
                                    "precondition": "Fixed by repair logic",
                                    "type": "functional",
                                    "steps": ["1. This test case was automatically repaired"],
                                    "expected_result": "Successful repair"
                                })
                        
                        # 构造完整JSON
                        fixed_json = {
                            "testcases": testcases,
                            "repair_note": "This JSON was automatically repaired due to format issues from the AI model"
                        }
                        
                        print(f"应急策略成功构造了 {len(testcases)} 个测试用例")
                        return json.dumps(fixed_json, ensure_ascii=False)
                        
                    except Exception as e:
                        print(f"应急策略也失败了: {e}")
                        # 最后的后备方案：返回空的测试用例结构
                        fallback_json = {
                            "testcases": [],
                            "error": "无法从AI模型响应中提取有效测试用例",
                            "raw_response": text[:500]  # 保留原始响应的前500字符用于调试
                        }
                        return json.dumps(fallback_json, ensure_ascii=False)
        
        cleaned_response = fix_doubau_specific_issues(cleaned_response)
        
        print(f"修复后响应预览: {cleaned_response[:200]}...")  # 添加调试信息
        
        # 首先尝试修复常见的JSON错误
        def fix_common_json_errors(text):
            # 修复未转义的嵌套引号
            text = re.sub(r'"([^"]*?)"([^"]*?)"([^"]*?)":', r'"\1\\"\2\\"\3":', text)
            # 修复尾随逗号
            text = re.sub(r',\s*([}\]])', r'\1', text)
            # 修复缺少逗号的地方
            text = re.sub(r'}\s*{', '},{', text)
            # 移除不完整的测试用例（以"-Expected:"结尾但没有内容的）
            text = re.sub(r',\s*{[^}]*"-Expected:"[^}]*}(?=\s*[}\]])', '', text)
            # 修复不完整的步骤数组
            text = re.sub(r'"steps":\s*\[[^\]]*"-Expected:"[^\]]*\]', '"steps": ["1. Placeholder step - Expected: Placeholder result"]', text)
            
            # 修复豆包特有的格式问题
            # 1. 修复字段值中的换行符
            text = re.sub(r'"([^"]+)"\s*:\s*"([^"]*?)\n([^"]*?)"', r'"\1": "\2 \3"', text)
            # 2. 修复被拆分的字段名
            text = re.sub(r'"\s*\n\s*([^"]+)"\s*:', r'"\1":', text)
            # 3. 修复字符串中的换行符
            text = re.sub(r'"([^"]*?)\n([^"]*?)"', r'"\1 \2"', text)
            # 4. 修复多余的换行和空白
            text = re.sub(r'\n\s*', ' ', text)
            # 5. 修复字段间的换行
            text = re.sub(r'"\s*,\s*\n\s*"', '", "', text)
            # 6. 新增：修复豆包的字段名空格问题（如 "priority " : "p ")
            text = re.sub(r'"([^"\s]+)\s+"\s*:', r'"\1":', text)  # 移除字段名后的空格
            text = re.sub(r'"\s*:\s*"([^"]*?)\s+"', r'": "\1"', text)  # 移除字段值后的空格
            
            return text
        
        # 特殊处理：尝试从完整的testcases数组中提取
        def extract_complete_testcases(text):
            # 查找testcases数组的开始
            testcases_start = text.find('"testcases":[')
            if testcases_start == -1:
                testcases_start = text.find('"testcases": [')
            
            if testcases_start != -1:
                print("找到testcases数组开始位置")
                # 从testcases开始解析
                remaining_text = text[testcases_start:]
                
                # 查找最后一个完整的测试用例
                last_expected_result = remaining_text.rfind('"expected_result":')
                if last_expected_result != -1:
                    # 查找这个expected_result后面的}
                    after_expected = remaining_text[last_expected_result:]
                    close_brace_pos = after_expected.find('}')
                    if close_brace_pos != -1:
                        # 截取到最后一个完整测试用例
                        complete_end = last_expected_result + close_brace_pos + 1
                        complete_testcases = remaining_text[:complete_end]
                        
                        # 检查是否有testcases数组的开始
                        array_start_pos = complete_testcases.find(':[') 
                        if array_start_pos == -1:
                            array_start_pos = complete_testcases.find(': [')
                        
                        if array_start_pos != -1:
                            # 构造完整的JSON
                            testcases_content = complete_testcases[array_start_pos + 2:]  # +2 to skip ':['  
                            complete_json = '{"testcases":[' + testcases_content + ']}'
                            print(f"构造完整JSON，长度: {len(complete_json)}")
                            return complete_json
            return text
        
        # 尝试提取完整的testcases
        complete_json = extract_complete_testcases(cleaned_response)
        
        # 应用修复
        fixed_response = fix_common_json_errors(complete_json)
        
        # 尝试直接解析
        try:
            data = json.loads(fixed_response)
            if isinstance(data, dict) and "testcases" in data:
                print(f"成功解析JSON，包含 {len(data.get('testcases', []))} 个测试用例")
                return data
        except json.JSONDecodeError as e:
            print(f"直接JSON解析失败: {e}")
        
        # 如果直接解析失败，尝试更激进的修复
        try:
            start = fixed_response.find('{')
            end = fixed_response.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = fixed_response[start:end + 1]
                
                # 修复破损的JSON结构
                def repair_broken_json(text):
                    # 处理嵌套引号问题
                    text = re.sub(r'"([^"]*?"[^"]*?)"', lambda m: '"' + m.group(1).replace('"', '\\"') + '"', text)
                    # 移除重复的逗号
                    text = re.sub(r',,+', ',', text)
                    # 修复缺少的闭合括号
                    open_braces = text.count('{')
                    close_braces = text.count('}')
                    if open_braces > close_braces:
                        text += '}' * (open_braces - close_braces)
                        print(f"添加了 {open_braces - close_braces} 个右花括号")
                    # 修复缺少的方括号
                    open_brackets = text.count('[')
                    close_brackets = text.count(']')
                    if open_brackets > close_brackets:
                        text += ']' * (open_brackets - close_brackets)
                        print(f"添加了 {open_brackets - close_brackets} 个右方括号")
                    return text
                
                repaired_json = repair_broken_json(json_str)
                try:
                    data = json.loads(repaired_json)
                    if isinstance(data, dict):
                        print(f"修复后成功解析JSON，包含 {len(data.get('testcases', []))} 个测试用例")
                        return data
                except json.JSONDecodeError as e:
                    print(f"修复后解析仍失败: {e}")
                    
                    # 最后尝试：手动提取testcases数组
                    testcase_pattern = r'"testcases"\s*:\s*\[([\s\S]*?)\]'
                    match = re.search(testcase_pattern, repaired_json)
                    if match:
                        try:
                            testcases_content = match.group(1)
                            # 清理并修复testcases内容
                            testcases_content = re.sub(r',\s*$', '', testcases_content)  # 移除末尾逗号
                            testcases_str = '[' + testcases_content + ']'
                            testcases = json.loads(testcases_str)
                            if isinstance(testcases, list):
                                print(f"通过正则提取成功，包含 {len(testcases)} 个测试用例")
                                return {"testcases": testcases}
                        except json.JSONDecodeError as e:
                            print(f"正则提取也失败: {e}")
                    
        except Exception as e:
            print(f"JSON修复尝试失败: {e}")
        
        print("所有JSON解析尝试都失败")
        return {"error": "无法提取有效JSON", "raw_output": cleaned_response[:1000]}

    def _normalize_testcase_structure(self, data: dict, jira_key: str | None = None) -> dict:
        """
        标准化测试用例结构并进行质量评估
        """
        # 处理不同的testcases键名
        testcases_keys = ["testcases", "测试用例", "test_cases", "cases"]
        testcases = None
        
        for key in testcases_keys:
            if key in data:
                testcases = data.pop(key)
                break
        
        # 如果没有找到testcases，检查是否是直接的列表
        if testcases is None:
            if isinstance(data, list):
                testcases = data
                data = {}
            else:
                # 查找可能的测试用例对象
                testcases = []
                testcase_fields = ["id", "module", "title", "priority", "steps"]
                
                for key, value in list(data.items()):
                    if isinstance(value, dict) and any(field in value for field in testcase_fields):
                        testcases.append(value)
                        data.pop(key)
        
        if not isinstance(testcases, list):
            testcases = []
            
        # 只在完全没有生成任何测试用例时视为错误
        if len(testcases) == 0:
            data["error"] = "未能生成任何测试用例，请检查需求描述是否完整"
            print("错误：未能生成任何测试用例")
        elif len(testcases) < 5:
            data["warning"] = f"测试用例数量较少({len(testcases)}个)，建议检查需求复杂度评估"
            print(f"警告：测试用例数量较少({len(testcases)}个)")
        
        # 标准化每个测试用例
        normalized_testcases = []
        titles = set()
        
        # 测试用例类型统计
        type_counts = {}
        priority_counts = {"P0": 0, "P1": 0, "P2": 0}
        quality_issues = []
        
        for i, testcase in enumerate(testcases):
            if not isinstance(testcase, dict):
                continue
            
            # 过滤空的或无效的测试用例
            if (not testcase.get("title") or 
                not testcase.get("steps") or 
                (isinstance(testcase.get("steps"), list) and len(testcase.get("steps", [])) == 0)):
                print(f"跳过空的测试用例 {i+1}")
                continue
                
            # 确保所有必需字段存在并转换为正确类型
            def safe_str_field(value, default=""):
                if isinstance(value, (list, dict)):
                    return str(value) if value else default
                return str(value) if value is not None else default
            
            normalized_case = {
                "id": safe_str_field(testcase.get("id", "")),
                "module": safe_str_field(testcase.get("module", "")),
                "title": safe_str_field(testcase.get("title", f"Test Case {i+1}")),
                "priority": safe_str_field(testcase.get("priority", "P2")),
                "precondition": safe_str_field(testcase.get("precondition", "")),
                "type": safe_str_field(testcase.get("type", "functional")),
                "steps": [],
                "expected_result": testcase.get("expected_result", "")
            }
            
            # 处理标题去重
            original_title = normalized_case["title"]
            counter = 1
            while normalized_case["title"] in titles:
                normalized_case["title"] = f"{original_title} (variant {counter})"
                counter += 1
            titles.add(normalized_case["title"])
            
            # 强制统一ID格式 - 完全忽略模型生成的ID，强制使用标准格式
            if jira_key:
                normalized_case["id"] = f"{jira_key}-{i+1:03d}"
            else:
                normalized_case["id"] = f"TC-{i+1:03d}"
            
            # 强制统一优先级格式 - 修复只有P的问题
            priority = normalized_case["priority"]
            if priority == "P" or not priority or priority not in ["P0", "P1", "P2"]:
                # 根据测试类型和重要性自动分配优先级
                test_type = normalized_case.get("type", "functional")
                if test_type in ["functional", "security"]:
                    normalized_case["priority"] = "P0"
                elif test_type in ["boundary", "negative", "integration"]:
                    normalized_case["priority"] = "P1"
                else:
                    normalized_case["priority"] = "P2"
            
            print(f"标准化第{i+1}个测试用例: ID={normalized_case['id']}, 优先级={normalized_case['priority']}")
            
            # 标准化步骤格式 - 统一转换为字符串数组，支持包含预期结果的格式
            steps = testcase.get("steps", [])
            normalized_steps = []
            
            if isinstance(steps, list) and steps:
                if isinstance(steps[0], dict):
                    # 字典格式：提取步骤文本，合并预期结果
                    for j, step in enumerate(steps):
                        if isinstance(step, dict):
                            step_text = step.get("step", step.get("action", step.get("description", "")))
                            expected = step.get("expected", step.get("expected_result", ""))
                            
                            # 确保step_text是字符串
                            if not isinstance(step_text, str):
                                step_text = str(step_text) if step_text else ""
                            
                            # 确保expected是字符串
                            if not isinstance(expected, str):
                                expected = str(expected) if expected else ""
                            
                            if step_text and step_text.strip():
                                # 确保步骤有编号
                                if not re.match(r'^\d+\.', step_text.strip()):
                                    step_text = f"{j+1}. {step_text.strip()}"
                                
                                # 如果有预期结果，添加到步骤中
                                if expected and expected.strip():
                                    step_text += f" - 预期：{expected.strip()}"
                                
                                normalized_steps.append(step_text)
                
                elif isinstance(steps[0], str):
                    # 字符串格式：直接使用，确保编号和预期结果格式
                    for j, step in enumerate(steps):
                        # 确保step是字符串
                        if not isinstance(step, str):
                            step = str(step) if step else ""
                        
                        if step and step.strip():
                            step_text = step.strip()
                            
                            # 确保步骤有编号
                            if not re.match(r'^\d+\.', step_text):
                                step_text = f"{j+1}. {step_text}"
                            
                            # 如果步骤中没有预期结果格式，但应该有，尝试添加
                            if " - 预期：" not in step_text and " - Expected:" not in step_text:
                                # 如果这是增强Prompt生成的测试用例，应该已经有预期结果
                                # 如果没有，我们添加一个占位符
                                if "Expected:" not in step_text:
                                    step_text += " - 预期：操作成功完成"
                            
                            normalized_steps.append(step_text)
            
            elif isinstance(steps, str) and steps.strip():
                # 单个字符串：转换为数组
                step_text = steps.strip()
                if not re.match(r'^\d+\.', step_text):
                    step_text = f"1. {step_text}"
                normalized_steps = [step_text]
            
            # 确保至少有一个步骤
            if not normalized_steps:
                normalized_steps = ["1. Execute the required operation - 预期: Operation completes successfully"]
                quality_issues.append(f"测试用例 '{normalized_case['title']}' 缺少详细步骤")
            
            # 检查步骤质量 - 确保每个步骤都包含预期结果
            steps_without_expected = []
            for step in normalized_steps:
                if " - 预期：" not in step and " - Expected:" not in step and "预期：" not in step:
                    steps_without_expected.append(step)
            
            if steps_without_expected:
                quality_issues.append(f"测试用例 '{normalized_case['title']}' 有 {len(steps_without_expected)} 个步骤缺少预期结果")
            
            normalized_case["steps"] = normalized_steps
            
            # 确保预期结果不为空
            expected_result = normalized_case["expected_result"]
            if isinstance(expected_result, list):
                # 如果是列表，转换为字符串
                expected_result = "; ".join(str(item) for item in expected_result if item)
                normalized_case["expected_result"] = expected_result
            elif not isinstance(expected_result, str):
                # 如果不是字符串也不是列表，转换为字符串
                expected_result = str(expected_result)
                normalized_case["expected_result"] = expected_result
            
            if not normalized_case["expected_result"].strip():
                normalized_case["expected_result"] = "Test should complete successfully with all expected results met"
                quality_issues.append(f"测试用例 '{normalized_case['title']}' 缺少整体预期结果")
            
            # 标准化优先级
            priority = normalized_case["priority"].upper()
            if priority not in ["P0", "P1", "P2"]:
                if "0" in priority or "高" in priority or "HIGH" in priority:
                    priority = "P0"
                elif "1" in priority or "中" in priority or "MEDIUM" in priority:
                    priority = "P1"
                else:
                    priority = "P2"
            normalized_case["priority"] = priority
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            # 标准化类型
            test_type = normalized_case["type"].lower()
            valid_types = ["functional", "boundary", "negative", "security", "performance", 
                          "compatibility", "usability", "integration", "regression", 
                          "data-validation", "workflow", "concurrency", "network"]
            
            if test_type not in valid_types:
                # 尝试映射到有效类型
                if "功能" in test_type or "function" in test_type:
                    test_type = "functional"
                elif "边界" in test_type or "bound" in test_type:
                    test_type = "boundary"
                elif "负面" in test_type or "异常" in test_type or "negative" in test_type:
                    test_type = "negative"
                elif "安全" in test_type or "secur" in test_type:
                    test_type = "security"
                elif "性能" in test_type or "perform" in test_type:
                    test_type = "performance"
                elif "兼容" in test_type or "compat" in test_type:
                    test_type = "compatibility"
                elif "用户" in test_type or "usab" in test_type:
                    test_type = "usability"
                elif "集成" in test_type or "integ" in test_type:
                    test_type = "integration"
                elif "回归" in test_type or "regress" in test_type:
                    test_type = "regression"
                elif "数据" in test_type or "data" in test_type:
                    test_type = "data-validation"
                elif "流程" in test_type or "work" in test_type:
                    test_type = "workflow"
                elif "并发" in test_type or "concur" in test_type:
                    test_type = "concurrency"
                elif "网络" in test_type or "network" in test_type:
                    test_type = "network"
                else:
                    test_type = "functional"
            
            normalized_case["type"] = test_type
            type_counts[test_type] = type_counts.get(test_type, 0) + 1
            
            # 检查前置条件
            if len(normalized_case["precondition"]) < 10:
                quality_issues.append(f"测试用例 '{normalized_case['title']}' 前置条件过于简单或缺失")
            
            normalized_testcases.append(normalized_case)
        
        # 添加测试用例类型分布统计
        data["testcases"] = normalized_testcases
        data["statistics"] = {
            "total_testcases": len(normalized_testcases),
            "type_distribution": type_counts,
            "priority_distribution": priority_counts
        }
        
        # 添加质量评估
        if quality_issues:
            data["quality_issues"] = quality_issues[:10]  # 最多显示10个质量问题
            if len(quality_issues) > 10:
                data["quality_issues"].append(f"... 还有 {len(quality_issues) - 10} 个质量问题未显示")
        
        # 检查测试用例类型分布是否合理（基于覆盖度而非数量）
        if len(normalized_testcases) >= 5:  # 至少5个测试用例才进行分布分析
            total_testcases = len(normalized_testcases)
            functional_percent = type_counts.get("functional", 0) / total_testcases * 100
            boundary_percent = type_counts.get("boundary", 0) / total_testcases * 100
            negative_percent = type_counts.get("negative", 0) / total_testcases * 100
            security_percent = type_counts.get("security", 0) / total_testcases * 100
            
            distribution_issues = []
            
            # 基于覆盖度要求进行检查
            if functional_percent < 25:  # 降低功能测试最低要求
                distribution_issues.append(f"功能测试用例比例较低 ({functional_percent:.1f}%)，建议至少25%")
            if total_testcases >= 8 and boundary_percent == 0:  # 复杂需求需要边界测试
                distribution_issues.append(f"缺少边界测试用例，建议添加边界值测试")
            if total_testcases >= 6 and negative_percent == 0:  # 中等以上复杂度需要负面测试
                distribution_issues.append(f"缺少负面测试用例，建议添加异常场景测试")
            if total_testcases >= 10 and security_percent == 0:  # 复杂系统需要安全测试
                distribution_issues.append(f"缺少安全测试用例，建议添加权限和数据验证测试")
            
            # 检查是否覆盖了10个测试维度
            expected_dimensions = ["functional", "boundary", "negative", "security", "integration", 
                                 "performance", "concurrency", "data-validation", "network", "compatibility"]
            covered_dimensions = [dim for dim in expected_dimensions if type_counts.get(dim, 0) > 0]
            coverage_rate = len(covered_dimensions) / len(expected_dimensions) * 100
            
            if coverage_rate < 50:  # 覆盖度低于50%
                distribution_issues.append(f"测试维度覆盖度低 ({coverage_rate:.1f}%)，建议完善{len(expected_dimensions)-len(covered_dimensions)}个缺失维度")
            
            if distribution_issues:
                data["distribution_issues"] = distribution_issues
        else:
            data["distribution_note"] = f"测试用例数量较少({len(normalized_testcases)}个)，跳过分布分析"
        
        return data

    def _process_llm_response(self, raw_response: str | None, jira_key: str | None = None) -> str:
        """
        处理大模型的原始响应，确保输出符合要求
        """
        import json
        
        try:
            print(f"处理大模型响应，长度: {len(raw_response) if raw_response else 0} 字符")
            
            # 1. 提取JSON数据
            data = self._extract_json_from_response(raw_response, jira_key)
            
            if "error" in data:
                print(f"JSON提取失败: {data['error']}")
                return json.dumps(data)
            
            # 2. 标准化测试用例结构
            normalized_data = self._normalize_testcase_structure(data, jira_key)
            
            testcases_count = len(normalized_data.get("testcases", []))
            print(f"成功处理 {testcases_count} 个测试用例")
            
            return json.dumps(normalized_data, ensure_ascii=False, indent=2)
            
        except Exception as e:
            print(f"处理响应时出错: {e}")
            return json.dumps({
                "error": f"处理响应失败: {str(e)}",
                "raw_output": raw_response[:500] if raw_response else ""
            })


    def _ensure_kb_store(self):
        # 懒加载与缓存：仅在首次调用时构建向量索引，后续直接复用，提高性能
        if getattr(self, "_kb_store", None) is not None:
            return self._kb_store
        import os
        kb_path = self._kb_path or os.getenv("KB_PDF_PATH")
        # 1) 解析 PDF 路径：支持从配置与环境变量读取
        if not kb_path:
            raise Exception("请配置KB_PDF_PATH 指向PDF文件")
        if not os.path.exists(kb_path):
            raise Exception("PDF not found")
        # 2) 依赖检查：RAG 依赖 PDF 加载、文本切分、向量化与索引构建
        if not (PyPDFLoader and RecursiveCharacterTextSplitter and HuggingFaceEmbeddings and FAISS):
            raise Exception("缺少依赖: langchain, langchain-community, faiss-cpu, sentence-transformers, pypdf")
        # 3) 加载 PDF 文档
        loader = PyPDFLoader(kb_path)
        docs = loader.load()
        # 4) 文本切分：将长文档切成重叠片段以提升召回与语义连续性
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = splitter.split_documents(docs)
        # 5) 向量化：将文本片段编码为嵌入向量（便于相似度检索）
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        # 6) 构建向量索引（FAISS）：后续检索按相似度（余弦距离）返回 TopK 片段
        self._kb_store = FAISS.from_documents(chunks, embeddings)
        return self._kb_store

    def query_kb(self, question: str, top_k: int = 4) -> dict:
        # 1) 取索引：保证向量索引已构建
        store = self._ensure_kb_store()
        # 2) TopK：返回与问题最相似的 k 个片段（k 不宜过大，避免噪声）
        k = max(1, min(int(top_k or 4), 10))
        results = store.similarity_search_with_score(question, k=k)
        # 3) 组装上下文：将检索到的片段拼接成“受控上下文”，供模型参考
        context = "\n\n".join([d.page_content for d, _ in results])
        messages = [
            {
                "role": "system",
                "content": (
                    "你是资深产品专家，只依据提供的产品文档上下文回答产品相关问题；"
                    "若无法从上下文得出结论则回答\"文档未涉及\"。"
                    "回答注重业务价值、功能解释、使用指引、限制与注意事项。"
                )
            },
            {
                "role": "user",
                "content": f"产品文档上下文：\n{context}\n\n用户问题：{question}"
            }
        ]
        # 4) 生成：将“上下文 + 问题”输入到大模型，生成最终答案
        resp = self.llm_client.chat.completions.create(
            model=settings.LLM_MODEL_NAME, messages=messages, max_tokens=1024, temperature=0.0
        )
        # 5) 结果整理：返回模型回答与对应的来源片段（便于可追溯性）
        answer = resp.choices[0].message.content if getattr(resp, "choices", None) else ""
        sources = [{"page": d.metadata.get("page", d.metadata.get("page_number")), "content": d.page_content} for d, _ in results]
        return {"answer": answer, "sources": sources}

# 方便后续在celery任务中调用
ai_service = AIService()
