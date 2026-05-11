import json
import re
from typing import Any, Optional, List


def repair_json_string(json_str: str) -> str:
    try:
        json_str = re.sub(r"/\*.*?\*/", "", json_str, flags=re.DOTALL)
        json_str = re.sub(r"(^|\s)//.*", "", json_str, flags=re.MULTILINE)
        json_str = re.sub(r",\s*}", "}", json_str)
        json_str = re.sub(r",\s*]", "]", json_str)
        return json_str
    except Exception:
        return json_str


def repair_doubao_specific_issues(text: str) -> str:
    """
    修复豆包模型特定的 JSON 格式问题。
    豆包模型在生成 JSON 时经常出现下划线替代引号/逗号、花括号配对错误、
    字段名损坏等情况。此函数按顺序应用多个正则修复，覆盖以下模式：
      1. "_" 替代 "，"      — "value_" → "value"
      2. "_," 替代 ',"'     — value_,_ → value","
      3. "{_" 替代 '{"'     — {_field → {"field
      4. ":_" 替代 '": "'   — ":"_xxx → '": "xxx'
      5. "}"_ 替代 '},'     — }_ → },
      6. "]"_ 替代 '],'     — ]_ → ],
      7. "{{" / "}}"        — 双重花括号
      8. '{_ ...}' 损坏字段 — "{_ module" → "module"
      9. '""_field"' 损坏   — ""_id" → "id"
     """
    if not text:
        return text

    # 1. "testcases_" → "testcases" (use look-ahead to not consume closing quote)
    text = re.sub(r'"testcases_"(?=:)', '"testcases"', text)
    # 2. "{_field" without quotes → '{"field'
    text = re.sub(r'\{_([^"]+)"', r'{"\1"', text)
    # 3. "value_," → 'value","'
    text = re.sub(r'([^_"]+)_,_', r'\1","', text)
    # 4. "value_}" → 'value"}'
    text = re.sub(r'([^_"]+)_([,\}\]])', r'\1"\2', text)
    # 5. ":"_value" → '": "value"'
    text = re.sub(r':\s*_([^_,\}\]]+)', r': "\1', text)
    # 6. "}"_ → '},'
    text = re.sub(r'\}\s*_', '},', text)
    # 7. "]"_ → '],'
    text = re.sub(r'\]\s*_', '],', text)
    # 8. "{{" → '{', "}}" → '}'
    text = re.sub(r'\{\{', '{', text)
    text = re.sub(r'\}\}', '}', text)
    # 9. '"{_' 损坏字段名 — "{_ module" → "module"
    text = re.sub(r'"\{_\s*([^"]+)"', r'"\1"', text)
    # 10. '""_field"' 损坏字段名 — ""_id" → "id"
    text = re.sub(r'""_([^"]+)"', r'"\1"', text)

    return text


def _has_doubao_corruption(text: str) -> bool:
    """Check if text contains known Doubao JSON corruption patterns."""
    return bool(
        re.search(r'"testcases_"', text)
        or re.search(r'\{_', text)
        or re.search(r'([^_"]+)_,_', text)
        or re.search(r'([^_"]+)_([,\}\]])', text)
        or re.search(r'\}\s*_', text)
        or re.search(r'\]\s*_', text)
        or re.search(r'\{\{', text)
        or re.search(r'\}\}', text)
        or re.search(r'"\{_\s*[^"]*"', text)
    )


def extract_json_from_llm_output(content: str) -> Optional[Any]:
    try:
        candidates = []

        match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if match:
            candidates.append(match.group(1).strip())

        match = re.search(r"```\s*(.*?)\s*```", content, re.DOTALL)
        if match:
            candidates.append(match.group(1).strip())

        # JSON object candidate: include char immediately before `{` to capture opening
        # quote, so downstream Doubao repair (e.g. '"testcases_"') can match.
        start_obj = content.find("{")
        end_obj = content.rfind("}")
        if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
            obj_start = start_obj
            if start_obj > 0 and content[start_obj - 1] == '"':
                obj_start -= 1  # include opening quote so repair pattern can match
            candidates.append(content[obj_start : end_obj + 1])
        start_list = content.find("[")
        end_list = content.rfind("]")
        if start_list != -1 and end_list != -1 and end_list > start_list:
            candidates.append(content[start_list : end_list + 1])

        candidates.append(content.strip())

        unique_candidates = sorted(list(set(candidates)), key=len, reverse=True)
        for cand in unique_candidates:
            # 1. Doubao repair FIRST if corruption is detected — the direct parse may
            # succeed on non-standard field names (e.g. "testcases_") but we need
            # to fix them before accepting.
            if _has_doubao_corruption(cand):
                try:
                    repaired = repair_doubao_specific_issues(cand)
                    return json.loads(repaired)
                except Exception:
                    pass
            # 2. Direct parse (for clean JSON)
            try:
                return json.loads(cand)
            except Exception:
                pass
            # 3. Generic repair (comments + trailing commas) — only for candidates
            # that did NOT have Doubao corruption (avoid redundant repair)
            try:
                repaired = repair_json_string(cand)
                return json.loads(repaired)
            except Exception:
                continue

        return None
    except Exception:
        return None


def assess_testcase_quality(testcases: list, jira_key: str | None = None) -> dict:
    """
    对生成的测试用例列表做质量评估，返回诊断字典。
    检查以下维度：
      - 步骤缺失预期结果
      - 前置条件过于简单
      - 测试类型分布合理性（功能测试比例、缺失关键测试维度）
      - 10 个测试维度覆盖度
    """
    quality_issues: List[str] = []
    type_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0}
    missing_expected_ids: set = set()
    missing_precondition_ids: set = set()

    for i, tc in enumerate(testcases):
        if not isinstance(tc, dict):
            continue

        # 检查步骤是否包含预期结果
        for step in tc.get("steps", []):
            step_str = str(step)
            if "预期" not in step_str and "Expected" not in step_str and "expected:" not in step_str.lower():
                tc_id = tc.get("id", f"#{i+1}")
                missing_expected_ids.add(tc_id)
                break  # 只记一次，不重复计数

        # 检查前置条件
        precondition = tc.get("precondition", "")
        if len(precondition) < 10:
            tc_id = tc.get("id", f"#{i+1}")
            missing_precondition_ids.add(tc_id)

        # 统计类型
        t = str(tc.get("type", "functional")).lower()
        type_counts[t] = type_counts.get(t, 0) + 1

        # 统计优先级（归一化）
        p = str(tc.get("priority", "P2")).upper()
        if p not in ("P0", "P1", "P2"):
            if "0" in p or "高" in p or "HIGH" in p:
                p = "P0"
            elif "1" in p or "中" in p or "MEDIUM" in p:
                p = "P1"
            else:
                p = "P2"
        priority_counts[p] = priority_counts.get(p, 0) + 1

    total = len(testcases)

    # 类型分布合理性检查
    distribution_issues: List[str] = []
    if total >= 5:
        func_pct = type_counts.get("functional", 0) / total * 100
        if func_pct < 25:
            distribution_issues.append(f"功能测试用例比例偏低 ({func_pct:.0f}%)，建议至少 25%")
    if total >= 8 and type_counts.get("boundary", 0) == 0:
        distribution_issues.append("缺少边界测试用例")
    if total >= 6 and type_counts.get("negative", 0) == 0:
        distribution_issues.append("缺少负面测试用例")
    if total >= 10 and type_counts.get("security", 0) == 0:
        distribution_issues.append("缺少安全测试用例")

    # 10 维度覆盖度检查
    expected_dims = {
        "functional", "boundary", "negative", "security",
        "integration", "performance", "concurrency",
        "data-validation", "network", "compatibility"
    }
    covered = set(type_counts.keys()) & expected_dims
    coverage_pct = len(covered) / len(expected_dims) * 100
    if coverage_pct < 50:
        missing_dims = expected_dims - covered
        distribution_issues.append(
            f"测试维度覆盖度低 ({coverage_pct:.0f}%)，"
            f"缺少 {len(missing_dims)} 个维度：{', '.join(sorted(missing_dims))}"
        )

    # 生成质量警告
    if missing_expected_ids:
        quality_issues.append(
            f"{len(missing_expected_ids)} 个测试用例的步骤缺少预期结果"
        )
    if missing_precondition_ids:
        quality_issues.append(
            f"{len(missing_precondition_ids)} 个测试用例的前置条件过于简单或缺失"
        )

    return {
        "quality_issues": quality_issues,
        "distribution_issues": distribution_issues,
        "statistics": {
            "total_testcases": total,
            "type_distribution": type_counts,
            "priority_distribution": priority_counts,
            "coverage_rate": round(coverage_pct, 1),
            "covered_dimensions": sorted(covered),
            "missing_expected_count": len(missing_expected_ids),
            "missing_precondition_count": len(missing_precondition_ids),
        }
    }


def normalize_testcase_output(raw: Any, jira_key: str | None = None) -> dict:
    """
    完整处理链：提取 JSON → 修复 Doubao 格式 → 归一化结构 → 去重 → 质检。
    返回 dict，包含：
      - testcases: 归一化后的测试用例列表
      - quality_issues: 质量问题列表
      - distribution_issues: 分布问题列表
      - statistics: 统计信息
    """
    # 1. 提取 JSON
    if isinstance(raw, str):
        parsed = extract_json_from_llm_output(raw)
    else:
        parsed = raw

    if isinstance(parsed, list):
        parsed = {"testcases": parsed}
    if not isinstance(parsed, dict):
        return {
            "testcases": [],
            "quality_issues": ["JSON 解析失败，无法提取结构化数据"],
            "distribution_issues": [],
            "statistics": {
                "total_testcases": 0,
                "type_distribution": {},
                "priority_distribution": {"P0": 0, "P1": 0, "P2": 0},
                "coverage_rate": 0.0,
                "covered_dimensions": [],
                "missing_expected_count": 0,
                "missing_precondition_count": 0,
            }
        }

    # 2. Doubao 格式修复（第一轮解析后可能仍有残留）
    if isinstance(raw, str) and raw:
        repaired = repair_doubao_specific_issues(raw)
        reparsed = extract_json_from_llm_output(repaired)
        if reparsed:
            parsed = reparsed

    # 3. 归一化 + 去重 + 优先级智能映射
    raw_testcases = parsed.get("testcases", [])
    normalized: List[dict] = []
    titles: set = set()

    for i, tc in enumerate(raw_testcases):
        if not isinstance(tc, dict):
            continue

        # 去重：标题去重，加 (variant N) 后缀
        original_title = str(tc.get("title", f"Test Case {i+1}"))
        title = original_title
        counter = 1
        while title in titles:
            title = f"{original_title} (variant {counter})"
            counter += 1
        titles.add(title)

        # 优先级智能映射
        p = str(tc.get("priority", "P2")).upper()
        t = str(tc.get("type", "functional")).lower()
        if p not in ("P0", "P1", "P2"):
            if t in ("functional", "security"):
                p = "P0"
            elif t in ("boundary", "negative", "integration"):
                p = "P1"
            else:
                p = "P2"

        # 归一化字段
        normalized.append({
            "id": tc.get("id", f"{jira_key}-{i+1:03d}" if jira_key else f"TC-{i+1:03d}"),
            "module": tc.get("module", "General"),
            "title": title,
            "priority": p,
            "precondition": tc.get("precondition", ""),
            "type": t,
            "steps": tc.get("steps", []),
            "expected_result": tc.get("expected_result", "Expected result not provided."),
        })

    # 4. 质量评估
    quality = assess_testcase_quality(normalized, jira_key)

    return {
        "testcases": normalized,
        **quality
    }
