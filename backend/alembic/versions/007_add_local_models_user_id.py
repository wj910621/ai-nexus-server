"""add user_id and hardware_profile to local_models

Revision ID: 007
Revises: 006_user_prefs
Create Date: 2026-07-20

Task 22 (Phase 8 P1): LocalModel 表扩展
- 新增 user_id（多用户隔离）
- 新增 hardware_profile（按硬件配置推荐）
- 新增 md5（下载校验）
- 新增 download_url（镜像/直链）
- 新增 original_size_mb（原始仓库大小）
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006_user_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：添加新字段"""
    op.add_column("local_models", sa.Column(
        "user_id", sa.Integer(), nullable=False, server_default="0"
    ))
    op.add_column("local_models", sa.Column(
        "hardware_profile", sa.String(16), nullable=True
    ))
    op.add_column("local_models", sa.Column(
        "md5", sa.String(64), nullable=True
    ))
    op.add_column("local_models", sa.Column(
        "download_url", sa.String(512), nullable=True
    ))
    op.add_column("local_models", sa.Column(
        "original_size_mb", sa.Integer(), nullable=False, server_default="0"
    ))

    # 创建索引
    op.create_index("ix_local_models_user_id", "local_models", ["user_id"])
    op.create_index("ix_local_models_hardware_profile", "local_models", ["hardware_profile"])


def downgrade() -> None:
    """回滚：删除新字段"""
    op.drop_index("ix_local_models_hardware_profile", table_name="local_models")
    op.drop_index("ix_local_models_user_id", table_name="local_models")
    op.drop_column("local_models", "original_size_mb")
    op.drop_column("local_models", "download_url")
    op.drop_column("local_models", "md5")
    op.drop_column("local_models", "hardware_profile")
    op.drop_column("local_models", "user_id")
