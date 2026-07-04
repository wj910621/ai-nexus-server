"""
移动端体验测试脚本
测试设备注册、远程控制、文件传输、PWA 静态文件存在性
"""

import os
from mobile_integration import (
    register_device,
    unregister_device,
    list_devices,
    remote_pc_action,
    upload_file,
    list_transfer_files,
)


def main():
    print("=== 移动端体验测试 ===\n")

    # 1. 设备注册
    print("1. 注册测试设备...")
    device = register_device("test_mobile_001", {
        "platform": "android",
        "name": "测试手机",
        "model": "Test Model",
    })
    print(f"  设备 ID: {device['id']}")
    print(f"  状态: {device['status']}")

    # 2. 列出设备
    print("\n2. 列出设备...")
    devices = list_devices()
    print(f"  共 {len(devices)} 个设备")

    # 3. 远程控制（使用未知动作测试接口，避免真实执行锁屏/关机等副作用）
    print("\n3. 测试远程控制接口...")
    result = remote_pc_action("__test_unknown__")
    print(f"  未知动作返回: {result.get('error')}")

    # 4. 文件传输
    print("\n4. 测试文件上传...")
    test_data = b"Hello from mobile test"
    upload_result = upload_file("mobile_test.txt", test_data, device_id="test_mobile_001")
    print(f"  上传结果: {upload_result}")

    files = list_transfer_files()
    print(f"  传输目录文件数: {len(files)}")

    # 5. 清理
    print("\n5. 清理测试设备...")
    unregister_device("test_mobile_001")

    # 6. PWA 文件存在性
    print("\n6. 检查 PWA 静态文件...")
    pwa_files = ["mobile.html", "mobile-manifest.json", "mobile-sw.js", "icon.svg"]
    for f in pwa_files:
        exists = os.path.exists(f)
        print(f"  {f}: {'存在' if exists else '缺失'}")

    print("\n=== 移动端测试完成 ===")


if __name__ == "__main__":
    main()
