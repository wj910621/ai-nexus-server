"""
全能力集成测试
验证视觉感知、自托管服务、远场麦克风、中文唤醒词等模块的导入和基础功能
"""

import os
import sys
import time


def test_vision_imports():
    print("\n=== 测试视觉感知模块 ===")
    from vision import (
        is_camera_available, VisionResult, MotionDetector,
        FaceDetector, PoseDetector, capture_snapshot,
        analyze_frame, vision_summary
    )
    print("视觉模块导入成功")
    print(f"摄像头可用: {is_camera_available()}")
    print("✅ 视觉模块测试通过")


def test_selfhost():
    print("\n=== 测试自托管服务模块 ===")
    from selfhost import (
        paperless_available, immich_available, n8n_available,
        search_documents, search_photos, list_workflows,
        selfhost_status, trigger_webhook
    )
    print("自托管模块导入成功")
    print(selfhost_status())
    print("✅ 自托管模块测试通过")


def test_far_field_mic():
    print("\n=== 测试远场麦克风 + 语音增强 ===")
    from far_field_mic import (
        reduce_noise, agc, simple_noise_gate, VAD,
        enhance_audio, mic_config_guide
    )
    print("语音增强模块导入成功")

    import numpy as np
    sr = 16000
    t = np.linspace(0, 1, sr, endpoint=False)
    clean = 0.1 * np.sin(2 * np.pi * 440 * t)
    noise = 0.02 * np.random.randn(len(t))
    audio = clean + noise

    # 测试 AGC
    agced = agc(audio)
    print(f"AGC 峰值: {np.max(np.abs(agced)):.3f}")
    assert np.max(np.abs(agced)) > 0.2, "AGC 未生效"

    # 测试噪声门
    gated = simple_noise_gate(audio, threshold=0.05)
    print(f"噪声门后非零比例: {np.mean(gated != 0):.2%}")

    # 测试 VAD
    vad = VAD(sample_rate=sr)
    pcm = (audio * 32768).astype(np.int16).tobytes()
    result = vad.is_speech(pcm)
    print(f"VAD 检测结果: {result}")

    print("✅ 远场麦克风模块测试通过")


def test_wake_word_zh():
    print("\n=== 测试中文唤醒词模块 ===")
    from wake_word_zh import (
        WakeWordDetector, list_available_models,
        get_training_guide, BUILTIN_MODELS
    )
    print("唤醒词模块导入成功")
    print(f"内置模型数量: {len(BUILTIN_MODELS)}")
    print(f"可用模型: {list_available_models()[:5]}...")
    print("训练指南获取成功:", len(get_training_guide()) > 100)
    print("✅ 中文唤醒词模块测试通过")


def test_skills_registration():
    print("\n=== 测试技能注册 ===")
    from skills import SKILL_MAP

    new_skills = [
        "vision_check", "vision_snapshot",
        "search_docs", "search_photos", "memory_lane",
        "list_workflows", "trigger_workflow", "selfhost_status"
    ]
    missing = [s for s in new_skills if s not in SKILL_MAP]
    if missing:
        print(f"❌ 缺少技能: {missing}")
        assert False
    print(f"新技能全部注册成功: {new_skills}")
    print("✅ 技能注册测试通过")


def test_brain_tools():
    print("\n=== 测试 Brain 工具定义 ===")
    from brain import TOOLS
    tool_names = [t["function"]["name"] for t in TOOLS]

    new_tools = [
        "vision_check", "vision_snapshot",
        "search_docs", "search_photos", "memory_lane",
        "list_workflows", "trigger_workflow", "selfhost_status"
    ]
    missing = [t for t in new_tools if t not in tool_names]
    if missing:
        print(f"❌ 缺少工具定义: {missing}")
        assert False
    print(f"新工具全部定义成功: {new_tools}")
    print(f"工具总数: {len(TOOLS)}")
    print("✅ Brain 工具定义测试通过")


def main():
    print("=== Y·NEX全能力集成测试 ===\n")

    tests = [
        test_vision_imports,
        test_selfhost,
        test_far_field_mic,
        test_wake_word_zh,
        test_skills_registration,
        test_brain_tools,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n=== 测试完成：{passed} 通过, {failed} 失败 ===")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
