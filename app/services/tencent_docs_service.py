from typing import List, Dict, Any, Optional, Tuple
import re
import json
import asyncio
import csv
import io
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TencentDocsService:
    """
    Tencent Docs MCP 工具调用服务。
    通过 langchain_mcp_adapters 加载腾讯文档 MCP Server，
    调用 smartsheet 工具获取测试用例数据并转换为目标格式。
    """

    def __init__(self):
        self._tools: Optional[List[Any]] = None

    async def _get_mcp_connection(self) -> Optional[Dict[str, Any]]:
        """从数据库获取腾讯文档 MCP Server 配置"""
        try:
            from sqlalchemy import select
            from app.database import async_session_maker
            from app.models.mcp_server import MCPServer

            async with async_session_maker() as session:
                result = await session.execute(
                    select(MCPServer).where(MCPServer.enabled == True)
                )
                server = result.scalars().first()

            if not server:
                logger.warning("未找到启用的腾讯文档 MCP Server")
                return None

            if server.transport == "stdio":
                return {
                    "transport": "stdio",
                    "command": server.command,
                    "args": server.args or [],
                    "env": server.env or {},
                }
            elif server.transport in ("http", "sse"):
                conn: Dict[str, Any] = {"transport": server.transport, "url": server.url}
                if server.headers:
                    conn["headers"] = server.headers
                return conn
            return None
        except Exception as e:
            logger.error(f"加载腾讯文档 MCP Server 失败: {e}")
            return None

    async def _load_tools_async(self) -> List[Any]:
        """异步加载 MCP 工具"""
        if self._tools is not None:
            return self._tools

        connection = await self._get_mcp_connection()
        if not connection:
            raise RuntimeError(
                "未找到腾讯文档 MCP Server 配置，请先在 MCP Server 页面配置并启用腾讯文档服务"
            )

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError:
            raise RuntimeError(
                "langchain-mcp-adapters 未安装，请运行: pip install langchain-mcp-adapters"
            )

        client = MultiServerMCPClient({"tencent-docs": connection})
        self._tools = await client.get_tools()
        logger.info(f"MCP 工具列表: {[t.name for t in self._tools]}")
        return self._tools

    async def _call_tool_with_retry(self, tool: Any, input_dict: Dict[str, Any], retries: int = 2) -> Any:
        """带重试的工具调用，自动处理 MCP 返回的 text 解析"""
        for attempt in range(retries + 1):
            try:
                result = await tool.ainvoke(input_dict)
                if isinstance(result, list) and result:
                    raw = result[0]
                    if isinstance(raw, dict) and raw.get("type") == "text":
                        return json.loads(raw["text"])
                return result
            except Exception as e:
                if attempt < retries and "ReadFrame" in str(e):
                    logger.warning(f"MCP 调用失败（尝试 {attempt + 1}/{retries}）: {e}")
                    await asyncio.sleep(1)
                    continue
                raise

    async def list_tables(self, file_id: str) -> List[Dict[str, Any]]:
        """列出文档中的所有 Sheet（使用 sheet.get_sheet_info，返回所有子表）"""
        tools = await self._load_tools_async()
        for tool in tools:
            if tool.name == "sheet.get_sheet_info":
                data = await self._call_tool_with_retry(tool, {"file_id": file_id})
                logger.info(f"list_tables (sheet.get_sheet_info) raw: {data}")
                if isinstance(data, dict):
                    sheets = data.get("sheets", [])
                    logger.info(f"list_tables 解析后 sheets: {sheets}")
                    return sheets
                return data if isinstance(data, list) else []
        raise ValueError(
            f"未找到 sheet.get_sheet_info 工具，可用工具: {[t.name for t in tools]}"
        )

    async def resolve_sheet_from_url(self, file_id: str, tab_value: str) -> Dict[str, str]:
        """
        通过 tab 参数找到腾讯文档中对应 sheet 的正确内部 sheet_id。
        腾讯文档的 tab 参数是 URL hash，需通过 list_tables 匹配。
        """
        sheets = await self.list_tables(file_id)
        logger.info(f"resolve_sheet: tab={tab_value}, 可用 sheets: {[s.get('sheet_name') for s in sheets]}")

        # 精确匹配 sheet_id
        for s in sheets:
            sid = s.get("sheet_id", "")
            if tab_value == sid or tab_value == sid.replace("ss_", ""):
                logger.info(f"通过 sheet_id 匹配到: {s.get('sheet_name')} ({sid})")
                return {"sheet_id": sid, "title": s.get("sheet_name", ""), "sheet_type": s.get("sheet_type", "worksheet"),
                        "col_count": s.get("col_count"), "row_count": s.get("row_count")}

        # 模糊匹配：sheet_name 前缀
        tab_lower = tab_value.lower()
        for s in sheets:
            name = s.get("sheet_name", "").lower().replace(" ", "")
            if name and tab_lower.startswith(name[:min(4, len(name))]):
                logger.info(f"通过 sheet_name 前缀匹配到: {s.get('sheet_name')} ({s.get('sheet_id')})")
                return {"sheet_id": s["sheet_id"], "title": s.get("sheet_name", ""), "sheet_type": s.get("sheet_type", "worksheet"),
                        "col_count": s.get("col_count"), "row_count": s.get("row_count")}

        # 按 index 匹配（tab 是纯数字）
        try:
            idx = int(tab_value)
            if 0 <= idx < len(sheets):
                s = sheets[idx]
                logger.info(f"按索引匹配到: {s.get('sheet_name')}")
                return {"sheet_id": s["sheet_id"], "title": s.get("sheet_name", ""), "sheet_type": s.get("sheet_type", "worksheet"),
                        "col_count": s.get("col_count"), "row_count": s.get("row_count")}
        except ValueError:
            pass

        # 如果只有一个 sheet，检查 tab 是否已经和它匹配；不匹配则直接用 tab 作为 sheet_id 尝
        # 试（腾讯文档 MCP 的 smartsheet.list_tables 有时会漏掉非首屏的 sheet）
        if len(sheets) == 1:
            single_sheet = sheets[0]
            name_hint = single_sheet.get("sheet_name", "").lower().replace(" ", "")[:4]
            if not name_hint or tab_lower != name_hint:
                logger.warning(
                    f"list_tables 只返回一个 sheet({single_sheet.get('sheet_name')})，"
                    f"但 tab={tab_value} 不匹配，尝试直接用 tab 作为 sheet_id"
                )
                return {"sheet_id": tab_value, "title": f"tab:{tab_value}", "sheet_type": "worksheet",
                        "col_count": None, "row_count": None}

        # fallback 到第一个 sheet
        s = sheets[0] if sheets else {"sheet_id": tab_value, "title": f"tab:{tab_value}"}
        logger.warning(f"无法精确匹配 tab={tab_value}，fallback 到: {s}")
        return {"sheet_id": s.get("sheet_id", tab_value), "title": s.get("sheet_name", f"tab:{tab_value}"),
                "sheet_type": s.get("sheet_type", "worksheet"),
                "col_count": s.get("col_count"), "row_count": s.get("row_count")}

    async def resolve_doc_url(self, url: str) -> Dict[str, str]:
        """
        从完整 URL 中解析 file_id 和正确的 sheet_id。
        URL 格式: https://docs.qq.com/sheet/DSVNDeERaUnpSc1VF?u=xxx&tab=f6ilfw
        file_id 从路径提取，sheet_id 通过 list_tables 解析 tab 参数获得。
        """
        file_id_match = re.search(r"docs\.qq\.com/sheet/([A-Za-z0-9]+)", url)
        file_id = file_id_match.group(1) if file_id_match else ""

        tab_match = re.search(r"[?&]tab=([A-Za-z0-9]+)", url)
        tab_value = tab_match.group(1) if tab_match else ""

        if not file_id:
            raise ValueError(f"无法从 URL 中提取文档 ID: {url}")

        sheet_info = await self.resolve_sheet_from_url(file_id, tab_value)
        logger.warning(f"===== RESOLVE_DOC_URL ===== sheet_info={sheet_info}")
        logger.info(f"URL 解析: file_id={file_id}, sheet_id={sheet_info['sheet_id']}, title={sheet_info['title']}, type={sheet_info.get('sheet_type')}")
        return {
            "file_id": file_id,
            "sheet_id": sheet_info["sheet_id"],
            "sheet_title": sheet_info["title"],
            "sheet_type": sheet_info.get("sheet_type", "worksheet"),
            "col_count": sheet_info.get("col_count"),
            "row_count": sheet_info.get("row_count"),
        }

    async def get_content_via_mcp(self, file_id: str) -> str:
        """用 get_content 工具获取文档原始文本"""
        tools = await self._load_tools_async()
        tool = next((t for t in tools if t.name == "get_content"), None)
        if not tool:
            raise ValueError("未找到 get_content 工具")
        data = await self._call_tool_with_retry(tool, {"file_id": file_id})
        if isinstance(data, dict):
            content = data.get("content", "")
        else:
            content = str(data)
        logger.info(f"[get_content_via_mcp] 获取内容长度: {len(content)}")
        return content

    async def smartcanvas_read_content(self, file_id: str, jira_id: Optional[str] = None) -> List[Dict[str, str]]:
        """
        使用 smartcanvas_read 获取文档全文内容（markdown 格式），解析其中的表格数据。
        适用于 worksheet/smartsheet 等所有类型，是 sheet API 失败时的兜底方案。
        """
        tools = await self._load_tools_async()
        tool = next((t for t in tools if t.name == "smartcanvas.read"), None)
        if not tool:
            raise ValueError("未找到 smartcanvas.read 工具")

        all_content = ""
        next_token = None
        page_count = 0
        while True:
            params: Dict[str, Any] = {"file_id": file_id}
            if next_token:
                params["next_token"] = next_token
            data = await self._call_tool_with_retry(tool, params)
            page_count += 1
            if isinstance(data, dict):
                content = data.get("content", "")
                all_content += content
                next_token = data.get("next_token")
                logger.info(f"[smartcanvas_read_content] 第{page_count}页: content长度={len(content)}, next_token={next_token!r}")
                if not next_token:
                    break
            else:
                logger.warning(f"[smartcanvas_read_content] 第{page_count}页: 返回非dict类型 {type(data)}")
                break
            if page_count > 20:
                logger.warning("[smartcanvas_read_content] 分页超过20页，强制停止")
                break

        logger.info(f"[smartcanvas_read_content] 总共获取内容长度: {len(all_content)}, 总页数: {page_count}")
        if len(all_content) < 100:
            logger.warning(f"[smartcanvas_read_content] 内容过短: {all_content[:200]!r}")

        records = self._parse_markdown_tables(all_content, jira_id)
        logger.info(f"[smartcanvas_read_content] 解析到 {len(records)} 条记录")
        return records

    def _parse_markdown_tables(self, content: str, jira_id: Optional[str] = None) -> List[Dict[str, str]]:
        """
        解析 markdown 格式的表格内容，返回记录列表。
        支持 "laws-xxx"、"gindex-xxx" 等格式的 TEST POINT ID。
        """
        records = []
        # 找到所有 markdown 表格（| 开头的行，相邻3行以上）
        lines = content.split("\n")
        in_table = False
        table_lines = []
        table_headers = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("|"):
                in_table = True
                table_lines.append(line)
            else:
                if in_table and len(table_lines) >= 3:
                    # 解析表格
                    try:
                        parsed = self._parse_single_table(table_lines, table_headers)
                        if parsed:
                            records.extend(parsed)
                    except Exception:
                        pass
                    table_lines = []
                    table_headers = []
                in_table = False
            i += 1

        # 处理最后一组表格
        if in_table and len(table_lines) >= 3:
            try:
                parsed = self._parse_single_table(table_lines, table_headers)
                if parsed:
                    records.extend(parsed)
            except Exception:
                pass

        # 按 jira_id 过滤
        if jira_id:
            import re as re_mod
            jira_pattern = re_mod.compile(re_mod.escape(jira_id), re_mod.IGNORECASE)
            records = [
                r for r in records
                if jira_pattern.search(str(r.get("TEST POINT ID", "")))
                or jira_pattern.search(str(r.get("CASE ID", "")))
            ]

        return records

    def _parse_single_table(self, table_lines: List[str], prev_headers: List[str]) -> List[Dict[str, str]]:
        """解析单个 markdown 表格，返回记录列表"""
        records = []
        # 找到表头行和分隔行
        header_idx = -1
        for idx, line in enumerate(table_lines):
            if line.startswith("|") and "|" in line[1:]:
                cells = [c.strip() for c in line.split("|")[1:-1]]
                # 检查是否是表头行（有 TEST POINT ID 等关键词）
                if any(k in str(cells) for k in ["TEST POINT ID", "TEST POINT", "CASE ID", "Priority", "PRIORITY"]):
                    header_idx = idx
                    break

        if header_idx < 0:
            return []

        header_line = table_lines[header_idx]
        headers = [c.strip() for c in header_line.split("|")[1:-1]]

        # 解析数据行（跳过分隔行 header_idx+1）
        for line in table_lines[header_idx + 2:]:
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not any(c for c in cells):
                continue
            # 对齐列
            record: Dict[str, str] = {}
            for idx, h in enumerate(headers):
                record[h] = cells[idx] if idx < len(cells) else ""
            # 提取 TEST POINT ID
            tp_id = record.get("TEST POINT ID", "") or record.get("TEST POINT", "") or record.get("CASE ID", "")
            if not tp_id or tp_id.startswith("|"):
                continue
            tp_lower = tp_id.lower()
            skip_keywords = {
                "demo", "note", "api_automation", "ui_automation",
                "autom", "test case completely", "at least one",
                "the test case cannot", "pass\t", "fail\t", "nt\t", "block\t",
            }
            if any(kw in tp_lower for kw in skip_keywords):
                continue
            records.append(record)

        return records

    async def list_fields(
        self, file_id: str, sheet_id: str
    ) -> List[Dict[str, Any]]:
        """获取 Sheet 的字段（列）信息

        优先用 smartsheet.list_fields；worksheet 类型 sheet 可能失败，此时通过
        list_records 第一页记录按位置推断字段（用序号作 field_title）。
        """
        tools = await self._load_tools_async()

        # 先尝试 smartsheet.list_fields
        for tool in tools:
            if tool.name == "smartsheet.list_fields":
                try:
                    data = await self._call_tool_with_retry(
                        tool, {"file_id": file_id, "sheet_id": sheet_id}
                    )
                    if isinstance(data, dict) and data.get("fields"):
                        logger.info(f"list_fields 成功获取 {len(data['fields'])} 个字段")
                        return data["fields"]
                    elif isinstance(data, list) and data:
                        return data
                except Exception as e:
                    logger.warning(f"smartsheet.list_fields 失败，改用记录推断字段: {e}")

        # fallback：通过 list_records 第一页按位置推断字段
        try:
            records_tool = next(
                (t for t in tools if t.name == "smartsheet.list_records"), None
            )
            if not records_tool:
                raise ValueError("未找到 smartsheet.list_records 工具")
            result = await self._call_tool_with_retry(
                records_tool,
                {"file_id": file_id, "sheet_id": sheet_id, "limit": 1, "offset": 0},
            )
            records = result.get("records", []) if isinstance(result, dict) else []
            if not records:
                return []

            first = records[0]
            field_values = first.get("field_values", [])
            fields = []
            for idx, fv in enumerate(field_values):
                if isinstance(fv, dict):
                    fields.append({
                        "field_title": fv.get("field_title", str(idx)),
                        "field_id": fv.get("field_id", str(idx)),
                        "index": idx,
                    })
                else:
                    fields.append({"field_title": str(idx), "field_id": str(idx), "index": idx})
            logger.info(f"list_fields fallback 推断到 {len(fields)} 个字段: {[f['field_title'] for f in fields]}")
            return fields
        except Exception as e2:
            logger.error(f"list_fields fallback 也失败: {e2}")
            return []

    def _extract_field_value(self, field_values: List, field_name: str) -> str:
        """从 field_values 中按字段名提取值，同时支持对象和平铺两种格式"""
        for fv in field_values:
            if isinstance(fv, dict):
                title = fv.get("field_title", "")
                if title.lower() == field_name.lower():
                    return str(fv.get("value", ""))
            elif isinstance(fv, list) and len(fv) >= 2:
                if str(fv[0]).lower() == field_name.lower():
                    return str(fv[1])
        # fallback：按索引
        try:
            idx = int(field_name)
            return str(field_values[idx]) if idx < len(field_values) else ""
        except (ValueError, TypeError):
            return ""

    def _csv_get(self, header_to_idx: Dict[str, int], row: List[str], field_name: str) -> str:
        """从 CSV row 中按列名提取值，大小写不敏感，支持别名"""
        aliases = {
            "CASE ID": ["Case No.", "Case No", "case id", "case no", "Test Point ID"],
            "TEST PRIORITY": ["Priority", "Case Priority"],
            "TESTER": ["Tester"],
        }
        names_to_try = [field_name] + aliases.get(field_name, [])
        for name in names_to_try:
            idx = header_to_idx.get(name, -1)
            if idx >= 0 and idx < len(row):
                return str(row[idx]).strip()
            # 再忽略大小写匹配
            name_lower = name.lower()
            for h, i in header_to_idx.items():
                if h.lower() == name_lower and i < len(row):
                    return str(row[i]).strip()
        return ""

    async def list_records(
        self,
        file_id: str,
        sheet_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """获取 Sheet 的记录（行），优先 smartsheet.list_records"""
        tools = await self._load_tools_async()
        for tool in tools:
            if tool.name == "smartsheet.list_records":
                try:
                    data = await self._call_tool_with_retry(
                        tool, {"file_id": file_id, "sheet_id": sheet_id, "limit": limit, "offset": offset}
                    )
                    return data or {}
                except Exception:
                    raise
        raise ValueError(
            f"未找到 smartsheet.list_records 工具，可用工具: {[t.name for t in tools]}"
        )

    async def get_csv_records(
        self, file_id: str, sheet_id: str, start_row: int = 0, max_rows: int = 300,
        col_count: Optional[int] = None
    ) -> Tuple[List[str], List[List[str]]]:
        """
        使用 smartsheet API 读取 worksheet 数据。
        1. smartsheet.list_fields + list_records（字段对齐正确）
        2. 仅 list_records（无 fields 时，从第一行推断字段名）
        3. sheet.get_cell_data CSV 格式（最后兜底）
        """
        tools = await self._load_tools_async()
        list_records_tool = next((t for t in tools if t.name == "smartsheet.list_records"), None)

        # 尝试1：smartsheet.list_fields + list_records
        try:
            list_fields_tool = next((t for t in tools if t.name == "smartsheet.list_fields"), None)
            if list_fields_tool and list_records_tool:
                fields_result = await self._call_tool_with_retry(list_fields_tool, {
                    "file_id": file_id, "sheet_id": sheet_id
                })
                fields: List[Dict] = fields_result.get("fields", []) if isinstance(fields_result, dict) else []
                if not fields:
                    fields = fields_result if isinstance(fields_result, list) else []

                # 无论 fields 是否为空，都调用 list_records
                # 如果 fields 为空，从第一条记录推断列数和列名
                all_records: List[Dict] = []
                offset = 0
                limit = 200
                while True:
                    records_result = await self._call_tool_with_retry(list_records_tool, {
                        "file_id": file_id, "sheet_id": sheet_id, "limit": limit, "offset": offset
                    })
                    page_records: List[Dict] = records_result.get("records", []) if isinstance(records_result, dict) else []
                    all_records.extend(page_records)
                    if not page_records or not records_result.get("has_more", False):
                        break
                    offset += limit
                    if offset > 5000:
                        break

                logger.info(f"[get_csv_records] smartsheet.list_records 返回 {len(all_records)} 条")

                if not all_records:
                    raise RuntimeError("smartsheet.list_records 返回空数据")

                # 生成 headers
                first_fv: List = all_records[0].get("field_values", []) if all_records else []
                num_cols = len(first_fv)
                if fields:
                    headers = [str(f.get("field_title", f.get("title", f"col_{i}"))) for i, f in enumerate(fields)]
                else:
                    headers = [f"col_{i}" for i in range(num_cols)]
                logger.info(f"[get_csv_records] headers: {headers[:5]}, 列数={num_cols}")

                data_rows: List[List[str]] = []
                for rec in all_records:
                    field_values: List = rec.get("field_values", []) if isinstance(rec, dict) else []
                    row = []
                    for i in range(num_cols):
                        if i < len(field_values):
                            fv = field_values[i]
                            if isinstance(fv, dict):
                                row.append(str(fv.get("value", fv.get("display", ""))).strip())
                            else:
                                row.append(str(fv).strip())
                        else:
                            row.append("")
                    if any(v.strip() for v in row):
                        data_rows.append(row)

                logger.info(f"[get_csv_records] smartsheet 数据: headers={headers[:5]}, 行数={len(data_rows)}")
                return headers, data_rows
        except Exception as e:
            logger.warning(f"[get_csv_records] smartsheet API 失败: {e}")

        # 尝试2：sheet.get_cell_data CSV 格式
        try:
            cell_tool = next((t for t in tools if t.name == "sheet.get_cell_data"), None)
            if not cell_tool:
                raise ValueError("未找到 sheet.get_cell_data 工具")

            csv_result = await self._call_tool_with_retry(
                cell_tool,
                {
                    "file_id": file_id, "sheet_id": sheet_id,
                    "start_col": 0, "end_col": 100,
                    "start_row": start_row, "end_row": start_row + max_rows,
                    "return_csv": True,
                },
            )
            if isinstance(csv_result, dict):
                csv_text = csv_result.get("csv_data") or csv_result.get("csv") or csv_result.get("content") or ""
            else:
                csv_text = str(csv_result)
            logger.info(f"[get_csv_records] CSV 返回长度: {len(csv_text)}")

            if csv_text.strip():
                reader = csv.reader(io.StringIO(csv_text))
                rows = [row for row in reader if any(c.strip() for c in row)]
                if rows:
                    headers = rows[0]
                    data_rows = rows[1:] if len(rows) > 1 else []
                    logger.info(f"[get_csv_records] CSV 解析: headers={headers[:5]}, 数据行={len(data_rows)}")
                    return headers, data_rows
        except Exception as e:
            logger.warning(f"[get_csv_records] CSV 格式失败: {e}")

        raise RuntimeError("无法读取腾讯文档数据（smartsheet 和 CSV 均失败）")

    def _parse_test_point_id(self, test_point_id: str) -> Dict[str, Any]:
        """
        解析 TEST POINT ID，提取 case_id, task, module。
        例如: "laws-19290-001" -> case_id=1, task=DM-19290, module=laws
        """
        match = re.match(r"^([a-zA-Z]+)-(\d+)-(\d+)$", test_point_id.strip())
        if match:
            return {
                "case_id": int(match.group(3)),
                "task": f"DM-{match.group(2)}",
                "module": match.group(1),
            }
        # fallback
        seq_match = re.search(r"-(\d+)$", test_point_id)
        result: Dict[str, Any] = {
            "case_id": int(seq_match.group(1)) if seq_match else 0,
            "task": "",
            "module": "",
        }
        jira_match = re.search(r"D[Mm]-\d+", test_point_id)
        if jira_match:
            result["task"] = jira_match.group(0).upper()
        prefix_match = re.match(r"^([a-zA-Z]+)-", test_point_id)
        if prefix_match:
            result["module"] = prefix_match.group(1)
        return result

    def _safe_get(
        self,
        field_values: List,
        field_name_to_idx: Dict[str, int],
        field_name: str,
        default: str,
    ) -> str:
        idx = field_name_to_idx.get(field_name)
        if idx is not None and idx < len(field_values):
            val = field_values[idx]
            return str(val) if val is not None else default
        return default

    def _esc(self, text: str) -> str:
        return str(text).replace("|", "\\|").replace("\r", "").strip()

    def _markup_field(self, value: str, label: str) -> str:
        """将字段值渲染为带标签的 HTML，空值显示占位符"""
        v = str(value).strip() if value else ""
        if not v:
            return (
                '<div style="margin-bottom:10px">'
                '<div style="font-size:10px;color:#c0c4cc;margin-bottom:4px">{label}</div>'
                '<div style="font-size:12px;color:#c0c4cc;font-style:italic">（未填写）</div>'
                '</div>'
            ).format(label=label)
        if label in ("CASE STEPS", "EXPECTED RESULT"):
            lines_html = ""
            for line in v.split("\n"):
                line = line.strip()
                if line:
                    lines_html += (
                        '<div style="margin-bottom:4px;padding-left:12px;position:relative">'
                        '<span style="position:absolute;left:0;color:#909399">{bullet}&#160;</span>'
                        '{text}</div>'
                    ).format(bullet="•" if label == "CASE STEPS" else "✓", text=self._esc(line))
            return (
                '<div style="margin-bottom:10px">'
                '<div style="font-size:10px;color:#909399;margin-bottom:4px">{label}</div>'
                '<div style="font-size:12px;color:#606266;font-family:monospace">{content}</div>'
                '</div>'
            ).format(label=label, content=lines_html)
        return (
            '<div style="margin-bottom:10px">'
            '<div style="font-size:10px;color:#909399;margin-bottom:4px">{label}</div>'
            '<div style="font-size:12px;color:#606266">{value}</div>'
            '</div>'
        ).format(label=label, value=self._esc(v))

    def _record_to_markdown(self, r: Dict, seq: int = 0) -> str:
        """将单条记录转为纯文本格式（用于复制粘贴）"""
        task = (r.get('task') or '').strip().upper()
        case_id_str = f"{task}-{seq:03d}" if task else str(r.get('case_id', ''))

        lines = []
        lines.append(f"CASE ID: {case_id_str}")
        lines.append(f"TASK: {task}")
        lines.append(f"MODULE: {r.get('module', '')}")
        lines.append(f"TEST PRIORITY: {r.get('test_priority', '')}")

        pre_cond = (r.get('pre_condition') or '').strip()
        lines.append(f"PRE-CONDITION: {pre_cond}")

        lines.append(f"CASE TITLE: {(r.get('case_title') or '').strip()}")

        case_steps = (r.get('case_steps') or '').strip()
        lines.append(f"CASE STEPS:\n{case_steps}")

        expected = (r.get('expected_result') or '').strip()
        lines.append(f"EXPECTED RESULT:\n{expected}")

        actual = (r.get('actual_results') or '').strip()
        lines.append(f"ACTUAL RESULTS:\n{actual}")

        lines.append(f"TESTER: {(r.get('tester') or '').strip()}")
        lines.append(f"RUN TIME: {(r.get('run_time') or '').strip()}")
        lines.append(f"NOTE: {(r.get('note') or '').strip()}")

        return "\n".join(lines)

    def _generate_card_html(self, records: List[Dict], title: str) -> str:
        """生成卡片样式的 HTML"""

        def priority_badge(priority: str) -> str:
            color_map = {
                "High": ("#f56c6c", "#fef0f0"),
                "Medium": ("#e6a23c", "#fdf6ec"),
                "Low": ("#67c23a", "#f0f9eb"),
                "Important": ("#9c27b0", "#f3e5f5"),
            }
            color = color_map.get(priority, ("#909399", "#f4f4f5"))
            return (
                '<span style="display:inline-block;padding:2px 8px;border-radius:12px;'
                'font-size:11px;font-weight:600;color:{};'
                'background:{};border:1px solid {}30">{}</span>'
            ).format(color[0], color[1], color[0], priority)

        cards_html = ""
        all_md: List[str] = []
        for idx, r in enumerate(records):
            pre_cond_html = self._markup_field(r.get("pre_condition", ""), "PRE-CONDITION")
            steps_html = self._markup_field(r.get("case_steps", ""), "CASE STEPS")
            expected_html = self._markup_field(r.get("expected_result", ""), "EXPECTED RESULT")

            note_val = r.get("note", "")
            note_html = ""
            if note_val and str(note_val).strip():
                note_html = (
                    '<div style="margin-top:8px;padding:8px;background:#fafafa;'
                    'border-radius:4px;font-size:11px;color:#909399">'
                    '<strong>NOTE:</strong> {}</div>'
                ).format(self._esc(str(note_val)))

            tester_val = self._esc(r.get("tester", "")) or "-"
            runtime_val = self._esc(r.get("run_time", "")) or "-"
            actual_val = self._esc(r.get("actual_results", "")) or "-"

            md = self._record_to_markdown(r, idx + 1)
            all_md.append(md)

            card = (
                '<div style="border:1px solid #ebeef5;border-radius:8px;margin-bottom:16px;'
                'background:#fff;box-shadow:0 2px 6px rgba(0,0,0,0.06);overflow:hidden">'
                '<div style="display:flex;align-items:center;padding:12px 16px;'
                'background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);'
                'color:#fff;font-size:13px;gap:12px">'
                '<span style="font-weight:700;min-width:60px">#{:03d}</span>'
                '<span style="flex:1;font-weight:500;overflow:hidden;'
                'text-overflow:ellipsis;white-space:nowrap">{}</span>'
                '{}'
                '<button class="card-copy-btn" data-copy-text="{copy_text_esc}" '
                'style="padding:3px 10px;border-radius:4px;border:1px solid rgba(255,255,255,0.4);'
                'background:rgba(255,255,255,0.15);color:#fff;cursor:pointer;font-size:11px;'
                'white-space:nowrap" title="复制为 Markdown">复制</button>'
                '</div>'
                '<div style="padding:14px 16px">'
                '<div style="display:flex;gap:16px;flex-wrap:wrap;'
                'margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid #f0f0f0">'
                '<div style="min-width:80px"><div style="font-size:10px;color:#909399;margin-bottom:2px">TASK</div>'
                '<div style="font-size:12px;font-weight:600;color:#409eff">{}</div></div>'
                '<div style="min-width:80px"><div style="font-size:10px;color:#909399;margin-bottom:2px">MODULE</div>'
                '<div style="font-size:12px;font-weight:600;color:#67c23a">{}</div></div>'
                '<div style="min-width:80px"><div style="font-size:10px;color:#909399;margin-bottom:2px">TESTER</div>'
                '<div style="font-size:12px;color:#606266">{}</div></div>'
                '<div style="min-width:80px"><div style="font-size:10px;color:#909399;margin-bottom:2px">RUN TIME</div>'
                '<div style="font-size:12px;color:#606266">{}</div></div>'
                '<div style="min-width:80px"><div style="font-size:10px;color:#909399;margin-bottom:2px">ACTUAL</div>'
                '<div style="font-size:12px;color:#606266">{}</div></div>'
                '</div>'
                '{}'
                '{}'
                '{}'
                '{}'
                '</div>'
                '</div>'
            ).format(
                r["case_id"],
                self._esc(r["case_title"]),
                priority_badge(r["test_priority"]),
                self._esc(r["task"]),
                self._esc(r["module"]),
                tester_val,
                runtime_val,
                actual_val,
                pre_cond_html,
                steps_html,
                expected_html,
                note_html,
                copy_text_esc=self._esc(md),
            )
            cards_html += card

        pass_count = sum(1 for r in records if r.get("actual_results", "").upper() in ["PASS", "PASSED"])
        fail_count = sum(1 for r in records if r.get("actual_results", "").upper() in ["FAIL", "FAILED"])

        all_md_json = json.dumps(all_md, ensure_ascii=False)

        page = (
            '<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<title>测试用例 - {title}</title>'
            '<style>'
            'body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;background:#f5f7fa;margin:24px;padding:0}}'
            '.container{{max-width:900px;margin:0 auto}}'
            '.page-header{{text-align:center;margin-bottom:24px}}'
            '.page-header h1{{margin:0 0 8px;font-size:22px;color:#303133}}'
            '.stats{{display:flex;justify-content:center;gap:24px;margin-bottom:8px;align-items:center}}'
            '.stat-item{{text-align:center}}'
            '.stat-value{{font-size:24px;font-weight:700;color:#409eff}}'
            '.stat-label{{font-size:11px;color:#909399;text-transform:uppercase}}'
            '</style>'
            
            '</head><body>'
            '<div class="container">'
            '<div class="page-header">'
            '<h1>测试用例 - {title}</h1>'
            '<div class="stats">'
            '<div class="stat-item"><div class="stat-value">{total}</div><div class="stat-label">Total</div></div>'
            '<div class="stat-item"><div class="stat-value">{pass_cnt}</div><div class="stat-label">Pass</div></div>'
            '<div class="stat-item"><div class="stat-value">{fail_cnt}</div><div class="stat-label">Fail</div></div>'
            '</div></div>'
            '{cards}'
            '</div></body></html>'
        ).format(
            title=title,
            total=len(records),
            pass_cnt=pass_count,
            fail_cnt=fail_count,
            cards=cards_html,
            all_md_json=all_md_json,
        )
        return page

    async def convert_testcases(
        self,
        doc_url: str,
        jira_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        从腾讯文档获取测试用例并转换为卡片样式 HTML。
        直接从 URL 解析 file_id 和 sheet_id，无需先列出所有 sheet。
        """
        parsed = await self.resolve_doc_url(doc_url)
        file_id = parsed["file_id"]
        sheet_id = parsed["sheet_id"]
        sheet_title = parsed.get("sheet_title", sheet_id)
        sheet_type = parsed.get("sheet_type", "worksheet")
        col_count = parsed.get("col_count")
        import sys
        print(f"DEBUG sheet_type={repr(sheet_type)}, worksheet_branch={'sheet_type != smartsheet'.replace('smartsheet', sheet_type)}", flush=True)
        logger.critical(f"!!! SHEET_TYPE_IS: {repr(sheet_type)} !!! WILL_USE_WORKSHEET_BRANCH={sheet_type != 'smartsheet'}")

        headers: List[str] = []
        data_rows: List[List[str]] = []

        logger.warning(f"===== CONVERT_TESTCASES CALLED ===== sheet_type={sheet_type!r}")
        if sheet_type == "smartsheet":
            # smartsheet 类型：用 smartsheet.list_records
            fields = await self.list_fields(file_id, sheet_id)
            field_name_to_idx: Dict[str, int] = {
                f.get("field_title", ""): idx for idx, f in enumerate(fields)
            }
            all_records = []
            offset = 0
            limit = 100
            while True:
                result = await self.list_records(file_id, sheet_id, limit=limit, offset=offset)
                records_data = result.get("records", [])
                all_records.extend(records_data)
                if not result.get("has_more", False):
                    break
                offset += limit
            logger.info(f"获取到 {len(all_records)} 条原始记录 (smartsheet)")

            # 根据 jira_id 过滤
            if jira_id:
                jira_pattern = re.compile(re.escape(jira_id), re.IGNORECASE)
                all_records = [
                    r
                    for r in all_records
                    if any(jira_pattern.search(str(fv.get("value") if isinstance(fv, dict) else fv))
                           for fv in r.get("field_values", []))
                ]

            # 转换为目标格式
            records = []
            seq_counter = 0
            for record in all_records:
                field_values = record.get("field_values", [])
                test_point_id = self._extract_field_value(field_values, "TEST POINT ID")
                if not test_point_id or str(test_point_id).startswith("|"):
                    continue
                test_point_id = str(test_point_id)
                parsed_tp = self._parse_test_point_id(test_point_id)
                seq_counter += 1
                if parsed_tp["case_id"] == 0:
                    parsed_tp["case_id"] = seq_counter
                records.append({
                    "case_id": parsed_tp["case_id"],
                    "task": parsed_tp["task"] or (f"DM-{jira_id}" if jira_id else sheet_title),
                    "module": parsed_tp["module"] or sheet_title,
                    "test_priority": self._extract_field_value(field_values, "TEST PRIORITY"),
                    "pre_condition": self._extract_field_value(field_values, "Precondition"),
                    "case_title": self._extract_field_value(field_values, "TEST POINT TITLE"),
                    "case_steps": self._extract_field_value(field_values, "Test Case"),
                    "expected_result": self._extract_field_value(field_values, "Expected Result"),
                    "actual_results": self._extract_field_value(field_values, "Actual Results"),
                    "tester": self._extract_field_value(field_values, "TESTER"),
                    "run_time": self._extract_field_value(field_values, "RUN TIME"),
                    "note": self._extract_field_value(field_values, "NOTE"),
                })
        else:
            # worksheet 类型：直接用 CSV 获取数据，通过 Task 列识别
            raw_records: List[Dict[str, str]] = []
            try:
                headers, data_rows = await self.get_csv_records(
                    file_id, sheet_id, start_row=0, max_rows=500, col_count=col_count
                )
                logger.info(f"[convert_testcases] CSV 返回: headers={len(headers) if headers else 0}, rows={len(data_rows) if data_rows else 0}")
                if headers:
                    header_to_idx: Dict[str, int] = {str(h).strip(): idx for idx, h in enumerate(headers)}
                    for row in data_rows:
                        r = {}
                        for h, idx in header_to_idx.items():
                            r[h] = row[idx] if idx < len(row) else ""
                        if any(str(v).strip() for v in r.values() if v):
                            raw_records.append(r)
                    logger.info(f"[convert_testcases] CSV 解析到 {len(raw_records)} 条")
            except Exception as e:
                logger.warning(f"[convert_testcases] CSV 解析失败: {e}")

            # 通过 Task 列过滤（不区分大小写）
            if jira_id and raw_records:
                filtered = [r for r in raw_records if jira_id.lower() in str(r.get("Task", "")).lower()]
                logger.info(f"[convert_testcases] Task={jira_id} 过滤后剩 {len(filtered)} 条")
                raw_records = filtered

            records = []
            if raw_records:
                logger.info(f"[convert_testcases] raw_records 示例: {raw_records[0]}")
                for raw in raw_records:
                    task_val = str(raw.get("Task", "") or raw.get("task", "")).strip()
                    case_id_val = (
                        raw.get("TEST POINT ID", "") or raw.get("CASE ID", "") or raw.get("CASE ID ", "")
                        or raw.get("TEST POINT", "") or ""
                    ).strip()
                    record_task = task_val or (f"DM-{jira_id}" if jira_id else sheet_title)
                    record_case_id = 0
                    if case_id_val and not case_id_val.startswith("|"):
                        parsed = self._parse_test_point_id(case_id_val)
                        record_case_id = parsed.get("case_id", 0)
                    records.append({
                        "case_id": record_case_id,
                        "task": record_task,
                        "module": raw.get("MODULE", "") or sheet_title,
                        "test_priority": raw.get("TEST PRIORITY", "") or "",
                        "pre_condition": raw.get("PRE-CONDITION", "") or "",
                        "case_title": raw.get("CASE TITLE", "") or raw.get("TEST POINT TITLE", "") or "",
                        "case_steps": raw.get("CASE STEPS", "") or raw.get("Test Case", "") or "",
                        "expected_result": raw.get("EXPECTED RESULT", "") or raw.get("ESPECTED RESULT", "") or "",
                        "actual_results": raw.get("ACTUAL RESULTS", "") or "",
                        "tester": raw.get("TESTER", "") or "",
                        "run_time": raw.get("RUN TIME", "") or "",
                        "note": raw.get("NOTE", "") or "",
                    })

            records.sort(key=lambda x: x["case_id"])

        for i, r in enumerate(records):
            r["copy_text"] = self._record_to_markdown(r, i + 1)

        title = jira_id or sheet_title
        card_html = self._generate_card_html(records, title)

        return {
            "jira_id": jira_id or sheet_title,
            "module_name": sheet_title,
            "total_count": len(records),
            "records": records,
            "card_html": card_html,
        }


_tencent_docs_service: Optional[TencentDocsService] = None


def get_tencent_docs_service() -> TencentDocsService:
    global _tencent_docs_service
    if _tencent_docs_service is None:
        _tencent_docs_service = TencentDocsService()
    return _tencent_docs_service
