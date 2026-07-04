"""
多模态模块测试脚本
测试 OCR 可用性、视觉模型状态、图片生成接口
"""

from multimodal import (
    is_ocr_available,
    is_vision_available,
    is_image_generation_available,
    list_vision_models,
    generate_image,
)


def main():
    print("=== 多模态模块测试 ===\n")

    print(f"OCR 可用: {is_ocr_available()}")
    print(f"本地视觉模型可用: {is_vision_available()}")
    print(f"可用视觉模型: {list_vision_models()}")
    print(f"图片生成服务可用: {is_image_generation_available()}")

    print("\n测试文本生成图片...")
    result = generate_image(
        prompt="a cute robot assistant in a futuristic room, digital art",
        width=512,
        height=512,
        style="3d",
    )
    if result.get("ok"):
        print(f"生成成功: {result['path']}")
        print(f"图片 URL: {result['url']}")
        print(f"增强提示词: {result['prompt']}")
    else:
        print(f"生成失败: {result.get('error')}")

    print("\n=== 多模态测试完成 ===")


if __name__ == "__main__":
    main()
