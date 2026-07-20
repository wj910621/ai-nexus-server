"""
config.py 配置校验测试
======================

目标：覆盖 config.validate_config() 的关键分支，防止配置错误时静默通过
导致 LLM 调用全部失败、唤醒词模型加载失败等不可用问题。

注意：config.py 模块在 import 时即创建全局 settings 实例，因此本测试
仅针对 validate_config(settings) 的纯函数行为进行覆盖，使用 monkeypatch
临时修改 settings 字段并在测试后恢复，确保不影响其他模块。
"""

import os
import sys
import tempfile
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
from config import validate_config, Settings  # noqa: E402


def _with_settings(**overrides):
    """临时覆盖全局 settings 字段，返回恢复函数。"""
    saved = {}
    for k, v in overrides.items():
        saved[k] = getattr(config.settings, k)
        setattr(config.settings, k, v)

    def restore():
        for k, v in saved.items():
            setattr(config.settings, k, v)
    return restore


def test_no_api_key_and_no_local_model_warns():
    """未配置 LLM：应给出明确问题。"""
    restore = _with_settings(
        use_local_first=False,
        deepseek_api_key="",
        local_base_url="http://localhost:11434",
    )
    try:
        issues = validate_config()
        assert any("DEEPSEEK_API_KEY" in i for i in issues), \
            f"应报 DEEPSEEK_API_KEY 缺失，但得到 {issues}"
    finally:
        restore()
    print("  ✓ 未配置 LLM：明确报错")


def test_local_model_with_valid_base_url_ok():
    """本地模型 + 合法 base URL：不应因 base URL 报错。"""
    restore = _with_settings(
        use_local_first=True,
        local_base_url="http://localhost:11434",
        deepseek_api_key="",
    )
    try:
        issues = validate_config()
        assert not any("LOCAL_BASE_URL" in i for i in issues), \
            f"合法 base URL 不应报错，但得到 {issues}"
    finally:
        restore()
    print("  ✓ 本地模式 + 合法 URL：通过")


def test_local_model_with_invalid_base_url_caught():
    """本地模式 + 非法 base URL：必须报错。"""
    restore = _with_settings(
        use_local_first=True,
        local_base_url="localhost:11434",  # 缺 scheme
        deepseek_api_key="",
    )
    try:
        issues = validate_config()
        assert any("LOCAL_BASE_URL" in i for i in issues), \
            f"非法 base URL 应报错，但得到 {issues}"
    finally:
        restore()
    print("  ✓ 本地模式 + 非法 URL：明确报错")


def test_wake_word_model_path_must_exist():
    """自定义唤醒词模型路径不存在时应报错。"""
    fake = "/nonexistent/path/that/should/not/exist/ynex_xyz_12345.pmdl"
    restore = _with_settings(wake_word_model_path=fake)
    try:
        issues = validate_config()
        assert any("唤醒词模型不存在" in i for i in issues), \
            f"不存在的唤醒词路径应报错，但得到 {issues}"
    finally:
        restore()
    print("  ✓ 唤醒词模型路径不存在：报错")


def test_wake_word_model_path_exists_ok():
    """合法存在的唤醒词模型路径：不产生相关 issue。"""
    with tempfile.NamedTemporaryFile(suffix=".pmdl", delete=False) as tf:
        path = tf.name
    try:
        restore = _with_settings(wake_word_model_path=path)
        try:
            issues = validate_config()
            assert not any("唤醒词模型" in i for i in issues), \
                f"存在路径不应报错，但得到 {issues}"
        finally:
            restore()
    finally:
        os.unlink(path)
    print("  ✓ 合法唤醒词模型路径：通过")


def test_having_api_key_silences_llm_warning():
    """配置了 deepseek_api_key 时不报 LLM 警告。"""
    restore = _with_settings(
        use_local_first=False,
        deepseek_api_key="sk-fake-just-for-test",
    )
    try:
        issues = validate_config()
        assert not any("DEEPSEEK_API_KEY" in i for i in issues), \
            f"已配置 key 时不应报 LLM 警告，但得到 {issues}"
    finally:
        restore()
    print("  ✓ 已配置 API Key：不报 LLM 警告")


def test_multiple_issues_aggregated():
    """多个问题应同时返回，便于一次性发现。"""
    restore = _with_settings(
        use_local_first=False,
        deepseek_api_key="",
        wake_word_model_path="/definitely/not/a/real/path/ynex.pmdl",
    )
    try:
        issues = validate_config()
        # 至少包含 LLM 与唤醒词两类问题
        assert any("DEEPSEEK" in i for i in issues)
        assert any("唤醒词" in i for i in issues)
    finally:
        restore()
    print("  ✓ 多问题聚合返回")


def test_settings_default_values_consistent():
    """Settings 默认值在重启后应保持稳定（防止默认值漂移回归）。"""
    fresh = Settings()
    # 关键安全默认
    assert fresh.api_bind_host == "127.0.0.1", "默认应仅监听回环"
    assert fresh.trusted_subnets == "127.0.0.1/32", "默认应仅信任本机"
    assert fresh.api_key_required is True, "生产环境应强制要求 API Key"
    # 关键限流默认
    assert fresh.rate_limit_enabled is True
    assert fresh.rate_limit_requests_per_minute > 0
    print("  ✓ Settings 关键默认未发生漂移")


def main():
    print("=== config.py 校验测试 ===\n")
    tests = [
        test_no_api_key_and_no_local_model_warns,
        test_local_model_with_valid_base_url_ok,
        test_local_model_with_invalid_base_url_caught,
        test_wake_word_model_path_must_exist,
        test_wake_word_model_path_exists_ok,
        test_having_api_key_silences_llm_warning,
        test_multiple_issues_aggregated,
        test_settings_default_values_consistent,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__} 异常: {type(e).__name__}: {e}")
            failed += 1
    if failed:
        print(f"\n❌ {failed} 个用例失败")
        sys.exit(1)
    print(f"\n✅ 全部 {len(tests)} 个 config 用例通过")


if __name__ == "__main__":
    main()
