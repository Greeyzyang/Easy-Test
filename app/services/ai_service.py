import json
import re
import os
from datetime import datetime, timedelta
from jira import JIRA
from openai import OpenAI
from sqlalchemy import select
from app.database import SessionLocal
from app.models.ai_model import AIModel

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
from app.utils.logger import get_logger
from app.utils.llm_parsing import extract_json_from_llm_output

settings = Settings()
logger = get_logger(__name__)

# Constants for JIRA Issue Types
# 兼容中文环境：Jira 中实际返回的类型是中文
JIRA_BUG_TYPES = {"Bug", "缺陷"}
JIRA_REQUIREMENT_TYPES = {"Task", "任务"}
ALL_ISSUE_TYPES = JIRA_BUG_TYPES | JIRA_REQUIREMENT_TYPES

# Global cache for Knowledge Base Store to avoid reloading on every request
_GLOBAL_KB_STORE = None

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
        # 初始化为空，使用时动态获取
        self._llm_client = None
        self._current_model_id = None
        self._current_model_name = None

        self._kb_store = None
        self._kb_path = settings.KB_PDF_PATH
        # KB（知识库）相关：RAG 使用的 PDF 路径与向量索引缓存

    def _get_llm_client(self):
        """
        获取 LLM 客户端，优先使用数据库中激活的模型配置，
        如果数据库没有激活的模型，则回退到配置文件。
        同步方法。
        """
        # 尝试从数据库获取激活的模型
        db_model = None
        try:
            with SessionLocal() as session:
                stmt = select(AIModel).where(AIModel.is_active == True)
                result = session.execute(stmt)
                db_model = result.scalars().first()
        except Exception as e:
            logger.error(f"Failed to fetch AI model from DB: {e}")

        # 场景1：数据库有激活模型
        if db_model:
            # 检查是否需要切换（不仅检查 ID，还要检查关键属性是否变更）
            # 构建当前模型的指纹
            current_fingerprint = getattr(self, '_current_model_fingerprint', None)
            new_fingerprint = f"{db_model.id}-{db_model.model_name}-{db_model.api_key}-{db_model.base_url}"
            
            if current_fingerprint != new_fingerprint:
                logger.info(f"Switching to AI Model: {db_model.name} ({db_model.provider})")
                self._llm_client = OpenAI(
                    api_key=db_model.api_key,
                    base_url=db_model.base_url,
                    timeout=float(settings.LLM_TIMEOUT),
                    max_retries=1
                )
                self._current_model_id = db_model.id
                self._current_model_name = db_model.model_name
                self._current_model_fingerprint = new_fingerprint
            return self._llm_client

        # 场景2：数据库无激活模型，回退到配置文件
        # 检查是否需要切换（当前不是config模式）
        # 注意：Config 模式下不支持热重载，必须重启服务
        if getattr(self, '_current_model_id', None) != 'config':
            logger.info("Switching to default config AI Model")
            self._llm_client = OpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_API_BASE,
                timeout=float(settings.LLM_TIMEOUT),
                max_retries=1
            )
            self._current_model_id = 'config'
            self._current_model_name = settings.LLM_MODEL_NAME
            self._current_model_fingerprint = 'config'
        
        return self._llm_client

    def _get_model_name(self):
        self._get_llm_client() # Ensure client and model name are updated
        return getattr(self, '_current_model_name', settings.LLM_MODEL_NAME)

    def get_jira_issue_details(self, issue_key: str):
        """
        同步获取Jira issue详细信息的内部方法
        """
        try:
            logger.info(f"开始获取Jira issue: {issue_key}")
            issue = self.jira_client.issue(issue_key)
            logger.info(f"成功获取Jira issue: {issue_key}")
            
            # 处理附件信息，供多模态分析
            attachments_for_llm = []
            attachment_count = 0
            
            if hasattr(issue.fields, 'attachment') and issue.fields.attachment:
                attachment_count = len(issue.fields.attachment)
                logger.info(f"发现 {attachment_count} 个附件")
                
                # 根据 ENABLE_IMAGE_PROCESSING 配置决定是否处理任何附件
                if settings.ENABLE_IMAGE_PROCESSING:
                    logger.info("图片处理已启用，开始处理所有附件...")
                    
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
                                    # 检查文件大小
                                    max_size = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
                                    if len(attachment_content) > max_size:
                                        logger.warning(f"图片附件 {attachment.filename} 超过最大限制 ({settings.MAX_ATTACHMENT_SIZE_MB}MB)，跳过")
                                        continue
                                        
                                    import base64
                                    base64_content = base64.b64encode(attachment_content).decode('utf-8')
                                    attachment_info["type"] = "image"
                                    attachment_info["base64_content"] = base64_content
                                    attachment_info["description"] = f"图片文件：{attachment.filename}，可用于界面分析和功能测试"
                                    logger.info(f"成功下载并处理图片附件: {attachment.filename} (大小: {len(attachment_content)} bytes)")
                                    attachments_for_llm.append(attachment_info)
                                else:
                                    logger.warning(f"图片附件获取失败: {attachment.filename}")
                            except Exception as e:
                                logger.error(f"下载图片附件 {attachment.filename} 失败: {e}")
                        
                        # 处理文本文件
                        elif (attachment_info["mime_type"].startswith('text/') or 
                              attachment.filename.lower().endswith(('.txt', '.md', '.doc', '.docx', '.pdf', '.json', '.xml', '.csv'))):
                            try:
                                attachment_content = attachment.get()
                                if isinstance(attachment_content, bytes):
                                    # 检查文件大小
                                    max_size = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
                                    if len(attachment_content) > max_size:
                                        logger.warning(f"文本附件 {attachment.filename} 超过最大限制 ({settings.MAX_ATTACHMENT_SIZE_MB}MB)，跳过")
                                        continue
                                        
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
                                
                                logger.info(f"成功获取文本附件: {attachment.filename} (长度: {len(content_text)})")
                                attachments_for_llm.append(attachment_info)
                            except Exception as e:
                                logger.error(f"获取文本附件 {attachment.filename} 失败: {e}")
                        
                        else:
                            logger.info(f"跳过非支持文件: {attachment.filename} ({attachment_info['mime_type']})")
                    
                    logger.info(f"成功准备 {len(attachments_for_llm)} 个附件供大模型分析 (图片处理: enabled)")
                else:
                    logger.info("Image processing disabled, skipping all attachments, using text-only mode")
            
            # Fetch Linked Issues
            linked_issues = []
            if hasattr(issue.fields, 'issuelinks'):
                for link in issue.fields.issuelinks:
                    link_info = {}
                    if hasattr(link, 'outwardIssue'):
                        try:
                            issuetype_name = getattr(getattr(link.outwardIssue.fields, 'issuetype', None), 'name', None)
                        except Exception:
                            issuetype_name = None
                        link_info = {
                            "key": link.outwardIssue.key,
                            "summary": link.outwardIssue.fields.summary,
                            "type": link.type.outward,
                            "direction": "outward",
                            "issuetype": issuetype_name
                        }
                    elif hasattr(link, 'inwardIssue'):
                        try:
                            issuetype_name = getattr(getattr(link.inwardIssue.fields, 'issuetype', None), 'name', None)
                        except Exception:
                            issuetype_name = None
                        link_info = {
                            "key": link.inwardIssue.key,
                            "summary": link.inwardIssue.fields.summary,
                            "type": link.type.inward,
                            "direction": "inward",
                            "issuetype": issuetype_name
                        }
                    if link_info:
                        linked_issues.append(link_info)
                logger.info(f"Found {len(linked_issues)} linked issues")

            return {
                "summary": issue.fields.summary,
                "description": issue.fields.description,
                "status": issue.fields.status.name if hasattr(issue.fields, 'status') else 'Unknown',
                "priority": issue.fields.priority.name if hasattr(issue.fields, 'priority') else 'Unknown',
                "issuetype": issue.fields.issuetype.name if hasattr(issue.fields, 'issuetype') else 'Unknown',
                "project": issue.fields.project.key if hasattr(issue.fields, 'project') else 'Unknown',
                "resolution": issue.fields.resolution.name if hasattr(issue.fields, 'resolution') and issue.fields.resolution else None,
                "created": issue.fields.created,
                "updated": issue.fields.updated,
                "attachment_count": attachment_count,
                "attachments_for_llm": attachments_for_llm,  # 供大模型分析
                "linked_issues": linked_issues # 关联需求
            }
        except Exception as e:
            # 更详细的错误日志记录
            logger.error(f"获取Jira issue {issue_key} 失败: {e}")
            logger.error(f"错误类型: {type(e).__name__}")
            
            # 如果是超时错误，提供更具体的错误信息
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                logger.error(f"Jira连接超时，请检查网络连接或Jira服务器状态")
                return None
            
            # 如果是认证错误
            if "unauthorized" in str(e).lower() or "401" in str(e):
                logger.error(f"Jira认证失败，请检查用户名和API Token")
                return None
            
            # 如果是权限错误
            if "forbidden" in str(e).lower() or "403" in str(e):
                logger.error(f"没有访问Jira issue {issue_key} 的权限")
                return None
            
            # 如果是issue不存在
            if "not found" in str(e).lower() or "404" in str(e):
                logger.error(f"Jira issue {issue_key} 不存在")
                return None
            
            logger.error(f"其他错误: {e}")
            return None

    def generate_testcases_from_jira(self, issue_details: dict, linked_req_details: list | None = None, jira_key: str | None = None, kb_context: str | None = None):
        """
        调用大模型生成测试用例
        保留完整的需求信息及关联需求内容，确保测试用例生成的全面性和准确性
        同步方法。
        """
        # 1. 构造简洁prompt（保持稳定性）
        summary = issue_details.get('summary', 'N/A')
        description = issue_details.get('description', 'N/A')
        project_key = issue_details.get('project', 'N/A')
        
        # 2. Construct Linked Requirements Context (from pre-fetched linked_req_details)
        # linked_req_details 已在 service 层通过 linked_issues 提取并完整获取
        linked_req_context = ""
        if linked_req_details and isinstance(linked_req_details, list) and len(linked_req_details) > 0:
            linked_req_summaries = []
            for idx, linked in enumerate(linked_req_details[:5], 1):  # Max 5 linked items
                linked_summary = linked.get('summary', 'N/A')
                linked_desc = linked.get('description', 'N/A')
                linked_req_summaries.append(f"### Linked Requirement {idx}: {linked_summary}\n**Description**: {linked_desc}")
            linked_req_context = f"\n\n### Linked Requirements Context\n{chr(10).join(linked_req_summaries)}"
        
        # 3. Construct Knowledge Base Context (RAG)
        rag_context = ""
        if kb_context:
            rag_context = f"\n\n### Product Documentation / Knowledge Base\nThe following are relevant business rules or document fragments retrieved, please prioritize them when generating test cases:\n{kb_context}\n"

        # Optimized Dynamic Prompt
        
        # Load jira_skill.md as System Prompt
        skill_prompt_path = os.path.join(os.path.dirname(__file__), "../prompts/skills/jira_skill.md")
        try:
            with open(skill_prompt_path, "r", encoding="utf-8") as f:
                skill_instruction = f.read()
        except Exception as e:
            logger.warning(f"Failed to load skill prompt: {e}")
            skill_instruction = "You are a senior test engineering expert."

        # User Prompt: Coverage-first, quantity as guidance
        prompt_text = f"""### Task
Execute the "Test Case Generation" skill defined in your system instructions for the following Jira requirement.

### Primary Objective
Generate business functional test cases that are review-ready, high-value, and grounded in the provided requirement context.

### Critical Instructions
1. Focus on business flows, key rules, risks, state transitions, permissions, and meaningful exception paths.
2. Functional coverage is mandatory. Boundary, Negative, Permission/Security, Data Validation, Integration, Performance/Concurrency, and Compatibility should be included only when applicable.
3. Do not create low-value cases just to satisfy category diversity.
4. Do not invent product rules that are not supported by the requirement, attachments, linked requirements, or knowledge context.
5. If important information is missing, explicitly state the missing information or assumption in the ANALYSIS section before generating test cases.
6. Keep the analysis concise, but make sure every generated testcase is traceable to at least one analysis checkpoint.

### Output Contract
- First output SECTION 1: ANALYSIS as concise bullet points.
- Then output SECTION 2: TEST CASES as a single JSON code block with structure `{{ "testcases": [...] }}`.
- If you include coverage statistics, they must be derived from the generated testcases and must not break the JSON structure.

### Requirement Details
**Jira Key**: {jira_key}
**Summary (Task)**: {summary}
**Module**: {project_key}
**Description**: {description}
{linked_req_context}
{rag_context}
"""

        # 2. Construct Multimodal Message (Text + Image)
        content_parts: list[dict[str, str | dict[str, str]]] = [{"type": "text", "text": prompt_text}]
        
        # Add attachments to message
        attachments_for_llm = issue_details.get('attachments_for_llm', [])
        if attachments_for_llm:
            logger.info(f"Preparing to pass {len(attachments_for_llm)} attachments to LLM (ENABLE_IMAGE_PROCESSING={settings.ENABLE_IMAGE_PROCESSING})")
            
            for attachment in attachments_for_llm:
                if attachment.get('type') == 'image' and attachment.get('base64_content'):
                    # Add base64 image
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{attachment.get('mime_type', 'image/png')};base64,{attachment['base64_content']}"
                        }
                    })
                    logger.info(f"Added image attachment to multimodal message: {attachment['filename']}")
                
                elif attachment.get('type') == 'text' and attachment.get('text_content'):
                    # Add text content
                    content_parts.append({
                        "type": "text",
                        "text": f"\n\n【Attachment Content: {attachment['filename']}】\n{attachment['text_content']}"
                    })
                    logger.info(f"Added text attachment content to multimodal message: {attachment['filename']}")
        else:
            logger.info(f"Using text-only mode, no attachments")
        
        # 3. 调用多模态模型
        try:
            attachment_count = len(attachments_for_llm) if attachments_for_llm else 0
            linked_req_count = len(linked_req_details) if linked_req_details else 0
            status_info = []
            if linked_req_count > 0:
                status_info.append(f"{linked_req_count} linked requirements")
            if attachment_count > 0:
                status_info.append(f"{attachment_count} attachments (downloaded)")
            
            status_text = ", ".join(status_info) if status_info else "No historical reference"
            current_model = self._get_model_name()
            logger.info(f"Calling {current_model} multimodal test case generation, Jira Key: {jira_key}, {status_text}")
            
            client = self._get_llm_client()
            response = client.chat.completions.create(
                model=current_model,
                messages=[
                    {
                        "role": "system",
                        "content": skill_instruction
                    },
                    {"role": "user", "content": content_parts}  # type: ignore
                ],
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=0.2,
                # response_format={"type": "json_object"}  <-- REMOVED TO ALLOW CHAIN OF THOUGHT
            )
            logger.info(f"Successfully processed {current_model} response, test case generation complete")
            return response.choices[0].message.content
            
        except Exception as e:
            current_model = self._get_model_name()
            logger.error(f"Call {current_model} API failed: {e}")
            return json.dumps({
                "error": f"Call {current_model} API failed: {str(e)}"
            })

    def generate_testcases_from_interface(self, interface_details: dict):
        """
        根据接口定义生成测试用例 (同步)
        """
        try:
            current_model = self._get_model_name()
            client = self._get_llm_client()
            
            # 动态读取 testing_skill.md 作为系统 Prompt
            skill_prompt_path = os.path.join(os.path.dirname(__file__), "../prompts/skills/testing_skill.md")
            try:
                with open(skill_prompt_path, "r", encoding="utf-8") as f:
                    skill_instruction = f.read()
            except Exception as e:
                logger.warning(f"Failed to load skill prompt: {e}")
                skill_instruction = "You are a Senior QA Automation Engineer."

            prompt = f"""{skill_instruction}

            ### Task
            Design comprehensive test cases for the following interface based on the "API Test Generation" guidelines above.
            
            ### Interface Details
            {json.dumps(interface_details, ensure_ascii=False, indent=2)}

            ### Output Requirement
            1.  **MUST** return pure JSON format, structure: `{{ "testcases": [...] }}`.
            2.  **NEVER** use Markdown code blocks (like ```json ... ```).
            3.  **NEVER** include any explanatory text.
            4.  Return JSON string directly so system can parse it.
            """
            
            response = client.chat.completions.create(
                model=current_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            parsed = extract_json_from_llm_output(content)
            if isinstance(parsed, list):
                return {"testcases": parsed}
            if isinstance(parsed, dict):
                return parsed
            logger.error(f"JSON Parse Error: Unable to extract JSON from LLM content (length={len(content) if content else 0})")
            return {"error": "JSON Parse Error", "raw": content}
            
        except Exception as e:
            logger.error(f"Error generating testcases from interface: {e}")
            return {"error": str(e)}
    
    def review_requirement(self, issue_details: dict) -> str:
        """
        对 Jira 需求进行深度评审（AI Insight）。
        """
        try:
            summary = issue_details.get('summary', 'N/A')
            description = issue_details.get('description', 'N/A')
            
            # 动态读取 jira_skill.md 作为系统 Prompt
            skill_prompt_path = os.path.join(os.path.dirname(__file__), "../prompts/skills/jira_skill.md")
            try:
                with open(skill_prompt_path, "r", encoding="utf-8") as f:
                    skill_instruction = f.read()
            except Exception as e:
                logger.warning(f"Failed to load skill prompt: {e}")
                skill_instruction = "You are a QA Architect."

            prompt = f"""{skill_instruction}

            ### 任务 (Task)
            请根据上述“需求评审”的维度，对以下需求进行深度评审。

            ### 需求详情 (Requirement Details)
            **摘要**: {summary}
            **描述**: {description}

            ### 输出 (Output)
            请使用中文 Markdown 格式提供结构化的评审报告。
            """
            
            current_model = self._get_model_name()
            client = self._get_llm_client()
            
            response = client.chat.completions.create(
                model=current_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Requirement review failed: {e}")
            return f"需求评审失败: {str(e)}"

    def query_kb(self, query: str, top_k: int = 3):
        """
        RAG 核心方法：检索知识库并生成答案
        同步方法。
        """
        if not PyPDFLoader:
            return {"answer": "RAG 相关依赖未安装，请联系管理员", "sources": []}
            
        try:
            # 1. 加载并初始化向量存储（如果尚未初始化）
            if not self._kb_store:
                if not os.path.exists(self._kb_path):
                    return {"answer": "知识库文件不存在", "sources": []}
                
                logger.info(f"正在初始化知识库索引: {self._kb_path}")
                self._init_kb_store()
                logger.info("知识库索引初始化完成")

            # 2. 检索相关文档
            docs = self._kb_store.similarity_search(query, k=top_k)
            
            # 3. 构造增强上下文
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # 4. 调用 LLM 生成基于知识库的回答
            # 动态读取 knowledge_skill.md 作为系统 Prompt，保持协议一致性
            current_model = self._get_model_name()
            skill_prompt_path = os.path.join(os.path.dirname(__file__), "../prompts/skills/knowledge_skill.md")
            
            try:
                with open(skill_prompt_path, "r", encoding="utf-8") as f:
                    skill_instruction = f.read()
            except Exception as e:
                logger.warning(f"Failed to load skill prompt: {e}, falling back to default.")
                skill_instruction = "请基于提供的上下文回答问题。"

            prompt = f"""{skill_instruction}

            ### 上下文 (Context)
            {context}

            ### 问题 (Question)
            {query}
            
            ### 回答 (Answer):"""

            client = self._get_llm_client()
            response = client.chat.completions.create(
                model=current_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1  # 降低随机性，确保基于事实
            )
            
            answer = response.choices[0].message.content
            sources = [{"content": doc.page_content, "metadata": doc.metadata} for doc in docs]
            
            return {"answer": answer, "sources": sources}
            
        except Exception as e:
            logger.error(f"KB Query failed: {e}")
            return {"answer": f"知识库检索失败: {str(e)}", "sources": []}

    def _init_kb_store(self):
        """
        同步初始化知识库，使用全局缓存
        """
        global _GLOBAL_KB_STORE
        
        if _GLOBAL_KB_STORE is not None:
            self._kb_store = _GLOBAL_KB_STORE
            return

        loader = PyPDFLoader(self._kb_path)
        docs = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)
        
        # 使用多语言模型，对中文 Jira 查询和中文 PDF 内容都能正确理解
        # paraphrase-multilingual-MiniLM-L12-v2 已缓存，无需重新下载（约 470MB）
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        _GLOBAL_KB_STORE = FAISS.from_documents(splits, embeddings)
        self._kb_store = _GLOBAL_KB_STORE


    def get_bug_fix_duration(self, jira_key: str):
        try:
            issue = self.jira_client.issue(jira_key, expand='changelog')
            created = datetime.strptime(issue.fields.created, '%Y-%m-%dT%H:%M:%S.%f%z')
            
            testing_time = None
            for history in issue.changelog.histories:
                for item in history.items:
                    if item.field == 'status' and item.toString in ['Testing', 'In Testing', 'QA', 'Ready for QA', '测试中']:
                        testing_time = datetime.strptime(history.created, '%Y-%m-%dT%H:%M:%S.%f%z')
                        break
                if testing_time: break
            
            result = {
                "summary": issue.fields.summary,
                "status": issue.fields.status.name,
                "created_at": created.strftime('%Y-%m-%d %H:%M'),
            }
            
            if testing_time:
                duration = testing_time - created
                result.update({
                    "testing_at": testing_time.strftime('%Y-%m-%d %H:%M'),
                    "testing_status_reached": "Yes",
                    "duration_readable": str(duration).split('.')[0]
                })
            else:
                result["message"] = "Bug 尚未进入测试状态。"
            return result
        except Exception as e:
            logger.error(f"Error in get_bug_fix_duration: {e}")
            return {"error": str(e)}

    def _search_jql_v3(self, jql: str, max_results: int = 50, fields: str = "*all", expand: list = None):
        """
        替代 jira_client.search_issues，使用 v3 search/jql 接口 (POST)
        解决 JiraError HTTP 410: The requested API has been removed. Please migrate to /rest/api/3/search/jql API.
        支持分页获取，并去重。
        """
        # 确保 server URL 没有尾部斜杠
        base_url = self.jira_client._options['server'].rstrip('/')
        # 修复：必须使用 /rest/api/3/search/jql，旧的 /search 已被移除 (HTTP 410)
        url = f"{base_url}/rest/api/3/search/jql"
        
        # 处理 fields 参数，POST 接口通常需要列表
        if isinstance(fields, str):
            field_list = [f.strip() for f in fields.split(',')]
        else:
            field_list = fields

        # 场景1：仅获取总数
        if max_results == 0:
            payload = {
                "jql": jql,
                "maxResults": 1,
                "fields": ["id"]
            }
            # 使用 POST 请求以避免 URL 长度限制和参数兼容性问题
            response = self.jira_client._session.post(url, json=payload)
            if response.status_code >= 400:
                raise Exception(f"Jira JQL Error {response.status_code}: {response.text}")
            
            return response.json()
            
        # 场景2：获取 Issue 列表（带分页）
        all_issues = []
        seen_ids = set() # 用于去重
        next_token = None
        batch_size = 100  # Jira Cloud 通常限制单次最大 100
        
        while True:
            # 计算本次需要拉取的数量
            remaining = max_results - len(all_issues)
            if remaining <= 0:
                break
            
            current_limit = min(batch_size, remaining)
            
            payload = {
                "jql": jql,
                "maxResults": current_limit,
                "fields": field_list
            }
            if expand:
                # 修复：search/jql 接口的 expand 参数要求是 string (comma-separated)，而不是 list
                # 之前的 400 Invalid request payload 可能是因为这里传了 list
                if isinstance(expand, list):
                    payload["expand"] = ",".join(expand)
                else:
                    payload["expand"] = expand

            # 优先使用 nextPageToken 进行分页 (Jira Cloud v3 search/jql 推荐方式)
            if next_token:
                payload["nextPageToken"] = next_token
            
            response = self.jira_client._session.post(url, json=payload)
            if response.status_code >= 400:
                raise Exception(f"Jira JQL Error {response.status_code}: {response.text}")
            
            data = response.json()
            issues = data.get('issues', [])
            
            # 去重处理
            new_issues = []
            for issue in issues:
                issue_id = issue.get('id')
                if issue_id and issue_id not in seen_ids:
                    seen_ids.add(issue_id)
                    new_issues.append(issue)
            
            all_issues.extend(new_issues)
            
            # 如果没有获取到数据，则结束
            if not issues:
                break

            # 使用 nextPageToken 判断是否还有下一页
            next_token = data.get("nextPageToken")
            if not next_token:
                break
             
        return {"issues": all_issues, "total": len(all_issues)}

    def get_jira_statistics(self, project_key: str, fix_versions: list = None, start_date=None, end_date=None):
        try:
            base_jql = f"project = {project_key}"
            if fix_versions:
                v_str = ",".join([f"'{v}'" for v in fix_versions])
                base_jql += f" AND fixVersion in ({v_str})"
            if start_date:
                 base_jql += f" AND created >= '{start_date}'"
            if end_date:
                 base_jql += f" AND created <= '{end_date}'"
            
            # 安全兜底：如果未指定版本且未指定时间，默认仅查询最近 90 天
            if not fix_versions and not (start_date or end_date):
                base_jql += " AND created >= -90d"

            # 拉取所有相关 issue 的 status 字段进行内存聚合统计
            resp = self._search_jql_v3(base_jql, max_results=10000, fields="status")
            issues = resp.get("issues", [])
            total = len(issues)
            
            status_dist = {}
            for issue in issues:
                status_name = issue.get('fields', {}).get('status', {}).get('name', 'Unknown')
                status_dist[status_name] = status_dist.get(status_name, 0) + 1
            
            return {
                "project": project_key,
                "fix_versions": fix_versions,
                "total_issues": total,
                "status_distribution": status_dist
            }
        except Exception as e:
            logger.error(f"Error in get_jira_statistics: {e}")
            return {"error": str(e)}

    def _count_issues_jql(self, jql: str) -> int:
        """
        通过拉取所有 issue ID 来统计总数。
        解决 Jira Cloud v3 search/jql 接口不返回 total 字段的问题。
        """
        try:
            # 限制最大 100000 条，避免内存溢出。通常单次查询不会超过这个数。
            # 仅获取 id 字段以最小化传输量
            data = self._search_jql_v3(jql, max_results=100000, fields="id")
            return len(data.get("issues", []))
        except Exception as e:
            logger.error(f"Error counting issues for JQL '{jql}': {e}")
            return 0

    def _to_jql_list(self, values: list) -> str:
        """
        Helper to format a list of strings for JQL IN clause.
        Escapes double quotes and wraps items in double quotes.
        """
        if not values:
            return ""
        escaped_values = [v.replace('"', '\\"') for v in values]
        return ",".join([f'"{v}"' for v in escaped_values])

    def _filter_versions(self, versions: list, start_date=None, end_date=None, version_type: str = "all", limit: int = None, default_limit: int = 15):
        """
        Helper to filter versions based on date, type, and limit.
        """
        # 1. Basic Validation
        valid_versions = [v for v in versions if getattr(v, 'releaseDate', None)]
        valid_versions.sort(key=lambda x: x.releaseDate)

        # 2. Filter by Type
        filtered_by_type = []
        import re
        official_pattern = re.compile(r'^\d+\.\d+\.0$')
        
        for v in valid_versions:
            v_name = v.name.strip()
            is_official = bool(official_pattern.match(v_name))
            
            if version_type == "official" and not is_official: continue
            if version_type == "patch" and is_official: continue
            filtered_by_type.append(v)
        
        valid_versions = filtered_by_type

        # 3. Filter by Date or Limit
        target_versions = []
        if limit:
            # If limit is specified, take last N versions
            if start_date or end_date:
                # If date is also specified, apply date filter first
                temp = []
                for v in valid_versions:
                    v_date = getattr(v, 'releaseDate', None)
                    if not v_date: continue
                    if start_date and v_date < start_date: continue
                    if end_date and v_date > end_date: continue
                    temp.append(v)
                target_versions = temp[-limit:]
            else:
                target_versions = valid_versions[-limit:]
        elif start_date or end_date:
            # Only filter by date
            for v in valid_versions:
                v_date = getattr(v, 'releaseDate', None)
                if not v_date: continue
                if start_date and v_date < start_date: continue
                if end_date and v_date > end_date: continue
                target_versions.append(v)
        else:
            # Default: take last N versions
            target_versions = valid_versions[-default_limit:]
            
        return target_versions

    def _get_filtered_versions(self, project_key: str, start_date=None, end_date=None, version_type: str = "all", fix_versions: list = None, limit: int = None, default_limit: int = 15):
        """
        Orchestrator to get and filter versions for a project.
        """
        # 1. Get all versions
        all_versions = self.jira_client.project_versions(project_key)
        
        # 2. Pre-filter by fix_versions if provided (before sorting/date check)
        if fix_versions:
            all_versions = [v for v in all_versions if v.name in fix_versions]
            
        # 3. Apply common filtering logic
        return self._filter_versions(
            all_versions, 
            start_date=start_date, 
            end_date=end_date, 
            version_type=version_type, 
            limit=limit,
            default_limit=default_limit
        )

    def get_project_bug_distribution(self, project_key: str, start_date=None, end_date=None, fix_versions=None, version_type="all"):
        try:
            bug_types_str = self._to_jql_list(list(JIRA_BUG_TYPES))
            jql = f"project = {project_key} AND issuetype in ({bug_types_str})"
            if start_date:
                jql += f" AND created >= '{start_date}'"
            if end_date:
                jql += f" AND created <= '{end_date}'"
            
            # Handle version_type logic if fix_versions is not explicitly provided
            if not fix_versions and version_type and version_type != "all":
                # Use helper to get versions based on type (limit=None to get all matching types)
                target_versions = self._get_filtered_versions(
                    project_key, 
                    version_type=version_type, 
                    limit=None,
                    default_limit=999 # Get all matching types if no limit
                )
                if target_versions:
                    fix_versions = [v.name for v in target_versions]
            
            if fix_versions:
                versions_str = self._to_jql_list(fix_versions)
                jql += f" AND fixVersion in ({versions_str})"
            
            # 增加 limit 到 10000 以避免数据截断 (用户反馈 1000 条限制)
            data = self._search_jql_v3(jql, max_results=10000, fields="components,priority")
            issues = data.get('issues', [])
            
            modules = {}
            severity = {}
            
            for issue in issues:
                fields = issue.get('fields', {})
                comps = fields.get('components', [])
                if not comps:
                    modules["Unassigned"] = modules.get("Unassigned", 0) + 1
                else:
                    for c in comps:
                        name = c.get('name', 'Unknown')
                        modules[name] = modules.get(name, 0) + 1
                
                priority_obj = fields.get('priority')
                p = priority_obj.get('name', 'Unknown') if priority_obj else "Unknown"
                severity[p] = severity.get(p, 0) + 1
            
            return {
                "project": project_key,
                "fix_versions": fix_versions,
                "total_bugs": len(issues),
                "items": [{"module": k, "bug_count": v} for k, v in modules.items()],
                "bug_severity": [{"name": k, "count": v} for k, v in severity.items()],
                "bugs": [] # Schema 需要此字段，暂返回空列表以减少传输量
            }
        except Exception as e:
            return {"error": str(e)}

    def get_project_version_trend(self, project_key: str, start_date=None, end_date=None, version_type: str = "all", fix_versions: list = None, limit: int = None):
        try:
            # Use helper to get and filter versions
            target_versions = self._get_filtered_versions(
                project_key, 
                start_date=start_date, 
                end_date=end_date, 
                version_type=version_type, 
                fix_versions=fix_versions,
                limit=limit
            )
            
            if not target_versions:
                 return {"items": []}
                
            # 初始化数据结构
            version_map = {
                v.name: {
                    "bug": 0, 
                    "story": 0, 
                    "releaseDate": getattr(v, 'releaseDate', None),
                    "released": getattr(v, 'released', False)
                } 
                for v in target_versions
            }
            # 保持排序顺序的名称列表
            version_names = [v.name for v in target_versions]
            
            # 3. 批量查询 (Batch Query)
            # 构造 JQL 一次性拉取所有数据，避免 N+1 查询导致 API 耗时过长
            v_names = [v.name for v in target_versions]
            versions_str = self._to_jql_list(v_names)
            
            # 使用预定义的常量包含所有相关类型
            all_types_str = self._to_jql_list(list(ALL_ISSUE_TYPES))
            jql = f"project = {project_key} AND fixVersion in ({versions_str}) AND issuetype in ({all_types_str})"
            
            # 拉取字段：fixVersions, issuetype
            # 限制 5000 条，通常 15 个版本的 Bug+Story 不会超过此数。如果超过，可能需要分页，但此处暂作简化。
            issues_resp = self._search_jql_v3(jql, max_results=5000, fields="fixVersions,issuetype")
            issues = issues_resp.get("issues", [])
            
            # 4. 内存聚合
            for issue in issues:
                fields = issue.get("fields", {})
                itype = fields.get("issuetype", {}).get("name")
                # 一个 Issue 可能对应多个 Fix Version
                fix_versions_field = fields.get("fixVersions", [])
                
                for fv in fix_versions_field:
                    v_name = fv.get("name")
                    # 只统计我们在目标范围内的版本
                    if v_name in version_map:
                        if itype in JIRA_BUG_TYPES:
                            version_map[v_name]["bug"] += 1
                        elif itype in JIRA_REQUIREMENT_TYPES:
                            version_map[v_name]["story"] += 1
            
            # 5. 格式化输出
            trend_data = []
            for v_name in version_names:
                data = version_map[v_name]
                trend_data.append({
                    "version": v_name,
                    "releaseDate": data["releaseDate"],
                    "released": data["released"],
                    "bug_count": data["bug"],
                    "demand_count": data["story"]
                })
                
            return {"items": trend_data}
            
        except Exception as e:
            logger.error(f"Error in get_project_version_trend: {e}")
            return {"error": str(e)}

    def get_project_fix_versions(self, project_key: str):
        try:
            versions = self.jira_client.project_versions(project_key)
            return [
                {
                    "name": v.name, 
                    "id": getattr(v, 'id', None),
                    "released": getattr(v, 'released', False), 
                    "archived": getattr(v, 'archived', False),
                    "releaseDate": getattr(v, 'releaseDate', None)
                } 
                for v in versions
            ]
        except Exception as e:
            logger.error(f"Error getting project versions: {e}")
            return {"error": str(e)}

    def get_version_regression_status(self, project_key: str, versions: list = None):
        try:
            results = []
            if not versions:
                target_versions = self._get_filtered_versions(project_key, limit=3, default_limit=3)
                # Sort descending to match original behavior (latest first)
                target_versions.sort(key=lambda x: getattr(x, 'releaseDate', '9999') or '9999', reverse=True)
                versions = [v.name for v in target_versions]
            
            for v in versions:
                # 1. 计算重新打开的 Bug 数 (Currently Reopened)
                # 定义：当前状态为"Reopened"或"重新打开"的 Bug
                reopened_statuses = '"Reopened", "重新打开"'
                not_resolved_statuses = '"Closed", "Resolved", "Done", "已关闭", "已解决"'
                
                # JQL: 在当前版本 & 是Bug & 状态是 Reopened
                bug_types_str = self._to_jql_list(list(JIRA_BUG_TYPES))
                jql_reopened = f"project = {project_key} AND fixVersion = '{v}' AND issuetype in ({bug_types_str}) AND status in ({reopened_statuses})"
                
                reopened_count = self._count_issues_jql(jql_reopened)
                
                # 2. 计算未解决的 Bug 数
                jql_open = f"project = {project_key} AND fixVersion = '{v}' AND issuetype in ({bug_types_str}) AND status not in ({not_resolved_statuses})"
                open_count = self._count_issues_jql(jql_open)
                
                results.append({
                    "version": v,
                    "reopened_bugs": reopened_count,
                    "open_bugs": open_count,
                    "status": "Stable" if open_count == 0 else "Unstable"
                })
            return results
        except Exception as e:
            return {"error": str(e)}

    def get_version_member_cycle_time(self, project_key: str, versions: list = None, start_date=None, end_date=None):
        """
        计算指定版本中各负责人的平均 Bug 周转时长（Cycle Time）。
        逻辑更新：
        1. 目标状态（Fix）：Resolved, Closed, Done, Testing, Ready for QA
        2. 起始状态（Start）：Last 'Open', 'Reopened', 'To Do' before Fix
        3. 时长 = Fix Time - Start Time
        4. 负责人 = Fix Action Author (若无则回退到 Assignee)
        """
        try:
            # 1. 构造查询 JQL
            # 状态范围：必须是已解决或进入测试流程的
            bug_types_str = self._to_jql_list(list(JIRA_BUG_TYPES))
            base_jql = f"project = {project_key} AND issuetype in ({bug_types_str}) AND status in (Resolved, Closed, Done, Testing, 'In Testing', 'Ready for QA')"
            if versions:
                v_str = self._to_jql_list(versions)
                base_jql += f" AND fixVersion in ({v_str})"
            
            if start_date:
                base_jql += f" AND created >= '{start_date}'"
            if end_date:
                base_jql += f" AND created <= '{end_date}'"
            
            # 2. 获取数据 (需要 changelog)
            # 减少 max_results 以防超时，或者依赖分页
            resp = self._search_jql_v3(base_jql, max_results=2000, fields="assignee,created,status", expand=["changelog"])
            issues = resp.get("issues", [])
            
            member_stats = {}
            
            # 定义状态集合
            # 排除 Closed/Done 以准确捕捉 "转到测试状态" (Dev -> QA) 的时间点，而非 QA 验证结束的时间点
            FIX_STATUSES = {'Resolved', 'Testing', 'In Testing', 'Ready for QA', '已解决', '待测试', '测试中'}
            # 优化：加入 In Progress 相关状态，以便更精准地找到开发开始时间 (T_Start)
            OPEN_STATUSES = {'Open', 'Reopened', 'To Do', 'New', '打开', '重新打开', '新建', '待办', 'In Progress', 'Processing', '处理中', '进行中', '开发中'}
            # 排除的机器人账号 (避免将自动化操作归属为机器人)
            EXCLUDED_BOTS = {'Jira Automation', 'Automation for Jira', 'System', 'gitlab-bot', 'jenkins', 'Gino Bot', 'System user'}
            
            for issue in issues:
                issue_id = issue.get("id")
                fields = issue.get("fields", {})
                created_str = fields.get("created")
                
                # 默认值
                fix_time = None
                start_time = None
                resolver = None
                starter = None # T_Start 时刻的操作人，作为归属兜底
                
                # 解析 Changelog
                changelog = issue.get("changelog", {})
                histories = changelog.get("histories", [])
                
                # 按时间正序排列
                sorted_histories = sorted(histories, key=lambda x: x.get("created", ""))
                
                # 1. 寻找第一次进入 FIX_STATUSES 的时间 (T_fix_first)
                # 用户定义：第一次转到测试状态的时间
                for history in sorted_histories:
                    for item in history.get("items", []):
                        if item.get("field") == "status":
                            to_string = item.get("toString", "")
                            if to_string in FIX_STATUSES:
                                fix_time = datetime.strptime(history.get("created"), '%Y-%m-%dT%H:%M:%S.%f%z')
                                # 更新解决人 (使用第一次转测试的操作人，排除机器人)
                                author = history.get("author", {})
                                r_name = author.get("displayName") or author.get("name")
                                if r_name and r_name not in EXCLUDED_BOTS:
                                    resolver = r_name
                                break # 找到第一次就退出
                    if fix_time:
                        break # 找到第一次就退出
                
                # 如果找不到 Fix 记录，可能 Issue 一开始就是 Resolved（极少见）或数据问题
                if not fix_time:
                    continue 

                # 2. 寻找 T_fix_first 之前的最后一次进入 In Progress (T_start)
                # 用户定义：更准确的开始时间是 "开发把打开状态变为 In Progress"
                # 因此，我们寻找最近一次变为 "In Progress" 类状态的时间点
                last_inprogress_time = None
                
                # 定义仅包含 "进行中" 的状态集，用于精确捕捉开发开始
                IN_PROGRESS_STATUSES = {'In Progress', 'Processing', '处理中', '进行中', '开发中'}
                
                for history in sorted_histories:
                    h_time = datetime.strptime(history.get("created"), '%Y-%m-%dT%H:%M:%S.%f%z')
                    if h_time >= fix_time:
                        break
                    
                    for item in history.get("items", []):
                        if item.get("field") == "status":
                            to_string = item.get("toString", "")
                            if to_string in IN_PROGRESS_STATUSES:
                                last_inprogress_time = h_time
                                # 记录 T_Start 的操作人
                                author = history.get("author", {})
                                s_name = author.get("displayName") or author.get("name")
                                if s_name and s_name not in EXCLUDED_BOTS:
                                    starter = s_name
                
                if last_inprogress_time:
                    start_time = last_inprogress_time
                else:
                    # 如果没有找到 In Progress 记录 (可能直接 Open -> Resolved)，则退化为找最近的 Open
                    # 再次遍历
                    last_open_time = None
                    for history in sorted_histories:
                        h_time = datetime.strptime(history.get("created"), '%Y-%m-%dT%H:%M:%S.%f%z')
                        if h_time >= fix_time:
                            break
                        for item in history.get("items", []):
                            if item.get("field") == "status":
                                to_string = item.get("toString", "")
                                if to_string in OPEN_STATUSES:
                                     # 这里 OPEN_STATUSES 包含了 Open, Reopened 等
                                     # 注意：此时 OPEN_STATUSES 也包含了 In Progress (上一轮修改加的)，
                                     # 但因为上面优先找了 IN_PROGRESS_STATUSES，这里作为兜底没问题
                                    last_open_time = h_time
                    
                    if last_open_time:
                        start_time = last_open_time
                    elif created_str:
                        start_time = datetime.strptime(created_str, '%Y-%m-%dT%H:%M:%S.%f%z')
                    # 如果用了创建时间，starter 可以尝试用 Reporter 或者保持 None
                    # 这里保持 None，后续逻辑会 fallback 到 assignee

                # 计算时长
                if start_time and fix_time and start_time < fix_time:
                        duration_hours = (fix_time - start_time).total_seconds() / 3600
                        
                        # 确定归属人逻辑：
                        # 1. 优先 (Priority)：转为 Testing/Resolved 状态的人 (Resolver)
                        #    - 这是用户指定的"转为测试状态的人"，最能代表修复者
                        # 2. 次要：转为 In Progress 状态的人 (Starter)
                        #    - 如果 Resolver 是机器人或没找到，则找谁开始做的
                        # 3. 兜底：当前 Assignee
                        final_assignee = resolver
                        
                        if not final_assignee:
                            final_assignee = starter
                            
                        if not final_assignee or final_assignee == "Unassigned":
                            assignee_field = fields.get("assignee")
                            if assignee_field:
                                a_name = assignee_field.get("displayName")
                                if a_name not in EXCLUDED_BOTS: # Assignee 也要防一手机器人
                                    final_assignee = a_name
                            
                        if not final_assignee:
                             final_assignee = "Unassigned"
                    
                        # 记录数据
                        if final_assignee not in member_stats:
                            member_stats[final_assignee] = {"count": 0, "total_hours": 0, "max_hours": 0, "min_hours": 999999}
                        
                        ms = member_stats[final_assignee]
                        ms["count"] += 1
                        ms["total_hours"] += duration_hours
                        ms["max_hours"] = max(ms["max_hours"], duration_hours)
                        ms["min_hours"] = min(ms["min_hours"], duration_hours)

            # 4. 格式化输出
            result_list = []
            for name, stats in member_stats.items():
                if stats["count"] == 0: continue
                # 再次过滤，以防万一
                if name in EXCLUDED_BOTS: continue
                avg_hours = stats["total_hours"] / stats["count"]
                
                result_list.append({
                    "assignee": name,
                    "bug_count": stats["count"],
                    "avg_cycle_time_hours": round(avg_hours, 1),
                    "avg_cycle_time_days": round(avg_hours / 24, 1),
                    "max_cycle_time_days": round(stats["max_hours"] / 24, 1),
                    "min_cycle_time_days": round(stats["min_hours"] / 24, 1)
                })
            
            result_list.sort(key=lambda x: x["avg_cycle_time_hours"], reverse=True)
            
            return {
                "project": project_key,
                "versions": versions,
                "member_cycle_time": result_list
            }

        except Exception as e:
            logger.error(f"Error in get_version_member_cycle_time: {e}")
            return {"error": str(e)}



    def get_jira_insight(self, project_key, versions=None, **kwargs):
        results = {}
        try:
            # Extract flags with defaults (matching schema)
            include_statistics = kwargs.get('include_statistics', True)
            include_regression = kwargs.get('include_regression', True)
            include_distribution = kwargs.get('include_distribution', True)
            include_cycle_time = kwargs.get('include_cycle_time', True)

            # 1. Statistics
            if include_statistics:
                results["statistics"] = self.get_jira_statistics(project_key, versions)
            
            # 2. Regression
            if include_regression:
                results["regression"] = self.get_version_regression_status(project_key, versions)

            # 3. Distribution (Module/Severity)
            if include_distribution:
                results["distribution"] = self.get_project_bug_distribution(project_key, fix_versions=versions)

            # 4. Cycle Time (Placeholder for now)
            if include_cycle_time:
                 results["cycle_time"] = self.get_version_member_cycle_time(project_key, versions)

            return results
        except Exception as e:
            return {"error": str(e)}

ai_service = AIService()
