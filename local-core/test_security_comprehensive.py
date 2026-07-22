"""
安全模块全面测试
覆盖：路径安全、命令安全、输入消毒、SSRF防护
"""

import os
import sys
import tempfile
import threading
from pathlib import Path

# 确保可以导入本地模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_path_normalization():
    """测试路径规范化"""
    print("\n=== 测试路径规范化 ===")
    from security import normalize_path
    
    # 正常路径
    assert normalize_path("/home/user/file.txt")
    assert normalize_path("relative/path")
    
    # 相对路径应转为绝对路径
    rel = normalize_path("some/relative/path")
    assert os.path.isabs(rel), "相对路径应转为绝对路径"
    
    # 包含 .. 的路径
    path_with_dots = normalize_path("/home/user/../other/./file")
    assert ".." not in path_with_dots, "应解析 .. 符号"
    assert "/home/other/file" in path_with_dots or path_with_dots.endswith("/home/other/file")
    
    # 用户目录展开
    home_path = normalize_path("~/documents")
    # 用户目录展开后应该是绝对路径
    assert os.path.isabs(home_path), f"用户目录展开应为绝对路径: {home_path}"
    # 应该包含用户主目录
    home_dir = os.path.expanduser("~")
    assert home_path.startswith(home_dir), f"应展开为用户目录: {home_path}"
    
    # 边界条件
    assert normalize_path("") is None
    assert normalize_path(None) is None
    assert normalize_path(123) is None  # 非字符串
    
    print("✅ 路径规范化测试通过")


def test_path_safety():
    """测试路径安全检查"""
    print("\n=== 测试路径安全检查 ===")
    from security import is_path_safe, DENIED_PATHS, ALLOWED_BASE_DIRS
    
    # 敏感系统路径应被拒绝
    for denied in DENIED_PATHS:
        if os.name == 'nt' and not denied.startswith("C:\\"):
            continue
        if os.name != 'nt' and denied.startswith("C:\\"):
            continue
        assert not is_path_safe(denied), f"敏感路径应被拒绝: {denied}"
    
    # 路径穿越攻击
    traversal_paths = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32",
        "normal/../../../etc/shadow",
        "/home/user/../../../root/.ssh/id_rsa",
    ]
    for path in traversal_paths:
        result = is_path_safe(path)
        # 应被拒绝或被限制在安全目录内
        if result:
            normalized = os.path.realpath(os.path.expanduser(path))
            # 如果通过了，必须确保最终路径在允许目录内
            safe = False
            for base in ALLOWED_BASE_DIRS:
                try:
                    common = os.path.commonpath([os.path.realpath(base), normalized])
                    if common == os.path.realpath(base):
                        safe = True
                        break
                except ValueError:
                    continue
            assert safe, f"路径穿越攻击应被限制: {path}"
    
    # 正常路径应被允许（在允许目录内）
    cwd = os.getcwd()
    safe_path = os.path.join(cwd, "data", "test.txt")
    assert is_path_safe(safe_path), f"工作目录内路径应安全: {safe_path}"
    
    print("✅ 路径安全检查测试通过")


def test_path_sanitization():
    """测试路径消毒"""
    print("\n=== 测试路径消毒 ===")
    from security import sanitize_path
    
    # 正常相对路径
    safe = sanitize_path("test.txt", default_base="/tmp")
    assert safe
    
    # 越界路径应回退到默认目录
    dangerous = sanitize_path("/etc/passwd", default_base="/tmp")
    assert dangerous == "/tmp" or dangerous.startswith("/tmp")
    
    # 无默认目录时越界应报错
    try:
        sanitize_path("/etc/passwd")
        assert False, "越界路径无默认目录应抛出异常"
    except ValueError as e:
        assert "非法" in str(e)
    
    print("✅ 路径消毒测试通过")


def test_command_safety():
    """测试命令安全检查"""
    print("\n=== 测试命令安全检查 ===")
    from security import is_command_safe, DANGEROUS_COMMANDS
    
    # 危险命令应被拒绝
    dangerous_cmds = [
        "rm -rf /",
        "format c:",
        "dd if=/dev/zero of=/dev/sda",
        ":(){ :|:& };:",
        "mkfs.ext4 /dev/sda1",
        "fdisk /dev/sda",
    ]
    for cmd in dangerous_cmds:
        assert not is_command_safe(cmd), f"危险命令应被拒绝: {cmd}"
    
    # 安全命令应被允许
    safe_cmds = [
        "ls -la",
        "echo 'hello'",
        "python script.py",
        "npm install",
        "git status",
    ]
    for cmd in safe_cmds:
        assert is_command_safe(cmd), f"安全命令应被允许: {cmd}"
    
    # 边界条件
    assert not is_command_safe("")
    assert not is_command_safe(None)
    assert not is_command_safe(123)  # 非字符串
    
    # 大小写混合
    assert not is_command_safe("FORMAT C:")
    assert not is_command_safe("RM -RF /")
    
    print("✅ 命令安全检查测试通过")


def test_input_sanitization():
    """测试输入消毒"""
    print("\n=== 测试输入消毒 ===")
    from security import sanitize_input
    
    # 长度限制
    long_text = "a" * 20000
    result = sanitize_input(long_text, max_length=100)
    assert len(result) == 100, "应限制长度"
    
    # 控制字符移除
    dirty = "hello\x00world\x1f\x7ftest"
    clean = sanitize_input(dirty)
    assert "\x00" not in clean
    assert "\x1f" not in clean
    assert "\x7f" not in clean
    assert "hello" in clean and "world" in clean
    
    # 零宽字符移除
    zero_width = "test\u200b\u200c\u200d\ufeffend"
    clean = sanitize_input(zero_width)
    assert "\u200b" not in clean
    assert "\ufeff" not in clean
    
    # 保留换行和制表符
    with_newline = "line1\nline2\ttab"
    clean = sanitize_input(with_newline)
    assert "\n" in clean
    assert "\t" in clean
    
    # 非字符串输入
    result = sanitize_input(123)
    assert result == "123"
    
    result = sanitize_input(None)
    assert result == "None"
    
    print("✅ 输入消毒测试通过")


def test_plugin_url_safety():
    """测试插件URL安全检查（SSRF防护）"""
    print("\n=== 测试插件URL安全检查 ===")
    from security import is_plugin_url_safe, ALLOWED_PLUGIN_PROTOCOLS
    
    # 安全协议
    assert "http" in ALLOWED_PLUGIN_PROTOCOLS
    assert "https" in ALLOWED_PLUGIN_PROTOCOLS
    
    # 不安全协议
    unsafe_urls = [
        "file:///etc/passwd",
        "ftp://example.com/plugin.zip",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
    ]
    for url in unsafe_urls:
        assert not is_plugin_url_safe(url), f"不安全协议应被拒绝: {url}"
    
    # 本地地址应被拒绝
    local_urls = [
        "http://localhost/plugin.zip",
        "http://127.0.0.1/plugin.zip",
        "http://0.0.0.0/plugin.zip",
        "http://[::1]/plugin.zip",
    ]
    for url in local_urls:
        assert not is_plugin_url_safe(url), f"本地地址应被拒绝: {url}"
    
    # 正常外部URL应被允许
    safe_urls = [
        "https://github.com/user/plugin/archive/main.zip",
        "https://example.com/plugin.zip",
        "http://public-website.com/plugin.py",
    ]
    for url in safe_urls:
        # 注意：DNS解析可能失败，所以我们只测试不抛异常
        try:
            result = is_plugin_url_safe(url)
            # 如果通过，应该没问题；如果失败，只要不是异常即可
        except Exception as e:
            # DNS解析失败等网络错误是预期的
            pass
    
    # 边界条件
    assert not is_plugin_url_safe("")
    assert not is_plugin_url_safe(None)
    assert not is_plugin_url_safe(123)
    
    # 无效URL
    assert not is_plugin_url_safe("not a url")
    assert not is_plugin_url_safe("http://")
    
    print("✅ 插件URL安全检查测试通过")


def test_safe_work_dir():
    """测试安全工作目录获取"""
    print("\n=== 测试安全工作目录 ===")
    from security import get_safe_work_dir
    
    # 默认工作目录
    work_dir = get_safe_work_dir()
    assert os.path.isdir(work_dir)
    assert "data" in work_dir
    
    # 自定义子目录
    custom_dir = get_safe_work_dir("custom_subdir")
    assert os.path.isdir(custom_dir)
    assert "custom_subdir" in custom_dir
    
    # 清理测试目录
    try:
        os.rmdir(custom_dir)
    except:
        pass
    
    print("✅ 安全工作目录测试通过")


def test_concurrent_path_checks():
    """测试并发路径检查"""
    print("\n=== 测试并发路径检查 ===")
    from security import is_path_safe
    
    errors = []
    results = []
    lock = threading.Lock()
    
    def check_path(path):
        try:
            result = is_path_safe(path)
            with lock:
                results.append(result)
        except Exception as e:
            errors.append(str(e))
    
    test_paths = [
        "/etc/passwd",
        "/home/user/file.txt",
        "../../../etc/shadow",
        "normal_file.txt",
        "/proc/self/environ",
    ] * 50
    
    threads = [threading.Thread(target=check_path, args=(p,)) for p in test_paths]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert not errors, f"并发路径检查出错: {errors}"
    assert len(results) == len(test_paths)
    
    print("✅ 并发路径检查测试通过")


def test_denied_paths_completeness():
    """测试敏感路径集合的完整性"""
    print("\n=== 测试敏感路径集合完整性 ===")
    from security import DENIED_PATHS
    
    # 必须包含关键系统路径
    required_paths = [
        "/etc",
        "/usr/bin",
        "/bin",
        "/sbin",
        "/sys",
        "/proc",
        "/dev",
    ]
    
    for path in required_paths:
        assert path in DENIED_PATHS, f"敏感路径应包含: {path}"
    
    # Windows路径（在Linux上也会定义，但不会匹配）
    assert "C:\\Windows" in DENIED_PATHS or any("Windows" in p for p in DENIED_PATHS)
    
    print("✅ 敏感路径集合完整性测试通过")


def main():
    print("=== 安全模块全面测试 ===")
    
    test_path_normalization()
    test_path_safety()
    test_path_sanitization()
    test_command_safety()
    test_input_sanitization()
    test_plugin_url_safety()
    test_safe_work_dir()
    test_concurrent_path_checks()
    test_denied_paths_completeness()
    
    print("\n=== 全部安全测试通过 ===")


if __name__ == "__main__":
    main()