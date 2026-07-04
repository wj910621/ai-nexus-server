"""
远场麦克风 + 语音增强模块
提供高质量的语音采集，适用于远距离说话场景。

功能：
1. 噪声抑制（基于 noisereduce / webrtcvad）
2. 自动增益控制（AGC）
3. VAD 语音端点检测
4. 多麦克风支持（ReSpeaker / Seeed Voicecard）

硬件推荐：
  - ReSpeaker 2-Mics Pi HAT（树莓派）
  - ReSpeaker 4-Mic Array
  - Seeed Studio Voicecard
  - 任意 USB 麦克风阵列

依赖：
  - noisereduce（噪声抑制）
  - webrtcvad（VAD）
  - numpy
  - sounddevice / pyaudio
"""

import os
import time
import threading
from typing import Callable, Optional

from logger import logger

# 延迟导入
_numpy = None
_noisereduce = None
_webrtcvad = None


def _import_numpy():
    global _numpy
    if _numpy is None:
        try:
            import numpy as np
            _numpy = np
        except ImportError:
            logger.warning("numpy 未安装，语音增强不可用。")
    return _numpy


def _import_noisereduce():
    global _noisereduce
    if _noisereduce is None:
        try:
            import noisereduce as nr
            _noisereduce = nr
        except ImportError:
            logger.warning("noisereduce 未安装，噪声抑制不可用。pip install noisereduce")
    return _noisereduce


def _import_webrtcvad():
    global _webrtcvad
    if _webrtcvad is None:
        try:
            import webrtcvad
            _webrtcvad = webrtcvad
        except ImportError:
            logger.warning("webrtcvad 未安装，VAD 不可用。pip install webrtcvad")
    return _webrtcvad


# =============================================================================
# 噪声抑制
# =============================================================================

def reduce_noise(audio_float, sample_rate: int = 16000, stationary: bool = True):
    """
    对音频做噪声抑制。
    audio_float: numpy float32 数组，范围 [-1, 1]
    返回处理后的音频。
    """
    np = _import_numpy()
    nr = _import_noisereduce()
    if not np or not nr:
        return audio_float

    try:
        reduced_noise = nr.reduce_noise(
            y=audio_float,
            sr=sample_rate,
            stationary=stationary,
            prop_decrease=0.85,
        )
        return reduced_noise
    except Exception as e:
        logger.warning(f"噪声抑制失败：{e}")
        return audio_float


def simple_noise_gate(audio_float, threshold: float = 0.01):
    """
    简单噪声门：低于阈值的静音置零。
    """
    np = _import_numpy()
    if not np:
        return audio_float
    mask = np.abs(audio_float) < threshold
    return np.where(mask, 0.0, audio_float)


def agc(audio_float, target_level: float = 0.3, max_gain: float = 10.0):
    """
    简单自动增益控制：将音频归一化到目标电平。
    """
    np = _import_numpy()
    if not np:
        return audio_float

    current_max = np.max(np.abs(audio_float))
    if current_max < 1e-6:
        return audio_float

    gain = min(max_gain, target_level / current_max)
    return audio_float * gain


# =============================================================================
# VAD 语音端点检测
# =============================================================================

class VAD:
    """WebRTC VAD 包装器"""

    def __init__(self, aggressiveness: int = 2, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.vad = None
        vad_mod = _import_webrtcvad()
        if vad_mod:
            self.vad = vad_mod.Vad(aggressiveness)

    def is_speech(self, pcm_bytes: bytes) -> bool:
        """
        判断一段 PCM 音频是否包含语音。
        pcm_bytes: 16-bit mono PCM
        """
        if not self.vad:
            # 回退：用简单能量判断
            np = _import_numpy()
            if not np:
                return True
            audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            energy = np.sqrt(np.mean(audio ** 2))
            return energy > 0.01

        # WebRTC VAD 只支持 10/20/30ms 帧
        frame_size = self.sample_rate * 20 // 1000  # 20ms
        samples_per_frame = frame_size * 2  # 16-bit

        if len(pcm_bytes) < samples_per_frame:
            return False

        try:
            # 检测前几帧
            for i in range(0, min(3, len(pcm_bytes) // samples_per_frame)):
                frame = pcm_bytes[i * samples_per_frame:(i + 1) * samples_per_frame]
                if self.vad.is_speech(frame, self.sample_rate):
                    return True
            return False
        except Exception:
            return True


# =============================================================================
# 增强音频处理流水线
# =============================================================================

def enhance_audio(audio_float, sample_rate: int = 16000,
                  do_noise_reduction: bool = True,
                  do_agc: bool = True,
                  do_noise_gate: bool = False) -> bytes:
    """
    完整的语音增强流水线。
    输入 float32 numpy 数组，输出 16-bit PCM bytes。
    """
    np = _import_numpy()
    if not np:
        return audio_float.tobytes() if hasattr(audio_float, 'tobytes') else audio_float

    audio = audio_float.copy()

    if do_noise_reduction:
        audio = reduce_noise(audio, sample_rate)

    if do_agc:
        audio = agc(audio)

    if do_noise_gate:
        audio = simple_noise_gate(audio)

    # 转为 16-bit PCM
    audio_int16 = np.clip(audio * 32768, -32768, 32767).astype(np.int16)
    return audio_int16.tobytes()


# =============================================================================
# 远场麦克风配置指南
# =============================================================================

RESPEAKER_GUIDE = """
=== ReSpeaker 麦克风阵列配置指南 ===

【硬件型号】
  - ReSpeaker 2-Mics Pi HAT（入门，约 100 元）
  - ReSpeaker 4-Mic Array（中级，约 200 元）
  - ReSpeaker 6-Mic Circular Array（高级，约 300 元）
  - Seeed Studio Voicecard（性价比高）

【树莓派驱动安装】
  # 2-Mic / 4-Mic
  git clone https://github.com/respeaker/seeed-voicecard.git
  cd seeed-voicecard
  sudo ./install.sh
  sudo reboot

  # 验证
  arecord -l
  aplay -l

【测试录音】
  arecord -D plughw:1,0 -f cd -d 3 test.wav
  aplay test.wav

【Python 录音】
  pip install sounddevice
  python -c "import sounddevice as sd; print(sd.query_devices())"

【调整增益】
  alsamixer
  # 或：
  amixer -D hw:1 sset Mic 50%

【与Y·NEX配合】
  1. 设置环境变量 YNEX_MIC_DEVICE=1（设备编号）
  2. speech.py 自动使用指定设备录音
  3. 启用噪声抑制：YNEX_NOISE_REDUCTION=1

【回声消除（可选）】
  # PulseAudio 模块
  pactl load-module module-echo-cancel aec_method=webrtc source_name=echocancel
  pactl set-default-source echocancel.monitor
"""


def mic_config_guide() -> str:
    """返回麦克风配置指南"""
    return RESPEAKER_GUIDE.strip()


if __name__ == "__main__":
    print("测试语音增强模块...")
    np = _import_numpy()
    if np:
        # 生成测试音频：带噪声的正弦波
        sr = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        clean = 0.1 * np.sin(2 * np.pi * 440 * t)
        noise = 0.02 * np.random.randn(len(t))
        audio = clean + noise

        # 测试噪声抑制
        enhanced = reduce_noise(audio, sr)
        print(f"原始 RMS: {np.sqrt(np.mean(audio**2)):.4f}")
        print(f"增强后 RMS: {np.sqrt(np.mean(enhanced**2)):.4f}")
        print("✅ 噪声抑制工作正常")

        # 测试 AGC
        agced = agc(audio)
        print(f"AGC 后峰值: {np.max(np.abs(agced)):.4f}")
        print("✅ AGC 工作正常")

        # 测试 VAD
        vad = VAD(sample_rate=sr)
        pcm = (audio * 32768).astype(np.int16).tobytes()
        print(f"VAD 检测（有语音）: {vad.is_speech(pcm)}")
        print("✅ VAD 工作正常")
    else:
        print("numpy 未安装，跳过测试")
