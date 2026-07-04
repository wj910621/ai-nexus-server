"""
代码沙箱测试
"""

from code_sandbox import safe_eval, execute_shell, execute_python


def test_safe_eval():
    print("\n=== 安全计算 ===")
    cases = [
        "1 + 2 * 3",
        "sqrt(16) + pow(2, 3)",
        "max(1, 5, 3)",
    ]
    for c in cases:
        print(f"  {c} -> {safe_eval(c)}")
    print("✅ 安全计算通过")


def test_shell():
    print("\n=== Shell 执行 ===")
    print(execute_shell("python --version"))
    print(execute_shell("rm -rf /"))  # 应被拒绝
    print("✅ Shell 白名单通过")


def test_python():
    print("\n=== Python 代码 ===")
    print(execute_python("print('hello world')"))
    print(execute_python("import os"))  # 应被拒绝
    print("✅ Python 沙箱通过")


def main():
    print("=== 代码沙箱测试 ===")
    test_safe_eval()
    test_shell()
    test_python()
    print("\n全部测试完成")


if __name__ == "__main__":
    main()
