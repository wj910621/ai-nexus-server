# backend/tests/test_workflow_templates.py
"""测试工作流模板系统"""
import pytest
from app.engines.workflow.template_manager import (
    TemplateManager, WorkflowTemplate, BUILTIN_TEMPLATES, template_manager,
)


def test_builtin_templates_loaded():
    """测试内置模板加载"""
    manager = TemplateManager()
    assert len(manager.templates) >= 5
    assert "basic_text_to_image" in manager.templates


def test_list_templates_all():
    """测试列出所有模板"""
    manager = TemplateManager()
    templates = manager.list_templates()
    assert len(templates) >= 5


def test_list_templates_by_category():
    """测试按分类列出模板"""
    manager = TemplateManager()
    basic = manager.list_templates(category="basic")
    assert all(t.category == "basic" for t in basic)
    assert len(basic) >= 2


def test_list_templates_exclude_premium():
    """测试排除高级模板"""
    manager = TemplateManager()
    free = manager.list_templates(include_premium=False)
    assert all(not t.is_premium for t in free)


def test_list_templates_by_tag():
    """测试按标签筛选"""
    manager = TemplateManager()
    tagged = manager.list_templates(tag="图像")
    assert all("图像" in t.tags for t in tagged)


def test_get_template():
    """测试获取模板"""
    manager = TemplateManager()
    t = manager.get_template("basic_text_to_image")
    assert t is not None
    assert t.name == "基础文生图"


def test_get_template_not_found():
    """测试获取不存在的模板"""
    manager = TemplateManager()
    assert manager.get_template("nonexistent") is None


def test_apply_template():
    """测试应用模板"""
    manager = TemplateManager()
    workflow = manager.apply_template("basic_text_to_image")
    assert "nodes" in workflow
    assert "edges" in workflow
    assert len(workflow["nodes"]) == 3


def test_apply_template_with_customization():
    """测试带定制的应用"""
    manager = TemplateManager()
    workflow = manager.apply_template("basic_text_to_image", customizations={
        "node_params": {
            "gen": {"width": 512, "height": 512}
        }
    })
    gen_node = next(n for n in workflow["nodes"] if n["id"] == "gen")
    assert gen_node["params"]["width"] == 512
    assert gen_node["params"]["height"] == 512


def test_apply_template_not_found():
    """测试应用不存在的模板"""
    manager = TemplateManager()
    with pytest.raises(ValueError, match="不存在"):
        manager.apply_template("nonexistent")


def test_apply_template_deep_copy():
    """测试应用模板返回深拷贝"""
    manager = TemplateManager()
    w1 = manager.apply_template("basic_text_to_image")
    w2 = manager.apply_template("basic_text_to_image")
    w1["nodes"][0]["params"]["value"] = "modified"
    # 修改 w1 不应影响 w2
    assert w2["nodes"][0]["params"]["value"] != "modified"


def test_add_custom_template():
    """测试添加自定义模板"""
    manager = TemplateManager()
    custom = WorkflowTemplate(
        template_id="custom",
        name="自定义",
        description="test",
        workflow_data={"nodes": [], "edges": []}
    )
    manager.add_template(custom)
    assert manager.get_template("custom") is not None


def test_list_categories():
    """测试列出分类"""
    manager = TemplateManager()
    categories = manager.list_categories()
    assert "basic" in categories
    assert "advanced" in categories


def test_template_to_dict():
    """测试模板转字典"""
    t = WorkflowTemplate(
        template_id="test", name="Test", description="desc",
        category="basic", workflow_data={"nodes": [], "edges": []}
    )
    d = t.to_dict()
    assert d["template_id"] == "test"
    assert d["name"] == "Test"
    assert d["category"] == "basic"


def test_global_template_manager():
    """测试全局模板管理器单例"""
    assert template_manager is not None
    assert len(template_manager.templates) >= 5
