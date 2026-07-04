"""
Y·NEX插件市场 v2 - 插件系统
让开发者编写并分享技能插件，扩展Y·NEX能力。

插件结构：
  plugins/
    my_plugin/
       __init__.py       # 插件入口，必须有 register() 函数
       plugin.json       # 插件元信息
       skills.py         # 可选，技能函数
       config.py         # 可选，插件配置

v2 新功能：
  - 远程插件安装（从 URL/插件市场下载）
  - 插件热加载/热卸载
  - 插件配置持久化存储
  - 事件总线（插件间通信）
  - 插件依赖自动安装
  - 插件权限控制
"""

import os
import sys
import importlib
import importlib.util
import json
import threading
import zipfile
import shutil
import hashlib
import hmac
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from logger import logger


# =============================================================================
# 插件安全沙箱
# =============================================================================

# 插件默认允许导入的白名单模块
_PLUGIN_ALLOWED_MODULES = {
    "json", "re", "math", "random", "datetime", "collections", "itertools",
    "typing", "pathlib", "os", "sys", "time", "hashlib", "base64", "urllib",
    "requests",  # 远程插件可能需要的网络请求
}

# 插件禁止使用的危险内置函数
_PLUGIN_FORBIDDEN_BUILTINS = {"eval", "exec", "compile", "open", "input"}


class PluginSandbox:
    """
    插件执行沙箱。
    通过限制模块导入白名单，降低恶意插件的风险。
    """

    def __init__(self, allowed_modules: set = None):
        self.allowed_modules = allowed_modules or _PLUGIN_ALLOWED_MODULES
        import builtins
        self._original_import = builtins.__import__

    def _safe_import(self, name: str, *args, **kwargs):
        base = name.split(".")[0]
        if base not in self.allowed_modules:
            raise ImportError(f"插件禁止导入模块: {name}")
        return self._original_import(name, *args, **kwargs)

    def run(self, func: Callable, *args, **kwargs):
        """在沙箱环境中执行函数（仅限制导入）"""
        import builtins
        try:
            builtins.__import__ = self._safe_import
            return func(*args, **kwargs)
        finally:
            builtins.__import__ = self._original_import


# =============================================================================
# 插件签名验证
# =============================================================================

class PluginSignatureVerifier:
    """
    插件签名验证器。
    使用 HMAC-SHA256 验证 plugin.json 的完整性。
    签名应放在 plugin.json 的 `signature` 字段，为 hex 字符串。
    """

    def __init__(self, secret: str = None):
        self.secret = (secret or os.getenv("YNEX_PLUGIN_SECRET", "")).encode("utf-8")

    def sign(self, plugin_dir: str) -> str:
        """为插件目录生成签名（仅用于开发者发布）"""
        manifest_path = os.path.join(plugin_dir, "plugin.json")
        if not os.path.exists(manifest_path):
            raise FileNotFoundError("plugin.json 不存在")
        with open(manifest_path, "rb") as f:
            data = f.read()
        return hmac.new(self.secret, data, hashlib.sha256).hexdigest()

    def verify(self, plugin_dir: str) -> bool:
        """
        验证插件签名。

        安全策略：
          - 已配置签名密钥：必须提供有效签名，否则拒绝；
          - 未配置签名密钥：仅放行"内置插件目录"（与本文件同级的 plugins/），
            第三方/外部插件目录一律拒绝，防止未配置密钥时加载任意代码。
        """
        # 内置插件目录（本文件同级 plugins/）
        builtin_plugins_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "plugins")
        )
        abs_plugin_dir = os.path.abspath(plugin_dir)

        if not self.secret:
            # 未配置密钥：仅允许内置插件目录
            if abs_plugin_dir.startswith(builtin_plugins_dir + os.sep) or abs_plugin_dir == builtin_plugins_dir:
                return True
            logger.warning(
                f"拒绝加载第三方插件 {plugin_dir}：未配置签名密钥（YNEX_PLUGIN_SECRET），"
                f"仅允许内置插件目录 {builtin_plugins_dir}"
            )
            return False

        manifest_path = os.path.join(plugin_dir, "plugin.json")
        if not os.path.exists(manifest_path):
            return False

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            expected_sig = meta.get("signature", "")
            if not expected_sig:
                logger.warning(f"插件 {plugin_dir} 未提供签名")
                return False

            actual_sig = self.sign(plugin_dir)
            return hmac.compare_digest(actual_sig, expected_sig)
        except Exception as e:
            logger.error(f"验证插件签名失败: {e}")
            return False



# =============================================================================
# 事件总线
# =============================================================================

class EventBus:
    """插件间事件总线"""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    def on(self, event: str, callback: Callable):
        """注册事件监听器"""
        with self._lock:
            if event not in self._listeners:
                self._listeners[event] = []
            self._listeners[event].append(callback)

    def off(self, event: str, callback: Callable):
        """移除事件监听器"""
        with self._lock:
            if event in self._listeners:
                self._listeners[event] = [
                    c for c in self._listeners[event] if c != callback
                ]

    def emit(self, event: str, *args, **kwargs):
        """触发事件"""
        listeners = []
        with self._lock:
            if event in self._listeners:
                listeners = list(self._listeners[event])
        for cb in listeners:
            try:
                cb(*args, **kwargs)
            except Exception as e:
                logger.error(f"事件 {event} 处理器异常: {e}")


# =============================================================================
# 插件定义
# =============================================================================

@dataclass
class PluginInfo:
    id: str
    name: str
    version: str
    author: str
    description: str
    homepage: str = ""
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    enabled: bool = True
    permissions: List[str] = field(default_factory=list)
    repository: str = ""


@dataclass
class Plugin:
    info: PluginInfo
    module: Any
    path: str = ""
    skills: Dict[str, Callable] = field(default_factory=dict)
    api_routes: List[dict] = field(default_factory=list)
    background_tasks: List[Callable] = field(default_factory=list)
    _task_threads: List[threading.Thread] = field(default_factory=list)
    _event_handlers: List[tuple] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# 插件配置存储
# =============================================================================

class PluginConfigStore:
    """插件配置持久化存储"""

    def __init__(self, config_file: str = "data/plugin_configs.json"):
        self._config_file = config_file
        self._configs: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    self._configs = json.load(f)
            else:
                os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
                with open(self._config_file, "w", encoding="utf-8") as f:
                    json.dump({}, f)
                self._configs = {}
        except Exception as e:
            logger.warning(f"加载插件配置失败: {e}")
            self._configs = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._configs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存插件配置失败: {e}")

    def get(self, plugin_id: str, key: str = None, default=None):
        with self._lock:
            plugin_cfg = self._configs.get(plugin_id, {})
            if key is None:
                return plugin_cfg
            return plugin_cfg.get(key, default)

    def set(self, plugin_id: str, key: str, value):
        with self._lock:
            if plugin_id not in self._configs:
                self._configs[plugin_id] = {}
            self._configs[plugin_id][key] = value
            self._save()

    def update(self, plugin_id: str, config: Dict):
        with self._lock:
            if plugin_id not in self._configs:
                self._configs[plugin_id] = {}
            self._configs[plugin_id].update(config)
            self._save()

    def delete(self, plugin_id: str, key: str = None):
        with self._lock:
            if key is None:
                self._configs.pop(plugin_id, None)
            else:
                if plugin_id in self._configs:
                    self._configs[plugin_id].pop(key, None)
            self._save()


# =============================================================================
# 插件管理器
# =============================================================================

class PluginManager:
    """
    Y·NEX插件管理器 v2。
    负责：加载插件、注册技能、启动后台任务、分发事件、远程安装。
    """

    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self.skills: Dict[str, Callable] = {}  # skill_name -> function
        self._jarvis = None
        self._plugins_dir = None
        self.event_bus = EventBus()
        self.config_store = PluginConfigStore()
        self._install_lock = threading.Lock()
        self._signature_verifier = PluginSignatureVerifier()
        self._sandbox = PluginSandbox()
        self._hot_reload_enabled = True
        self._watcher_thread = None
        self._watcher_stop = threading.Event()
        self._plugin_mtimes: Dict[str, Dict[str, float]] = {}

    def set_jarvis(self, jarvis_instance):
        """注入Y·NEX主实例（用于插件回调）"""
        self._jarvis = jarvis_instance

    def load_plugins(self, plugins_dir: str = None):
        """扫描并加载所有插件"""
        if plugins_dir is None:
            plugins_dir = Path(__file__).parent / "plugins"
        self._plugins_dir = str(plugins_dir)

        if not os.path.isdir(plugins_dir):
            logger.info(f"插件目录不存在: {plugins_dir}")
            return

        for entry in sorted(os.listdir(plugins_dir)):
            plugin_path = os.path.join(plugins_dir, entry)
            if not os.path.isdir(plugin_path):
                continue
            if entry.startswith("_") or entry.startswith("."):
                continue
            try:
                self._load_plugin(entry, plugin_path)
            except Exception as e:
                logger.error(f"加载插件 {entry} 失败: {e}")

        logger.info(f"插件加载完成，共 {len(self.plugins)} 个")

        if self._hot_reload_enabled:
            self.start_hot_reload()

    def start_hot_reload(self, interval: int = 3):
        """启动插件热重载监视器"""
        if self._watcher_thread and self._watcher_thread.is_alive():
            return
        self._watcher_stop.clear()
        self._snapshot_mtimes()
        self._watcher_thread = threading.Thread(
            target=self._watch_plugins,
            args=(interval,),
            daemon=True,
            name="plugin-hot-reload"
        )
        self._watcher_thread.start()
        logger.info(f"插件热重载已启动，轮询间隔 {interval}s")

    def stop_hot_reload(self):
        """停止插件热重载监视器"""
        self._watcher_stop.set()
        if self._watcher_thread:
            self._watcher_thread.join(timeout=1)
            self._watcher_thread = None

    def _snapshot_mtimes(self):
        """记录当前所有插件文件的修改时间"""
        self._plugin_mtimes = {}
        for plugin in self.plugins.values():
            mtimes = {}
            for root, _, files in os.walk(plugin.path):
                for f in files:
                    if f.endswith(".pyc"):
                        continue
                    fpath = os.path.join(root, f)
                    try:
                        mtimes[fpath] = os.path.getmtime(fpath)
                    except OSError:
                        pass
            self._plugin_mtimes[plugin.info.id] = mtimes

    def _watch_plugins(self, interval: int):
        """后台线程：检测插件文件变更并热重载"""
        while not self._watcher_stop.is_set():
            try:
                self._check_plugin_changes()
            except Exception as e:
                logger.error(f"插件热重载检查异常: {e}")
            self._watcher_stop.wait(interval)

    def _check_plugin_changes(self):
        """检查并处理插件文件变更"""
        changed_plugins = []
        for pid, plugin in self.plugins.items():
            old_mtimes = self._plugin_mtimes.get(pid, {})
            current_mtimes = {}
            changed = False
            for root, _, files in os.walk(plugin.path):
                for f in files:
                    if f.endswith(".pyc"):
                        continue
                    fpath = os.path.join(root, f)
                    try:
                        mtime = os.path.getmtime(fpath)
                        current_mtimes[fpath] = mtime
                        if fpath not in old_mtimes or old_mtimes[fpath] != mtime:
                            changed = True
                    except OSError:
                        pass
            # 文件被删除也算变更
            if set(old_mtimes.keys()) != set(current_mtimes.keys()):
                changed = True
            if changed:
                changed_plugins.append(pid)
            self._plugin_mtimes[pid] = current_mtimes

        for pid in changed_plugins:
            logger.info(f"检测到插件 {pid} 文件变化，准备热重载")
            self.reload_plugin(pid)

    def _load_plugin(self, name: str, plugin_path: str):
        """加载单个插件"""
        # 签名验证
        if not self._signature_verifier.verify(plugin_path):
            logger.error(f"插件 {name} 签名验证失败，拒绝加载")
            return

        # 读取 plugin.json
        meta_path = os.path.join(plugin_path, "plugin.json")
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
        else:
            meta = {"id": name, "name": name, "version": "0.0.1",
                    "author": "unknown", "description": ""}

        info = PluginInfo(
            id=meta["id"],
            name=meta.get("name", name),
            version=meta.get("version", "0.0.1"),
            author=meta.get("author", "unknown"),
            description=meta.get("description", ""),
            homepage=meta.get("homepage", ""),
            tags=meta.get("tags", []),
            dependencies=meta.get("dependencies", []),
            enabled=meta.get("enabled", True),
            permissions=meta.get("permissions", []),
            repository=meta.get("repository", ""),
        )

        if not info.enabled:
            logger.info(f"跳过禁用的插件: {info.name}")
            return

        if info.id in self.plugins:
            logger.warning(f"插件 {info.id} 已存在，跳过")
            return

        # 检查并安装依赖
        if info.dependencies:
            self._install_dependencies(info.id, info.dependencies)

        # 导入模块
        init_path = os.path.join(plugin_path, "__init__.py")
        if not os.path.exists(init_path):
            logger.warning(f"插件 {name} 缺少 __init__.py")
            return

        # 确保在 sys.path 中
        plugin_parent = os.path.dirname(plugin_path)
        if plugin_parent not in sys.path:
            sys.path.insert(0, plugin_parent)

        module_name = f"plugins_{name}"
        spec = importlib.util.spec_from_file_location(module_name, init_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)

        plugin = Plugin(info=info, module=mod, path=plugin_path)
        plugin.config = self.config_store.get(info.id) or {}
        self.plugins[info.id] = plugin
        logger.info(f"加载插件: {info.name} v{info.version} by {info.author}")

        # 调用 register()，在沙箱中执行
        if hasattr(mod, "register"):
            try:
                self._sandbox.run(mod.register, self)
                logger.info(f"  ✓ 插件 {info.name} 注册成功")
            except Exception as e:
                logger.error(f"  ✗ 插件 {info.name} 注册失败: {e}")

        # 触发事件
        self.event_bus.emit("plugin:loaded", info.id, plugin)

    def _install_dependencies(self, plugin_id: str, deps: List[str]):
        """安装插件依赖"""
        import subprocess
        missing = []
        for dep in deps:
            try:
                importlib.import_module(dep)
            except ImportError:
                missing.append(dep)

        if not missing:
            return

        logger.info(f"插件 {plugin_id} 需要安装依赖: {missing}")
        try:
            for dep in missing:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", dep],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=60
                )
            logger.info(f"  ✓ 依赖安装完成")
        except Exception as e:
            logger.warning(f"  ✗ 依赖安装失败: {e}")

    def register_skill(self, plugin_id: str, skill_name: str, func: Callable,
                      description: str = ""):
        """注册一个技能到Y·NEX"""
        if skill_name in self.skills:
            logger.warning(f"技能 {skill_name} 已存在，覆盖")
        self.skills[skill_name] = func
        # 记录到插件
        if plugin_id in self.plugins:
            self.plugins[plugin_id].skills[skill_name] = func
        logger.debug(f"  注册技能: {skill_name}")

    def register_api_route(self, plugin_id: str, rule: str, handler: Callable,
                           methods: List[str] = None):
        """注册一个 Flask API 路由"""
        if methods is None:
            methods = ["GET"]
        if plugin_id in self.plugins:
            self.plugins[plugin_id].api_routes.append({
                "rule": rule, "handler": handler, "methods": methods
            })
        logger.debug(f"  注册路由: {rule}")

    def register_background_task(self, plugin_id: str, task_func: Callable,
                                 interval: float = 60.0, daemon: bool = True):
        """注册一个后台定时任务"""
        def run():
            while True:
                try:
                    task_func()
                except Exception as e:
                    logger.error(f"插件 {plugin_id} 后台任务异常: {e}")
                threading.Event().wait(interval)

        t = threading.Thread(target=run, daemon=daemon, name=f"plugin-{plugin_id}")
        if plugin_id in self.plugins:
            self.plugins[plugin_id]._task_threads.append(t)
        t.start()

    def register_event_handler(self, plugin_id: str, event: str, callback: Callable):
        """注册事件处理器"""
        self.event_bus.on(event, callback)
        if plugin_id in self.plugins:
            self.plugins[plugin_id]._event_handlers.append((event, callback))

    def get_skill(self, skill_name: str) -> Optional[Callable]:
        """获取技能函数"""
        return self.skills.get(skill_name)

    def list_skills(self) -> List[dict]:
        """列出所有已注册技能"""
        return [
            {"name": name, "plugin": self._find_skill_plugin(name)}
            for name in sorted(self.skills.keys())
        ]

    def _find_skill_plugin(self, skill_name: str) -> str:
        for pid, plugin in self.plugins.items():
            if skill_name in plugin.skills:
                return pid
        return "core"

    def list_plugins(self) -> List[dict]:
        """列出所有插件信息"""
        return [
            {
                "id": p.info.id,
                "name": p.info.name,
                "version": p.info.version,
                "author": p.info.author,
                "description": p.info.description,
                "homepage": p.info.homepage,
                "tags": p.info.tags,
                "skills": list(p.skills.keys()),
                "api_routes": [r["rule"] for r in p.api_routes],
                "dependencies": p.info.dependencies,
                "permissions": p.info.permissions,
                "enabled": p.info.enabled,
            }
            for p in self.plugins.values()
        ]

    def get_plugin_config(self, plugin_id: str, key: str = None, default=None):
        """获取插件配置"""
        return self.config_store.get(plugin_id, key, default)

    def set_plugin_config(self, plugin_id: str, key: str, value):
        """设置插件配置"""
        self.config_store.set(plugin_id, key, value)
        if plugin_id in self.plugins:
            self.plugins[plugin_id].config[key] = value

    def enable_plugin(self, plugin_id: str) -> bool:
        if plugin_id in self.plugins:
            self.plugins[plugin_id].info.enabled = True
            # 保存到 plugin.json
            self._save_plugin_meta(plugin_id)
            logger.info(f"插件已启用: {plugin_id}")
            self.event_bus.emit("plugin:enabled", plugin_id)
            return True
        return False

    def disable_plugin(self, plugin_id: str) -> bool:
        if plugin_id in self.plugins:
            self.plugins[plugin_id].info.enabled = False
            self._save_plugin_meta(plugin_id)
            logger.info(f"插件已禁用: {plugin_id}")
            self.event_bus.emit("plugin:disabled", plugin_id)
            return True
        return False

    def _save_plugin_meta(self, plugin_id: str):
        """保存插件元信息到 plugin.json"""
        if plugin_id not in self.plugins:
            return
        plugin = self.plugins[plugin_id]
        meta_path = os.path.join(plugin.path, "plugin.json")
        try:
            meta = {
                "id": plugin.info.id,
                "name": plugin.info.name,
                "version": plugin.info.version,
                "author": plugin.info.author,
                "description": plugin.info.description,
                "homepage": plugin.info.homepage,
                "tags": plugin.info.tags,
                "dependencies": plugin.info.dependencies,
                "permissions": plugin.info.permissions,
                "repository": plugin.info.repository,
                "enabled": plugin.info.enabled,
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存插件元信息失败: {e}")

    def uninstall_plugin(self, plugin_id: str) -> bool:
        """卸载插件（删除目录）"""
        with self._install_lock:
            if plugin_id not in self.plugins:
                return False

            plugin = self.plugins[plugin_id]
            plugin_path = plugin.path

            # 清理事件处理器
            for event, cb in plugin._event_handlers:
                self.event_bus.off(event, cb)

            # 从技能中移除
            for skill_name in list(plugin.skills.keys()):
                self.skills.pop(skill_name, None)

            # 删除
            del self.plugins[plugin_id]

            # 删除目录
            try:
                if os.path.exists(plugin_path):
                    shutil.rmtree(plugin_path)
            except Exception as e:
                logger.error(f"删除插件目录失败: {e}")

            # 删除配置
            self.config_store.delete(plugin_id)

            logger.info(f"插件已卸载: {plugin_id}")
            self.event_bus.emit("plugin:uninstalled", plugin_id)
            return True

    def install_plugin_from_url(self, url: str) -> Dict[str, Any]:
        """
        从 URL 安装插件
        支持 .zip 包或直接是 __init__.py 文件
        """
        with self._install_lock:
            try:
                import tempfile
                logger.info(f"从 URL 安装插件: {url}")

                # 下载
                resp = _http_get(url)
                if not resp.get("ok"):
                    return {"ok": False, "error": f"下载失败: {resp.get('error')}"}

                data = resp["data"]
                plugins_dir = self._plugins_dir or str(Path(__file__).parent / "plugins")
                os.makedirs(plugins_dir, exist_ok=True)

                # 检测是 zip 还是 py 文件
                if url.endswith(".zip") or data[:2] == b"PK":
                    # zip 包
                    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                        tmp.write(data)
                        tmp_path = tmp.name

                    try:
                        with zipfile.ZipFile(tmp_path, "r") as zf:
                            # 安全：Zip Slip 路径穿越防护。
                            # 校验每个解压路径都在 extract_dir 范围内，防止恶意插件包
                            # 构造 ../../ynex_server.py 等路径覆盖系统文件实现 RCE。
                            extract_dir = os.path.abspath(plugins_dir)
                            max_files = 500
                            max_total_size = 50 * 1024 * 1024  # 50MB
                            total_size = 0
                            file_count = 0
                            for info in zf.infolist():
                                file_count += 1
                                if file_count > max_files:
                                    return {"ok": False, "error": "插件包文件数量超过限制（500）"}
                                total_size += info.file_size
                                if total_size > max_total_size:
                                    return {"ok": False, "error": "插件包总大小超过限制（50MB）"}
                                target = os.path.normpath(os.path.join(extract_dir, info.filename))
                                if not target.startswith(extract_dir + os.sep):
                                    return {"ok": False, "error": f"非法路径: {info.filename}"}

                            # 找到插件根目录
                            root_dirs = set()
                            for name in zf.namelist():
                                parts = name.split("/")
                                if len(parts) > 1 and parts[0]:
                                    root_dirs.add(parts[0])

                            zf.extractall(extract_dir)

                            # 确定插件目录
                            if len(root_dirs) == 1:
                                plugin_dir_name = list(root_dirs)[0]
                            else:
                                # 从 URL 推断
                                plugin_dir_name = Path(url).stem

                            plugin_path = os.path.join(plugins_dir, plugin_dir_name)
                    finally:
                        os.unlink(tmp_path)
                else:
                    # 单个 py 文件，创建插件目录
                    plugin_dir_name = Path(url).stem
                    plugin_path = os.path.join(plugins_dir, plugin_dir_name)
                    os.makedirs(plugin_path, exist_ok=True)

                    # 写入 __init__.py
                    with open(os.path.join(plugin_path, "__init__.py"), "wb") as f:
                        f.write(data)

                    # 创建默认 plugin.json
                    meta = {
                        "id": plugin_dir_name,
                        "name": plugin_dir_name,
                        "version": "0.0.1",
                        "author": "remote",
                        "description": f"从 {url} 安装的插件",
                        "enabled": True,
                    }
                    with open(os.path.join(plugin_path, "plugin.json"), "w", encoding="utf-8") as f:
                        json.dump(meta, f, ensure_ascii=False, indent=2)

                # 加载插件
                dir_name = os.path.basename(plugin_path)
                self._load_plugin(dir_name, plugin_path)

                logger.info(f"插件安装成功: {dir_name}")
                return {"ok": True, "plugin_id": dir_name, "path": plugin_path}

            except Exception as e:
                logger.error(f"安装插件失败: {e}")
                return {"ok": False, "error": str(e)}

    def _unload_from_memory(self, plugin_id: str):
        """从内存中卸载插件，但不删除目录"""
        if plugin_id not in self.plugins:
            return
        plugin = self.plugins[plugin_id]

        # 清理事件处理器
        for event, cb in plugin._event_handlers:
            self.event_bus.off(event, cb)

        # 停止后台任务（daemon 线程无法强制停止，设置标志位后不再使用）
        plugin.background_tasks.clear()

        # 从技能中移除
        for skill_name in list(plugin.skills.keys()):
            self.skills.pop(skill_name, None)

        del self.plugins[plugin_id]
        self.event_bus.emit("plugin:unloaded", plugin_id)

    def reload_plugin(self, plugin_id: str) -> bool:
        """热重载插件"""
        if plugin_id not in self.plugins:
            return False

        plugin_path = self.plugins[plugin_id].path
        dir_name = os.path.basename(plugin_path)
        old_info = self.plugins[plugin_id].info

        # 只从内存中卸载，保留目录
        self._unload_from_memory(plugin_id)

        # 重新加载：直接读取文件并执行，避免 importlib 缓存问题
        try:
            module_name = f"plugins_{dir_name}"
            mod = sys.modules.get(module_name)
            if mod is None:
                self._load_plugin(dir_name, plugin_path)
            else:
                init_path = os.path.join(plugin_path, "__init__.py")
                with open(init_path, "r", encoding="utf-8") as f:
                    source = f.read()
                code = compile(source, init_path, "exec")
                self._sandbox.run(exec, code, mod.__dict__)

                # 重新注册
                plugin = Plugin(info=old_info, module=mod, path=plugin_path)
                # 重新读取 plugin.json 以获取可能的更新
                meta_path = os.path.join(plugin_path, "plugin.json")
                if os.path.exists(meta_path):
                    with open(meta_path, encoding="utf-8") as f:
                        meta = json.load(f)
                    plugin.info = PluginInfo(
                        id=meta["id"],
                        name=meta.get("name", dir_name),
                        version=meta.get("version", "0.0.1"),
                        author=meta.get("author", "unknown"),
                        description=meta.get("description", ""),
                        homepage=meta.get("homepage", ""),
                        tags=meta.get("tags", []),
                        dependencies=meta.get("dependencies", []),
                        enabled=meta.get("enabled", True),
                        permissions=meta.get("permissions", []),
                        repository=meta.get("repository", ""),
                    )
                plugin.config = self.config_store.get(plugin.info.id) or {}
                self.plugins[plugin.info.id] = plugin
                if hasattr(mod, "register"):
                    self._sandbox.run(mod.register, self)
                    logger.info(f"  ✓ 插件 {plugin.info.name} 重新注册成功")
            logger.info(f"插件热重载完成: {plugin_id}")
            return True
        except Exception as e:
            logger.error(f"插件重载失败: {e}")
            return False

    def call_skill(self, skill_name: str, **kwargs) -> str:
        """调用技能，返回结果字符串"""
        func = self.get_skill(skill_name)
        if not func:
            return f"未找到技能: {skill_name}"
        try:
            return self._sandbox.run(func, **kwargs)
        except TypeError as e:
            # 尝试不带参数调用
            try:
                return self._sandbox.run(func)
            except Exception:
                return f"技能执行失败：{e}"
        except Exception as e:
            return f"技能执行失败：{e}"


def _http_get(url: str, timeout: int = 30) -> Dict[str, Any]:
    """简单的 HTTP GET 工具"""
    try:
        import requests
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return {"ok": True, "data": resp.content}
    except ImportError:
        from urllib.request import urlopen
        try:
            with urlopen(url, timeout=timeout) as resp:
                return {"ok": True, "data": resp.read()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# 全局单例
_plugin_manager = PluginManager()


def get_plugin_manager() -> PluginManager:
    return _plugin_manager


# =============================================================================
# 插件开发示例（实际生成到 plugins/example/ 目录）
# =============================================================================

EXAMPLE_PLUGIN = {
    "__init__.py": '''
"""Y·NEX示例插件 - 货币转换"""

def register(manager: "PluginManager"):
    """插件入口，注册技能和API路由"""
    manager.register_skill(
        "example",         # 所属插件ID
        "convert_currency", # 技能名
        convert_currency,   # 技能函数
        "将金额从一种货币转换到另一种货币"
    )
    manager.register_api_route("example", "/api/currency/convert", convert_api)

CURRENCY_RATES = {
    "USD": 7.2, "EUR": 7.8, "GBP": 9.0,
    "JPY": 0.048, "CNY": 1.0
}

def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    if from_currency not in CURRENCY_RATES or to_currency not in CURRENCY_RATES:
        return "不支持该货币"
    result = amount / CURRENCY_RATES[from_currency] * CURRENCY_RATES[to_currency]
    return f"{amount} {from_currency} = {result:.2f} {to_currency}"

def convert_api():
    from flask import request, jsonify
    amt = float(request.args.get("amount", 0))
    from_c = request.args.get("from", "USD")
    to_c = request.args.get("to", "CNY")
    return jsonify({"result": convert_currency(amt, from_c, to_c)})
''',

    "plugin.json": '''
{
    "id": "example",
    "name": "货币转换",
    "version": "1.0.0",
    "author": "Y·NEX官方",
    "description": "提供货币转换功能，支持主要国际货币。",
    "tags": ["工具", "金融"],
    "dependencies": [],
    "enabled": true
}
'''
}


def install_example_plugin():
    """安装示例插件到 plugins/example/"""
    plugin_dir = Path(__file__).parent / "plugins" / "example"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    for fname, content in EXAMPLE_PLUGIN.items():
        fpath = plugin_dir / fname
        fpath.write_text(content.strip(), encoding="utf-8")
    logger.info("示例插件已安装到 plugins/example/")


# 自动加载（如果 plugins 目录存在）
_plugins_auto_loaded = False


def auto_load():
    global _plugins_auto_loaded
    if not _plugins_auto_loaded:
        _plugins_auto_loaded = True
        mgr = get_plugin_manager()
        mgr.load_plugins()
        if not mgr.plugins:
            install_example_plugin()
            mgr.load_plugins()
