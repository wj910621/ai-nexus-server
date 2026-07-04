import os
import warnings
import speech_recognition as sr
from config import settings

# 尝试加载 porcupine 唤醒词引擎
try:
    import pvporcupine
    import pvrecorder
    _PORCUPINE_AVAILABLE = True
except Exception:
    _PORCUPINE_AVAILABLE = False
    warnings.warn("pvporcupine / pvrecorder 未安装，唤醒词功能将不可用。")


def _create_porcupine():
    """创建 porcupine 唤醒词引擎"""
    access_key = settings.wake_word_access_key
    model_path = settings.wake_word_model_path

    if model_path and os.path.exists(model_path):
        print(f"使用自定义唤醒词模型：{model_path}")
        return pvporcupine.create(access_key=access_key, keyword_paths=[model_path])

    # 默认使用内置 "jarvis" 作为占位
    print("未找到自定义唤醒词模型，使用内置英文 'jarvis' 作为占位。")
    if access_key:
        return pvporcupine.create(access_key=access_key, keywords=["jarvis"])

    # 无 access_key 时尝试免费版（有限制）
    return pvporcupine.create(keywords=["jarvis"])


def wait_for_wake_word():
    """等待唤醒词，被唤醒后返回"""
    if not _PORCUPINE_AVAILABLE:
        print("唤醒词引擎未安装，跳过唤醒检测，直接进入聆听模式。")
        return

    try:
        porcupine = _create_porcupine()
    except Exception as e:
        print(f"唤醒词引擎初始化失败：{e}，跳过唤醒检测。")
        return

    recorder = pvrecorder.PvRecorder(
        frame_length=porcupine.frame_length,
        device_index=-1
    )

    print(f"等待唤醒词：{settings.wake_word} ...")
    try:
        recorder.start()
        while True:
            pcm = recorder.read()
            result = porcupine.process(pcm)
            if result >= 0:
                print(f"检测到唤醒词：{settings.wake_word}")
                break
    finally:
        recorder.stop()
        recorder.delete()
        porcupine.delete()


def wait_for_wake_word_simple():
    """简化版：用 SpeechRecognition 检测关键词（备用方案）"""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print(f"等待唤醒词：{settings.wake_word} ...")
        r.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = r.listen(source, timeout=None, phrase_time_limit=3)
            text = r.recognize_google(audio, language="zh-CN")
            if settings.wake_word in text:
                print(f"检测到唤醒词：{settings.wake_word}")
                return True
        except sr.UnknownValueError:
            pass
        except sr.RequestError:
            pass
    return False
