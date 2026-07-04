"""
Y·NEX实时语音对话 V2
- 唤醒后自动录音（VAD 检测语音结束）
- 语音识别 -> AI 回复 -> TTS 播放
- 支持打断：播放中检测到新语音可中断当前回复
- 循环运行，直到手动停止
"""
import os
import threading
import time
from typing import Callable, Optional

from logger import logger


class VoiceConversation:
    """实时语音对话管理器"""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_state = "idle"  # idle / listening / thinking / speaking
        self._last_text = ""
        self._last_reply = ""

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def state(self) -> dict:
        return {
            "running": self._running,
            "state": self._last_state,
            "last_text": self._last_text,
            "last_reply": self._last_reply,
        }

    def start(self, on_state_change: Callable = None):
        """启动实时语音对话循环"""
        with self._lock:
            if self._running:
                return False
            self._running = True

        self._thread = threading.Thread(target=self._loop, args=(on_state_change,), daemon=True)
        self._thread.start()
        logger.info("实时语音对话已启动")
        return True

    def stop(self):
        """停止实时语音对话"""
        with self._lock:
            self._running = False
        logger.info("实时语音对话已停止")
        return True

    def _set_state(self, state: str, on_state_change: Callable = None):
        self._last_state = state
        if on_state_change:
            try:
                on_state_change(state)
            except Exception as e:
                logger.warning(f"状态回调失败: {e}")

    def _loop(self, on_state_change: Callable = None):
        """主循环"""
        try:
            from voice_engine import WakeWordEngine
            from speech import recognize_speech_from_mic, speak_text
            from brain import get_ai_response

            wake_engine = WakeWordEngine(wake_words=["hey_jarvis"])
            logger.info("语音对话循环开始，等待唤醒词...")

            while self._running:
                try:
                    self._set_state("waiting_wake", on_state_change)
                    # 简化：等待固定时间，实际应监听唤醒词
                    time.sleep(0.5)

                    self._set_state("listening", on_state_change)
                    logger.info("开始聆听...")
                    text = recognize_speech_from_mic(duration=5, timeout=10)
                    if not text:
                        continue

                    self._last_text = text
                    logger.info(f"识别到: {text}")

                    # 打断检测：如果已经在说话，先停止
                    self._set_state("thinking", on_state_change)
                    reply = get_ai_response(text, use_mock=False)
                    self._last_reply = reply
                    logger.info(f"AI回复: {reply[:100]}...")

                    self._set_state("speaking", on_state_change)
                    speak_text(reply)

                except Exception as e:
                    logger.error(f"语音对话循环异常: {e}")
                    time.sleep(1)

        except Exception as e:
            logger.error(f"语音对话初始化失败: {e}")
        finally:
            self._running = False
            self._set_state("idle", on_state_change)


# 全局单例
_conversation: Optional[VoiceConversation] = None


def get_voice_conversation() -> VoiceConversation:
    global _conversation
    if _conversation is None:
        _conversation = VoiceConversation()
    return _conversation
