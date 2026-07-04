"""
Y·NEX 3D 粒子可视化界面
基于 PyQt6 + QWebEngineView 嵌入 Three.js 粒子界面

功能：
  - 3D 光束粒子人脸（可切换 7 种形态）
  - 5 种颜色主题
  - 悬浮控制按钮（对话/天气/灯光/音乐/系统/视觉/自动变换）
  - 底部状态栏
  - 与 Python 后端双向通信（QWebChannel）
  - 无边框透明窗口，可拖动
  - 始终置顶可选
  - 支持任意带屏幕设备（PC/平板/树莓派显示屏）
"""

import os
import sys
import json
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import (
    Qt, QObject, pyqtSignal, pyqtSlot, QUrl, QTimer,
    QPoint, QSize, QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import QIcon, QColor, QPainter, QBrush, QPen
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QFrame, QLabel, QPushButton, QMenu, QSystemTrayIcon
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

from logger import logger


# 资源路径（兼容打包后的 exe）
def _resource_path(rel_path: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent.parent
    full = base / rel_path
    return str(full.resolve())


class BridgeObject(QObject):
    """JS <-> Python 通信桥"""

    messageFromJs = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._callbacks = []

    @pyqtSlot(str)
    def sendToPython(self, message: str):
        """JS 调用 Python"""
        logger.debug(f"JS -> Python: {message[:80]}")
        self.messageFromJs.emit(message)


class ParticleFaceWindow(QMainWindow):
    """
    Y·NEX 3D 粒子主窗口
    """

    def __init__(self, use_mock: bool = False, always_on_top: bool = False):
        super().__init__()
        self.use_mock = use_mock
        self._drag_position = None
        self._bridge = None
        self._web_view = None
        self._channel = None

        self._setup_window(always_on_top)
        self._setup_webview()
        self._setup_tray()

        # 延迟加载，等页面 ready
        QTimer.singleShot(1500, self._on_page_ready)

    def _setup_window(self, always_on_top: bool):
        """设置窗口样式"""
        self.setWindowTitle("Y·NEX AI")
        self.resize(1000, 700)
        self.setMinimumSize(600, 500)

        # 无边框 + 透明背景
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
        )
        if always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # 居中
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )

    def _setup_webview(self):
        """设置 WebEngineView"""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._web_view = QWebEngineView()
        self._web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        # 透明背景
        page = self._web_view.page()
        page.setBackgroundColor(QColor(0, 0, 0, 0))

        # 通信通道
        self._channel = QWebChannel()
        self._bridge = BridgeObject(self)
        self._channel.registerObject("bridge", self._bridge)
        page.setWebChannel(self._channel)

        # 连接消息
        self._bridge.messageFromJs.connect(self._on_js_message)

        # 加载 HTML
        html_path = _resource_path("gui/particle_face.html")
        self._web_view.setUrl(QUrl.fromLocalFile(html_path))

        layout.addWidget(self._web_view)

    def _setup_tray(self):
        """系统托盘"""
        try:
            tray = QSystemTrayIcon(self)
            tray.setIcon(QIcon(_resource_path("gui/icon.png")))
            tray.setToolTip("Y·NEX AI 管家")

            menu = QMenu()
            show_action = menu.addAction("显示界面")
            show_action.triggered.connect(self.showNormal)
            hide_action = menu.addAction("隐藏到托盘")
            hide_action.triggered.connect(self.hide)
            menu.addSeparator()
            quit_action = menu.addAction("退出")
            quit_action.triggered.connect(QApplication.instance().quit)

            tray.setContextMenu(menu)
            tray.show()
            self._tray = tray
        except Exception as e:
            logger.warning(f"系统托盘初始化失败: {e}")
            self._tray = None

    def _on_page_ready(self):
        """页面加载完成后的初始化"""
        # 注入 bridge 对象（因为 QWebChannel 需要 JS 端配合）
        # 我们用简单的 window.bridge 模式
        js = """
        (function() {
            // 简化通信：直接将 bridge 挂到 window
            window.bridge = {
                sendToPython: function(msg) {
                    if (window.pyBridge && window.pyBridge.receiveFromJs) {
                        window.pyBridge.receiveFromJs(msg);
                    }
                }
            };
            console.log("Bridge injected");
        })();
        """
        self._web_view.page().runJavaScript(js)
        logger.info("3D 粒子界面就绪")

    def _on_js_message(self, message: str):
        """处理来自 JS 的消息"""
        # 调用 AI 回复
        try:
            from brain import get_ai_response
            reply = get_ai_response(message, use_mock=self.use_mock)
            self.show_message(reply)
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            self.show_message(f"抱歉，处理出错了：{e}")

    # ------------------------------------------------------------------
    # 对外 API（Python 控制 UI）
    # ------------------------------------------------------------------

    def show_message(self, text: str):
        """在界面上显示对话气泡"""
        safe_text = json.dumps(text)
        js = f"if (window.pyShowMessage) pyShowMessage({safe_text});"
        self._web_view.page().runJavaScript(js)

    def change_shape(self, shape: str):
        """切换形态：face/sphere/torus/nebula/heart/wave/dna"""
        js = f"if (window.pyChangeShape) pyChangeShape('{shape}');"
        self._web_view.page().runJavaScript(js)

    def set_color(self, color: str):
        """设置颜色：#00ffff / #ff00ff / #00ff88 / #ffaa00 / #ff4466"""
        js = f"if (window.pySetColor) pySetColor('{color}');"
        self._web_view.page().runJavaScript(js)

    # ------------------------------------------------------------------
    # 鼠标拖动窗口
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_position and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_position = None

    def mouseDoubleClickEvent(self, event):
        """双击切换最大化"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()


def launch_gui(use_mock: bool = False, always_on_top: bool = False):
    """启动 GUI 界面（阻塞式）"""
    app = QApplication.instance() or QApplication(sys.argv)
    window = ParticleFaceWindow(use_mock=use_mock, always_on_top=always_on_top)
    window.show()
    return app.exec(), window


if __name__ == "__main__":
    launch_gui(use_mock=True)
