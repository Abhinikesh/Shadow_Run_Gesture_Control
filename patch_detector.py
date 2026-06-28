import re

PATH = "gesture/detector.py"

with open(PATH, "r") as f:
    content = f.read()

old = '''    def process_frame(self, bgr_frame) -> GestureResult:
        """
        Detect the current gesture from a single BGR webcam frame.

        Returns GestureResult with gesture="calibrating" if calibration
        hasn't been set yet.
        """
        import cv2

        if self._calib is None or not self._calib.is_valid:
            return GestureResult(gesture=GESTURE_CALIBRATING)

        # MediaPipe Tasks expects an mp.Image in RGB
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        detection = self._landmarker.detect(mp_image)

        if not detection.pose_landmarks:
            # No pose found — drain wrist history so slide velocity is clean
            self._wrist_y_history.clear()
            return GestureResult()

        raw = detection.pose_landmarks[0]
        body = self._extract_body(raw)

        if body is None:
            return GestureResult(raw_landmarks=raw)

        gesture, confidence = self._classify(body)

        return GestureResult(
            gesture=gesture,
            confidence=confidence,
            landmarks=body,
            raw_landmarks=raw,
        )'''

new = '''    def process_frame(self, bgr_frame) -> GestureResult:
        """
        Detect the current gesture from a single BGR webcam frame.

        Pose detection always runs, regardless of calibration state —
        calibration.py needs raw_landmarks to compute its baseline in the
        first place, so detection can't be gated behind calibration being
        ready (that would be a chicken-and-egg deadlock). Only gesture
        CLASSIFICATION (which needs calibrated thresholds) is gated behind
        self._calib being valid; before that, gesture is reported as
        "calibrating" but raw_landmarks is still populated normally.
        """
        import cv2

        # MediaPipe Tasks expects an mp.Image in RGB
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        detection = self._landmarker.detect(mp_image)

        if not detection.pose_landmarks:
            # No pose found — drain wrist history so slide velocity is clean
            self._wrist_y_history.clear()
            if self._calib is None or not self._calib.is_valid:
                return GestureResult(gesture=GESTURE_CALIBRATING)
            return GestureResult()

        raw = detection.pose_landmarks[0]

        if self._calib is None or not self._calib.is_valid:
            # Calibration not ready yet — still return raw_landmarks so
            # calibration.py can use them to build its baseline.
            return GestureResult(gesture=GESTURE_CALIBRATING, raw_landmarks=raw)

        body = self._extract_body(raw)

        if body is None:
            return GestureResult(raw_landmarks=raw)

        gesture, confidence = self._classify(body)

        return GestureResult(
            gesture=gesture,
            confidence=confidence,
            landmarks=body,
            raw_landmarks=raw,
        )'''

if old not in content:
    print("PATTERN NOT FOUND — file content differs from expected, no changes made.")
else:
    content = content.replace(old, new)
    with open(PATH, "w") as f:
        f.write(content)
    print("Patched process_frame() successfully — raw_landmarks now populated during calibration.")
