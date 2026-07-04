"""
多 Agent 协作模块测试
验证规划、执行、校验、重试及与 brain/skills 的集成
"""

import re
from multi_agent import run_multi_agent, _plan_steps, _execute_step, _looks_like_failure, _verify_and_retry
from skills import SKILL_MAP
from brain import get_ai_response
from memory import save_memory


def test_plan_steps():
    """测试规划 Agent 的任务拆解"""
    print("\n=== 规划 Agent 任务拆解 ===")

    cases = [
        ("帮我准备今天的晨间日报", ["get_time", "get_weather", "list_reminders", "list_events"]),
        ("我要出门，帮我巡检一下", ["get_system_info", "list_ha_entities", "list_reminders"]),
        ("查一下上海天气和今天的日程", ["get_weather", "list_events"]),
    ]

    for task, expected_tools in cases:
        steps = _plan_steps(task)
        actual_tools = [s["tool"] for s in steps]
        print(f"  任务：{task}")
        print(f"  拆解：{actual_tools}")
        assert all(t in actual_tools for t in expected_tools), f"缺少工具：{expected_tools}"

    print("✅ 规划 Agent 拆解通过")


def test_failure_detection():
    """测试校验 Agent 的失败识别"""
    print("\n=== 校验 Agent 失败识别 ===")

    assert _looks_like_failure("先生，邮件服务未配置。") is True
    assert _looks_like_failure("先生，获取系统信息失败：xxx") is True
    assert _looks_like_failure("先生，现在是 2026年6月27日 11点33分。") is False
    assert _looks_like_failure("") is True

    print("✅ 失败识别通过")


def test_execute_known_tool():
    """测试执行 Agent 调用已知工具"""
    print("\n=== 执行 Agent 调用工具 ===")

    res = _execute_step({"tool": "get_time", "args": {}})
    print(f"  get_time -> success={res['success']}, output={res['output'][:30]}...")
    assert res["success"] is True
    assert "先生" in res["output"]

    res = _execute_step({"tool": "non_existent_tool", "args": {}})
    print(f"  unknown -> success={res['success']}, output={res['output']}")
    assert res["success"] is False

    print("✅ 执行 Agent 调用通过")


def test_retry():
    """测试校验 Agent 的简化重试逻辑"""
    print("\n=== 校验 Agent 重试 ===")

    # 构造一个会失败的步骤，和一个已经成功的步骤
    steps = [
        {"tool": "get_time", "args": {}},
        {"tool": "read_emails", "args": {"count": 5}},  # 未配置通常会失败
    ]
    results = [_execute_step(s) for s in steps]
    final = _verify_and_retry(steps, results, max_retry=1)

    assert final[0]["success"] is True
    print(f"  步骤1 get_time success={final[0]['success']}")
    print(f"  步骤2 read_emails success={final[1]['success']}, tried count={final[1]['args'].get('count')}")

    print("✅ 重试逻辑通过")


def test_run_multi_agent():
    """测试完整多 Agent 入口"""
    print("\n=== 完整多 Agent 入口 ===")

    report = run_multi_agent("帮我准备今天的晨间日报")
    print(report[:300])
    assert "多 Agent 协作处理" in report
    assert "get_time" in report or "步骤" in report

    print("✅ 完整入口通过")


def test_skill_registration():
    """测试 skills.py 中已注册 multi_agent"""
    print("\n=== Skills 注册检查 ===")

    assert "run_multi_agent_task" in SKILL_MAP
    result = SKILL_MAP["run_multi_agent_task"]("查一下时间")
    print(result[:200])
    assert "多 Agent 协作处理" in result

    print("✅ Skills 注册通过")


def test_mock_llm_integration():
    """测试 Mock LLM 能触发多 Agent 工具"""
    print("\n=== Mock LLM 集成 ===")

    save_memory([])
    reply = get_ai_response("帮我准备今天的晨间日报", use_mock=True)
    print(reply[:300])
    assert "多 Agent 协作处理" in reply

    print("✅ Mock LLM 集成通过")


def main():
    print("Y·NEX多 Agent 协作测试开始...")

    test_plan_steps()
    test_failure_detection()
    test_execute_known_tool()
    test_retry()
    test_run_multi_agent()
    test_skill_registration()
    test_mock_llm_integration()

    print("\n=== 多 Agent 全部测试通过 ===")


if __name__ == "__main__":
    main()
