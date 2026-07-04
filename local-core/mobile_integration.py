"""
Y·NEX移动端集成 v2 - 全平台移动终端接入

功能：
  - 消息平台：微信公众平台 / 钉钉群机器人 / 飞书 / Telegram / 企业微信
  - 推送服务：Bark (iOS) / Server酱 / PushPlus / 企业微信机器人
  - 设备管理：手机设备注册、状态同步、心跳保活
  - 远程控制：手机遥控 PC（锁屏/关机/打开应用/截图/音量等）
  - 位置服务：手机位置上报、地理围栏触发自动化
  - 通知转发：PC 通知转发到手机
  - 文件传输：手机 ↔ PC 文件互传

配置方式（.env）：
  WECHAT_APPID / WECHAT_SECRET / WECHAT_TOKEN
  DINGTALK_ROBOT_TOKEN / DINGTALK_SECRET
  FEISHU_APP_ID / FEISHU_APP_SECRET
  TELEGRAM_BOT_TOKEN
  BARK_URL (iOS Bark 推送)
  SERVERCHAN_KEY (Server酱推送)
  PUSHPLUS_TOKEN (PushPlus推送)
  QYWX_WEBHOOK (企业微信机器人)
"""

import hashlib
import time
import json
import re
import os
import uuid
import base64
import threading
import requests
from typing import Callable, Optional, Dict, List, Any
from logger import logger


# =============================================================================
# 设备管理
# =============================================================================

_DEVICES_FILE = "data/mobile_devices.json"
_devices: Dict[str, Dict[str, Any]] = {}
_devices_lock = threading.Lock()


def _load_devices():
    """加载设备列表"""
    global _devices
    try:
        if os.path.exists(_DEVICES_FILE):
            with open(_DEVICES_FILE, "r", encoding="utf-8") as f:
                _devices = json.load(f)
    except Exception as e:
        logger.warning(f"加载设备列表失败: {e}")
        _devices = {}


def _save_devices():
    """保存设备列表"""
    try:
        os.makedirs(os.path.dirname(_DEVICES_FILE), exist_ok=True)
        with open(_DEVICES_FILE, "w", encoding="utf-8") as f:
            json.dump(_devices, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存设备列表失败: {e}")


def register_device(device_id: str, device_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    注册/更新移动设备
    device_id: 设备唯一标识
    device_info: {platform, name, model, os_version, app_version, push_token...}
    """
    with _devices_lock:
        if device_id in _devices:
            _devices[device_id].update(device_info)
            _devices[device_id]["last_seen"] = time.time()
            _devices[device_id]["status"] = "online"
        else:
            _devices[device_id] = {
                "id": device_id,
                "registered_at": time.time(),
                "last_seen": time.time(),
                "status": "online",
                "location": None,
                "battery": None,
                **device_info
            }
        _save_devices()
        return _devices[device_id]


def unregister_device(device_id: str) -> bool:
    """注销设备"""
    with _devices_lock:
        if device_id in _devices:
            del _devices[device_id]
            _save_devices()
            return True
        return False


def device_heartbeat(device_id: str, extra: Dict = None) -> Optional[Dict]:
    """设备心跳保活"""
    with _devices_lock:
        if device_id in _devices:
            _devices[device_id]["last_seen"] = time.time()
            _devices[device_id]["status"] = "online"
            if extra:
                _devices[device_id].update(extra)
            _save_devices()
            return _devices[device_id]
        return None


def get_device(device_id: str) -> Optional[Dict]:
    """获取设备信息"""
    return _devices.get(device_id)


def list_devices(platform: str = None) -> List[Dict]:
    """列出所有设备"""
    devices = list(_devices.values())
    if platform:
        devices = [d for d in devices if d.get("platform") == platform]
    return devices


def update_device_location(device_id: str, lat: float, lon: float, accuracy: float = None) -> Optional[Dict]:
    """更新设备位置"""
    with _devices_lock:
        if device_id in _devices:
            _devices[device_id]["location"] = {
                "lat": lat,
                "lon": lon,
                "accuracy": accuracy,
                "timestamp": time.time()
            }
            _save_devices()
            return _devices[device_id]
        return None


# =============================================================================
# 通用推送服务
# =============================================================================

def _get_push_config():
    """从环境变量获取推送配置"""
    from config import settings
    return {
        "bark_url": getattr(settings, "bark_url", "") or os.getenv("BARK_URL", ""),
        "serverchan_key": getattr(settings, "serverchan_key", "") or os.getenv("SERVERCHAN_KEY", ""),
        "pushplus_token": getattr(settings, "pushplus_token", "") or os.getenv("PUSHPLUS_TOKEN", ""),
        "qywx_webhook": getattr(settings, "qywx_webhook", "") or os.getenv("QYWX_WEBHOOK", ""),
    }


def push_notification(title: str, body: str, **kwargs) -> Dict[str, Any]:
    """
    统一推送通知（多通道同时发送）
    支持：Bark / Server酱 / PushPlus / 企业微信机器人 / 钉钉 / Telegram
    """
    results = {}
    config = _get_push_config()

    # Bark (iOS)
    if config["bark_url"]:
        try:
            url = config["bark_url"].rstrip("/")
            params = {}
            if kwargs.get("sound"):
                params["sound"] = kwargs["sound"]
            if kwargs.get("icon"):
                params["icon"] = kwargs["icon"]
            if kwargs.get("group"):
                params["group"] = kwargs["group"]
            if kwargs.get("url"):
                params["url"] = kwargs["url"]

            encoded_title = requests.utils.quote(title)
            encoded_body = requests.utils.quote(body)
            full_url = f"{url}/{encoded_title}/{encoded_body}"

            resp = requests.get(full_url, params=params, timeout=10)
            results["bark"] = {"ok": resp.status_code == 200, "status": resp.status_code}
        except Exception as e:
            results["bark"] = {"ok": False, "error": str(e)}

    # Server酱
    if config["serverchan_key"]:
        try:
            resp = requests.post(
                f"https://sctapi.ftqq.com/{config['serverchan_key']}.send",
                data={"title": title, "desp": body},
                timeout=10
            )
            results["serverchan"] = {"ok": resp.json().get("code") == 0, "data": resp.json()}
        except Exception as e:
            results["serverchan"] = {"ok": False, "error": str(e)}

    # PushPlus
    if config["pushplus_token"]:
        try:
            resp = requests.post(
                "https://www.pushplus.plus/send",
                json={
                    "token": config["pushplus_token"],
                    "title": title,
                    "content": body,
                    "template": kwargs.get("template", "txt")
                },
                timeout=10
            )
            results["pushplus"] = {"ok": resp.json().get("code") == 200, "data": resp.json()}
        except Exception as e:
            results["pushplus"] = {"ok": False, "error": str(e)}

    # 企业微信机器人
    if config["qywx_webhook"]:
        try:
            resp = requests.post(
                config["qywx_webhook"],
                json={"msgtype": "text", "text": {"content": f"【{title}】\n{body}"}},
                timeout=10
            )
            results["qywx"] = {"ok": resp.json().get("errcode") == 0, "data": resp.json()}
        except Exception as e:
            results["qywx"] = {"ok": False, "error": str(e)}

    # 钉钉机器人
    try:
        from mobile_integration import dingtalk_send_text
        ok = dingtalk_send_text(f"【{title}】{body}")
        if ok is not None:
            results["dingtalk"] = {"ok": ok}
    except Exception:
        pass

    logger.info(f"推送通知 '{title}' 结果: {results}")
    return results


# =============================================================================
# 手机远程控制 PC
# =============================================================================

def remote_pc_action(action: str, params: Dict = None) -> Dict[str, Any]:
    """
    手机远程控制 PC
    action: lock / shutdown / restart / sleep / screenshot / volume_up / volume_down / mute / open_app / type_text
    """
    params = params or {}
    result = {"action": action, "ok": False, "message": ""}

    try:
        if action == "lock":
            try:
                import ctypes
                ctypes.windll.user32.LockWorkStation()
                result["ok"] = True
                result["message"] = "电脑已锁定"
            except Exception as e:
                result["error"] = str(e)

        elif action == "shutdown":
            import subprocess
            subprocess.Popen(["shutdown", "/s", "/t", "60"])
            result["ok"] = True
            result["message"] = "电脑将在 60 秒后关机，可运行 shutdown /a 取消"

        elif action == "restart":
            import subprocess
            subprocess.Popen(["shutdown", "/r", "/t", "60"])
            result["ok"] = True
            result["message"] = "电脑将在 60 秒后重启"

        elif action == "sleep":
            try:
                import psutil
                import subprocess
                # Windows 休眠
                subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"])
                result["ok"] = True
                result["message"] = "电脑即将进入睡眠"
            except Exception as e:
                result["error"] = str(e)

        elif action == "screenshot":
            try:
                import pyautogui
                os.makedirs("data/screenshots", exist_ok=True)
                filename = f"data/screenshots/remote_{int(time.time())}.png"
                pyautogui.screenshot(filename)
                result["ok"] = True
                result["message"] = f"截图已保存: {filename}"
                result["file"] = filename
            except ImportError:
                result["error"] = "pyautogui 未安装"
            except Exception as e:
                result["error"] = str(e)

        elif action in ("volume_up", "volume_down", "volume_mute"):
            try:
                from pc_control import set_volume, get_volume
                if action == "volume_up":
                    current = get_volume()
                    set_volume(min(current + 10, 100))
                    result["ok"] = True
                    result["message"] = f"音量 +10，当前 {min(current + 10, 100)}%"
                elif action == "volume_down":
                    current = get_volume()
                    set_volume(max(current - 10, 0))
                    result["ok"] = True
                    result["message"] = f"音量 -10，当前 {max(current - 10, 0)}%"
                elif action == "volume_mute":
                    from pc_control import toggle_mute
                    muted = toggle_mute()
                    result["ok"] = True
                    result["message"] = "已静音" if muted else "已取消静音"
            except Exception as e:
                result["error"] = str(e)

        elif action == "open_app":
            app = params.get("app", "")
            if not app:
                result["error"] = "缺少 app 参数"
            else:
                try:
                    import subprocess
                    subprocess.Popen([app], shell=False)
                    result["ok"] = True
                    result["message"] = f"已启动: {app}"
                except Exception as e:
                    result["error"] = str(e)

        elif action == "type_text":
            text = params.get("text", "")
            if not text:
                result["error"] = "缺少 text 参数"
            else:
                try:
                    import pyautogui
                    pyautogui.typewrite(text)
                    result["ok"] = True
                    result["message"] = f"已输入: {text}"
                except ImportError:
                    result["error"] = "pyautogui 未安装"
                except Exception as e:
                    result["error"] = str(e)

        else:
            result["error"] = f"未知操作: {action}"

    except Exception as e:
        result["error"] = f"执行失败: {e}"

    if result.get("ok"):
        logger.info(f"远程控制 {action} 成功: {result.get('message')}")
    else:
        logger.warning(f"远程控制 {action} 失败: {result.get('error')}")

    return result


# =============================================================================
# 通知转发（PC → 手机）
# =============================================================================

_notification_history: List[Dict] = []
_max_history = 100


def forward_notification(title: str, body: str, priority: str = "normal") -> Dict[str, Any]:
    """
    将 PC 端通知转发到手机
    priority: low / normal / high
    """
    notif = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "body": body,
        "priority": priority,
        "timestamp": time.time()
    }

    _notification_history.append(notif)
    if len(_notification_history) > _max_history:
        _notification_history.pop(0)

    # 高优先级立即推送
    if priority == "high":
        push_notification(title, body, sound="alarm")
    else:
        push_notification(title, body)

    return notif


def get_notification_history(limit: int = 20) -> List[Dict]:
    """获取通知历史"""
    return _notification_history[-limit:]


# =============================================================================
# 文件传输
# =============================================================================

_TRANSFER_DIR = "data/file_transfer"


def upload_file(filename: str, data: bytes, device_id: str = None) -> Dict[str, Any]:
    """手机上传文件到 PC"""
    try:
        os.makedirs(_TRANSFER_DIR, exist_ok=True)
        # 安全处理文件名
        safe_name = os.path.basename(filename)
        filepath = os.path.join(_TRANSFER_DIR, safe_name)

        # 如果文件已存在，加时间戳
        if os.path.exists(filepath):
            name, ext = os.path.splitext(safe_name)
            filepath = os.path.join(_TRANSFER_DIR, f"{name}_{int(time.time())}{ext}")

        with open(filepath, "wb") as f:
            f.write(data)

        logger.info(f"文件上传成功: {filepath} ({len(data)} bytes)")
        return {
            "ok": True,
            "filename": os.path.basename(filepath),
            "size": len(data),
            "path": filepath
        }
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        return {"ok": False, "error": str(e)}


def list_transfer_files() -> List[Dict]:
    """列出传输目录中的文件"""
    try:
        os.makedirs(_TRANSFER_DIR, exist_ok=True)
        files = []
        for f in os.listdir(_TRANSFER_DIR):
            fp = os.path.join(_TRANSFER_DIR, f)
            if os.path.isfile(fp):
                stat = os.stat(fp)
                files.append({
                    "name": f,
                    "size": stat.st_size,
                    "modified": stat.st_mtime
                })
        files.sort(key=lambda x: x["modified"], reverse=True)
        return files
    except Exception as e:
        logger.error(f"列出文件失败: {e}")
        return []


def get_transfer_file(filename: str) -> Optional[bytes]:
    """获取传输的文件内容"""
    try:
        safe_name = os.path.basename(filename)
        filepath = os.path.join(_TRANSFER_DIR, safe_name)
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                return f.read()
        return None
    except Exception:
        return None


# =============================================================================
# 地理围栏与位置触发
# =============================================================================

_geofences: List[Dict] = []


def add_geofence(name: str, lat: float, lon: float, radius: float,
                 enter_action: str = None, exit_action: str = None) -> Dict:
    """添加地理围栏"""
    fence = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "lat": lat,
        "lon": lon,
        "radius": radius,
        "enter_action": enter_action,
        "exit_action": exit_action,
        "inside": {}
    }
    _geofences.append(fence)
    logger.info(f"添加地理围栏: {name} ({lat}, {lon}, r={radius}m)")
    return fence


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """计算两点间距离（米）"""
    import math
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def check_geofences(device_id: str, lat: float, lon: float) -> List[Dict]:
    """检查设备位置触发的地理围栏事件"""
    events = []
    for fence in _geofences:
        distance = _haversine(lat, lon, fence["lat"], fence["lon"])
        was_inside = fence["inside"].get(device_id, False)
        is_inside = distance <= fence["radius"]

        if is_inside and not was_inside:
            fence["inside"][device_id] = True
            events.append({"type": "enter", "fence": fence["name"], "distance": distance})
            if fence.get("enter_action"):
                logger.info(f"设备 {device_id} 进入围栏 {fence['name']}，触发: {fence['enter_action']}")

        elif not is_inside and was_inside:
            fence["inside"][device_id] = False
            events.append({"type": "exit", "fence": fence["name"], "distance": distance})
            if fence.get("exit_action"):
                logger.info(f"设备 {device_id} 离开围栏 {fence['name']}，触发: {fence['exit_action']}")

    return events


# =============================================================================
# 初始化
# =============================================================================

_load_devices()


# =============================================================================
# 微信公众平台
# =============================================================================

WECHAT_TOKEN = ""  # 微信公众平台设置的 Token
WECHAT_APPID = ""
WECHAT_APPSECRET = ""
_wechat_access_token = {"token": "", "expires_at": 0}
_wechat_api = "https://api.weixin.qq.com"


def _get_wechat_token() -> str:
    """获取微信 access_token（带缓存）"""
    global _wechat_access_token
    if _wechat_access_token["token"] and _wechat_access_token["expires_at"] > time.time() + 60:
        return _wechat_access_token["token"]

    url = f"{_wechat_api}/cgi-bin/token"
    params = {"grant_type": "client_credential", "appid": WECHAT_APPID, "secret": WECHAT_APPSECRET}
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()

    if "access_token" in data:
        _wechat_access_token["token"] = data["access_token"]
        _wechat_access_token["expires_at"] = time.time() + data.get("expires_in", 7200)
        return data["access_token"]
    raise RuntimeError(f"WeChat token failed: {data}")


def wechat_verify_url(token: str, signature: str, timestamp: str, nonce: str) -> bool:
    """验证微信签名（用于 URL 验证）"""
    arr = sorted([token, timestamp, nonce])
    arr_str = "".join(arr)
    return hashlib.sha1(arr_str.encode()).hexdigest() == signature


def wechat_handle_xml(body: str, ai_handler: Callable[[str], str]) -> str:
    """
    处理微信 XML 消息格式。
    body: POST 请求体（XML）
    ai_handler: 处理用户消息并返回回复的函数
    返回 XML 回复体。
    """
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(body)
        msg_type = root.find("MsgType").text
        from_user = root.find("FromUserName").text
        to_user = root.find("ToUserName").text
        content = root.find("Content").text if root.find("Content") is not None else ""

        if msg_type == "text":
            reply = ai_handler(content)
            return _wechat_text_reply(from_user, to_user, reply)
        elif msg_type == "image":
            pic_url = root.find("PicUrl").text
            reply = ai_handler(f"[用户发送了图片: {pic_url}]")
            return _wechat_text_reply(from_user, to_user, reply)
        elif msg_type == "event":
            event = root.find("Event").text
            if event == "subscribe":
                return _wechat_text_reply(from_user, to_user, "欢迎使用Y·NEX AI！有什么可以帮您的？")
            return ""
        else:
            return ""
    except Exception as e:
        logger.error(f"WeChat XML 处理失败: {e}")
        return ""


def _wechat_text_reply(to_user: str, from_user: str, content: str) -> str:
    """构造微信文本回复 XML"""
    return f"""
<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""


def _wechat_news_reply(to_user: str, from_user: str, articles: list) -> str:
    """构造微信图文回复 XML"""
    item_xml = ""
    for a in articles[:8]:
        item_xml += f"""
<item>
<Title><![CDATA[{a.get('title','')}]]></Title>
<Description><![CDATA[{a.get('description','')}]]></Description>
<PicUrl><![CDATA[{a.get('picurl','')}]]></PicUrl>
<Url><![CDATA[{a.get('url','')}]]></Url>
</item>"""
    return f"""
<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[news]]></MsgType>
<ArticleCount>{len(articles[:8])}</ArticleCount>
<Articles>{item_xml}</Articles>
</xml>"""


def wechat_send_message(openid: str, content: str) -> bool:
    """主动向用户发送消息（模板消息/客服消息）"""
    try:
        token = _get_wechat_token()
        url = f"{_wechat_api}/cgi-bin/message/custom/send?access_token={token}"
        payload = {
            "touser": openid,
            "msgtype": "text",
            "text": {"content": content}
        }
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json().get("errcode", 0) == 0
    except Exception as e:
        logger.error(f"WeChat 发送消息失败: {e}")
        return False


# =============================================================================
# 钉钉群机器人
# =============================================================================

DINGTALK_ROBOT_TOKEN = ""
DINGTALK_SECRET = ""


def _get_dingtalk_sign() -> tuple[str, int]:
    """获取钉钉签名（用于加签机器人）"""
    if not DINGTALK_SECRET:
        return "", 0
    import base64, hmac, hashlib, time as _time
    timestamp = str(int(_time.time() * 1000))
    sign_str = f"{timestamp}\n{DINGTALK_SECRET}"
    sign = base64.b64encode(hmac.new(
        DINGTALK_SECRET.encode(), sign_str.encode(), hashlib.sha256
    ).digest()).decode()
    return sign, int(timestamp)


def dingtalk_send_text(content: str, at_mobiles: list = None) -> bool:
    """通过钉钉机器人发送文本消息到群"""
    if not DINGTALK_ROBOT_TOKEN:
        logger.warning("钉钉机器人未配置")
        return False

    url = f"https://oapi.dingtalk.com/robot/send?access_token={DINGTALK_ROBOT_TOKEN}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "msgtype": "text",
        "text": {"content": f"Y·NEX：{content}"},
        "at": {"atMobiles": at_mobiles or []}
    }

    # 如果配置了加签
    if DINGTALK_SECRET:
        sign, timestamp = _get_dingtalk_sign()
        url += f"&timestamp={timestamp}&sign={sign}"

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            return True
        logger.error(f"钉钉发送失败: {result}")
        return False
    except Exception as e:
        logger.error(f"钉钉请求异常: {e}")
        return False


def dingtalk_send_link(title: str, text: str, pic_url: str, message_url: str) -> bool:
    """发送 Link 类型消息"""
    if not DINGTALK_ROBOT_TOKEN:
        return False

    url = f"https://oapi.dingtalk.com/robot/send?access_token={DINGTALK_ROBOT_TOKEN}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "msgtype": "link",
        "link": {
            "title": title,
            "text": text,
            "picUrl": pic_url,
            "messageUrl": message_url
        }
    }

    if DINGTALK_SECRET:
        sign, timestamp = _get_dingtalk_sign()
        url += f"&timestamp={timestamp}&sign={sign}"

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        return resp.json().get("errcode") == 0
    except Exception as e:
        logger.error(f"钉钉 Link 消息失败: {e}")
        return False


def dingtalk_send_card(title: str, text: str, btns: list = None) -> bool:
    """发送 FeedCard / ActionCard 消息"""
    if not DINGTALK_ROBOT_TOKEN:
        return False

    url = f"https://oapi.dingtalk.com/robot/send?access_token={DINGTALK_ROBOT_TOKEN}"
    headers = {"Content-Type": "application/json"}

    if not btns:
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": f"### {title}\n{text}"}
        }
    else:
        btn_str = "\n".join([f"- [{b['title']}]({b['actionURL']})" for b in btns])
        payload = {
            "msgtype": "actionCard",
            "actionCard": {
                "title": title,
                "text": text,
                "btnOrientation": "0",
                "btns": btns
            }
        }

    if DINGTALK_SECRET:
        sign, timestamp = _get_dingtalk_sign()
        url += f"&timestamp={timestamp}&sign={sign}"

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        return resp.json().get("errcode") == 0
    except Exception as e:
        logger.error(f"钉钉卡片消息失败: {e}")
        return False


# =============================================================================
# 飞书
# =============================================================================

FEISHU_APP_ID = ""
FEISHU_APP_SECRET = ""
_feishubot_token = {"token": "", "expires_at": 0}


def _get_feishu_token() -> str:
    """获取飞书 tenant_access_token"""
    global _feishubot_token
    if _feishubot_token["token"] and _feishubot_token["expires_at"] > time.time() + 60:
        return _feishubot_token["token"]

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    resp = requests.post(url, json=payload, timeout=10)
    data = resp.json()

    if data.get("code") == 0:
        _feishubot_token["token"] = data["tenant_access_token"]
        _feishubot_token["expires_at"] = time.time() + data.get("expire", 7200)
        return data["tenant_access_token"]
    raise RuntimeError(f"Feishu token failed: {data}")


def feishu_send_message(open_id: str, msg_type: str, content: dict) -> bool:
    """向用户发送消息"""
    try:
        token = _get_feishu_token()
        url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "receive_id": open_id,
            "msg_type": msg_type,
            "content": json.dumps(content)
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        return resp.json().get("code") == 0
    except Exception as e:
        logger.error(f"飞书发送消息失败: {e}")
        return False


def feishu_reply_message(message_id: str, msg_type: str, content: dict) -> bool:
    """回复消息（用 message_id 回复）"""
    try:
        token = _get_feishu_token()
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "msg_type": msg_type,
            "content": json.dumps(content)
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        return resp.json().get("code") == 0
    except Exception as e:
        logger.error(f"飞书回复消息失败: {e}")
        return False


def feishu_handle_event(event_data: dict, ai_handler: Callable[[str], str]) -> dict:
    """
    处理飞书 events API 事件。
    返回要发送给用户的回复内容 dict。
    """
    try:
        event_type = event_data.get("header", {}).get("event_type", "")

        if event_type == "im.message.receive_v1":
            message = event_data.get("event", {}).get("message", {})
            if message.get("msg_type") == "text":
                content = json.loads(message.get("content", "{}"))
                text = content.get("text", "")
                reply_text = ai_handler(text)
                return {"msg_type": "text", "content": json.dumps({"text": reply_text})}

        return {}
    except Exception as e:
        logger.error(f"飞书事件处理失败: {e}")
        return {}


def feishu_create_card(text: str, btns: list = None) -> dict:
    """创建 Interactive Card payload"""
    card = {
        "config": {"wide_screen_mode": True},
        "elements": [
            {"tag": "markdown", "content": text},
            {"tag": "hr"}
        ],
        "header": {"title": {"tag": "plain_text", "content": "Y·NEX AI"}, "template": "blue"}
    }
    if btns:
        card["elements"].append({
            "tag": "action",
            "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": b["title"]},
                 "type": "primary", "action_id": b.get("action_id", b["title"]),
                 "value": b.get("value", {})}
                for b in btns
            ]
        })
    return card


# =============================================================================
# 统一消息发送接口
# =============================================================================

def send_to_user(platform: str, user_id: str, message: str, **kwargs) -> bool:
    """
    跨平台统一发送接口。
    platform: wechat / dingtalk / feishu
    user_id: 平台用户标识
    message: 消息文本
    """
    if platform == "wechat":
        return wechat_send_message(user_id, message)
    elif platform == "dingtalk":
        return dingtalk_send_text(message, kwargs.get("at_mobiles"))
    elif platform == "feishu":
        return feishu_send_message(user_id, "text", {"text": message})
    return False


# =============================================================================
# 多设备同步
# =============================================================================

_sync_state = {}


def sync_state_to_device(device: str, key: str, value):
    """
    同步状态到指定设备（通过 MQTT 或平台推送）。
    例如：手机发送"打开客厅灯" → 同步到 PC 端显示状态变化。
    """
    _sync_state[device] = {key: value, "ts": time.time()}
    try:
        from mqtt_bus import mqtt_client
        if mqtt_client:
            mqtt_client.publish(
                f"ynex/sync/{device}",
                json.dumps({"key": key, "value": value, "ts": time.time()})
            )
    except Exception:
        pass
    return True


def get_synced_state(device: str = None) -> dict:
    """获取同步状态"""
    if device:
        return _sync_state.get(device, {})
    return _sync_state
