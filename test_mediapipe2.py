"""
Standalone diagnostic v2 — checks ALL FOUR landmarks calibration.py needs:
left shoulder, right shoulder, left hip, right hip — and prints whether
each one passes the visibility > 0.4 threshold that calibration.py uses.

Run this directly: python test_mediapipe2.py
Stand with your FULL upper body + hips visible in frame.
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

options = PoseLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=RunningMode.IMAGE,
    num_poses=1,
    min_pose_detection_confidence=0.5,
    min_pose_presence_confidence=0.5,
    min_tracking_confidence=0.5,
)
landmarker = PoseLandmarker.create_from_options(options)

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[test] FAILED to open camera.")
    sys.exit(1)

print("[test] Reading 60 frames. Stand back so shoulders AND hips are visible…")

pass_count = 0
for i in range(60):
    ok, frame = cap.read()
    if not ok:
        continue

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    detection = landmarker.detect(mp_image)

    if not detection.pose_landmarks:
        print(f"[test] Frame {i}: NO POSE")
        continue

    lm = detection.pose_landmarks[0]
    ls, rs, lh, rh = lm[11], lm[12], lm[23], lm[24]

    all_pass = all(p.visibility > 0.4 for p in (ls, rs, lh, rh))
    if all_pass:
        pass_count += 1

    print(
        f"[test] Frame {i}: "
        f"L_sh={ls.visibility:.2f} R_sh={rs.visibility:.2f} "
        f"L_hip={lh.visibility:.2f} R_hip={rh.visibility:.2f}  "
        f"{'PASS' if all_pass else 'fail'}"
    )

print(f"\n[test] {pass_count}/60 frames would count toward calibration.")

cap.release()
landmarker.close()
