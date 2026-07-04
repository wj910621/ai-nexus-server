"""
Y·NEX多模态模块 - 图片理解 + OCR + 截图分析 + 图片生成

功能：
- 图片理解：通过 Ollama 多模态模型（如 llava、qwen2-vl 等理解图片内容
- OCR：文字识别（支持本地 PaddleOCR / pytesseract 双后端，自动降级）
- 截图分析：自动截屏 + 理解屏幕内容
- 图片生成：使用 Pollinations.ai 免费接口根据文本生成图片
- 图片搜索：基于内容的图片描述、提取文本
"""

import os
import re
import time
import base64
import hashlib
import threading
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from logger import logger


# =============================================================================
# 图片理解（基于 Ollama 多模态模型
# =============================================================================

@dataclass
class VisionAnalysis:
    """图片分析结果"""
    description: str = ""
    text_detected: bool = False
    text_content: str = ""
    objects: List[str] = None
    confidence: float = 0.0
    model_used: str = ""


def encode_image_to_base64(image_path: str) -> Optional[str]:
    """将图片编码为 base64"""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"图片编码失败: {e}")
        return None


def analyze_image(image_path: str, prompt: str = "请详细描述这张图片的内容", model: str = None) -> VisionAnalysis:
    """
    分析图片内容（通过 Ollama 多模态模型）
    
    Args:
        image_path: 图片路径
        prompt: 提问内容
        model: 指定模型，默认自动选择
    """
    result = VisionAnalysis()
    
    if not os.path.exists(image_path):
        result.description = f"图片不存在: {image_path}"
        return result

    # 自动选择模型
    if model is None:
        model = _get_best_vision_model()
    result.model_used = model

    try:
        import ollama
        img_b64 = encode_image_to_base64(image_path)
        if not img_b64:
            result.description = "图片编码失败"
            return result

        logger.info(f"使用模型 {model} 分析图片: {image_path}")
        response = ollama.generate(
            model=model,
            prompt=prompt,
            images=[img_b64],
        )
        result.description = response.get("response", "")
        result.confidence = 0.8
        return result
    except ImportError:
        logger.warning("ollama 未安装或不可用，尝试降级到 OCR")
        result.description = "多模态模型不可用，仅进行 OCR"
    except Exception as e:
        logger.error(f"图片分析失败: {e}")
        result.description = f"分析失败: {str(e)}"
    
    return result


def _get_best_vision_model() -> str:
    """获取最佳可用多模态模型"""
    try:
        import ollama
        models = ollama.list()
        model_names = [m["name"] for m in models.get("models", [])]
        
        # 优先级排序
        priority = [
            "qwen2.5-vl", "qwen2-vl", "llava", "bakllava", "moondream",
        ]
        for prefix in priority:
            for name in model_names:
                if prefix in name.lower():
                    return name
        
        # 没有找到，返回第一个模型（可能不支持图片，调用方会报错）
        if model_names:
            return model_names[0]
    except Exception:
        pass
    return "llava:7b"


# =============================================================================
# OCR 文字识别
# =============================================================================

_ocr_engine = None
_ocr_lock = threading.Lock()


def _get_ocr_engine():
    """获取 OCR 引擎（懒加载）"""
    global _ocr_engine
    with _ocr_lock:
        if _ocr_engine is not None:
            return _ocr_engine

        # 尝试 PaddleOCR
        try:
            from paddleocr import PaddleOCR
            _ocr_engine = ("paddle", PaddleOCR(use_angle_cls=True, lang="ch", show_log=False))
            logger.info("OCR 引擎: PaddleOCR")
            return _ocr_engine
        except ImportError:
            logger.debug("PaddleOCR 未安装")
        except Exception as e:
            logger.debug(f"PaddleOCR 初始化失败: {e}")

        # 尝试 pytesseract
        try:
            import pytesseract
            _ocr_engine = ("tesseract", pytesseract)
            logger.info("OCR 引擎: Tesseract")
            return _ocr_engine
        except ImportError:
            logger.debug("pytesseract 未安装")

        logger.warning("未找到可用的 OCR 引擎")
        return None


def ocr_image(image_path: str) -> Dict[str, Any]:
    """
    识别图片中的文字
    
    Returns:
        {"ok": bool, "text": str, "engine": str, "lines": list}
    """
    engine = _get_ocr_engine()
    if engine is None:
        return {
            "ok": False,
            "text": "",
            "engine": "none",
            "lines": [],
            "error": "未安装 OCR 引擎，请安装 paddleocr 或 pytesseract",
        }

    try:
        engine_type, engine_obj = engine
        lines = []

        if engine_type == "paddle":
            result = engine_obj.ocr(image_path, cls=True)
            if result and result[0]:
                for line in result[0]:
                    text = line[1][0]
                    confidence = line[1][1]
                    lines.append({"text": text, "confidence": confidence})
        elif engine_type == "tesseract":
            import cv2
            img = cv2.imread(image_path)
            text = engine_obj.image_to_string(img, lang="chi_sim+eng")
            for line in text.split("\n"):
                line = line.strip()
                if line:
                    lines.append({"text": line, "confidence": 0.7})

        full_text = "\n".join([l["text"] for l in lines])
        return {
            "ok": True,
            "text": full_text,
            "engine": engine_type,
            "lines": lines,
        }
    except Exception as e:
        logger.error(f"OCR 识别失败: {e}")
        return {
            "ok": False,
            "text": "",
            "engine": engine[0] if engine else "none",
            "lines": [],
            "error": str(e),
        }


# =============================================================================
# 屏幕截图分析
# =============================================================================

def capture_screen(save_path: Optional[str] = None) -> Optional[str]:
    """
    截取全屏
    
    Returns:
        保存的图片路径，失败返回 None
    """
    try:
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            import mss.tools
            if save_path is None:
                os.makedirs("data/screenshots", exist_ok=True)
                save_path = os.path.join(
                    "data", "screenshots",
                    f"screen_{time.strftime('%Y%m%d_%H%M%S')}.png"
                )
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=save_path)
            logger.info(f"截图已保存: {save_path}")
            return save_path
    except ImportError:
        logger.warning("mss 未安装，尝试 PIL")
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            if save_path is None:
                os.makedirs("data/screenshots", exist_ok=True)
                save_path = os.path.join(
                    "data", "screenshots",
                    f"screen_{time.strftime('%Y%m%d_%H%M%S')}.png"
                )
            img.save(save_path)
            logger.info(f"截图已保存: {save_path}")
            return save_path
        except Exception as e2:
            logger.error(f"截图失败: {e2}")
            return None
    except Exception as e:
        logger.error(f"截图失败: {e}")
        return None


def analyze_screen(prompt: str = "描述一下当前屏幕显示的内容") -> Dict[str, Any]:
    """
    截屏并分析
    
    Returns:
        {"ok": bool, "image_path": str, "description": str, "ocr_text": str}
    """
    image_path = capture_screen()
    if not image_path:
        return {"ok": False, "error": "截图失败"}

    result = {"ok": True, "image_path": image_path, "description": "", "ocr_text": ""}

    # 尝试图片理解
    vision_result = analyze_image(image_path, prompt)
    result["description"] = vision_result.description

    # 尝试 OCR
    ocr_result = ocr_image(image_path)
    if ocr_result.get("ok"):
        result["ocr_text"] = ocr_result["text"]

    return result


# =============================================================================
# 摄像头拍照并分析
# =============================================================================

def analyze_camera(prompt: str = "描述一下摄像头拍到的内容", camera_index: int = 0) -> Dict[str, Any]:
    """
    调用摄像头拍照并分析
    
    Returns:
        {"ok": bool, "image_path": str, "description": str, "ocr_text": str}
    """
    try:
        from vision import capture_snapshot
        image_path = capture_snapshot(camera_index=camera_index)
        if not image_path:
            return {"ok": False, "error": "拍照失败"}

        result = {"ok": True, "image_path": image_path, "description": "", "ocr_text": ""}

        vision_result = analyze_image(image_path, prompt)
        result["description"] = vision_result.description

        ocr_result = ocr_image(image_path)
        if ocr_result.get("ok"):
            result["ocr_text"] = ocr_result["text"]

        return result
    except Exception as e:
        logger.error(f"摄像头分析失败: {e}")
        return {"ok": False, "error": str(e)}


# =============================================================================
# 工具函数
# =============================================================================

def list_vision_models() -> List[str]:
    """列出可用的多模态模型"""
    try:
        import ollama
        models = ollama.list()
        vision_prefixes = ["llava", "qwen2-vl", "qwen2.5-vl", "bakllava", "moondream", "cogvlm"]
        result = []
        for m in models.get("models", []):
            name = m.get("name", "")
            for prefix in vision_prefixes:
                if prefix in name.lower():
                    result.append(name)
                    break
        return result
    except Exception:
        return []


def is_vision_available() -> bool:
    """检查多模态能力是否可用"""
    try:
        import ollama
        models = ollama.list()
        for m in models.get("models", []):
            name = m.get("name", "").lower()
            if any(v in name for v in ["llava", "qwen2-vl", "qwen2.5-vl", "bakllava", "moondream"]):
                return True
    except Exception:
        pass
    return False


def is_ocr_available() -> bool:
    """检查 OCR 是否可用"""
    return _get_ocr_engine() is not None


# =============================================================================
# 图片生成（零成本：Pollinations.ai 免费 API）
# =============================================================================

def enhance_image_prompt(prompt: str, style: str = "") -> str:
    """
    对生成提示词做简单增强，提升出图质量。
    支持风格：photo/realistic/anime/3d/painting，留空则不添加风格词。
    """
    style_prefix = {
        "photo": "professional photography, highly detailed, 8k uhd, sharp focus, ",
        "realistic": "photorealistic, ultra detailed, natural lighting, ",
        "anime": "anime style, vibrant colors, detailed anime illustration, ",
        "3d": "3d render, octane render, blender, cinematic lighting, ",
        "painting": "digital painting, artstation, concept art, dramatic lighting, ",
    }
    prefix = style_prefix.get(style.lower(), "") if style else ""
    # 移除首尾空白，避免 URL 编码后多余空格
    enhanced = (prefix + prompt).strip()
    # 过滤可能导致 URL 问题的特殊字符
    enhanced = re.sub(r"[<>:\"|?*]", "", enhanced)
    return enhanced


def generate_image(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    seed: int = None,
    style: str = "",
    save_dir: str = "data/generated_images",
    timeout: int = 120,
) -> Dict[str, Any]:
    """
    使用 Pollinations.ai 免费接口根据文本生成图片。

    参数：
        prompt: 图片描述
        width/height: 图片尺寸
        seed: 随机种子（保证可复现）
        style: 风格前缀
        save_dir: 保存目录

    返回：
        {"ok": bool, "path": str, "url": str, "prompt": str, "error": str}
    """
    if not prompt or not prompt.strip():
        return {"ok": False, "error": "prompt 不能为空"}

    try:
        import requests
        from urllib.parse import quote
    except ImportError:
        return {"ok": False, "error": "requests 未安装"}

    enhanced = enhance_image_prompt(prompt, style)
    encoded_prompt = quote(enhanced)
    params = {"width": width, "height": height, "nologo": "true"}
    if seed is not None:
        params["seed"] = seed

    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"

    try:
        os.makedirs(save_dir, exist_ok=True)
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()

        if not resp.headers.get("content-type", "").startswith("image/"):
            return {"ok": False, "error": "接口未返回图片数据"}

        ext = "png"
        if "jpeg" in resp.headers.get("content-type", "") or "jpg" in resp.headers.get("content-type", ""):
            ext = "jpg"

        filename = f"gen_{int(time.time())}_{hashlib.md5(prompt.encode()).hexdigest()[:6]}.{ext}"
        save_path = os.path.join(save_dir, filename)
        with open(save_path, "wb") as f:
            f.write(resp.content)

        return {
            "ok": True,
            "path": save_path,
            "url": resp.url,
            "prompt": enhanced,
            "width": width,
            "height": height,
        }
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "图片生成超时，请稍后重试"}
    except Exception as e:
        logger.error(f"图片生成失败: {e}")
        return {"ok": False, "error": str(e)}


def is_image_generation_available() -> bool:
    """检查图片生成是否可用（网络可达 Pollinations.ai）"""
    try:
        import requests
        resp = requests.head("https://image.pollinations.ai/prompt/test", timeout=5)
        return resp.status_code < 500
    except Exception:
        return False


if __name__ == "__main__":
    print("多模态模块测试")
    print(f"OCR 可用: {is_ocr_available()}")
    print(f"视觉模型可用: {is_vision_available()}")
    print(f"可用视觉模型: {list_vision_models()}")
    print(f"图片生成可用: {is_image_generation_available()}")
