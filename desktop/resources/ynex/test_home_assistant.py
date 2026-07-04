"""
Home Assistant 集成测试
未配置 HA 时验证优雅降级
"""

from home_assistant import (
    list_entities, control_device, list_scenes, activate_scene,
    list_areas, get_sensor_value, get_entity_state
)


def test_without_config():
    """未配置 HA 时应返回友好提示"""
    print("\n=== 未配置 Home Assistant ===")
    result = list_entities()
    print(result)
    assert "未配置" in result
    print("✅ 降级提示正常")


def test_control_without_config():
    print("\n=== 控制设备（未配置）===")
    result = control_device("light.living_room", "on")
    print(result)
    assert "未配置" in result
    print("✅ 控制降级正常")


def test_scene_without_config():
    print("\n=== 场景列表（未配置）===")
    result = list_scenes()
    print(result)
    assert "未配置" in result
    print("✅ 场景降级正常")


def test_activate_scene_without_config():
    print("\n=== 激活场景（未配置）===")
    result = activate_scene("movie_mode")
    print(result)
    assert "未配置" in result
    print("✅ 场景激活降级正常")


def test_areas_without_config():
    print("\n=== 区域列表（未配置）===")
    result = list_areas()
    print(result)
    assert "未配置" in result
    print("✅ 区域降级正常")


def test_sensor_without_config():
    print("\n=== 传感器读取（未配置）===")
    result = get_sensor_value("living_room_temperature")
    print(result)
    assert "未配置" in result
    print("✅ 传感器降级正常")


def test_entity_state_without_config():
    print("\n=== 实体状态（未配置）===")
    result = get_entity_state("light.living_room")
    print(result)
    assert "未配置" in result
    print("✅ 实体状态降级正常")


def main():
    print("=== Home Assistant 集成测试 ===")
    test_without_config()
    test_control_without_config()
    test_scene_without_config()
    test_activate_scene_without_config()
    test_areas_without_config()
    test_sensor_without_config()
    test_entity_state_without_config()
    print("\n全部测试完成")
    print("提示：配置 HOME_ASSISTANT_URL 和 TOKEN 后，可连接真实设备测试。")


if __name__ == "__main__":
    main()
