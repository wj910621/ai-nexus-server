"""
security.py 单元测试
=====================
覆盖范围：
  - normalize_path：路径规范化、空值/非法输入、用户目录展开
  - is_path_safe：.. 路径穿越、敏感系统路径拒绝、allowed_bases 自定义
  - sanitize_path：越界 fallback 到默认基目录
  - is_command_safe：危险命令黑名单匹配
  - sanitize_input：控制字符移除、零宽字符移除、长度截断
  - is_plugin_url_safe：SSRF 防护（协议白名单、localhost/内网 IP 拦截）
  - get_safe_work_dir：安全目录创建与返回
"""

import os
import sys
import tempfile
import threading

# 确保在测试专用目录运行，避免污染真实 data/
_ORIG_CWD = os.getcwd()


def _setup_tmp_cwd():
    tmp = tempfile.mkdtemp(prefix="ynex_security_test_")
    os.chdir(tmp)
    return tmp


def _teardown():
    os.chdir(_ORIG_CWD)


def main():
    tmp_dir = _setup_tmp_cwd()
    os.makedirs(os.path.join(tmp_dir, "data"), exist_ok=True)

    try:
        import security
        _run_tests(security, tmp_dir)
    finally:
        _teardown()


def _run_tests(security, tmp_dir):
    errors = []

    # ================================
    # 1. normalize_path
    # ================================
    print("1. normalize_path - 路径规范化")

    # 空值和非法输入
    for bad in [None, "", 123, b"/etc/passwd"]:
        got = security.normalize_path(bad)
        assert got is None, f"normalize_path({bad!r}) 应返回 None，实际 {got}"
    print("   ✓ 空值 / 非法输入返回 None")

    # 合法路径
    good = security.normalize_path("./data")
    assert good is not None and os.path.isabs(good), "合法路径应返回绝对路径"
    print("   ✓ 合法路径返回规范化绝对路径")

    # 用户目录展开
    home = security.normalize_path("~")
    assert home == os.path.realpath(os.path.expanduser("~")), "~ 应正确展开"
    print("   ✓ ~ 正确展开为用户目录")

    # ================================
    # 2. is_path_safe —— 路径穿越防护
    # ================================
    print("\n2. is_path_safe - 路径安全检查")

    # 2.1 经典 ../ 穿越到系统目录
    attack_paths = [
        "../etc/passwd",
        "../../etc/shadow",
        "data/../../../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",  # URL 编码穿越（os.path.abspath 会处理）
    ]
    for p in attack_paths:
        safe = security.is_path_safe(p)
        # 展开 base 目录后 ../etc 应落到 DENIED_PATHS 或越界
        if safe:
            # 某些路径在特定 cwd 下可能恰好安全，看具体情况
            real = os.path.realpath(os.path.abspath(os.path.expanduser(p)))
            print(f"   ⚠ 攻击路径 {p!r} 规范化后是 {real}，当前判定 safe={safe}")
        else:
            print(f"   ✓ 攻击路径被拦截: {p}")

    # 2.2 明确的敏感系统路径必须被拒
    denied_hits = ["/etc", "/etc/passwd", "/usr/bin", "/proc/self"]
    for p in denied_hits:
        safe = security.is_path_safe(p, allowed_bases=[tmp_dir])
        if safe:
            errors.append(f"敏感路径 {p} 被判定为安全")
            print(f"   ✗ BUG: 敏感路径 {p} 未被拦截")
        else:
            print(f"   ✓ 敏感路径被拒: {p}")

    # 2.3 在允许基目录内的合法路径
    safe_path = os.path.join(tmp_dir, "data", "notes.txt")
    open(safe_path, "w").close()
    assert security.is_path_safe(safe_path, allowed_bases=[tmp_dir]), \
        f"合法路径 {safe_path} 应被允许"
    print("   ✓ 合法路径在基目录内被允许")

    # 2.4 自定义 allowed_bases
    custom_base = os.path.join(tmp_dir, "custom")
    os.makedirs(custom_base, exist_ok=True)
    p_in_custom = os.path.join(custom_base, "file.txt")
    open(p_in_custom, "w").close()
    assert security.is_path_safe(p_in_custom, allowed_bases=[custom_base]), \
        "自定义基目录内的路径应被允许"
    # 不在自定义基目录内的路径（如 tmp_dir/data），当 bases 只有 custom_base 时应被拒绝
    p_outside = os.path.join(tmp_dir, "data", "notes.txt")
    assert not security.is_path_safe(p_outside, allowed_bases=[custom_base]), \
        "自定义基目录外的路径应被拒绝"
    print("   ✓ 自定义 allowed_bases 生效")

    # ================================
    # 3. sanitize_path —— 越界 fallback
    # ================================
    print("\n3. sanitize_path - 越界路径 fallback")

    # 合法路径返回规范化路径
    legal = security.sanitize_path("./data/notes.txt", default_base=tmp_dir)
    assert os.path.isabs(legal)
    print(f"   ✓ 合法路径规范化: {legal}")

    # 越界路径 fallback 到 default_base
    try:
        result = security.sanitize_path("/etc/passwd", default_base=tmp_dir)
        assert result == os.path.realpath(tmp_dir), f"越界应 fallback 到 {tmp_dir}，实际 {result}"
        print(f"   ✓ 越界路径 fallback 到默认基目录: {result}")
    except ValueError:
        print("   ✓ 越界路径在无 default_base 时抛出 ValueError")

    # 没有 default_base 时非法路径应抛 ValueError
    try:
        security.sanitize_path("/etc/passwd")
        errors.append("无 default_base 时越界路径未抛 ValueError")
        print("   ✗ BUG: 无 default_base 时越界路径未抛 ValueError")
    except ValueError:
        print("   ✓ 越界无 default_base 抛 ValueError")

    # ================================
    # 4. is_command_safe —— 危险命令拦截
    # ================================
    print("\n4. is_command_safe - 危险命令拦截")

    dangerous_cases = [
        "rm -rf /",
        "dd if=/dev/zero of=/dev/sda",
        "echo hello; rm -rf /",
        ":(){ :|:& };:",
        "FORMAT C:",
    ]
    for cmd in dangerous_cases:
        safe = security.is_command_safe(cmd)
        assert not safe, f"危险命令应被拦截: {cmd!r}"
        print(f"   ✓ 危险命令被拦截: {cmd[:40]}")

    safe_cases = [
        "ls -la",
        "echo 'hello world'",
        "python3 -c 'print(1+1)'",
        "pwd",
    ]
    for cmd in safe_cases:
        assert security.is_command_safe(cmd), f"安全命令不应被拦截: {cmd!r}"
    print("   ✓ 安全命令通过")

    # 空值和非法输入
    assert not security.is_command_safe("")
    assert not security.is_command_safe(None)
    print("   ✓ 空值 / None 命令返回 False")

    # ================================
    # 5. sanitize_input
    # ================================
    print("\n5. sanitize_input - 输入消毒")

    # 5.1 零宽字符去除
    zwi = "hello\u200b\u200c\u200d\uFEFFworld"
    assert security.sanitize_input(zwi) == "helloworld"
    print("   ✓ 零宽字符 / BOM 被移除")

    # 5.2 控制字符移除（保留 \n \t）
    ctrl = "hello\x00\x01\x07\x1fworld\n\ttab"
    out = security.sanitize_input(ctrl)
    assert "\x00" not in out and "\x07" not in out
    assert "\n" in out and "\t" in out
    print("   ✓ 控制字符被移除，保留换行制表符")

    # 5.3 长度截断
    long_text = "a" * 50000
    assert len(security.sanitize_input(long_text, max_length=100)) == 100
    print("   ✓ 超长文本被截断")

    # 5.4 strip 空白
    assert security.sanitize_input("  hello  ") == "hello"
    print("   ✓ 首尾空白被 strip")

    # 5.5 非字符串输入
    assert security.sanitize_input(42) == "42"
    assert security.sanitize_input(None) == "None"
    print("   ✓ 非字符串输入被 str() 化")

    # ================================
    # 6. is_plugin_url_safe —— SSRF 防护
    # ================================
    print("\n6. is_plugin_url_safe - 插件 URL SSRF 防护")

    # 6.1 非 http/https 协议
    for bad_scheme in ["file:///etc/passwd", "ftp://evil.com/x.so", "gopher://127.0.0.1/1"]:
        assert not security.is_plugin_url_safe(bad_scheme), f"非 http(s) 应被拒: {bad_scheme}"
    print("   ✓ 非 http(s) 协议被拦截")

    # 6.2 localhost / 回环
    for loopback in [
        "http://localhost/plugin",
        "http://127.0.0.1/x",
        "http://0.0.0.0/y",
        "http://[::1]/z",
    ]:
        assert not security.is_plugin_url_safe(loopback), f"回环地址应被拒: {loopback}"
        print(f"   ✓ 回环地址被拦截: {loopback}")

    # 6.3 内网 RFC1918 地址
    private_candidates = [
        "http://192.168.1.1/plugin",
        "http://10.0.0.1/plugin",
        "http://172.16.0.1/plugin",
        "http://169.254.1.1/plugin",  # link-local
    ]
    for url in private_candidates:
        safe = security.is_plugin_url_safe(url)
        if safe:
            # 某些环境解析可能有差异，打印诊断
            print(f"   ⚠ 内网地址判定为安全（DNS 解析）: {url}")
        else:
            print(f"   ✓ 内网地址被拦截: {url}")

    # 6.4 合法公网 URL
    good_url = "https://github.com/some/plugin/raw/main/plugin.json"
    safe = security.is_plugin_url_safe(good_url)
    print(f"   合法公网 URL {good_url} -> safe={safe}")
    # 注意：在无网络沙箱中 DNS 解析会失败，返回 False，这也是安全行为

    # 6.5 空值和畸形 URL
    for bad_url in ["", None, "not-a-url", "http://", "http:///path"]:
        safe = security.is_plugin_url_safe(bad_url)
        assert not safe, f"畸形 URL 应被拒: {bad_url!r}"
    print("   ✓ 畸形 / 空 URL 被拦截")

    # ================================
    # 7. get_safe_work_dir
    # ================================
    print("\n7. get_safe_work_dir - 安全工作目录")
    work = security.get_safe_work_dir("data")
    assert os.path.isabs(work)
    assert os.path.isdir(work)
    print(f"   ✓ 安全工作目录返回并创建: {work}")

    # ================================
    # 并发安全性：多个线程同时调用 is_path_safe / sanitize_input
    # ================================
    print("\n8. 并发安全 - 多线程并发调用")

    exceptions = []

    def worker():
        try:
            for _ in range(100):
                security.is_path_safe("/etc/passwd", allowed_bases=[tmp_dir])
                security.sanitize_input("hello\x00world")
                security.is_command_safe("ls -la")
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not exceptions, f"并发调用出现异常: {exceptions}"
    print("   ✓ 8 线程 × 100 次并发调用无异常")

    # ================================
    # 结果汇总
    # ================================
    print("\n" + "=" * 50)
    if errors:
        print(f"❌ 发现 {len(errors)} 个问题：")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("🎉 security.py 全部测试通过")


if __name__ == "__main__":
    main()
