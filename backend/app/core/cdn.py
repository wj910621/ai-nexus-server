"""CDN 管理器 - Cloudflare R2 / 七牛云 统一抽象"""
import enum
import logging

import boto3
from botocore.config import Config as BotoConfig

from app.core.config import settings
from app.core.storage import storage as local_storage

logger = logging.getLogger(__name__)


class CDNProvider(str, enum.Enum):
    NONE = "none"
    R2 = "r2"
    QINIU = "qiniu"


class CDNManager:
    """CDN 管理器

    - Provider=NONE: 返回原始 URL（桌面模式 / 开发）
    - Provider=R2:   Cloudflare R2 (S3-compatible API via boto3)
    - Provider=QINIU: 七牛云 Kodo (S3-compatible API via boto3)

    上传时文件被推送到 CDN，返回 CDN 公网 URL。
    下载时直接返回 CDN URL（由 nginx/前端直接拉取）。
    """

    def __init__(
        self,
        provider: CDNProvider = CDNProvider.NONE,
        public_url: str = "",
        access_key: str = "",
        secret_key: str = "",
        bucket: str = "",
        account_id: str = "",
        endpoint: str = "",
    ) -> None:
        self.provider = provider
        self.public_url = public_url.rstrip("/")
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.account_id = account_id
        self.endpoint = endpoint
        self._s3_client = None

    @property
    def is_enabled(self) -> bool:
        return self.provider != CDNProvider.NONE

    def _get_s3_client(self):
        """Lazy-init S3 client for R2/Qiniu (both S3-compatible)."""
        if self._s3_client is not None:
            return self._s3_client

        if self.provider == CDNProvider.R2:
            endpoint = f"https://{self.account_id}.r2.cloudflarestorage.com"
        elif self.provider == CDNProvider.QINIU:
            endpoint = self.endpoint or f"https://s3-{self.bucket}.qiniucs.com"
        else:
            return None

        self._s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="auto",
        )
        return self._s3_client

    def get_url(self, path: str) -> str:
        """获取文件的访问 URL

        - 绝对 URL（http://...）原样返回
        - 相对路径在 CDN 启用时返回 CDN URL，否则原样返回
        """
        if path.startswith(("http://", "https://")):
            return path
        if not self.is_enabled:
            return path
        # Prefix with public_url
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.public_url}{path}"

    async def upload(self, data: bytes, key: str) -> str:
        """上传文件到 CDN，返回 CDN URL"""
        if not self.is_enabled:
            # Fallback to local storage
            return local_storage.save(data, filename=key.split("/")[-1])

        client = self._get_s3_client()
        client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
        )
        return self.get_url(f"/{key}")

    async def delete(self, key: str) -> None:
        """删除 CDN 上的文件"""
        if not self.is_enabled:
            return
        client = self._get_s3_client()
        client.delete_object(Bucket=self.bucket, Key=key)


# Global singleton (initialized from settings on import)
cdn_manager = CDNManager(
    provider=CDNProvider(settings.cdn_provider),
    public_url=settings.cdn_r2_public_url or settings.cdn_qiniu_domain,
    access_key=settings.cdn_r2_access_key or settings.cdn_qiniu_access_key,
    secret_key=settings.cdn_r2_secret_key or settings.cdn_qiniu_secret_key,
    bucket=settings.cdn_r2_bucket or settings.cdn_qiniu_bucket,
    account_id=settings.cdn_r2_account_id,
)
