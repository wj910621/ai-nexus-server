"""
多 Agent 协作模块
规划 Agent + 执行 Agent + 校验 Agent

设计原则：
- 不引入额外 LLM 成本，优先复用 brain 的调用能力
- 规划器做任务拆解，执行器调用 SKILL_MAP，校验器检查失败并决定重试
- 对常见复合任务内置规则模板，复杂任务退回给主 LLM
"""

import json
import re
from typing import List, Dict, Any, Callable

from logger import logger
from skills import SKILL_MAP


# 简单规则：关键词 -> 建议执行的工具链
_TASK_TEMPLATES = [
    {
        "name": "晨间日报",
        "keywords": ["晨间日报", "早上好", "日报", "今天安排"],
        "steps": [
            {"tool": "get_time", "args": {}},
            {"tool": "get_weather", "args": {"city": "北京"}},
            {"tool": "list_reminders", "args": {}},
            {"tool": "list_events", "args": {"days": 1}},
        ]
    },
    {
        "name": "离家巡检",
        "keywords": ["离家", "出门", "巡检", "检查一下"],
        "steps": [
            {"tool": "get_system_info", "args": {}},
            {"tool": "list_ha_entities", "args": {"domain": "light"}},
            {"tool": "list_reminders", "args": {}},
        ]
    },
    {
        "name": "工作准备",
        "keywords": ["准备工作", "开始工作", "今天工作"],
        "steps": [
            {"tool": "get_time", "args": {}},
            {"tool": "read_emails", "args": {"count": 3}},
            {"tool": "list_events", "args": {"days": 1}},
        ]
    },
]


def _match_template(task: str) -> List[Dict[str, Any]]:
    """根据关键词匹配预设任务模板"""
    text = task.lower()
    for t in _TASK_TEMPLATES:
        if any(k in text for k in t["keywords"]):
            return t["steps"]
    return []


def _extract_city(task: str) -> str:
    """从任务描述中简单提取城市名"""
    for city in ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "西安"]:
        if city in task:
            return city
    return "北京"


def _plan_steps(task: str) -> List[Dict[str, Any]]:
    """
    规划 Agent：把用户任务拆成可执行步骤
    优先匹配模板，否则做简单启发式拆分
    """
    steps = _match_template(task)
    if steps:
        # 替换模板中的城市占位
        for s in steps:
            if "city" in s.get("args", {}):
                s["args"]["city"] = _extract_city(task)
        return steps

    # 启发式拆分：逐句按动作识别
    result = []
    text = task.lower()

    if any(k in text for k in ["天气", "气温"]):
        result.append({"tool": "get_weather", "args": {"city": _extract_city(task)}})

    if any(k in text for k in ["时间", "几点", "日期"]):
        result.append({"tool": "get_time", "args": {}})

    if any(k in text for k in ["邮件", "邮箱"]):
        result.append({"tool": "read_emails", "args": {"count": 5}})

    if any(k in text for k in ["日程", "会议", "安排"]):
        result.append({"tool": "list_events", "args": {"days": 7}})

    if any(k in text for k in ["提醒", "待办"]):
        result.append({"tool": "list_reminders", "args": {}})

    if any(k in text for k in ["系统", "cpu", "内存", "磁盘"]):
        result.append({"tool": "get_system_info", "args": {}})

    if any(k in text for k in ["设备", "灯", "空调", "窗帘", "家居"]):
        result.append({"tool": "list_ha_entities", "args": {}})

    if any(k in text for k in ["文件", "搜索"]):
        keyword = "文档"
        m = re.search(r"(?:搜索|找|文件)\s*(.+?)(?:\s|$)", task)
        if m:
            keyword = m.group(1).strip(" 。，？")
        result.append({"tool": "search_file", "args": {"name": keyword}})

    if not result:
        # 无法识别，执行一个通用信息收集
        result.append({"tool": "get_time", "args": {}})

    return result


def _execute_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """执行 Agent：调用 SKILL_MAP 中的单个工具"""
    tool_name = step["tool"]
    args = step.get("args", {})
    logger.info(f"执行子任务：{tool_name}({args})")

    if tool_name not in SKILL_MAP:
        return {
            "tool": tool_name,
            "args": args,
            "success": False,
            "output": f"未知工具：{tool_name}"
        }

    try:
        output = SKILL_MAP[tool_name](**args)
        success = not _looks_like_failure(output)
        return {
            "tool": tool_name,
            "args": args,
            "success": success,
            "output": output
        }
    except Exception as e:
        logger.exception(f"子任务执行失败：{tool_name}")
        return {
            "tool": tool_name,
            "args": args,
            "success": False,
            "output": f"执行异常：{e}"
        }


def _looks_like_failure(output: str) -> bool:
    """校验 Agent：判断工具输出是否像失败信息"""
    if not output:
        return True
    failure_keywords = [
        "失败", "错误", "异常", "无法", "不可用", "未配置", "未找到",
        "unknown", "error", "fail", "exception", "not available",
    ]
    lowered = output.lower()
    return any(k in lowered for k in failure_keywords)


def _verify_and_retry(steps: List[Dict[str, Any]], results: List[Dict[str, Any]], max_retry: int = 1) -> List[Dict[str, Any]]:
    """
    校验 Agent：检查步骤结果，对失败的步骤尝试简化重试
    """
    final_results = []
    for step, res in zip(steps, results):
        if res["success"]:
            final_results.append(res)
            continue

        # 尝试一次简化重试
        retried = False
        for _ in range(max_retry):
            simplified = _simplify_step(step)
            if simplified == step:
                break
            logger.info(f"简化重试：{simplified['tool']}({simplified.get('args', {})})")
            new_res = _execute_step(simplified)
            if new_res["success"]:
                res = new_res
                retried = True
                break

        final_results.append(res)

    return final_results


def _simplify_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """对失败步骤做简化，例如减少参数、替换默认值"""
    simplified = dict(step)
    args = dict(simplified.get("args", {}))

    if step["tool"] == "read_emails" and args.get("count", 5) > 1:
        args["count"] = 1
    elif step["tool"] == "list_events" and args.get("days", 7) > 1:
        args["days"] = 1
    elif step["tool"] == "search_file" and not args.get("name"):
        args["name"] = "文档"
    else:
        # 没有可简化项，返回原步骤
        return step

    simplified["args"] = args
    return simplified


def _summarize_results(task: str, results: List[Dict[str, Any]]) -> str:
    """汇总多 Agent 执行结果，生成给用户的自然语言报告"""
    success_count = sum(1 for r in results if r["success"])
    total = len(results)

    lines = [f"先生，已完成「{task}」的多 Agent 协作处理。"]
    lines.append(f"共执行 {total} 个子任务，成功 {success_count} 项。")

    for idx, r in enumerate(results, 1):
        status = "✅" if r["success"] else "⚠️"
        output = r["output"]
        # 去掉可能重复的"先生，"前缀
        if output.startswith("先生，"):
            output = output[3:]
        lines.append(f"{status} 步骤 {idx} [{r['tool']}]：{output}")

    if success_count < total:
        lines.append("部分步骤未成功，可能是相关服务未配置或暂时不可用。")

    return "\n".join(lines)


def run_multi_agent(task_description: str) -> str:
    """
    多 Agent 协作入口
    1. 规划 Agent 拆解任务
    2. 执行 Agent 调用工具
    3. 校验 Agent 失败重试
    4. 返回汇总报告
    """
    if not task_description or not task_description.strip():
        return "先生，任务描述为空，无法启动多 Agent 协作。"

    task = task_description.strip()
    logger.info(f"启动多 Agent 协作：{task}")

    steps = _plan_steps(task)
    if not steps:
        return "先生，我暂时无法拆解这个任务，请换种方式描述。"

    results = [_execute_step(s) for s in steps]
    final_results = _verify_and_retry(steps, results)
    return _summarize_results(task, final_results)


if __name__ == "__main__":
    # 本地快速验证
    print(run_multi_agent("帮我准备今天的晨间日报"))
