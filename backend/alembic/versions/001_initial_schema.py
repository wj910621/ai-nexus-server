"""Initial schema — matches Base.metadata.create_all output.

Revision ID: 001
Revises:
Create Date: 2026-07-19

This migration produces a schema identical to what
Base.metadata.create_all() would generate, given the current set of models
in app/models/. Verified by tests/test_migrations.py::test_migration_matches_create_all.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("email_verification_code", sa.String(20), nullable=True),
        sa.Column("reset_password_code", sa.String(20), nullable=True),
        sa.Column("code_expires_at", sa.DateTime(), nullable=True),
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("plan", sa.String(20), nullable=True),
        sa.Column("plan_expires_at", sa.DateTime(), nullable=True),
        sa.Column("credits", sa.Integer(), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_is_deleted", "users", ["is_deleted"])

    # Projects
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("genre", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("character_count", sa.Integer(), nullable=True),
        sa.Column("scene_count", sa.Integer(), nullable=True),
        sa.Column("frame_count", sa.Integer(), nullable=True),
        sa.Column("is_shared", sa.Boolean(), nullable=True),
        sa.Column("collaborators", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_id", "projects", ["id"])
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_projects_is_deleted", "projects", ["is_deleted"])

    # Characters
    op.create_table(
        "characters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("style", sa.String(50), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("age", sa.String(50), nullable=True),
        sa.Column("hair_color", sa.String(50), nullable=True),
        sa.Column("eye_color", sa.String(50), nullable=True),
        sa.Column("skin_tone", sa.String(50), nullable=True),
        sa.Column("body_type", sa.String(50), nullable=True),
        sa.Column("lora_model_path", sa.String(500), nullable=True),
        sa.Column("lora_training_status", sa.String(20), nullable=True),
        sa.Column("main_image_url", sa.String(500), nullable=True),
        sa.Column("reference_images", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_characters_id", "characters", ["id"])
    op.create_index("ix_characters_user_id", "characters", ["user_id"])
    op.create_index("ix_characters_project_id", "characters", ["project_id"])
    op.create_index("ix_characters_is_deleted", "characters", ["is_deleted"])

    # Scripts
    op.create_table(
        "scripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("structure", sa.String(50), nullable=True),
        sa.Column("genre", sa.String(50), nullable=True),
        sa.Column("outline", sa.Text(), nullable=True),
        sa.Column("total_scenes", sa.Integer(), nullable=True),
        sa.Column("total_duration", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scripts_id", "scripts", ["id"])
    op.create_index("ix_scripts_user_id", "scripts", ["user_id"])
    op.create_index("ix_scripts_project_id", "scripts", ["project_id"])

    # Script scenes
    op.create_table(
        "script_scenes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("script_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("time_of_day", sa.String(50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mood", sa.String(50), nullable=True),
        sa.Column("intensity", sa.Integer(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["script_id"], ["scripts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_script_scenes_id", "script_scenes", ["id"])
    op.create_index("ix_script_scenes_script_id", "script_scenes", ["script_id"])

    # Dialogues
    op.create_table(
        "dialogues",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("character_name", sa.String(100), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("emotion", sa.String(50), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("bubble_type", sa.String(50), nullable=True),
        sa.Column("bubble_position", sa.String(50), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["scene_id"], ["script_scenes.id"]),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dialogues_id", "dialogues", ["id"])
    op.create_index("ix_dialogues_scene_id", "dialogues", ["scene_id"])

    # Storyboard frames
    op.create_table(
        "storyboard_frames",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("script_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("frame_number", sa.Integer(), nullable=False),
        sa.Column("shot_type", sa.String(50), nullable=True),
        sa.Column("camera_angle", sa.String(50), nullable=True),
        sa.Column("composition", sa.String(50), nullable=True),
        sa.Column("camera_movement", sa.String(50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("characters_in_frame", sa.JSON(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("transition", sa.String(50), nullable=True),
        sa.Column("transition_duration", sa.Float(), nullable=True),
        sa.Column("generated_image_url", sa.String(500), nullable=True),
        sa.Column("generation_status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["script_id"], ["scripts.id"]),
        sa.ForeignKeyConstraint(["scene_id"], ["script_scenes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_storyboard_frames_id", "storyboard_frames", ["id"])
    op.create_index("ix_storyboard_frames_script_id", "storyboard_frames", ["script_id"])

    # Voice profiles
    op.create_table(
        "voice_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("engine", sa.String(50), nullable=True),
        sa.Column("voice_id", sa.String(100), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("rate", sa.Integer(), nullable=True),
        sa.Column("pitch", sa.Integer(), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("age_group", sa.String(20), nullable=True),
        sa.Column("tone", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_voice_profiles_id", "voice_profiles", ["id"])
    op.create_index("ix_voice_profiles_user_id", "voice_profiles", ["user_id"])
    op.create_index("ix_voice_profiles_is_deleted", "voice_profiles", ["is_deleted"])

    # Audio tracks
    op.create_table(
        "audio_tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("track_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("audio_url", sa.String(500), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("start_time", sa.Float(), nullable=True),
        sa.Column("end_time", sa.Float(), nullable=True),
        sa.Column("frame_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dialogue_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("voice_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("fade_in", sa.Float(), nullable=True),
        sa.Column("fade_out", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["frame_id"], ["storyboard_frames.id"]),
        sa.ForeignKeyConstraint(["dialogue_id"], ["dialogues.id"]),
        sa.ForeignKeyConstraint(["voice_profile_id"], ["voice_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audio_tracks_id", "audio_tracks", ["id"])
    op.create_index("ix_audio_tracks_project_id", "audio_tracks", ["project_id"])
    op.create_index("ix_audio_tracks_is_deleted", "audio_tracks", ["is_deleted"])

    # Render tasks
    op.create_table(
        "render_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("script_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("output_url", sa.String(500), nullable=True),
        sa.Column("output_size", sa.Integer(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("frame_count", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("credits_cost", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["script_id"], ["scripts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_render_tasks_id", "render_tasks", ["id"])
    op.create_index("ix_render_tasks_user_id", "render_tasks", ["user_id"])
    op.create_index("ix_render_tasks_project_id", "render_tasks", ["project_id"])

    # Workflows
    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("nodes", sa.JSON(), nullable=False),
        sa.Column("edges", sa.JSON(), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("is_template", sa.Boolean(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflows_id", "workflows", ["id"])
    op.create_index("ix_workflows_user_id", "workflows", ["user_id"])
    op.create_index("ix_workflows_is_deleted", "workflows", ["is_deleted"])

    # Workflow executions
    op.create_table(
        "workflow_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("inputs", sa.JSON(), nullable=True),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("node_executions", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_executions_id", "workflow_executions", ["id"])
    op.create_index("ix_workflow_executions_workflow_id", "workflow_executions", ["workflow_id"])

    # Subscriptions
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("payment_id", sa.String(200), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_id", "subscriptions", ["id"])
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    # Credit transactions
    op.create_table(
        "credit_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(50), nullable=True),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("related_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("related_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_transactions_id", "credit_transactions", ["id"])
    op.create_index("ix_credit_transactions_user_id", "credit_transactions", ["user_id"])

    # Audit logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    # Background tasks (Task 2)
    op.create_table(
        "background_tasks",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_background_tasks_user_id", "background_tasks", ["user_id"])
    op.create_index("ix_background_tasks_status", "background_tasks", ["status"])
    op.create_index("ix_background_tasks_task_type", "background_tasks", ["task_type"])


def downgrade() -> None:
    op.drop_index("ix_background_tasks_task_type", table_name="background_tasks")
    op.drop_index("ix_background_tasks_status", table_name="background_tasks")
    op.drop_index("ix_background_tasks_user_id", table_name="background_tasks")
    op.drop_table("background_tasks")

    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_credit_transactions_user_id", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_id", table_name="credit_transactions")
    op.drop_table("credit_transactions")

    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_workflow_executions_workflow_id", table_name="workflow_executions")
    op.drop_index("ix_workflow_executions_id", table_name="workflow_executions")
    op.drop_table("workflow_executions")

    op.drop_index("ix_workflows_is_deleted", table_name="workflows")
    op.drop_index("ix_workflows_user_id", table_name="workflows")
    op.drop_index("ix_workflows_id", table_name="workflows")
    op.drop_table("workflows")

    op.drop_index("ix_render_tasks_project_id", table_name="render_tasks")
    op.drop_index("ix_render_tasks_user_id", table_name="render_tasks")
    op.drop_index("ix_render_tasks_id", table_name="render_tasks")
    op.drop_table("render_tasks")

    op.drop_index("ix_audio_tracks_is_deleted", table_name="audio_tracks")
    op.drop_index("ix_audio_tracks_project_id", table_name="audio_tracks")
    op.drop_index("ix_audio_tracks_id", table_name="audio_tracks")
    op.drop_table("audio_tracks")

    op.drop_index("ix_voice_profiles_is_deleted", table_name="voice_profiles")
    op.drop_index("ix_voice_profiles_user_id", table_name="voice_profiles")
    op.drop_index("ix_voice_profiles_id", table_name="voice_profiles")
    op.drop_table("voice_profiles")

    op.drop_index("ix_storyboard_frames_script_id", table_name="storyboard_frames")
    op.drop_index("ix_storyboard_frames_id", table_name="storyboard_frames")
    op.drop_table("storyboard_frames")

    op.drop_index("ix_dialogues_scene_id", table_name="dialogues")
    op.drop_index("ix_dialogues_id", table_name="dialogues")
    op.drop_table("dialogues")

    op.drop_index("ix_script_scenes_script_id", table_name="script_scenes")
    op.drop_index("ix_script_scenes_id", table_name="script_scenes")
    op.drop_table("script_scenes")

    op.drop_index("ix_scripts_project_id", table_name="scripts")
    op.drop_index("ix_scripts_user_id", table_name="scripts")
    op.drop_index("ix_scripts_id", table_name="scripts")
    op.drop_table("scripts")

    op.drop_index("ix_characters_is_deleted", table_name="characters")
    op.drop_index("ix_characters_project_id", table_name="characters")
    op.drop_index("ix_characters_user_id", table_name="characters")
    op.drop_index("ix_characters_id", table_name="characters")
    op.drop_table("characters")

    op.drop_index("ix_projects_is_deleted", table_name="projects")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_index("ix_projects_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_users_is_deleted", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
