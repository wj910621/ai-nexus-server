"""Phase 8 P4: 阿里云 OSS 异步存储实现。

实现 `StorageBackend` 接口，将文件保存到阿里云 OSS。
仅在 `settings.oss_enabled=True` 且生产环境时启用。

依赖：oss2 (Aliyun OSS Python SDK)
"""

from .metrics import storage_operations_total
from .storage_async import StorageBackend

try:
    import oss2  # type: ignore
except ImportError:
    oss2 = None  # type: ignore


class OSSStorage(StorageBackend):
    """阿里云 OSS 异步存储实现。"""

    def __init__(
        self,
        bucket: str,
        access_key_id: str,
        access_key_secret: str,
        endpoint: str,
    ):
        if oss2 is None:
            raise ImportError(
                "oss2 not installed. Run: pip install oss2"
            )
        if not bucket or not access_key_id or not access_key_secret or not endpoint:
            raise ValueError("OSS bucket / access_key_id / access_key_secret / endpoint must be set")
        self.bucket_name = bucket
        self.endpoint = endpoint
        auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(auth, endpoint, bucket)

    async def save(self, path: str, data: bytes) -> str:
        """上传字节数据到 OSS，返回可公开访问的 URL。"""
        try:
            self.bucket.put_object(path, data)
            storage_operations_total.labels(backend="oss", operation="save", result="success").inc()
        except Exception:
            storage_operations_total.labels(backend="oss", operation="save", result="failure").inc()
            raise
        return self._public_url(path)

    async def get_full_path(self, path: str) -> str:
        """返回 OSS 公开 URL。"""
        # 移除可能的 /uploads/ 前缀
        if path.startswith("/uploads/"):
            path = path[len("/uploads/"):]
        elif path.startswith("uploads/"):
            path = path[len("uploads/"):]
        storage_operations_total.labels(backend="oss", operation="get", result="success").inc()
        return self._public_url(path)

    async def exists(self, path: str) -> bool:
        """检查 OSS 对象是否存在。"""
        if path.startswith("/uploads/"):
            path = path[len("/uploads/"):]
        elif path.startswith("uploads/"):
            path = path[len("uploads/"):]
        return self.bucket.object_exists(path)

    async def delete(self, path: str) -> None:
        """删除 OSS 对象。"""
        if path.startswith("/uploads/"):
            path = path[len("/uploads/"):]
        elif path.startswith("uploads/"):
            path = path[len("uploads/"):]
        try:
            self.bucket.delete_object(path)
            storage_operations_total.labels(backend="oss", operation="delete", result="success").inc()
        except Exception:
            storage_operations_total.labels(backend="oss", operation="delete", result="failure").inc()
            raise

    def _public_url(self, path: str) -> str:
        """构造公开访问 URL。"""
        return f"https://{self.bucket_name}.{self.endpoint}/{path}"
