"""模型测试 - 验证表结构与关系"""
import pytest
from sqlalchemy import inspect
from app.models import (
    Base, User, Project, Character, Script, Scene, Dialogue,
    StoryboardFrame, VoiceProfile, AudioTrack, RenderTask,
    Workflow, WorkflowExecution, Subscription, CreditTransaction,
)


def test_all_models_registered():
    """测试所有模型已注册到 Base.metadata"""
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users", "projects", "characters", "scripts", "script_scenes",
        "dialogues", "storyboard_frames", "voice_profiles", "audio_tracks",
        "render_tasks", "workflows", "workflow_executions",
        "subscriptions", "credit_transactions",
    }
    assert expected.issubset(table_names), f"缺少表: {expected - table_names}"


def test_user_model_columns():
    """测试 User 模型字段"""
    mapper = inspect(User)
    column_names = {c.key for c in mapper.columns}
    required = {"id", "username", "email", "password_hash", "status", "plan", "credits"}
    assert required.issubset(column_names)


def test_project_user_relationship():
    """测试 Project.user_id 外键指向 users.id"""
    fk = Project.__table__.c.user_id.foreign_keys
    assert len(fk) == 1
    assert fk.pop().column.table.name == "users"


def test_character_project_relationship():
    """测试 Character.project_id 外键指向 projects.id"""
    fk = Character.__table__.c.project_id.foreign_keys
    assert len(fk) == 1
    assert fk.pop().column.table.name == "projects"
