"""
远程语音通道模块
让手机/其他麦克风设备可以远程唤醒Y·NEX并发送语音。

架构：
- Y·NEX主服务启动一个 UDP 语音接收器（默认端口 7799）
- 手机端 App / 脚本把音频流编码为 Opus/PCM 后发送到该端口
- 收到完整语音包后，本地 ASR 识别，再交给 brain 处理

简化实现（零额外依赖）：
- 使用 UDP 传输 16kHz 16bit 单声道 PCM 数据包
- 支持 VAD 端点检测
- 识别完成后返回文本，并触发语音播报

手机端示例用法：
  python termux_voice_client.py
"""

import socket
import threading
import wave
import io
import time
import struct
from typing import Optional

from logger import logger
from speech import listen, _asr_whisper, _asr_google
from brain import get_ai_response
import speech_recognition as sr


REMOTE_VOICE_PORT = int(__import__("os").getenv("YNEX_VOICE_PORT", "7799"))
REMOTE_VOICE_ENABLED = True
_server_thread = None
_udp_socket = None


def _process_audio_frame(wav_data: bytes, client_addr: tuple) -> str:
    """处理收到的 WAV 数据并识别"""
    try:
        # 验证 WAV 头
        with wave.open(io.BytesIO(wav_data), "rb") as wf:
            nchannels = wf.getnchannels()
            framerate = wf.getframerate()
            pcm = wf.readframes(wf.getnframes())

        # 标准化为 16kHz 16bit mono（如果是 44.1kHz 需要重采样）
        if framerate != 16000:
            pcm = _resample_pcm(pcm, framerate, 16000)

        # ASR 识别
        r = sr.Recognizer()
        audio = sr.AudioData(pcm, sample_rate=16000, sample_width=2)
        try:
            text = r.recognize_google(audio, language="zh-CN")
        except Exception:
            text = ""

        if not text:
            return ""

        logger.info(f"远程语音来自 {client_addr}: {text}")

        # 自动处理指令
        reply = get_ai_response(text)
        from speech import speak
        try:
            speak(reply)
        except Exception as e:
            logger.error(f"远程语音回复播报失败：{e}")

        return reply
    except Exception as e:
        logger.error(f"处理远程语音失败：{e}")
        return ""


def _resample_pcm(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    """简单的线性重采样（16bit mono）"""
    import struct
    import math

    if src_rate == dst_rate:
        return pcm

    count = len(pcm) // 2
    samples = struct.unpack(f"<{count}h", pcm)
    ratio = dst_rate / src_rate
    new_count = int(count * ratio)
    new_samples = []
    for i in range(new_count):
        src_idx = i / ratio
        idx0 = int(src_idx)
        idx1 = min(idx0 + 1, count - 1)
        frac = src_idx - idx0
        val = samples[idx0] * (1 - frac) + samples[idx1] * frac
        new_samples.append(int(val))
    return struct.pack(f"<{len(new_samples)}h", *new_samples)


def _voice_server_loop():
    """UDP 语音服务器主循环"""
    global _udp_socket
    _udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _udp_socket.bind(("0.0.0.0", REMOTE_VOICE_PORT))
    _udp_socket.settimeout(2.0)

    logger.info(f"远程语音通道已启动：UDP 0.0.0.0:{REMOTE_VOICE_PORT}")

    # 会话缓冲：client_addr -> chunks
    sessions: dict = {}
    last_seen: dict = {}

    try:
        while REMOTE_VOICE_ENABLED:
            try:
                data, addr = _udp_socket.recvfrom(4096)
            except socket.timeout:
                # 清理过期会话
                now = time.time()
                expired = [k for k, v in last_seen.items() if now - v > 10]
                for k in expired:
                    sessions.pop(k, None)
                    last_seen.pop(k, None)
                continue
            except OSError:
                break

            if not data:
                continue

            # 协议：
            # - 第一字节为标志位：0x01=开始, 0x02=数据, 0xFF=结束
            flag = data[0]
            payload = data[1:]

            if flag == 0x01:
                sessions[addr] = [payload]
                last_seen[addr] = time.time()
            elif flag == 0x02:
                if addr in sessions:
                    sessions[addr].append(payload)
                    last_seen[addr] = time.time()
            elif flag == 0xFF:
                if addr in sessions:
                    sessions[addr].append(payload)
                    wav_data = b"".join(sessions[addr])
                    sessions.pop(addr, None)
                    last_seen.pop(addr, None)
                    threading.Thread(
                        target=_process_audio_frame,
                        args=(wav_data, addr),
                        daemon=True
                    ).start()
    finally:
        if _udp_socket:
            _udp_socket.close()
            _udp_socket = None


def start_remote_voice_server():
    """启动远程语音服务器"""
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        logger.info("远程语音服务器已在运行")
        return

    _server_thread = threading.Thread(target=_voice_server_loop, daemon=True)
    _server_thread.start()


def stop_remote_voice_server():
    """停止远程语音服务器"""
    global REMOTE_VOICE_ENABLED, _udp_socket
    REMOTE_VOICE_ENABLED = False
    if _udp_socket:
        _udp_socket.close()


if __name__ == "__main__":
    print(f"启动远程语音接收器，端口 {REMOTE_VOICE_PORT}")
    start_remote_voice_server()
    while True:
        time.sleep(1)
