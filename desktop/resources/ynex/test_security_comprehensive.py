"""
security.py 综合测试
覆盖：路径遍历防护、命令注入防护、URL安全校验等关键安全逻辑
"""

import os
import tempfile
import shutil
import sys

sys.path.insert(0, os.path.dirname(__file__))

import security
from security import (
    normalize_path,
    is_path_safe,
    sanitize_path,
    is_command_safe,
    sanitize_input,
    is_plugin_url_safe,
    get_safe_work_dir,
)


def test_path_normalization():
    """测试路径规范化"""
    print("\n=== 测试路径规范化 ===")

    # 正常路径
    assert normalize_path("/tmp/test") == "/tmp/test"

    # 用户目录展开
    home = os.path.expanduser("~")
    assert normalize_path("~/test").startswith(home)

    # 相对路径解析
    cwd = os.getcwd()
    assert normalize_path("relative/path").startswith(cwd)

    # None 和空字符串
    assert normalize_path(None) is None
    assert normalize_path("") is None
    assert normalize_path(123) is None

    # 路径遍历攻击
    malicious = "../../../etc/passwd"
    result = normalize_path(malicious)
    assert result is not None  # 规范化后是合法路径
    assert ".." not in result

    print("✓ 路径规范化正确")


def test_path_safety_basic():
    """测试基础路径安全检查"""
    print("\n=== 测试基础路径安全检查 ===")

    # 允许的路径（必须在允许的基目录内）
    cwd = os.getcwd()
    assert is_path_safe(os.path.join(cwd, "test"))
    assert is_path_safe(os.path.join(cwd, "data/test.txt"))
    assert is_path_safe(os.path.expanduser("~/documents"))

    # 敏感系统路径（Windows）
    if os.name == "nt":
        assert not is_path_safe("C:\\Windows\\System32")
        assert not is_path_safe("C:\\Program Files\\App")

    # 敏感系统路径（Unix）
    assert not is_path_safe("/etc/passwd")
    assert not is_path_safe("/usr/bin/python")
    assert not is_path_safe("/bin/bash")
    assert not is_path_safe("/proc/self")

    print("✓ 基础路径安全检查正确")


def test_path_traversal_protection():
    """测试路径遍历攻击防护"""
    print("\n=== 测试路径遍历防护 ===")

    cwd = os.getcwd()

    # 在允许目录内的遍历
    safe_path = os.path.join(cwd, "data", "test.txt")
    assert is_path_safe(safe_path)

    # 尝试遍历到父目录
    traversal = os.path.join(cwd, "data", "..", "..", "..", "etc", "passwd")
    assert not is_path_safe(traversal)

    # 复杂的路径遍历
    complex_traversal = "/tmp/../../../etc/passwd"
    assert not is_path_safe(complex_traversal)

    print("✓ 路径遍历防护正确")


def test_path_sanitization():
    """测试路径清洗"""
    print("\n=== 测试路径清洗 ===")

    # 正常相对路径
    cwd = os.getcwd()
    safe = sanitize_path("data/test.txt", cwd)
    assert safe.endswith("data/test.txt")

    # 越界路径应返回默认基目录
    unsafe = "../../../etc/passwd"
    result = sanitize_path(unsafe, cwd)
    assert result == os.path.realpath(cwd)

    # 无默认基目录时应抛出异常
    try:
        sanitize_path("/etc/passwd")
        assert False, "应抛出异常"
    except ValueError as e:
        assert "非法路径" in str(e)

    print("✓ 路径清洗正确")


def test_command_safety():
    """测试命令安全检查"""
    print("\n=== 测试命令安全检查 ===")

    # 安全命令
    assert is_command_safe("ls -la")
    assert is_command_safe("python script.py")
    assert is_command_safe("echo hello")

    # 危险命令（黑名单）
    assert not is_command_safe("rm -rf /")
    assert not is_command_safe("rm -rf /*")
    assert not is_command_safe("format C:")
    assert not is_command_safe("dd if=/dev/zero of=/dev/sda")
    assert not is_command_safe("mkfs.ext4 /dev/sda1")

    # Fork 炸弹
    assert not is_command_safe(":(){ :|:& };:")

    # None 和空字符串
    assert not is_command_safe(None)
    assert not is_command_safe("")
    assert not is_command_safe(123)

    print("✓ 命令安全检查正确")


def test_input_sanitization():
    """测试输入清洗"""
    print("\n=== 测试输入清洗 ===")

    # 长度限制
    long_text = "a" * 20000
    result = sanitize_input(long_text, max_length=1000)
    assert len(result) == 1000

    # 控制字符移除
    text_with_control = "Hello\x00World\x08Test\x1f"
    clean = sanitize_input(text_with_control)
    assert "\x00" not in clean
    assert "\x08" not in clean
    assert "\x1f" not in clean
    assert "HelloWorldTest" in clean

    # 零宽字符移除
    text_with_zw = "Test\u200b\u200c\u200dContent\ufeff"
    clean = sanitize_input(text_with_zw)
    assert "\u200b" not in clean
    assert "\ufeff" not in clean

    # 保留换行和制表符
    text_with_newline = "Line1\nLine2\tTab"
    clean = sanitize_input(text_with_newline)
    assert "\n" in clean
    assert "\t" in clean

    # 非 string 类型
    assert sanitize_input(123) == "123"
    assert sanitize_input(None) == "None"

    print("✓ 输入清洗正确")


def test_plugin_url_safety():
    """测试插件 URL 安全校验"""
    print("\n=== 测试插件 URL 安全校验 ===")

    # 安全 URL
    assert is_plugin_url_safe("https://github.com/user/plugin.git")
    assert is_plugin_url_safe("https://example.com/package.zip")

    # 不安全的协议
    assert not is_plugin_url_safe("ftp://example.com/plugin")
    assert not is_plugin_url_safe("file:///etc/passwd")

    # 本地地址（应禁止）
    assert not is_plugin_url_safe("https://localhost/plugin.zip")
    assert not is_plugin_url_safe("https://127.0.0.1/plugin.zip")
    assert not is_plugin_url_safe("https://0.0.0.0/plugin.zip")

    # 内网地址（应禁止）
    assert not is_plugin_url_safe("https://192.168.1.1/plugin.zip")
    assert not is_plugin_url_safe("https://10.0.0.1/plugin.zip")
    assert not is_plugin_url_safe("https://172.16.0.1/plugin.zip")

    # None 和空字符串
    assert not is_plugin_url_safe(None)
    assert not is_plugin_url_safe("")
    assert not is_plugin_url_safe(123)

    print("✓ 插件 URL 安全校验正确")


def test_allowed_directory_boundaries():
    """测试允许目录边界检查"""
    print("\n=== 测试目录边界检查 ===")

    # 创建临时目录结构
    test_dir = tempfile.mkdtemp(prefix="test_security_")
    allowed_dir = os.path.join(test_dir, "allowed")
    os.makedirs(allowed_dir)

    try:
        # 在允许目录内的文件
        safe_file = os.path.join(allowed_dir, "test.txt")
        assert is_path_safe(safe_file, allowed_bases=[allowed_dir])

        # 在允许目录外的文件
        outside_file = os.path.join(test_dir, "outside.txt")
        assert not is_path_safe(outside_file, allowed_bases=[allowed_dir])

        # 符号链接检查（如果系统支持）
        link_path = os.path.join(allowed_dir, "link")
        try:
            os.symlink(outside_file, link_path)
            # 符号链接解析后仍应被拦截
            assert not is_path_safe(link_path, allowed_bases=[allowed_dir])
        except (OSError, NotImplementedError):
            pass  # 某些系统不支持符号链接

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)

    print("✓ 目录边界检查正确")


def test_case_sensitivity():
    """测试大小写不敏感检查"""
    print("\n=== 测试大小写不敏感 ===")

    # Windows 路径大小写
    if os.name == "nt":
        assert not is_path_safe("c:\\windows\\system32")
        assert not is_path_safe("C:\\WINDOWS\\SYSTEM32")

    # Unix 路径大小写
    assert not is_path_safe("/ETC/passwd")
    assert not is_path_safe("/Bin/bash")

    print("✓ 大小写检查正确")


def test_safe_work_dir_creation():
    """测试安全工作目录创建"""
    print("\n=== 测试安全工作目录 ===")

    test_dir = tempfile.mkdtemp(prefix="test_work_dir_")
    os.chdir(test_dir)

    try:
        work_dir = get_safe_work_dir("test_data")

        # 应该已创建
        assert os.path.exists(work_dir)
        assert os.path.isdir(work_dir)

        # 应该在当前目录下
        assert work_dir.startswith(os.path.realpath(test_dir))

    finally:
        os.chdir("/")
        shutil.rmtree(test_dir, ignore_errors=True)

    print("✓ 安全工作目录创建正确")


def test_empty_and_invalid_inputs():
    """测试空值和无效输入"""
    print("\n=== 测试空值和无效输入 ===")

    # 空路径
    assert normalize_path(None) is None
    assert normalize_path("") is None

    # 空命令
    assert not is_command_safe(None)
    assert not is_command_safe("")

    # 空 URL
    assert not is_plugin_url_safe(None)
    assert not is_plugin_url_safe("")

    print("✓ 空值处理正确")


def run_all_tests():
    """运行所有测试"""
    test_path_normalization()
    test_path_safety_basic()
    test_path_traversal_protection()
    test_path_sanitization()
    test_command_safety()
    test_input_sanitization()
    test_plugin_url_safety()
    test_allowed_directory_boundaries()
    test_case_sensitivity()
    test_safe_work_dir_creation()
    test_empty_and_invalid_inputs()

    print("\n" + "="*50)
    print("✅ 所有 security.py 测试通过")
    print("="*50)


if __name__ == "__main__":
    run_all_tests()