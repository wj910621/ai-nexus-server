"""
Termux 远程语音客户端
使用手机麦克风录制语音，通过 UDP 发送到Y·NEX 服务器，
实现"在任何地方用手机语音唤醒/控制Y·NEX"。

安装：
  pkg install python python-pyaudio
  pip install speechrecognition

运行：
  python termux_voice_client.py
"""

import socket
import wave
import io
import time
import os
import struct

YNEX_HOST = os.getenv("YNEX_HOST", "192.168.1.100")
VOICE_PORT = int(os.getenv("YNEX_VOICE_PORT", "7799"))


def _record_and_send():
    """录音并发送到Y·NEX"""
    try:
        import speech_recognition as sr
    except ImportError:
        print("请先安装 speechrecognition: pip install speechrecognition")
        return

    print("按住说话（说完松开自动发送）...")
    r = sr.Recognizer()

    with sr.Microphone(sample_rate=16000) as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = r.listen(source, timeout=10, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            print("没有检测到语音")
            return

    wav_data = audio.get_wav_data()
    _send_wav(wav_data)


def _send_wav(wav_data: bytes):
    """将 WAV 数据分包发送"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)

    # 分包大小
    chunk_size = 1400

    # 发送开始标志
    sock.sendto(b"\x01" + wav_data[:chunk_size], (YNEX_HOST, VOICE_PORT))

    offset = chunk_size
    while offset < len(wav_data):
        end = min(offset + chunk_size, len(wav_data))
        chunk = wav_data[offset:end]
        if end == len(wav_data):
            # 结束标志
            sock.sendto(b"\xff" + chunk, (YNEX_HOST, VOICE_PORT))
        else:
            sock.sendto(b"\x02" + chunk, (YNEX_HOST, VOICE_PORT))
        offset = end
        time.sleep(0.005)

    print(f"已发送 {len(wav_data)} 字节语音数据到 {YNEX_HOST}:{VOICE_PORT}")
    sock.close()


if __name__ == "__main__":
    while True:
        try:
            _record_and_send()
            time.sleep(1)
        except KeyboardInterrupt:
            print("退出")
            break
        except Exception as e:
            print(f"错误: {e}")
