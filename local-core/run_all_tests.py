"""
统一测试运行器
运行所有新增的全面测试套件
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# 测试文件列表
TEST_FILES = [
    "test_auth_comprehensive.py",
    "test_security_comprehensive.py",
    "test_plugin_system_comprehensive.py",
    "test_rate_limiter_comprehensive.py",
    # 原有测试
    "test_cache.py",
    "test_rate_limiter.py",
    "test_async_utils.py",
    "test_new_features.py",
]


def run_test(test_file: str) -> tuple[bool, str]:
    """运行单个测试文件"""
    test_path = Path(__file__).parent / test_file
    
    if not test_path.exists():
        return False, f"测试文件不存在: {test_file}"
    
    print(f"\n{'='*60}")
    print(f"运行测试: {test_file}")
    print('='*60)
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_path)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(test_path.parent)
        )
        
        elapsed = time.time() - start_time
        
        # 输出结果
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        success = result.returncode == 0
        
        if success:
            print(f"\n✅ {test_file} 通过 ({elapsed:.2f}s)")
        else:
            print(f"\n❌ {test_file} 失败 (返回码: {result.returncode})")
        
        return success, f"{test_file}: {'通过' if success else '失败'}"
        
    except subprocess.TimeoutExpired:
        return False, f"{test_file}: 超时"
    except Exception as e:
        return False, f"{test_file}: 异常 - {str(e)}"


def main():
    """运行所有测试"""
    print("="*60)
    print("Y·NEX 测试套件运行器")
    print("="*60)
    
    # 确保数据目录存在
    os.makedirs("data", exist_ok=True)
    
    results = []
    start_time = time.time()
    
    for test_file in TEST_FILES:
        success, message = run_test(test_file)
        results.append((test_file, success, message))
    
    total_time = time.time() - start_time
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    passed = sum(1 for _, success, _ in results if success)
    failed = len(results) - passed
    
    for test_file, success, message in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {test_file}")
    
    print("\n" + "-"*60)
    print(f"总计: {len(results)} 个测试文件")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"总耗时: {total_time:.2f}秒")
    
    if failed == 0:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())