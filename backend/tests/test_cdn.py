"""Tests for Task 13: CDN + Provider Failover."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.cdn import CDNManager, cdn_manager, CDNProvider


def test_cdn_manager_no_provider_returns_original_url():
    """When cdn_provider='none', get_url returns the original URL."""
    mgr = CDNManager(provider=CDNProvider.NONE)
    url = mgr.get_url("/uploads/images/cat.png")
    assert url == "/uploads/images/cat.png"


def test_cdn_manager_r2_provider_prepends_cdn_url():
    """R2 provider prepends the public CDN URL."""
    mgr = CDNManager(
        provider=CDNProvider.R2,
        public_url="https://cdn.example.com",
    )
    url = mgr.get_url("/uploads/images/cat.png")
    assert url == "https://cdn.example.com/uploads/images/cat.png"


def test_cdn_manager_qiniu_provider_prepends_domain():
    """Qiniu provider prepends the CDN domain."""
    mgr = CDNManager(
        provider=CDNProvider.QINIU,
        public_url="https://cdn.qiniu.example.com",
    )
    url = mgr.get_url("/uploads/videos/v1.mp4")
    assert url == "https://cdn.qiniu.example.com/uploads/videos/v1.mp4"


def test_cdn_manager_already_absolute_url_is_returned_as_is():
    """Absolute URLs (http://...) are returned unchanged."""
    mgr = CDNManager(provider=CDNProvider.R2, public_url="https://cdn.example.com")
    url = mgr.get_url("https://other.com/image.png")
    assert url == "https://other.com/image.png"


@pytest.mark.asyncio
async def test_cdn_manager_upload_no_provider_uses_local():
    """No provider → upload() returns the local relative path."""
    mgr = CDNManager(provider=CDNProvider.NONE)
    path = await mgr.upload(b"hello", "test/file.txt")
    # Should call local storage; verify returns a string path
    assert isinstance(path, str)


@pytest.mark.asyncio
async def test_cdn_manager_upload_r2_calls_boto3(monkeypatch):
    """R2 upload() pushes to R2 via boto3 S3-compatible API."""
    mgr = CDNManager(
        provider=CDNProvider.R2,
        public_url="https://cdn.example.com",
        access_key="ak",
        secret_key="sk",
        bucket="comicstudio",
        account_id="acct",
    )
    # Mock boto3 client
    mock_s3 = MagicMock()
    mock_client = MagicMock()
    mock_s3.client.return_value = mock_client
    monkeypatch.setattr("app.core.cdn.boto3", mock_s3)

    path = await mgr.upload(b"hello", "test/file.txt")
    assert mock_s3.client.called
    assert path == "https://cdn.example.com/test/file.txt"


def test_cdn_is_enabled_property():
    """is_enabled reflects whether a provider is configured."""
    assert CDNManager(provider=CDNProvider.NONE).is_enabled is False
    assert CDNManager(provider=CDNProvider.R2).is_enabled is True
