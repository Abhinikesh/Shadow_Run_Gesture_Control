import queue
import threading
import cv2
import numpy as np
import config
from gesture.calibration import run_calibration
from gesture.detector import GestureDetector, GESTURE_NONE, GESTURE_CALIBRATING
_BONES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24), (0, 11), (0, 12)]
_JOINTS = {0, 11, 12, 13, 14, 15, 16, 23, 24}

def _push_result(gesture_queue: queue.Queue, result):
    try:
        gesture_queue.put_nowait(result)
    except queue.Full:
        try:
            gesture_queue.get_nowait()
        except queue.Empty:
            pass
        gesture_queue.put_nowait(result)

def _draw_skeleton(frame, raw_landmarks, active_gesture: str):
    if raw_landmarks is None:
        return
    h, w = frame.shape[:2]
    pts = {}
    for idx in _JOINTS:
        lm = raw_landmarks[idx]
        if lm.visibility >= 0.35:
            pts[idx] = (int(lm.x * w), int(lm.y * h))
    for a, b in _BONES:
        if a in pts and b in pts:
            cv2.line(frame, pts[a], pts[b], config.SKEL_BONE_BGR, config.SKEL_BONE_THICKNESS, cv2.LINE_AA)
    for idx, pt in pts.items():
        cv2.circle(frame, pt, config.SKEL_JOINT_RADIUS, config.SKEL_JOINT_BGR, -1, cv2.LINE_AA)
        cv2.circle(frame, pt, config.SKEL_JOINT_RADIUS + 1, (30, 30, 30), 1, cv2.LINE_AA)
    if config.WEBCAM_DEBUG_LANDMARKS:
        for idx, pt in pts.items():
            cv2.putText(frame, str(idx), (pt[0] + 7, pt[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.38, config.SKEL_LABEL_BGR, 1, cv2.LINE_AA)

def _draw_gesture_label(frame, gesture: str, confidence: int):
    if gesture in (GESTURE_NONE, GESTURE_CALIBRATING):
        return
    h = frame.shape[0]
    label = f"{gesture.replace('_', ' ').upper()}  {confidence}%"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    pad = 6
    x0, y0 = (12, h - 20)
    cv2.rectangle(frame, (x0 - pad, y0 - th - pad), (x0 + tw + pad, y0 + pad), (24, 27, 50), -1)
    cv2.putText(frame, label, (x0, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.55, config.SKEL_ACTIVE_BGR, 1, cv2.LINE_AA)

def _draw_calibration_bar(frame, progress: float):
    h, w = frame.shape[:2]
    bar_h = 5
    bar_w = int(w * progress)
    bar_y = h - bar_h
    cv2.rectangle(frame, (0, bar_y), (w, h), (24, 27, 50), -1)
    if bar_w > 0:
        cv2.rectangle(frame, (0, bar_y), (bar_w, h), config.SKEL_JOINT_BGR, -1)
    msg = 'Stand still — calibrating'
    cv2.putText(frame, msg, (12, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.48, config.SKEL_LABEL_BGR, 1, cv2.LINE_AA)

def init_webcam(gesture_queue: queue.Queue, stop_event: threading.Event):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print('[webcam] ERROR: Could not open camera.')
        stop_event.set()
        return (None, None)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.WEBCAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.WEBCAM_HEIGHT)
    detector = GestureDetector()
    calib = run_calibration(cap, detector, stop_event)
    detector.set_calibration(calib)
    if not calib.is_valid:
        print('[webcam] Calibration was cancelled or failed.')
        stop_event.set()
        detector.close()
        cap.release()
        return (None, None)
    print('[webcam] Calibration complete — gesture detection active.')
    detector._last_printed_gesture = GESTURE_NONE
    return (cap, detector)

def step_webcam(cap, detector, gesture_queue: queue.Queue, stop_event: threading.Event) -> None:
    if cap is None or not cap.isOpened():
        return
    ok, frame = cap.read()
    if not ok:
        print('[webcam] WARNING: Camera disconnected mid-game. Switching to keyboard-only mode.')
        cap.release()
        cv2.destroyAllWindows()
        return
    result = detector.process_frame(frame)
    if result.gesture != detector._last_printed_gesture and result.gesture != GESTURE_NONE:
        print(f'[gesture] {result.gesture:<14}  conf={result.confidence}%')
    detector._last_printed_gesture = result.gesture
    _push_result(gesture_queue, result)
    _draw_skeleton(frame, result.raw_landmarks, result.gesture)
    _draw_gesture_label(frame, result.gesture, result.confidence)
    cv2.imshow(config.WEBCAM_WINDOW_TITLE, frame)
    key = cv2.waitKey(1) & 255
    if key == ord('q') or key == 27:
        stop_event.set()
    try:
        visible = cv2.getWindowProperty(config.WEBCAM_WINDOW_TITLE, cv2.WND_PROP_VISIBLE)
        if visible < 1:
            stop_event.set()
    except cv2.error:
        pass

def shutdown_webcam(cap, detector) -> None:
    if detector is not None:
        detector.close()
    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()
