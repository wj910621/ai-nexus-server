"""Tests for CosyVoiceProvider (local)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.base import GenerationResult


@pytest.fixture
def cosyvoice_provider():
    from app.engines.tts.cosyvoice import CosyVoiceProvider
    p = CosyVoiceProvider(model_id="FunAudioLLM/CosyVoice-300M")
    p._initialized = True
    return p


def test_import_with_mocked_torch():
    """torch 未安装时仍可导入模块"""
    import sys
    original = sys.modules.get("torch")
    sys.modules["torch"] = MagicMock()  # type: ignore
    try:
        import importlib
        import app.engines.tts.cosyvoice as cv_mod
        importlib.reload(cv_mod)
    finally:
        if original is not None:
            sys.modules["torch"] = original
        else:
            del sys.modules["torch"]


@pytest.mark.asyncio
async def test_synthesize_success(cosyvoice_provider):
    """合成成功"""
    fake_model = MagicMock()
    fake_audio = MagicMock()
    fake_audio.tobytes.return_value = b"fake-wav-bytes"
    fake_model.inference_sft.return_value = [fake_audio]
    cosyvoice_provider._model = fake_model

    import io
    import sys
    # torchaudio 未安装时，patch("torchaudio.save") 需要可导入 torchaudio
    original_ta = sys.modules.get("torchaudio")
    sys.modules["torchaudio"] = MagicMock()
    try:
        with patch("app.engines.tts.cosyvoice.BytesIO", new=io.BytesIO):
            with patch("torchaudio.save", new=MagicMock()):
                result = await cosyvoice_provider.synthesize(
                    text="你好", voice="中文女",
                )
    finally:
        if original_ta is not None:
            sys.modules["torchaudio"] = original_ta
        else:
            del sys.modules["torchaudio"]

    assert result.success is True
    assert result.metadata["provider"] == "cosyvoice"


@pytest.mark.asyncio
async def test_synthesize_not_initialized():
    from app.engines.tts.cosyvoice import CosyVoiceProvider
    p = CosyVoiceProvider(model_id="test")
    result = await p.synthesize(text="hi")
    assert result.success is False
    assert "未初始化" in result.error or "not initialized" in result.error.lower()


@pytest.mark.asyncio
async def test_lazy_loading():
    from app.engines.tts.cosyvoice import CosyVoiceProvider
    p = CosyVoiceProvider(model_id="test-model")
    assert p._model is None
    assert p._initialized is False


@pytest.mark.asyncio
async def test_health_check(cosyvoice_provider):
    with patch.object(cosyvoice_provider, "synthesize", new=AsyncMock(return_value=GenerationResult(
        success=True, data=b"fake-wav", content_type="audio/wav", metadata={},
    ))):
        result = await cosyvoice_provider.health_check()
    assert result is True
