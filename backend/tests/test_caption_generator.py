"""Tests for CaptionGenerator (P3 Task 9)."""
import pytest
from unittest.mock import MagicMock, patch


def test_caption_generator_init():
    """CaptionGenerator 初始化"""
    from app.engines.training.caption import CaptionGenerator

    cg = CaptionGenerator()
    assert cg._model_name == "Salesforce/blip-image-captioning-large"
    assert cg._processor is None
    assert cg._model is None


def test_caption_generator_custom_model():
    """支持自定义模型名"""
    from app.engines.training.caption import CaptionGenerator

    cg = CaptionGenerator(model="custom/blip-model")
    assert cg._model_name == "custom/blip-model"


@pytest.mark.asyncio
async def test_caption_generate_returns_string(tmp_path):
    """generate 返回 caption 字符串"""
    from app.engines.training.caption import CaptionGenerator

    # 创建假图片
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image bytes")

    cg = CaptionGenerator()

    # mock _load_model + _generate_caption
    with patch.object(cg, "_load_model"), \
         patch.object(cg, "_generate_caption", return_value="a woman with red hair"):
        result = await cg.generate(str(img_path), trigger_word="zkq_char")

    assert isinstance(result, str)
    assert "zkq_char" in result
    assert "a woman with red hair" in result


@pytest.mark.asyncio
async def test_caption_generate_appends_trigger_word(tmp_path):
    """generate 应在 caption 末尾追加 trigger_word"""
    from app.engines.training.caption import CaptionGenerator

    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"x")

    cg = CaptionGenerator()

    with patch.object(cg, "_load_model"), \
         patch.object(cg, "_generate_caption", return_value="a cat sitting on a table"):
        result = await cg.generate(str(img_path), trigger_word="my_cat")

    assert result == "a cat sitting on a table, my_cat character"


@pytest.mark.asyncio
async def test_caption_generate_no_trigger_word(tmp_path):
    """无 trigger_word 时不追加"""
    from app.engines.training.caption import CaptionGenerator

    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"x")

    cg = CaptionGenerator()

    with patch.object(cg, "_load_model"), \
         patch.object(cg, "_generate_caption", return_value="a dog running"):
        result = await cg.generate(str(img_path), trigger_word="")

    assert result == "a dog running"


@pytest.mark.asyncio
async def test_caption_generate_handles_model_error(tmp_path):
    """模型加载失败时应抛出 RuntimeError"""
    from app.engines.training.caption import CaptionGenerator

    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"x")

    cg = CaptionGenerator()

    with patch.object(cg, "_load_model", side_effect=ImportError("transformers not installed")):
        with pytest.raises(RuntimeError, match="caption 模型加载失败"):
            await cg.generate(str(img_path), trigger_word="zkq")


@pytest.mark.asyncio
async def test_caption_generate_batch(tmp_path):
    """batch_generate 批量生成 caption"""
    from app.engines.training.caption import CaptionGenerator

    for i in range(3):
        (tmp_path / f"img_{i}.png").write_bytes(b"x")

    cg = CaptionGenerator()
    image_paths = [str(tmp_path / f"img_{i}.png") for i in range(3)]

    async def fake_generate(path, trigger_word):
        return f"caption for {path}, {trigger_word} character"

    with patch.object(cg, "generate", side_effect=fake_generate):
        results = await cg.batch_generate(image_paths, trigger_word="zkq")

    assert len(results) == 3
    assert all("zkq" in r for r in results)
