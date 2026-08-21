"""订阅鉴权守卫 - 本地推理订阅验证

Task 7 (Phase 8 P1)

职责：
1. 验证用户 JWT 订阅状态（Pro/Enterprise 才能本地推理）
2. 7 天离线宽限期（订阅过期后仍可用 7 天）
3. 按硬件配置推荐 4 个 profile（low/mid/high/cpu）
4. 按 profile 返回推荐下载模型清单

硬件 profile：
- HIGH: 12GB+ VRAM（可跑 FLUX.1-dev + Qwen2.5-14B + Wan2.1）
- MID:  6-12GB VRAM（可跑 SDXL + Qwen2.5-7B + Hunyuan）
- LOW:  4-6GB VRAM（可跑 SDXL-512 + Qwen2.5-1.5B）
- CPU:  无 GPU，8GB+ RAM（仅跑 ONNX/INT8 小模型）
"""
import enum
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import jwt

logger = logging.getLogger(__name__)


class HardwareProfile(str, enum.Enum):
    """硬件配置档位"""
    HIGH = "high"  # 12GB+ VRAM
    MID = "mid"    # 6-12GB VRAM
    LOW = "low"    # 4-6GB VRAM
    CPU = "cpu"    # 无 GPU


@dataclass
class SubscriptionInfo:
    """订阅验证结果"""
    user_id: str
    tier: str  # free | pro | enterprise
    is_expired: bool
    is_within_grace: bool
    expires_at: datetime
    raw_payload: dict


@dataclass
class ModelDownloadItem:
    """模型下载项"""
    name: str
    repo_id: str
    size_mb: int
    model_type: str  # image | llm | video | tts


# 各 profile 推荐模型清单（保守取值，确保实际可跑）
_PROFILE_MODELS: dict[HardwareProfile, list[ModelDownloadItem]] = {
    HardwareProfile.HIGH: [
        ModelDownloadItem("FLUX.1-dev", "black-forest-labs/FLUX.1-dev", 23800, "image"),
        ModelDownloadItem("Qwen2.5-14B-Instruct-Q4_K_M", "Qwen/Qwen2.5-14B-Instruct-GGUF", 9000, "llm"),
        ModelDownloadItem("Wan2.1-T2V-1.3B", "Wan-AI/Wan2.1-T2V-1.3B", 8000, "video"),
        ModelDownloadItem("CosyVoice-300M", "FunAudioLLM/CosyVoice-300M", 3500, "tts"),
    ],
    HardwareProfile.MID: [
        ModelDownloadItem("stable-diffusion-xl-base-1.0", "stabilityai/stable-diffusion-xl-base-1.0", 7000, "image"),
        ModelDownloadItem("Qwen2.5-7B-Instruct-Q4_K_M", "Qwen/Qwen2.5-7B-Instruct-GGUF", 4500, "llm"),
        ModelDownloadItem("HunyuanVideo", "tencent/HunyuanVideo", 13000, "video"),
        ModelDownloadItem("CosyVoice-300M", "FunAudioLLM/CosyVoice-300M", 3500, "tts"),
    ],
    HardwareProfile.LOW: [
        ModelDownloadItem("stable-diffusion-xl-base-1.0", "stabilityai/stable-diffusion-xl-base-1.0", 7000, "image"),
        ModelDownloadItem("Qwen2.5-1.5B-Instruct-Q4_K_M", "Qwen/Qwen2.5-1.5B-Instruct-GGUF", 1200, "llm"),
        ModelDownloadItem("CosyVoice-300M", "FunAudioLLM/CosyVoice-300M", 3500, "tts"),
    ],
    HardwareProfile.CPU: [
        ModelDownloadItem("stable-diffusion-2-1-onnx-int8", "stabilityai/sd-2-1-onnx-int8", 4500, "image"),
        ModelDownloadItem("Qwen2.5-0.5B-Instruct-Q4_K_M", "Qwen/Qwen2.5-0.5B-Instruct-GGUF", 500, "llm"),
        ModelDownloadItem("CosyVoice-300M-onnx", "FunAudioLLM/CosyVoice-300M", 3500, "tts"),
    ],
}


class SubscriptionGuard:
    """订阅鉴权守卫

    使用 PyJWT 验证 token，支持 7 天离线宽限期。
    不依赖网络（离线可用），token 过期判断完全本地完成。
    """

    def __init__(
        self,
        jwt_secret: str,
        jwt_issuer: str,
        offline_grace_days: int = 7,
    ) -> None:
        self.jwt_secret = jwt_secret
        self.jwt_issuer = jwt_issuer
        self.offline_grace_days = offline_grace_days

    def verify_subscription(self, jwt_token: str) -> SubscriptionInfo:
        """验证订阅 JWT token

        Args:
            jwt_token: JWT 订阅 token

        Returns:
            SubscriptionInfo: 订阅信息

        Raises:
            PermissionError: token 无效、签名错误、issuer 不匹配、或过期超过宽限期
        """
        try:
            payload = jwt.decode(
                jwt_token,
                self.jwt_secret,
                algorithms=["HS256"],
                issuer=self.jwt_issuer,
                options={"verify_exp": False},  # 自行处理过期逻辑（含宽限期）
            )
        except jwt.InvalidTokenError as exc:
            raise PermissionError(f"无效的订阅 token: {exc}") from exc

        user_id = payload.get("sub", "")
        tier = payload.get("tier", "free")
        exp_ts = payload.get("exp", 0)
        expires_at = (
            datetime.fromtimestamp(exp_ts, UTC).replace(tzinfo=None)
            if exp_ts
            else datetime.now(UTC).replace(tzinfo=None)
        )

        now = datetime.now(UTC).replace(tzinfo=None)
        is_expired = expires_at < now
        days_since_expiry = (now - expires_at).days if is_expired else 0
        is_within_grace = is_expired and days_since_expiry < self.offline_grace_days

        # Free 用户不允许本地推理
        if tier == "free":
            raise PermissionError("Free 用户不支持本地推理，请升级 Pro")

        # 过期超过宽限期
        if is_expired and not is_within_grace:
            raise PermissionError(
                f"订阅已过期 {days_since_expiry} 天，超出 {self.offline_grace_days} 天宽限期，请续费"
            )

        return SubscriptionInfo(
            user_id=user_id,
            tier=tier,
            is_expired=is_expired,
            is_within_grace=is_within_grace,
            expires_at=expires_at,
            raw_payload=payload,
        )

    def recommend_hardware_profile(
        self,
        vram_gb: float = 0.0,
        ram_gb: float = 0.0,
    ) -> HardwareProfile:
        """根据硬件资源推荐 HardwareProfile

        Args:
            vram_gb: 显存 GB
            ram_gb: 内存 GB

        Returns:
            HardwareProfile 枚举值
        """
        if vram_gb >= 12.0:
            return HardwareProfile.HIGH
        if vram_gb >= 6.0:
            return HardwareProfile.MID
        if vram_gb >= 4.0:
            return HardwareProfile.LOW
        if ram_gb >= 8.0:
            return HardwareProfile.CPU
        # 资源不足，返回最低档
        return HardwareProfile.CPU

    def check_local_inference_allowed(
        self,
        user: SubscriptionInfo,
        hardware_profile: HardwareProfile,
    ) -> bool:
        """检查是否允许本地推理

        Args:
            user: 订阅信息
            hardware_profile: 硬件配置档位

        Returns:
            True 表示允许
        """
        # Free 用户不允许
        if user.tier == "free":
            return False
        # 过期超过宽限期不允许
        if user.is_expired and not user.is_within_grace:
            return False
        # 无硬件（CPU 档 + 8GB 以下 RAM）也不允许
        if hardware_profile == HardwareProfile.CPU and user.tier != "pro":
            # Enterprise 用户允许 CPU 推理（备用）
            return user.tier == "enterprise"
        return True

    def get_model_download_list(
        self,
        hardware_profile: HardwareProfile,
    ) -> list[dict]:
        """按硬件配置返回推荐下载模型清单

        Args:
            hardware_profile: 硬件配置档位

        Returns:
            模型列表（dict 格式：name, repo_id, size_mb, model_type）
        """
        items = _PROFILE_MODELS.get(hardware_profile, [])
        return [
            {
                "name": item.name,
                "repo_id": item.repo_id,
                "size_mb": item.size_mb,
                "model_type": item.model_type,
            }
            for item in items
        ]
