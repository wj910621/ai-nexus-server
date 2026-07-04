"""
Y·NEX自动化测试运行器
- 编译检查所有 Python 文件
- 导入检查所有核心模块
- 运行基础 API 测试
"""
import os
import sys
import subprocess
import glob
import time
import urllib.request
import urllib.error

PYTHON = sys.executable
ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 7799  # 测试端口，避免冲突


def run_compile_check():
    print("\n" + "=" * 60)
    print("1. Python 编译检查")
    print("=" * 60)
    files = glob.glob(os.path.join(ROOT, "*.py"))
    failed = []
    for f in files:
        try:
            subprocess.check_call([PYTHON, "-m", "py_compile", f], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            failed.append(os.path.basename(f))
    if failed:
        print(f"❌ 编译失败: {', '.join(failed)}")
        return False
    print(f"✅ 全部 {len(files)} 个 Python 文件编译通过")
    return True


def run_import_check():
    print("\n" + "=" * 60)
    print("2. 核心模块导入检查")
    print("=" * 60)
    modules = [
        "ynex_server",
        "mobile_integration",
        "plugin_system",
        "performance",
        "multimodal",
        "voice_engine",
        "browser_automation",
        "pc_automation",
        "knowledge_enhancer",
        "super_agent",
        "local_llm",
        "brain",
        "skills",
        "memory",
    ]
    failed = []
    for mod in modules:
        try:
            __import__(mod)
            print(f"  ✓ {mod}")
        except Exception as e:
            failed.append((mod, str(e)))
            print(f"  ✗ {mod}: {e}")
    if failed:
        return False
    print(f"✅ 全部 {len(modules)} 个核心模块导入成功")
    return True


def run_api_test():
    print("\n" + "=" * 60)
    print("3. API 服务测试")
    print("=" * 60)

    env = os.environ.copy()
    env["YNEX_PORT"] = str(PORT)

    proc = subprocess.Popen(
        [PYTHON, "ynex_server.py", "--port", str(PORT)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 等待服务就绪
    for _ in range(30):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    else:
        print("❌ 服务启动超时")
        proc.terminate()
        return False

    endpoints = [
        "/api/health",
        "/api/skills",
        "/api/vision/models",
        "/api/plugins",
        "/api/performance/stats",
    ]

    passed = 0
    for endpoint in endpoints:
        try:
            url = f"http://127.0.0.1:{PORT}{endpoint}"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    print(f"  ✓ {endpoint}")
                    passed += 1
                else:
                    print(f"  ✗ {endpoint}: HTTP {resp.status}")
        except Exception as e:
            print(f"  ✗ {endpoint}: {e}")

    proc.terminate()
    proc.wait(timeout=5)

    if passed == len(endpoints):
        print(f"✅ 全部 {len(endpoints)} 个 API 端点测试通过")
        return True
    else:
        print(f"❌ API 测试通过 {passed}/{len(endpoints)}")
        return False


def main():
    print("=" * 60)
    print("  Y·NEX自动化测试")
    print("=" * 60)

    results = []
    results.append(("编译检查", run_compile_check()))
    results.append(("导入检查", run_import_check()))
    results.append(("API 测试", run_api_test()))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")

    all_ok = all(ok for _, ok in results)
    print("\n" + ("🎉 所有测试通过" if all_ok else "⚠ 部分测试未通过"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
