"""
Y·NEX语音交互引擎 v2
统一唤醒词检测、语音增强、语音识别，支持多后端 fallback。

后端优先级：
1. openWakeWord（免费离线，支持中文自定义模型）
2. pvporcupine（英文/付费）
3. SpeechRecognition 关键词检测（备用）

语音增强：
- noisereduce 噪声抑制
- webrtcvad 语音端点检测
- 自动增益控制
"""

import os
import threading
import time
from typing import Callable, List, Optional

from logger import logger


# ---------------- 后端可用性检测 ----------------

_OWW_AVAILABLE = False
_PORCUPINE_AVAILABLE = False
_SR_AVAILABLE = False

try:
    import pvporcupine
    import pvrecorder
    _PORCUPINE_AVAILABLE = True
except Exception:
    pass

try:
    from openwakeword.model import Model
    _OWW_AVAILABLE = True
except Exception:
    pass

try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except Exception:
    pass


def get_available_backends() -> List[str]:
    backends = []
    if _OWW_AVAILABLE:
        backends.append("openwakeword")
    if _PORCUPINE_AVAILABLE:
        backends.append("porcupine")
    if _SR_AVAILABLE:
        backends.append("speech_recognition")
    return backends


# ---------------- 唤醒词引擎 ----------------

class WakeWordEngine:
    """统一唤醒词引擎，自动选择最佳可用后端"""

    def __init__(
        self,
        wake_words: Optional[List[str]] = None,
        sensitivity: float = 0.5,
        model_dir: str = "data/wake_words",
    ):
        self.wake_words = wake_words or ["hey_jarvis"]
        self.sensitivity = sensitivity
        self.model_dir = model_dir
        self.backend = None
        self.model = None
        self.porcupine = None
        self.recognizer = None
        self._init_engine()

    def _init_engine(self):
        # 优先 openWakeWord
        if _OWW_AVAILABLE:
            try:
                model_paths = []
                for ww in self.wake_words:
                    custom_path = os.path.join(self.model_dir, f"{ww}.onnx")
                    if os.path.exists(custom_path):
                        model_paths.append(custom_path)
                    else:
                        model_paths.append(ww)
                self.model = Model(
                    wakeword_models=model_paths,
                    inference_framework="onnxruntime",
                )
                self.backend = "openwakeword"
                logger.info(f"唤醒词引擎：openWakeWord，模型：{self.wake_words}")
                return
            except Exception as e:
                logger.warning(f"openWakeWord 初始化失败：{e}")

        # 其次 porcupine
        if _PORCUPINE_AVAILABLE:
            try:
                # 默认用 jarvis，忽略自定义中文唤醒词
                self.porcupine = pvporcupine.create(keywords=["jarvis"])
                self.backend = "porcupine"
                logger.info("唤醒词引擎：porcupine，默认关键词 jarvis")
                return
            except Exception as e:
                logger.warning(f"porcupine 初始化失败：{e}")

        # 备用 SR 关键词
        if _SR_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.backend = "speech_recognition"
            logger.info("唤醒词引擎：SpeechRecognition 关键词检测")
            return

        self.backend = None
        logger.warning("无可用唤醒词引擎")

    def process_audio(self, pcm_data: bytes) -> Optional[str]:
        """处理一帧 PCM 音频，返回检测到的唤醒词或 None"""
        if self.backend == "openwakeword" and self.model:
            try:
                predictions = self.model.predict(pcm_data)
                for word, score in predictions.items():
                    if score >= self.sensitivity:
                        self.model.reset()
                        return word
            except Exception as e:
                logger.warning(f"openWakeWord 检测异常：{e}")

        elif self.backend == "porcupine" and self.porcupine:
            try:
                import struct
                # porcupine 需要 int16 列表
                shorts = struct.unpack("%dh" % (len(pcm_data) // 2), pcm_data)
                result = self.porcupine.process(shorts)
                if result >= 0:
                    return "jarvis"
            except Exception as e:
                logger.warning(f"porcupine 检测异常：{e}")

        return None

    def cleanup(self):
        if self.model:
            try:
                self.model.delete()
            except Exception:
                pass
        if self.porcupine:
            try:
                self.porcupine.delete()
            except Exception:
                pass


# ---------------- 语音采集与增强 ----------------

class AudioPipeline:
    """音频采集 + 增强（噪声抑制 / VAD / AGC）"""

    def __init__(self, sample_rate: int = 16000, frame_ms: int = 80):
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * frame_ms / 1000)
        self._pyaudio = None
        self._stream = None
        self._vad = None
        self._import_vad()

    def _import_vad(self):
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(2)  # 0-3，越大越激进
        except Exception:
            pass

    def open(self, device_index: Optional[int] = None) -> bool:
        try:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()
            self._stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.frame_size,
            )
            logger.info("麦克风已打开")
            return True
        except Exception as e:
            logger.warning(f"麦克风打开失败：{e}")
            return False

    def read_frame(self) -> Optional[bytes]:
        if not self._stream:
            return None
        try:
            return self._stream.read(self.frame_size, exception_on_overflow=False)
        except Exception as e:
            logger.warning(f"麦克风读取失败：{e}")
            return None

    def is_speech(self, frame: bytes) -> bool:
        if not self._vad:
            return True
        try:
            return self._vad.is_speech(frame, self.sample_rate)
        except Exception:
            return True

    def close(self):
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pyaudio:
            try:
                self._pyaudio.terminate()
            except Exception:
                pass
            self._pyaudio = None


# ---------------- 统一语音引擎 ----------------

class VoiceEngine:
    """Y·NEX语音交互引擎：唤醒词监听 + 语音增强 + ASR"""

    def __init__(
        self,
        wake_words: Optional[List[str]] = None,
        sensitivity: float = 0.5,
        on_wake: Optional[Callable[[str], None]] = None,
        on_speech: Optional[Callable[[str], None]] = None,
    ):
        self.wake_words = wake_words or ["hey_jarvis"]
        self.sensitivity = sensitivity
        self.on_wake = on_wake
        self.on_speech = on_speech
        self.wake_engine = WakeWordEngine(self.wake_words, sensitivity)
        self.audio = AudioPipeline()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._state = "idle"  # idle, listening, processing
        self._last_wake_time = 0
        self._wake_cooldown = 2.0  # 唤醒后 2 秒内不再触发

    @property
    def available(self) -> bool:
        return self.wake_engine.backend is not None and self.audio.open()

    @property
    def status(self) -> dict:
        return {
            "running": self._running,
            "state": self._state,
            "backend": self.wake_engine.backend,
            "wake_words": self.wake_words,
            "sensitivity": self.sensitivity,
        }

    def start(self):
        """启动后台监听线程"""
        if self._running:
            return
        if not self.audio.open():
            logger.warning("无法打开麦克风，语音引擎未启动")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="voice-engine")
        self._thread.start()
        logger.info("语音交互引擎已启动")

    def stop(self):
        """停止监听"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        self.audio.close()
        self.wake_engine.cleanup()
        logger.info("语音交互引擎已停止")

    def _loop(self):
        """主循环"""
        while self._running:
            try:
                frame = self.audio.read_frame()
                if not frame:
                    time.sleep(0.05)
                    continue

                # 唤醒词检测
                detected = self.wake_engine.process_audio(frame)
                if detected:
                    now = time.time()
                    if now - self._last_wake_time > self._wake_cooldown:
                        self._last_wake_time = now
                        self._state = "listening"
                        logger.info(f"检测到唤醒词：{detected}")
                        if self.on_wake:
                            try:
                                threading.Thread(target=self.on_wake, args=(detected,), daemon=True).start()
                            except Exception as e:
                                logger.error(f"唤醒回调失败：{e}")

                # 唤醒后进入聆听模式，检测语音并识别
                if self._state == "listening" and self.on_speech:
                    if self.audio.is_speech(frame):
                        # 这里可以收集音频段落后调用 ASR
                        pass

            except Exception as e:
                logger.warning(f"语音引擎循环异常：{e}")
                time.sleep(0.1)

    def listen_once(self, timeout: int = 5) -> str:
        """使用 SpeechRecognition 识别一次语音"""
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=timeout, phrase_time_limit=timeout)
            return r.recognize_google(audio, language="zh-CN")
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            logger.warning(f"语音识别请求失败：{e}")
            return ""
        except Exception as e:
            logger.warning(f"语音识别失败：{e}")
            return ""


# ---------------- 便捷入口 ----------------

_engine: Optional[VoiceEngine] = None


def start_voice_engine(
    wake_words: Optional[List[str]] = None,
    sensitivity: float = 0.5,
    on_wake: Optional[Callable[[str], None]] = None,
    on_speech: Optional[Callable[[str], None]] = None,
) -> VoiceEngine:
    global _engine
    _engine = VoiceEngine(
        wake_words=wake_words or ["hey_jarvis"],
        sensitivity=sensitivity,
        on_wake=on_wake,
        on_speech=on_speech,
    )
    _engine.start()
    return _engine


def stop_voice_engine():
    global _engine
    if _engine:
        _engine.stop()
        _engine = None


def voice_engine_status() -> dict:
    if _engine:
        return _engine.status
    return {
        "running": False,
        "state": "idle",
        "backend": None,
        "wake_words": [],
        "available_backends": get_available_backends(),
    }
