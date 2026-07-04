import asyncio
import os
import tempfile
import math
import threading
from concurrent.futures import ThreadPoolExecutor
import speech_recognition as sr
import edge_tts
import pygame
from config import settings
from logger import logger


# 后台线程池，用于非阻塞语音合成/播放
_tts_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ynex_tts_")


def speak_text(text: str, voice: str = None, async_mode: bool = True):
    """
    文本转语音并播放。

    参数：
        text: 要播报的文本
        voice: edge-tts 音色，默认使用 settings.tts_voice
        async_mode: True 时在后台线程播放，立即返回；False 时阻塞等待播放完成
    """
    voice = voice or settings.tts_voice

    def _run():
        try:
            speak_with_voice(text, voice)
        except Exception as e:
            logger.error(f"后台语音播放失败: {e}")

    if async_mode:
        _tts_executor.submit(_run)
    else:
        _run()


def speak_async(text: str, voice: str = None):
    """ speak_text 的异步别名，永远在后台播放 """
    speak_text(text, voice=voice, async_mode=True)


def speak_with_voice(text: str, voice: str):
    """同步执行 TTS：生成音频并播放，完成后清理临时文件"""
    logger.info(f"Y·NEX: {text}")

    async def _speak():
        communicate = edge_tts.Communicate(text, voice)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp_path = tmp.name
        await communicate.save(tmp_path)

        try:
            pygame.mixer.init()
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        finally:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
            for _ in range(5):
                try:
                    os.unlink(tmp_path)
                    break
                except PermissionError:
                    import time
                    time.sleep(0.1)

    asyncio.run(_speak())

# 尝试加载 faster-whisper，未安装则回退 Google
_try_local_asr = settings.asr_use_local
try:
    from faster_whisper import WhisperModel
    _whisper_model = None
except Exception:
    _try_local_asr = False
    logger.warning("faster-whisper 未安装或加载失败，将使用 Google ASR 作为语音识别。")


def _get_whisper_model():
    """懒加载 Whisper 模型"""
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(
            settings.asr_model,
            device="auto",
            compute_type="int8"
        )
    return _whisper_model


def speak(text: str):
    """语音合成并播放（向后兼容，默认阻塞等待播放完成）"""
    speak_text(text, async_mode=False)


def list_microphones():
    """列出可用麦克风设备"""
    try:
        mics = sr.Microphone.list_microphone_names()
        logger.info("可用麦克风设备：")
        for i, name in enumerate(mics):
            logger.info(f"  [{i}] {name}")
        return mics
    except Exception as e:
        logger.error(f"无法列出麦克风设备：{e}")
        return []


def _rms(frame: bytes) -> float:
    """计算音频帧的能量（RMS）"""
    count = len(frame) // 2
    if count == 0:
        return 0.0
    import struct
    shorts = struct.unpack(f"{count}h", frame)
    sum_squares = sum((s * s) for s in shorts)
    rms = math.sqrt(sum_squares / count)
    return rms


def _listen_audio_vad(
    timeout: float = 10.0,
    silence_duration: float = 1.2,
    energy_threshold_ratio: float = 1.5
) -> bytes:
    """
    基于能量的简单 VAD 录音：检测到声音后开始录制，静音持续一定时间后停止
    返回 16kHz 16bit 单声道 WAV 数据
    """
    import struct
    import wave
    import io
    import time

    chunk_size = 1024
    sample_rate = 16000
    sample_width = 2

    r = sr.Recognizer()

    try:
        with sr.Microphone(sample_rate=sample_rate) as source:
            logger.info("正在聆听（VAD 模式）...")
            r.adjust_for_ambient_noise(source, duration=0.5)

            # 根据环境噪声设定阈值
            ambient_rms = getattr(r, "_ambient_noise_rms", 100.0)
            threshold = max(ambient_rms * energy_threshold_ratio, 300.0)

            start_time = time.time()
            frames = []
            recording = False
            last_sound_time = None

            while True:
                # 超时退出
                if time.time() - start_time > timeout:
                    logger.info("聆听超时")
                    break

                chunk = source.stream.read(chunk_size, exception_on_overflow=False)
                energy = _rms(chunk)

                if energy > threshold:
                    if not recording:
                        recording = True
                        logger.info("检测到语音，开始录制...")
                    last_sound_time = time.time()
                    frames.append(chunk)
                elif recording:
                    frames.append(chunk)
                    if last_sound_time and time.time() - last_sound_time > silence_duration:
                        logger.info("检测到静音，结束录制")
                        break

            if not frames:
                return b""

            # 封装为 WAV 字节流
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(sample_width)
                wf.setframerate(sample_rate)
                wf.writeframes(b"".join(frames))
            return buffer.getvalue()

    except sr.WaitTimeoutError:
        return b""
    except Exception as e:
        logger.error(f"VAD 录音失败：{e}")
        return b""


def _listen_audio(timeout: int = 5, phrase_limit: int = 10):
    """传统录音：固定超时，返回音频数据"""
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            logger.info("正在聆听...")
            r.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
                return audio.get_wav_data()
            except sr.WaitTimeoutError:
                return None
    except OSError as e:
        logger.error(f"麦克风初始化失败：{e}")
        return None
    except Exception as e:
        logger.error(f"录音失败：{e}")
        return None


def _asr_whisper(audio_data: bytes) -> str:
    """使用 faster-whisper 本地识别"""
    import wave

    model = _get_whisper_model()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp_path = tmp.name
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio_data)

    try:
        segments, _ = model.transcribe(tmp_path, language="zh", beam_size=5)
        text = "".join([seg.text for seg in segments]).strip()
        return text
    finally:
        os.unlink(tmp_path)


def _asr_google(audio) -> str:
    """Google Web Speech API 识别（已弃用 - 违反本地优先原则，上传音频到 Google 服务器）"""
    logger.warning("Google ASR 已弃用：违反本地优先原则，请使用本地 whisper 模型")
    return ""


def listen(use_vad: bool = True) -> str:
    """
    语音识别，返回中文文本
    use_vad=True 时使用 VAD 录音，说完即停；False 时使用固定超时
    本地优先：仅使用本地 faster-whisper，不再上传音频到第三方服务
    """
    if use_vad:
        audio = _listen_audio_vad()
    else:
        audio_data = _listen_audio()
        audio = audio_data if audio_data else b""

    if not audio:
        return ""

    # 仅使用本地 whisper 识别（保护隐私，不上传音频）
    if _try_local_asr:
        try:
            text = _asr_whisper(audio)
            if text:
                logger.info(f"先生: {text}")
                return text
        except Exception as e:
            logger.error(f"本地 ASR 识别失败: {e}")

    # 本地识别失败时不再回退到 Google（隐私优先）
    logger.warning("本地 ASR 无结果，请检查 whisper 模型是否已加载")
    speak("抱歉先生，我没听清。")
    return ""
