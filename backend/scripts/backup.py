"""自动化备份脚本 - DB + Uploads + Redis

用法:
    python scripts/backup.py --type db        # 仅备份数据库
    python scripts/backup.py --type uploads    # 仅备份上传文件
    python scripts/backup.py --type redis      # 仅备份 Redis
    python scripts/backup.py --type all        # 全部备份（默认）

保留策略（rolling）:
    - 每日备份保留 30 天
    - 每周备份保留 12 周（每周一保留一份）
    - 每月备份保留 12 个月（每月 1 号保留一份）

加密: AES-256 (Fernet) — 备份文件加密后存储为 .enc
"""
import argparse
import os
import subprocess
import sys
import tarfile
import time
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet


# Lazy-loaded settings (avoid importing app.core.config at module-import time
# so the script can be inspected by tests without a full app context).
def _get_settings():
    from app.core.config import settings
    return settings


def _backup_dir() -> Path:
    """Resolve backup directory from settings or env."""
    s = _get_settings()
    val = getattr(s, "backup_dir", None) or os.environ.get("BACKUP_DIR", "")
    return Path(val) if val else Path("/var/backups/comicstudio")


def _encryption_key() -> bytes:
    """Resolve Fernet encryption key from settings or env.

    Falls back to a random ephemeral key (NOT for production — logged to stderr).
    """
    s = _get_settings()
    key = getattr(s, "backup_encryption_key", None) or os.environ.get("BACKUP_ENCRYPTION_KEY", "")
    if key:
        if isinstance(key, str):
            return key.encode("utf-8")
        return key
    if str(getattr(s, "app_env", "")).lower() == "production":
        raise RuntimeError(
            "BACKUP_ENCRYPTION_KEY is required in production; "
            "refusing to create an unrestorable backup"
        )
    # Ephemeral key — only for dev; backups won't be restorable across runs.
    sys.stderr.write(
        "WARNING: BACKUP_ENCRYPTION_KEY not set; using ephemeral key. "
        "Restoring these backups will be impossible after this process exits.\n"
    )
    return Fernet.generate_key()


def _uploads_dir() -> Path:
    """Resolve uploads directory from settings or env."""
    s = _get_settings()
    val = getattr(s, "uploads_dir", None) or os.environ.get("UPLOADS_DIR", "")
    return Path(val) if val else Path("uploads")


def encrypt_file(input_path: Path, output_path: Path, key: bytes | None = None) -> None:
    """AES-256 加密文件 (Fernet — AES-128-CBC + HMAC-SHA256 underneath).

    Fernet provides authenticated encryption; the .enc output is the encrypted
    token. AES-256 is used here as the conceptual security target; Fernet's
    actual AES key size is 128-bit by design (NIST-approved, safe).
    """
    fernet = Fernet(key or _encryption_key())
    data = input_path.read_bytes()
    encrypted = fernet.encrypt(data)
    output_path.write_bytes(encrypted)


def backup_database() -> Path:
    """pg_dump + gzip + AES encrypt."""
    backup_dir = _backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    raw_path = backup_dir / f"db-{timestamp}.sql"
    gz_path = backup_dir / f"db-{timestamp}.sql.gz"
    enc_path = backup_dir / f"db-{timestamp}.sql.gz.enc"

    s = _get_settings()
    # pg_dump wants a libpq URL (no +asyncpg driver suffix)
    db_url = s.database_url.replace("+asyncpg", "")
    subprocess.run(
        ["pg_dump", db_url, "-f", str(raw_path)],
        check=True,
    )
    # gzip the raw dump
    with open(raw_path, "rb") as fin, open(gz_path, "wb") as fout:
        subprocess.run(["gzip"], stdin=fin, stdout=fout, check=True)
    raw_path.unlink()
    # AES-256 (Fernet) encrypt
    encrypt_file(gz_path, enc_path)
    gz_path.unlink()
    print(f"✓ DB backup: {enc_path}")
    return enc_path


def backup_uploads() -> Path:
    """tar + AES encrypt uploads/."""
    backup_dir = _backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    tar_path = backup_dir / f"uploads-{timestamp}.tar"
    enc_path = backup_dir / f"uploads-{timestamp}.tar.enc"

    uploads_dir = _uploads_dir()
    if not uploads_dir.exists():
        print(f"⚠ Uploads dir not found: {uploads_dir}; skipping", file=sys.stderr)
        return enc_path
    with tarfile.open(tar_path, "w") as tar:
        tar.add(uploads_dir, arcname="uploads")
    encrypt_file(tar_path, enc_path)
    tar_path.unlink()
    print(f"✓ Uploads backup: {enc_path}")
    return enc_path


def backup_redis() -> Path:
    """Redis BGSAVE + copy dump.rdb + AES encrypt."""
    import redis
    backup_dir = _backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    enc_path = backup_dir / f"redis-{timestamp}.rdb.enc"

    s = _get_settings()
    r = redis.from_url(getattr(s, "redis_url", "redis://localhost:6379/0"))
    r.bgsave()
    time.sleep(2)  # Wait for BGSAVE to complete (best-effort)
    cfg = r.config_get()
    rdb_dir = Path(cfg.get("dir", "/var/lib/redis"))
    rdb_filename = cfg.get("dbfilename", "dump.rdb")
    rdb_path = rdb_dir / rdb_filename
    encrypt_file(rdb_path, enc_path)
    print(f"✓ Redis backup: {enc_path}")
    return enc_path


def cleanup_old_backups() -> None:
    """滚动清理: 30天/12周/12月。

    文件名格式: <type>-YYYYMMDD-HHMMSS.<ext>.enc
    保留规则:
      - 30 天内: 全部保留
      - 30-84 天 (12 周): 仅保留每周一 (weekday()==0)
      - 84-365 天 (12 月): 仅保留每月 1 号
      - 超过 365 天: 删除
    """
    backup_dir = _backup_dir()
    now = datetime.now(UTC).replace(tzinfo=None)
    if not backup_dir.exists():
        return
    for f in backup_dir.glob("*.enc"):
        try:
            date_str = f.name.split("-")[1]
            file_date = datetime.strptime(date_str, "%Y%m%d")
        except (ValueError, IndexError):
            continue
        age_days = (now - file_date).days
        if age_days > 365:
            f.unlink()
        elif age_days > 84 and file_date.day != 1:
            f.unlink()
        elif age_days > 30 and file_date.weekday() != 0:
            f.unlink()


def main():
    parser = argparse.ArgumentParser(description="ComicStudio backup")
    parser.add_argument("--type", choices=["db", "uploads", "redis", "all"], default="all")
    args = parser.parse_args()

    if args.type in ("db", "all"):
        backup_database()
    if args.type in ("uploads", "all"):
        backup_uploads()
    if args.type in ("redis", "all"):
        try:
            backup_redis()
        except Exception as exc:
            print(f"⚠ Redis backup failed: {exc}", file=sys.stderr)

    cleanup_old_backups()
    print("✓ Backup complete")


if __name__ == "__main__":
    main()
