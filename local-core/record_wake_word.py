"""
录制“Y·NEX”唤醒词样本

使用方式：
1. 确保麦克风可用，运行 python record_wake_word.py
2. 按照提示每次说“Y·NEX”，共录制指定数量样本
3. 将 data/wake_word_samples/ 目录下的 wav 文件上传到 Picovoice Console 训练
   https://console.picovoice.ai/ppn
4. 下载 .ppn 文件，填入 .env 的 WAKE_WORD_MODEL_PATH
"""

import os
import wave
import time
import math
import struct


def _rms(frame: bytes) -> float:
    """计算音频能量"""
    count = len(frame) // 2
    if count == 0:
        return 0.0
    shorts = struct.unpack(f"{count}h", frame)
    return math.sqrt(sum((s * s) for s in shorts) / count)


def _level_bar(rms: float, max_rms: float = 5000) -> str:
    """把音量转成进度条"""
    ratio = min(rms / max_rms, 1.0)
    blocks = int(ratio * 20)
    return "█" * blocks + "░" * (20 - blocks)


def record_sample(index: int, seconds: int = 2):
    """录制单条样本，带音量提示"""
    try:
        import pyaudio
    except ImportError:
        print("请先安装 pyaudio：pip install pyaudio")
        return False

    sample_rate = 16000
    channels = 1
    sample_width = 2
    chunk_size = 1024

    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=sample_rate,
        input=True,
        frames_per_buffer=chunk_size
    )

    print(f"\n第 {index} 条：")
    print("准备... 看到音量条跳动时，清晰地说出“Y·NEX”（2秒）")
    input("按回车开始...")

    # 预读 0.3 秒环境音做参考
    ambient_frames = []
    for _ in range(int(sample_rate / chunk_size * 0.3)):
        ambient_frames.append(stream.read(chunk_size, exception_on_overflow=False))
    ambient_rms = _rms(b"".join(ambient_frames))
    threshold = max(ambient_rms * 3, 300)

    print("🎙️  正在录音...")
    frames = []
    silent_chunks = 0
    max_rms = 0

    total_chunks = int(sample_rate / chunk_size * seconds)
    for _ in range(total_chunks):
        data = stream.read(chunk_size, exception_on_overflow=False)
        rms = _rms(data)
        max_rms = max(max_rms, rms)
        frames.append(data)
        bar = _level_bar(rms)
        print(f"\r  {bar} {rms:.0f}", end="", flush=True)

        if rms < threshold:
            silent_chunks += 1

    print()

    stream.stop_stream()
    stream.close()
    p.terminate()

    # 检查录音质量
    if max_rms < 500:
        print("⚠️  音量过小，这条可能不合格，建议重录。")
        retry = input("是否重录？(y/n): ").strip().lower()
        if retry == "y":
            return record_sample(index, seconds)

    save_dir = "data/wake_word_samples"
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, f"yijie_{index:02d}.wav")

    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))

    print(f"✅ 已保存：{path}")
    return True


def main():
    print("=== Y·NEX唤醒词样本录制 ===")
    print("建议：在安静环境下，每次用自然语速和音量说“Y·NEX”。")
    print("样本将保存在 data/wake_word_samples/\n")

    try:
        count = int(input("要录制多少条样本？（建议 20-30）: ") or "20")
    except ValueError:
        count = 20

    for i in range(1, count + 1):
        if not record_sample(i):
            break

    print(f"\n完成！共录制 {count} 条样本。")
    print("下一步：访问 https://console.picovoice.ai/ppn 训练并下载 .ppn 模型文件。")
    print("然后将模型路径填入 .env：")
    print("  WAKE_WORD_MODEL_PATH=C:\\路径\\Y·NEX.ppn")
    print("  WAKE_WORD_ACCESS_KEY=你的PicovoiceKey")


if __name__ == "__main__":
    main()
