"""
Home Assistant 智能家居控制
通过 REST API 查询设备状态、执行开关/调光/温控等操作
"""

import requests
from typing import Optional

from config import settings
from logger import logger


def _get_headers():
    """构造 HA 请求头"""
    return {
        "Authorization": f"Bearer {settings.home_assistant_token}",
        "Content-Type": "application/json"
    }


def _ha_enabled() -> bool:
    """检查是否已配置 Home Assistant"""
    return bool(settings.home_assistant_url and settings.home_assistant_token)


def list_entities(domain: Optional[str] = None) -> str:
    """列出 Home Assistant 中的设备实体"""
    if not _ha_enabled():
        return "先生，未配置 Home Assistant。请在 .env 中设置 HOME_ASSISTANT_URL 和 HOME_ASSISTANT_TOKEN。"

    try:
        url = f"{settings.home_assistant_url}/api/states"
        resp = requests.get(url, headers=_get_headers(), timeout=10)
        resp.raise_for_status()
        entities = resp.json()

        if domain:
            entities = [e for e in entities if e["entity_id"].startswith(f"{domain}.")]

        lines = []
        for e in entities[:20]:
            entity_id = e["entity_id"]
            friendly = e["attributes"].get("friendly_name", entity_id)
            state = e["state"]
            lines.append(f"{friendly} ({entity_id}): {state}")

        if not lines:
            return f"先生，未找到 {domain or ''} 设备。"
        return "先生，智能家居设备：\n" + "\n".join(lines)
    except Exception as e:
        logger.error(f"Home Assistant 查询失败：{e}")
        return f"先生，无法连接到 Home Assistant：{e}"


def control_device(entity_id: str, action: str, **kwargs) -> str:
    """
    控制 Home Assistant 设备
    entity_id: 如 light.living_room
    action: on / off / toggle / brightness / temperature / open / close / stop / activate
    """
    if not _ha_enabled():
        return "先生，未配置 Home Assistant。"

    try:
        domain = entity_id.split(".")[0]

        # 场景特殊处理
        if domain == "scene" or action == "activate":
            return activate_scene(entity_id)

        service = _map_action_to_service(domain, action)
        if not service:
            return f"先生，不支持对 {domain} 执行 {action} 操作。"

        service_domain, service_name = service.split(".")
        url = f"{settings.home_assistant_url}/api/services/{service_domain}/{service_name}"
        payload = {"entity_id": entity_id}

        # 附加参数
        if action == "brightness" and "value" in kwargs:
            payload["brightness"] = int(kwargs["value"])
        if action == "temperature" and "value" in kwargs:
            payload["temperature"] = float(kwargs["value"])
        if action == "color" and "value" in kwargs:
            payload["color_name"] = kwargs["value"]

        resp = requests.post(url, headers=_get_headers(), json=payload, timeout=10)
        resp.raise_for_status()

        friendly = entity_id
        try:
            states_url = f"{settings.home_assistant_url}/api/states/{entity_id}"
            state_resp = requests.get(states_url, headers=_get_headers(), timeout=10)
            if state_resp.status_code == 200:
                friendly = state_resp.json()["attributes"].get("friendly_name", entity_id)
        except Exception:
            pass

        logger.info(f"HA 控制成功：{entity_id} -> {action}")
        return f"先生，已执行 {action}，{friendly}。"
    except Exception as e:
        logger.error(f"Home Assistant 控制失败：{e}")
        return f"先生，控制设备失败：{e}"


def get_entity_state(entity_id: str) -> str:
    """获取指定实体的当前状态"""
    if not _ha_enabled():
        return "先生，未配置 Home Assistant。"

    try:
        url = f"{settings.home_assistant_url}/api/states/{entity_id}"
        resp = requests.get(url, headers=_get_headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        friendly = data["attributes"].get("friendly_name", entity_id)
        return f"先生，{friendly}（{entity_id}）当前状态：{data['state']}。"
    except Exception as e:
        return f"先生，读取状态失败：{e}"


def list_scenes() -> str:
    """列出 Home Assistant 场景"""
    if not _ha_enabled():
        return "先生，未配置 Home Assistant。"

    try:
        url = f"{settings.home_assistant_url}/api/states"
        resp = requests.get(url, headers=_get_headers(), timeout=10)
        resp.raise_for_status()
        scenes = [e for e in resp.json() if e["entity_id"].startswith("scene.")]
        if not scenes:
            return "先生，没有配置场景。"
        lines = [f"{e['attributes'].get('friendly_name', e['entity_id'])} ({e['entity_id']})" for e in scenes[:20]]
        return "先生，可用场景：\n" + "\n".join(lines)
    except Exception as e:
        return f"先生，读取场景失败：{e}"


def activate_scene(scene_id: str) -> str:
    """激活场景"""
    if not _ha_enabled():
        return "先生，未配置 Home Assistant。"

    try:
        if not scene_id.startswith("scene."):
            scene_id = f"scene.{scene_id}"
        url = f"{settings.home_assistant_url}/api/services/scene/turn_on"
        resp = requests.post(url, headers=_get_headers(), json={"entity_id": scene_id}, timeout=10)
        resp.raise_for_status()
        return f"先生，已激活场景 {scene_id}。"
    except Exception as e:
        return f"先生，激活场景失败：{e}"


def list_areas() -> str:
    """列出 Home Assistant 区域（需要 HA 提供区域 API）"""
    if not _ha_enabled():
        return "先生，未配置 Home Assistant。"

    try:
        url = f"{settings.home_assistant_url}/api/config/area_registry/list"
        resp = requests.post(url, headers=_get_headers(), timeout=10)
        resp.raise_for_status()
        areas = resp.json()
        if not areas:
            return "先生，没有配置区域。"
        lines = [f"- {a.get('name', a.get('area_id', '未知'))}" for a in areas]
        return "先生，家庭区域：\n" + "\n".join(lines)
    except Exception as e:
        return f"先生，读取区域失败：{e}"


def get_sensor_value(sensor_id: str) -> str:
    """读取传感器数值"""
    if not _ha_enabled():
        return "先生，未配置 Home Assistant。"

    try:
        if not "." in sensor_id:
            sensor_id = f"sensor.{sensor_id}"
        return get_entity_state(sensor_id)
    except Exception as e:
        return f"先生，读取传感器失败：{e}"


def _map_action_to_service(domain: str, action: str) -> Optional[str]:
    """将自然语言动作映射到 HA service"""
    action = action.lower().strip()

    # 通用开关
    if action in ("on", "off", "toggle"):
        if domain in ("light", "switch", "fan", "climate"):
            return f"{domain}.turn_{action}"

    # 亮度
    if action == "brightness" and domain == "light":
        return "light.turn_on"

    # 温度
    if action == "temperature" and domain == "climate":
        return "climate.set_temperature"

    # 窗帘/门
    if domain == "cover":
        if action in ("open", "close", "stop"):
            return f"cover.{action}"

    # 媒体播放器
    if domain == "media_player":
        if action in ("play", "pause", "stop", "volume_up", "volume_down"):
            return f"media_player.media_{action}"

    return None


# 为 skills.py 提供统一接口
SKILL_MAP = {
    "list_ha_entities": list_entities,
    "control_ha_device": control_device,
}
