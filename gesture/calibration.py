import time
from dataclasses import dataclass, field
from typing import Optional
import cv2
from config import CALIBRATION_FRAMES, WEBCAM_WINDOW_TITLE

@dataclass
class CalibrationData:
    shoulder_mid_x: float = 0.5
    shoulder_mid_y: float = 0.35
    shoulder_width: float = 0.3
    hip_mid_y: float = 0.6
    lean_left_x: float = 0.0
    lean_right_x: float = 0.0
    jump_y: float = 0.0
    slide_y: float = 0.0
    is_valid: bool = False

def _extract_keypoints(landmarks):
    L_SHOULDER, R_SHOULDER = (11, 12)
    L_HIP, R_HIP = (23, 24)
    ls = landmarks[L_SHOULDER]
    rs = landmarks[R_SHOULDER]
    lh = landmarks[L_HIP]
    rh = landmarks[R_HIP]
    return (ls, rs, lh, rh)

def run_calibration(cap: cv2.VideoCapture, detector, stop_event=None) -> CalibrationData:
    from config import CALIBRATION_FRAMES, LEAN_THRESHOLD_RATIO, JUMP_THRESHOLD_RATIO, SLIDE_POSITION_RATIO, COLORS
    import config
    samples: list[dict] = []
    needed = CALIBRATION_FRAMES
    print('[calibration] Stand in a neutral position. Collecting baseline…')
    while len(samples) < needed:
        if stop_event is not None and stop_event.is_set():
            break
        ok, frame = cap.read()
        if not ok:
            continue
        result = detector.process_frame(frame)
        raw = result.raw_landmarks
        if raw is not None:
            ls, rs, lh, rh = _extract_keypoints(raw)
            if all((lm.visibility > 0.4 for lm in (ls, rs, lh, rh))):
                samples.append({'mid_x': (ls.x + rs.x) / 2, 'mid_y': (ls.y + rs.y) / 2, 'width': abs(ls.x - rs.x), 'hip_y': (lh.y + rh.y) / 2})
        progress = int(len(samples) / needed * frame.shape[1])
        display = frame.copy()
        cv2.rectangle(display, (0, frame.shape[0] - 30), (progress, frame.shape[0]), config.SKEL_JOINT_BGR, -1)
        cv2.putText(display, f'Calibrating… stand still  ({len(samples)}/{needed})', (10, frame.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, config.SKEL_LABEL_BGR, 1, cv2.LINE_AA)
        cv2.imshow(WEBCAM_WINDOW_TITLE, display)
        key = cv2.waitKey(1) & 255
        if key == ord('q') or key == 27:
            if stop_event is not None:
                stop_event.set()
            break
        try:
            visible = cv2.getWindowProperty(WEBCAM_WINDOW_TITLE, cv2.WND_PROP_VISIBLE)
            if visible < 1:
                if stop_event is not None:
                    stop_event.set()
                break
        except cv2.error:
            pass
    if not samples:
        return CalibrationData(is_valid=False)
    n = len(samples)
    mid_x = sum((s['mid_x'] for s in samples)) / n
    mid_y = sum((s['mid_y'] for s in samples)) / n
    width = sum((s['width'] for s in samples)) / n
    hip_y = sum((s['hip_y'] for s in samples)) / n
    data = CalibrationData(shoulder_mid_x=mid_x, shoulder_mid_y=mid_y, shoulder_width=max(width, 0.05), hip_mid_y=hip_y, lean_left_x=mid_x - LEAN_THRESHOLD_RATIO * width, lean_right_x=mid_x + LEAN_THRESHOLD_RATIO * width, jump_y=mid_y - JUMP_THRESHOLD_RATIO * width, slide_y=hip_y + SLIDE_POSITION_RATIO * width, is_valid=True)
    print(f'[calibration] Done. shoulder_mid_x={mid_x:.3f}  width={width:.3f}  hip_y={hip_y:.3f}')
    return data
