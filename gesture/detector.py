from __future__ import annotations
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions, RunningMode
import config
from gesture.calibration import CalibrationData
_NOSE = 0
_L_SHOULDER = 11
_R_SHOULDER = 12
_L_WRIST = 15
_R_WRIST = 16
_L_HIP = 23
_R_HIP = 24
GESTURE_NONE = 'none'
GESTURE_CALIBRATING = 'calibrating'
GESTURE_LEAN_LEFT = 'lean_left'
GESTURE_LEAN_RIGHT = 'lean_right'
GESTURE_JUMP = 'jump'
GESTURE_SLIDE = 'slide'
GESTURE_SHIELD = 'shield'
_PRIORITY = [GESTURE_SHIELD, GESTURE_JUMP, GESTURE_SLIDE, GESTURE_LEAN_LEFT, GESTURE_LEAN_RIGHT]

@dataclass
class LandmarkPoint:
    x: float
    y: float
    visibility: float

@dataclass
class BodyLandmarks:
    nose: LandmarkPoint
    l_shoulder: LandmarkPoint
    r_shoulder: LandmarkPoint
    l_wrist: LandmarkPoint
    r_wrist: LandmarkPoint
    l_hip: LandmarkPoint
    r_hip: LandmarkPoint
    shoulder_mid_x: float = 0.0
    shoulder_mid_y: float = 0.0

    def __post_init__(self):
        self.shoulder_mid_x = (self.l_shoulder.x + self.r_shoulder.x) / 2
        self.shoulder_mid_y = (self.l_shoulder.y + self.r_shoulder.y) / 2

@dataclass
class GestureResult:
    gesture: str = GESTURE_NONE
    confidence: int = 0
    landmarks: Optional[BodyLandmarks] = None
    raw_landmarks: object = None
    timestamp: float = field(default_factory=time.monotonic)

class _GestureState:

    def __init__(self, name: str):
        self.name = name
        self._consecutive = 0
        self._cooldown = 0

    def observe(self, triggered: bool) -> bool:
        if self._cooldown > 0:
            self._cooldown -= 1
            if triggered:
                self._consecutive = 0
            return False
        if triggered:
            self._consecutive += 1
            if self._consecutive >= config.GESTURE_CONFIRM_FRAMES:
                self._consecutive = 0
                self._cooldown = config.GESTURE_COOLDOWN_FRAMES
                return True
        else:
            self._consecutive = 0
        return False

class GestureDetector:

    def __init__(self):
        options = PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=config.POSE_MODEL_PATH), running_mode=RunningMode.IMAGE, num_poses=1, min_pose_detection_confidence=config.POSE_MIN_DETECTION_CONFIDENCE, min_pose_presence_confidence=config.POSE_MIN_PRESENCE_CONFIDENCE, min_tracking_confidence=config.POSE_MIN_TRACKING_CONFIDENCE)
        self._landmarker = PoseLandmarker.create_from_options(options)
        self._states: dict[str, _GestureState] = {g: _GestureState(g) for g in _PRIORITY}
        self._wrist_y_history: deque[tuple[float, float]] = deque(maxlen=5)
        self._calib: Optional[CalibrationData] = None

    def set_calibration(self, calib: CalibrationData):
        self._calib = calib

    def process_frame(self, bgr_frame) -> GestureResult:
        import cv2
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        detection = self._landmarker.detect(mp_image)
        if not detection.pose_landmarks:
            self._wrist_y_history.clear()
            return GestureResult()
        raw = detection.pose_landmarks[0]
        if self._calib is None or not self._calib.is_valid:
            return GestureResult(gesture=GESTURE_CALIBRATING, raw_landmarks=raw)
        body = self._extract_body(raw)
        if body is None:
            return GestureResult(raw_landmarks=raw)
        gesture, confidence = self._classify(body)
        return GestureResult(gesture=gesture, confidence=confidence, landmarks=body, raw_landmarks=raw)

    def close(self):
        self._landmarker.close()

    def _extract_body(self, raw) -> Optional[BodyLandmarks]:

        def _pt(idx) -> Optional[LandmarkPoint]:
            lm = raw[idx]
            if lm.visibility < config.LANDMARK_VISIBILITY_MIN:
                return None
            return LandmarkPoint(x=lm.x, y=lm.y, visibility=lm.visibility)
        pts = {'nose': _pt(_NOSE), 'l_shoulder': _pt(_L_SHOULDER), 'r_shoulder': _pt(_R_SHOULDER), 'l_wrist': _pt(_L_WRIST), 'r_wrist': _pt(_R_WRIST), 'l_hip': _pt(_L_HIP), 'r_hip': _pt(_R_HIP)}
        if None in (pts['l_shoulder'], pts['r_shoulder'], pts['l_hip'], pts['r_hip']):
            return None
        return BodyLandmarks(**pts)

    def _classify(self, body: BodyLandmarks) -> tuple[str, int]:
        calib = self._calib
        sw = calib.shoulder_width
        mid_x = body.shoulder_mid_x
        lean_left_delta = calib.lean_left_x - mid_x
        lean_right_delta = mid_x - calib.lean_right_x
        jump_triggered = False
        jump_delta = 0.0
        for wrist in (body.l_wrist, body.r_wrist):
            if wrist is not None:
                delta = calib.jump_y - wrist.y
                if delta > 0:
                    jump_triggered = True
                    jump_delta = max(jump_delta, delta)
        slide_triggered = False
        slide_delta = 0.0
        if body.l_wrist is not None and body.r_wrist is not None:
            lwy, rwy = (body.l_wrist.y, body.r_wrist.y)
            self._wrist_y_history.append((lwy, rwy))
            below_hip = lwy > calib.slide_y and rwy > calib.slide_y
            if below_hip and len(self._wrist_y_history) >= 3:
                old_l, old_r = self._wrist_y_history[-3]
                vel_l = (lwy - old_l) / 3
                vel_r = (rwy - old_r) / 3
                avg_vel = (vel_l + vel_r) / 2
                if avg_vel >= config.SLIDE_VELOCITY_THRESHOLD:
                    slide_triggered = True
                    slide_delta = avg_vel
        else:
            self._wrist_y_history.clear()
        shield_triggered = False
        shield_delta = 0.0
        if body.l_wrist is not None and body.r_wrist is not None:
            l_cross = body.l_wrist.x - calib.shoulder_mid_x - calib.shoulder_width * (0.5 + config.SHIELD_CROSS_RATIO)
            r_cross = calib.shoulder_mid_x - calib.shoulder_width * (0.5 + config.SHIELD_CROSS_RATIO) - body.r_wrist.x
            if l_cross > 0 and r_cross > 0:
                shield_triggered = True
                shield_delta = (l_cross + r_cross) / 2
        triggered_map = {GESTURE_SHIELD: (shield_triggered, shield_delta, sw * config.SHIELD_CROSS_RATIO), GESTURE_JUMP: (jump_triggered, jump_delta, sw * config.JUMP_THRESHOLD_RATIO), GESTURE_SLIDE: (slide_triggered, slide_delta, config.SLIDE_VELOCITY_THRESHOLD * 3), GESTURE_LEAN_LEFT: (lean_left_delta > 0, lean_left_delta, sw * config.LEAN_THRESHOLD_RATIO), GESTURE_LEAN_RIGHT: (lean_right_delta > 0, lean_right_delta, sw * config.LEAN_THRESHOLD_RATIO)}
        for gesture_name in _PRIORITY:
            is_triggered, delta, scale = triggered_map[gesture_name]
            if self._states[gesture_name].observe(is_triggered):
                confidence = min(100, int(delta / max(scale, 1e-06) * 100))
                return (gesture_name, confidence)
        return (GESTURE_NONE, 0)
