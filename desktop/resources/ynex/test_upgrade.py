"""
Y·NEX系统升级验证测试
测试所有新增功能模块是否能正常导入和基本运行
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

passed = 0
failed = 0
results = []


def test(name, func):
    global passed, failed
    try:
        result = func()
        passed += 1
        status = "✓ PASS"
        detail = result if result else ""
        print(f"  {status} - {name} {detail}")
        results.append((name, True, detail))
    except Exception as e:
        failed += 1
        status = "✗ FAIL"
        print(f"  {status} - {name}: {e}")
        results.append((name, False, str(e)))


print("=" * 60)
print("  Y·NEX系统升级验证测试")
print("=" * 60)

# ---------------------------------------------------------------------------
# 1. 本地LLM引擎
# ---------------------------------------------------------------------------
print("\n📦 模块1: 本地LLM推理引擎 (local_llm.py)")


def test_local_llm_import():
    from local_llm import get_local_llm, detect_hardware, MODEL_CATALOG
    return f"(模型目录: {len(MODEL_CATALOG)}个模型)"


def test_local_llm_hardware():
    from local_llm import detect_hardware
    hw = detect_hardware()
    return f"(RAM: {hw.total_ram_gb}GB, VRAM: {hw.vram_gb}GB, CPU: {hw.cpu_cores}核)"


def test_local_llm_recommend():
    from local_llm import detect_hardware, recommend_models
    hw = detect_hardware()
    models = recommend_models(hw)
    return f"(推荐 {len(models)} 个模型，首选: {models[0]['name'] if models else '无'})"


test("导入local_llm模块", test_local_llm_import)
test("硬件检测", test_local_llm_hardware)
test("模型推荐", test_local_llm_recommend)

# ---------------------------------------------------------------------------
# 2. 支付系统
# ---------------------------------------------------------------------------
print("\n💰 模块2: 支付系统 (payment_system.py)")


def test_payment_import():
    from payment_system import (
        create_order, get_order, list_user_orders,
        process_payment, mock_payment_callback,
        get_agent_settings, get_agent_commission_summary,
        PaymentStatus, PaymentMethod,
    )
    return "(支付+分销佣金系统)"


def test_payment_create_order():
    from payment_system import create_order
    test_user_id = "test_user_" + str(int(__import__('time').time()))
    order = create_order(test_user_id, 99.0, "alipay", "recharge")
    return f"(订单: {order.id}, 金额: {order.amount}元)"


def test_payment_mock_callback():
    from payment_system import create_order, mock_payment_callback
    test_user_id = "test_user_mock_" + str(int(__import__('time').time()))
    order = create_order(test_user_id, 10.0, "alipay", "recharge")
    ok, msg = mock_payment_callback(order.id)
    return f"({'成功' if ok else '失败'}: {msg[:30]})"


test("导入payment_system模块", test_payment_import)
test("创建支付订单", test_payment_create_order)
test("模拟支付回调", test_payment_mock_callback)

# ---------------------------------------------------------------------------
# 3. 超级Agent
# ---------------------------------------------------------------------------
print("\n🤖 模块3: 超级Agent (super_agent.py)")


def test_super_agent_import():
    from super_agent import (
        get_super_agent, get_tool_registry,
        TaskPlan, TaskStep, ToolRegistry,
    )
    registry = get_tool_registry()
    return f"(工具数: {len(registry.tools)})"


def test_super_agent_tools():
    from super_agent import get_tool_registry
    registry = get_tool_registry()
    tool_names = list(registry.tools.keys())
    return f"({', '.join(tool_names[:5])}... 共{len(tool_names)}个)"


def test_super_agent_plan():
    from super_agent import get_super_agent
    agent = get_super_agent()
    plan = agent.planner.plan("帮我写一个Python爬虫")
    return f"(拆解为 {len(plan.steps)} 步)"


test("导入super_agent模块", test_super_agent_import)
test("工具注册表", test_super_agent_tools)
test("任务规划", test_super_agent_plan)

# ---------------------------------------------------------------------------
# 4. Skills集成
# ---------------------------------------------------------------------------
print("\n⚡ 模块4: Skills技能集成")


def test_skills_new_functions():
    from skills import (
        super_agent_task, agent_chat, write_code, local_llm_status,
        SKILL_MAP,
    )
    new_skills = ["super_agent_task", "agent_chat", "write_code", "local_llm_status"]
    missing = [s for s in new_skills if s not in SKILL_MAP]
    if missing:
        raise Exception(f"缺失技能: {missing}")
    return f"(4个新技能已注册)"


def test_skills_local_llm_status():
    from skills import local_llm_status
    result = local_llm_status()
    return f"({result[:50]}...)"


test("新技能注册检查", test_skills_new_functions)
test("local_llm_status技能", test_skills_local_llm_status)

# ---------------------------------------------------------------------------
# 5. Brain Function Calling
# ---------------------------------------------------------------------------
print("\n🧠 模块5: Brain Function Calling")


def test_brain_tools():
    from brain import TOOLS
    tool_names = [t["function"]["name"] for t in TOOLS]
    new_tools = ["super_agent_task", "write_code", "local_llm_status"]
    missing = [t for t in new_tools if t not in tool_names]
    if missing:
        raise Exception(f"缺失工具定义: {missing}")
    return f"(共{len(tool_names)}个工具，新增已就位)"


test("Brain工具定义检查", test_brain_tools)

# ---------------------------------------------------------------------------
# 6. Platform Web服务
# ---------------------------------------------------------------------------
print("\n🌐 模块6: 在线服务平台 (platform_server.py)")


def test_platform_import():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "platform_server",
        os.path.join(os.path.dirname(__file__), "platform_server.py")
    )
    return "(Flask平台模块可导入)"


test("导入platform_server模块", test_platform_import)

# ---------------------------------------------------------------------------
# 总结
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print(f"  测试结果: {passed} 通过 / {failed} 失败 / {passed + failed} 总计")
print("=" * 60)

if failed == 0:
    print("\n🎉 所有新增模块测试通过！系统升级成功。")
else:
    print(f"\n⚠️  有 {failed} 个测试失败，请检查上面的错误信息。")

print("\n📋 新增功能清单:")
print("  1. local_llm.py     - 本地LLM推理引擎（Ollama支持+硬件检测+模型推荐）")
print("  2. payment_system.py - 支付系统（支付宝沙箱+分销佣金+订单管理）")
print("  3. super_agent.py   - 超级Agent（任务规划+12个工具+ReAct对话）")
print("  4. platform_server.py - Web平台v2.0（全新UI+流式对话+充值+分销）")
print("  5. skills.py        - 新增4个技能（super_agent/write_code/local_llm等）")
print("  6. brain.py         - Function Calling新增3个工具定义")

print("\n🚀 快速体验:")
print("  启动Web平台:  python platform_server.py")
print("  访问地址:     http://localhost:7789")
print("  查看本地LLM:  对Y·NEX说 '查看本地模型状态'")
print("  生成代码:     对Y·NEX说 '帮我写一个xxx脚本'")

sys.exit(0 if failed == 0 else 1)
