"""
Y·NEX视觉感知模块
通过摄像头实现人脸检测、姿态识别、运动检测，让Y·NEX"看得见"。

依赖：
  - opencv-python（基础摄像头 + 运动检测，必需）
  - mediapipe（人脸/姿态/手势识别，可选）
  - numpy（必需）

功能：
  - 运动检测（有人经过自动通知）
  - 人脸检测（识别是否有人在镜头前）
  - 姿态检测（站立/坐着/挥手等简单动作）
  - 截图 + 存入知识库
  - 定时巡检（每 N 秒拍一张，有人则告警）
"""

import os
import time
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional

from logger import logger

# 延迟导入，避免无摄像头环境报错
_cv2 = None
_mp = None
_mp_face_detection = None
_mp_pose = None


def _import_cv2():
    global _cv2
    if _cv2 is None:
        try:
            import cv2
            _cv2 = cv2
        except ImportError:
            logger.warning("opencv-python 未安装，视觉模块不可用。pip install opencv-python")
    return _cv2


def _import_mediapipe():
    global _mp, _mp_face_detection, _mp_pose
    if _mp is None:
        try:
            import mediapipe as mp
            _mp = mp
            _mp_face_detection = mp.solutions.face_detection
            _mp_pose = mp.solutions.pose
        except ImportError:
            logger.warning("mediapipe 未安装，人脸/姿态识别不可用。pip install mediapipe")
    return _mp


def is_camera_available() -> bool:
    """检查摄像头是否可用"""
    cv2 = _import_cv2()
    if not cv2:
        return False
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return False
    cap.release()
    return True


@dataclass
class VisionResult:
    has_person: bool = False
    face_count: int = 0
    motion_detected: bool = False
    pose: Optional[str] = None  # standing / sitting / waving
    confidence: float = 0.0
    timestamp: float = 0.0


class MotionDetector:
    """简单的帧间差分运动检测"""

    def __init__(self, threshold: int = 25, min_area: int = 500):
        self.threshold = threshold
        self.min_area = min_area
        self._prev_frame = None

    def detect(self, frame) -> bool:
        cv2 = _import_cv2()
        if not cv2:
            return False

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._prev_frame is None:
            self._prev_frame = gray
            return False

        frame_delta = cv2.absdiff(self._prev_frame, gray)
        thresh = cv2.threshold(frame_delta, self.threshold, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self._prev_frame = gray

        for c in contours:
            if cv2.contourArea(c) > self.min_area:
                return True
        return False


class FaceDetector:
    """人脸检测器（基于 MediaPipe）"""

    def __init__(self, min_detection_confidence: float = 0.5):
        _import_mediapipe()
        self.detector = None
        if _mp_face_detection:
            self.detector = _mp_face_detection.FaceDetection(
                model_selection=1,
                min_detection_confidence=min_detection_confidence
            )

    def count_faces(self, frame) -> int:
        if not self.detector:
            return 0
        cv2 = _import_cv2()
        if not cv2:
            return 0
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.detector.process(rgb)
        if results.detections:
            return len(results.detections)
        return 0


class PoseDetector:
    """人体姿态检测器（基于 MediaPipe Pose）"""

    def __init__(self):
        _import_mediapipe()
        self.pose = None
        if _mp_pose:
            self.pose = _mp_pose.Pose(
                static_image_mode=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )

    def detect_pose(self, frame) -> Optional[str]:
        """
        粗略姿态识别：
        - standing: 站立（肩膀和髋部y差大）
        - sitting: 坐着
        - waving: 挥手（手腕高于肩膀）
        """
        if not self.pose:
            return None
        cv2 = _import_cv2()
        if not cv2:
            return None

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)
        if not results.pose_landmarks:
            return None

        lm = results.pose_landmarks.landmark
        # 关键点索引：11=左肩 12=右肩 23=左髋 24=右髋 15=左腕 16=右腕
        left_shoulder = lm[11]
        right_shoulder = lm[12]
        left_hip = lm[23]
        right_hip = lm[24]
        left_wrist = lm[15]
        right_wrist = lm[16]

        # 低置信度跳过
        if left_shoulder.visibility < 0.3 or left_hip.visibility < 0.3:
            return None

        shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
        hip_y = (left_hip.y + right_hip.y) / 2
        waist_diff = abs(hip_y - shoulder_y)

        # 挥手检测：任意手腕高于肩膀
        if (left_wrist.visibility > 0.5 and left_wrist.y < left_shoulder.y) or \
           (right_wrist.visibility > 0.5 and right_wrist.y < right_shoulder.y):
            return "waving"

        # 粗略：髋部相对肩膀的垂直距离判断姿态
        if waist_diff > 0.25:
            return "standing"
        else:
            return "sitting"


def capture_snapshot(save_path: Optional[str] = None, camera_index: int = 0) -> Optional[str]:
    """
    拍一张照片。
    返回保存的文件路径，失败返回 None。
    """
    cv2 = _import_cv2()
    if not cv2:
        logger.warning("OpenCV 未安装，无法拍照")
        return None

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        logger.warning("摄像头无法打开")
        return None

    try:
        # 预热：丢弃前几帧（避免曝光不足）
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        if not ret:
            return None

        if save_path is None:
            os.makedirs("data/snapshots", exist_ok=True)
            save_path = os.path.join(
                "data", "snapshots",
                f"snapshot_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
            )

        cv2.imwrite(save_path, frame)
        logger.info(f"快照已保存：{save_path}")
        return save_path
    finally:
        cap.release()


def analyze_frame(camera_index: int = 0) -> VisionResult:
    """
    分析一帧画面，返回检测结果。
    """
    cv2 = _import_cv2()
    if not cv2:
        return VisionResult()

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        return VisionResult()

    try:
        for _ in range(3):
            cap.read()
        ret, frame = cap.read()
        if not ret:
            return VisionResult()

        result = VisionResult(timestamp=time.time())

        # 人脸检测
        face_det = FaceDetector()
        result.face_count = face_det.count_faces(frame)
        result.has_person = result.face_count > 0

        # 运动检测
        motion_det = MotionDetector()
        for _ in range(3):
            _, f2 = cap.read()
        result.motion_detected = motion_det.detect(frame)

        # 姿态检测
        pose_det = PoseDetector()
        result.pose = pose_det.detect_pose(frame)

        result.confidence = min(1.0, result.face_count * 0.3 + (0.3 if result.motion_detected else 0))
        return result
    finally:
        cap.release()


# ---------------------------------------------------------------------------
# 后台视觉守护线程
# ---------------------------------------------------------------------------

_vision_thread = None
_vision_running = False
_vision_listeners: List[Callable[[VisionResult], None]] = []


def add_vision_listener(callback: Callable[[VisionResult], None]):
    """添加视觉事件监听"""
    _vision_listeners.append(callback)


def _vision_loop(interval: float = 10.0):
    """
    后台视觉巡检循环。
    每 interval 秒拍一张照片，检测到人时触发通知。
    """
    motion_det = MotionDetector()
    face_det = FaceDetector()
    pose_det = PoseDetector()
    last_face_time = 0
    face_cooldown = 300  # 5分钟内重复检测到同一人不重复通知

    cv2 = _import_cv2()
    if not cv2:
        logger.warning("OpenCV 未安装，视觉守护不启动")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.warning("摄像头不可用，视觉守护不启动")
        return

    logger.info(f"视觉守护已启动，巡检间隔 {interval} 秒")

    try:
        while _vision_running:
            try:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(interval)
                    continue

                result = VisionResult(timestamp=time.time())

                # 快速运动检测（低功耗）
                if motion_det.detect(frame):
                    result.motion_detected = True
                    # 有运动时才做人脸检测
                    result.face_count = face_det.count_faces(frame)
                    result.has_person = result.face_count > 0

                    if result.has_person:
                        result.pose = pose_det.detect_pose(frame)
                        result.confidence = 0.8

                        # 冷却后通知
                        now = time.time()
                        if now - last_face_time > face_cooldown:
                            last_face_time = now
                            _notify_vision_event(result)

                # 通知监听者
                for listener in _vision_listeners:
                    try:
                        listener(result)
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"视觉检测异常：{e}")

            time.sleep(interval)
    finally:
        cap.release()
        logger.info("视觉守护已停止")


def _notify_vision_event(result: VisionResult):
    """视觉检测到人时的通知逻辑"""
    from speech import speak
    pose_desc = {
        "standing": "站着",
        "sitting": "坐着",
        "waving": "在挥手",
        None: ""
    }
    msg = f"先生，检测到有人{pose_desc.get(result.pose, '')}。"
    logger.info(msg)
    try:
        speak(msg)
    except Exception:
        pass


def start_vision_guard(interval: float = 10.0):
    """启动视觉守护线程"""
    global _vision_thread, _vision_running
    if _vision_running:
        return

    if not is_camera_available():
        logger.warning("摄像头不可用，跳过视觉守护")
        return

    _vision_running = True
    _vision_thread = threading.Thread(
        target=_vision_loop, args=(interval,), daemon=True, name="vision-guard"
    )
    _vision_thread.start()


def stop_vision_guard():
    """停止视觉守护"""
    global _vision_running
    _vision_running = False


def vision_summary() -> str:
    """返回视觉状态摘要"""
    if not is_camera_available():
        return "先生，摄像头未接入。"
    result = analyze_frame()
    if result.has_person:
        pose_desc = {"standing": "站着", "sitting": "坐着", "waving": "在挥手"}
        pose = pose_desc.get(result.pose, "")
        return f"先生，摄像头前有 {result.face_count} 个人，{pose}。"
    if result.motion_detected:
        return "先生，检测到轻微运动，但未识别人脸。"
    return "先生，摄像头前没有人。"


if __name__ == "__main__":
    print("测试视觉模块...")
    print(f"摄像头可用：{is_camera_available()}")
    result = analyze_frame()
    print(f"检测结果：{result}")
