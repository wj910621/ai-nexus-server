"""
中文唤醒词模块
支持多种离线唤醒词方案，优先使用 openWakeWord（完全免费、开源、离线）。

方案对比：
  - openWakeWord：免费、开源、离线、支持自定义训练，推荐
  - pvporcupine：Picovoice 商业产品，有免费额度，精度高
  - snowboy：已停止维护，不推荐
  - porcupine + 自定义训练：需 Picovoice Console

本模块提供：
  1. openWakeWord 集成（默认）
  2. 中文唤醒词训练指南
  3. 多唤醒词支持（"Y·NEX"、"嘿Y·NEX"、"Y·NEX"等）
  4. 唤醒灵敏度调节
"""

import os
import time
import threading
from typing import Callable, List, Optional

from logger import logger

# 延迟导入
_oww = None


def _import_openwakeword():
    global _oww
    if _oww is None:
        try:
            from openwakeword.model import Model
            _oww = Model
        except ImportError:
            logger.warning("openWakeWord 未安装，离线唤醒词不可用。")
            logger.warning("安装命令：pip install openwakeword")
    return _oww


# 内置模型列表（openWakeWord 自带的英文模型）
BUILTIN_MODELS = [
    "alexa",
    "hey_mycroft",
    "hey_jarvis",
    "computer",
    "hey_google",
    "hey_siri",
    "naptime",
    "timer",
    "weather",
]

# 中文唤醒词建议模型（需自行训练或下载社区模型）
CHINESE_MODELS = [
    "yi_jie",     # Y·NEX
    "jia_wei_si", # Y·NEX
]


# =============================================================================
# 唤醒词检测器
# =============================================================================

class WakeWordDetector:
    """
    openWakeWord 唤醒词检测器。
    持续监听麦克风，检测到唤醒词时触发回调。
    """

    def __init__(
        self,
        wake_words: Optional[List[str]] = None,
        sensitivity: float = 0.5,
        on_wake: Optional[Callable[[str], None]] = None,
        sample_rate: int = 16000,
    ):
        """
        wake_words: 要检测的唤醒词模型名称列表
        sensitivity: 灵敏度 0-1，越高越灵敏但误报也多
        on_wake: 检测到唤醒词时的回调，参数为唤醒词名称
        """
        self.wake_words = wake_words or ["hey_jarvis"]
        self.sensitivity = sensitivity
        self.on_wake = on_wake
        self.sample_rate = sample_rate
        self.model = None
        self._running = False
        self._thread = None
        self._audio_queue = None

        self._init_model()

    def _init_model(self):
        """初始化唤醒词模型"""
        Model = _import_openwakeword()
        if not Model:
            return

        try:
            # 检查自定义模型路径
            model_paths = []
            for ww in self.wake_words:
                custom_path = os.path.join("data", "wake_words", f"{ww}.onnx")
                if os.path.exists(custom_path):
                    model_paths.append(custom_path)
                else:
                    model_paths.append(ww)  # 使用内置模型名

            self.model = Model(
                wakeword_models=model_paths,
                inference_framework="onnxruntime",
            )
            logger.info(f"唤醒词模型加载成功：{self.wake_words}")
        except Exception as e:
            logger.error(f"唤醒词模型加载失败：{e}")
            self.model = None

    def detect(self, pcm_audio) -> Optional[str]:
        """
        检测一段 PCM 音频中是否有唤醒词。
        返回检测到的唤醒词名称，或 None。
        """
        if not self.model:
            return None

        try:
            predictions = self.model.predict(pcm_audio)
            for word, score in predictions.items():
                if score >= self.sensitivity:
                    # 重置模型状态，避免连续触发
                    self.model.reset()
                    return word
        except Exception as e:
            logger.warning(f"唤醒词检测异常：{e}")

        return None

    def start_listening(self):
        """开始后台持续监听"""
        if self._running:
            return
        if not self.model:
            logger.warning("唤醒词模型未加载，无法监听")
            return

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("唤醒词监听已启动")

    def stop_listening(self):
        """停止监听"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _listen_loop(self):
        """监听主循环（需要外部音频输入时重写）"""
        # 默认从系统麦克风获取音频
        try:
            import pyaudio
        except ImportError:
            logger.warning("pyaudio 未安装，无法监听麦克风")
            return

        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=1280,  # 80ms @ 16kHz
        )

        try:
            while self._running:
                # 读取一帧音频
                data = stream.read(1280, exception_on_overflow=False)

                # 检测唤醒词
                detected = self.detect(data)
                if detected and self.on_wake:
                    try:
                        self.on_wake(detected)
                    except Exception:
                        pass
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()


# =============================================================================
# 中文唤醒词训练指南
# =============================================================================

TRAINING_GUIDE = """
=== 中文唤醒词"Y·NEX"训练指南 ===

【方案一：openWakeWord 自定义训练（推荐，完全免费）】

1. 准备训练数据
   - 录制 30-100 个"Y·NEX"语音样本（不同语速、语调）
   - 每个样本 1-2 秒，16kHz 单声道 WAV
   - 用你自己的声音 + 家人的声音各录一些
   - 录制工具：Audacity / 手机录音 App

2. 准备负样本（降低误报）
   - 10-30 分钟环境噪声
   - 常见对话、电视声音、音乐等
   - 从 freesound.org 下载环境音

3. 训练步骤
   # 克隆训练工具
   git clone https://github.com/dscripka/openWakeWord.git
   cd openWakeWord

   # 安装依赖
   pip install -e .[train]

   # 准备数据目录结构：
   # my_wakeword/
   #   ├── positive/     # 正样本（唤醒词）
   #   ├── negative/     # 负样本（非唤醒词）
   #   └── data.json     # 标注文件

   # 生成训练数据
   python -m openwakeword.data.create_dataset \\
     --positive_dir my_wakeword/positive \\
     --negative_dir my_wakeword/negative \\
     --output_dir my_wakeword/dataset \\
     --wakeword "yi_jie"

   # 训练模型
   python -m openwakeword.train \\
     --dataset_path my_wakeword/dataset \\
     --output_dir my_wakeword/model

4. 部署
   - 训练完成后得到 .onnx 模型文件
   - 复制到 data/wake_words/yi_jie.onnx
   - 在Y·NEX中设置 WAKE_WORD_MODEL=yi_jie

【方案二：Picovoice Porcupine（精度高，有免费额度）】

1. 注册 Picovoice Console
   https://console.picovoice.ai/

2. 创建自定义唤醒词
   - 选择中文（zh）
   - 输入"Y·NEX"
   - 选择平台（Windows/Linux/Raspberry Pi）
   - 生成 .ppn 文件

3. 部署
   - 下载 .ppn 文件
   - 设置 PV_ACCESS_KEY 和 PORCUPINE_MODEL_PATH

【方案三：用 Edge 浏览器语音识别做兜底】
   - 识别文本中包含"Y·NEX"就算唤醒
   - 优点：不需要训练
   - 缺点：必须联网，延迟高，功耗大
"""


def get_training_guide() -> str:
    """返回中文唤醒词训练指南"""
    return TRAINING_GUIDE.strip()


# =============================================================================
# 便捷函数
# =============================================================================

def wait_for_wake_word_openwakeword(wake_word: str = "hey_jarvis",
                                     sensitivity: float = 0.5,
                                     timeout: Optional[float] = None) -> bool:
    """
    阻塞等待唤醒词。
    检测到返回 True，超时返回 False。
    """
    detected = threading.Event()

    def on_wake(word):
        logger.info(f"检测到唤醒词：{word}")
        detected.set()

    detector = WakeWordDetector(
        wake_words=[wake_word],
        sensitivity=sensitivity,
        on_wake=on_wake,
    )

    if not detector.model:
        logger.warning("唤醒词模型不可用，跳过等待")
        return False

    detector.start_listening()

    try:
        return detected.wait(timeout=timeout)
    finally:
        detector.stop_listening()


def list_available_models() -> List[str]:
    """列出可用的唤醒词模型"""
    models = list(BUILTIN_MODELS)

    # 检查自定义模型
    custom_dir = os.path.join("data", "wake_words")
    if os.path.isdir(custom_dir):
        for f in os.listdir(custom_dir):
            if f.endswith(".onnx") or f.endswith(".tflite"):
                name = os.path.splitext(f)[0]
                if name not in models:
                    models.append(name)

    return models


if __name__ == "__main__":
    print("可用唤醒词模型：", list_available_models())
    print("\n" + get_training_guide())
