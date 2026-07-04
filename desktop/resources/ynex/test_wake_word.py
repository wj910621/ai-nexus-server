"""
唤醒词引擎测试

用法：
1. 配置好 .env 中的 WAKE_WORD_MODEL_PATH 和 WAKE_WORD_ACCESS_KEY
2. 运行 python test_wake_word.py
3. 说出唤醒词，看是否能被检测到
"""

import sys
from config import settings


def main():
    print("=== 唤醒词引擎测试 ===\n")

    if settings.wake_word_model_path:
        print(f"自定义模型路径：{settings.wake_word_model_path}")
        if not sys.platform.startswith("win"):
            print(f"注意：当前平台 {sys.platform}，模型路径可能需要调整格式")
    else:
        print("未配置自定义模型，将使用内置英文 'jarvis' 占位。")
        print("要测试中文'Y·NEX'，请先运行 record_wake_word.py 并训练模型。\n")

    try:
        from wake_word import wait_for_wake_word
        print(f"等待唤醒词：{settings.wake_word}")
        print("（按 Ctrl+C 退出）\n")
        wait_for_wake_word()
        print("✅ 唤醒词检测成功！")
    except KeyboardInterrupt:
        print("\n已退出")
    except Exception as e:
        print(f"❌ 唤醒词检测失败：{e}")


if __name__ == "__main__":
    main()
