"""
Standalone diagnostic — tests MediaPipe pose detection in isolation.
Run this directly: python test_mediapipe.py
It will print whether the model loads, whether the camera opens, and
whether any pose landmarks are detected per frame. No Pygame, no threading,
no calibration logic — just the raw MediaPipe call path.
"""

import os
import sys

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    PoseLandmarker,
    PoseLandmarkerOptions,
    RunningMode,
)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "assets", "pose_landmarker_lite.task")

print(f"[test] Model path: {MODEL_PATH}")
print(f"[test] Model exists: {os.path.isfile(MODEL_PATH)}")
print(f"[test] Model size: {os.path.getsize(MODEL_PATH) if os.path.isfile(MODEL_PATH) else 'N/A'} bytes")

try:
    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=RunningMode.IMAGE,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    landmarker = PoseLandmarker.create_from_options(options)
    print("[test] PoseLandmarker created successfully.")
except Exception as e:
    print(f"[test] FAILED to create PoseLandmarker: {e!r}")
    sys.exit(1)

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[test] FAILED to open camera.")
    sys.exit(1)
print("[test] Camera opened. Reading 30 frames…")

detected_count = 0
for i in range(30):
    ok, frame = cap.read()
    if not ok:
        print(f"[test] Frame {i}: read FAILED")
        continue

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    try:
        detection = landmarker.detect(mp_image)
    except Exception as e:
        print(f"[test] Frame {i}: detect() raised {e!r}")
        continue

    has_pose = bool(detection.pose_landmarks)
    if has_pose:
        detected_count += 1
        ls = detection.pose_landmarks[0][11]  # left shoulder
        print(f"[test] Frame {i}: POSE FOUND  left_shoulder=({ls.x:.3f},{ls.y:.3f}) vis={ls.visibility:.3f}")
    else:
        print(f"[test] Frame {i}: no pose detected")

print(f"\n[test] Summary: {detected_count}/30 frames had a detected pose.")

cap.release()
landmarker.close()
