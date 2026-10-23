"""Liveness (anti-spoofing): is a face a real person, or a photo / phone screen?

Recognition alone only checks what a face looks like, so holding up a photo of a
resident would get their name. Before Live Feed shows a resident's name, this
checks the face with MiniFASNet (Silent-Face-Anti-Spoofing by Minivision,
Apache 2.0): two small models that look at the face at two crop sizes for the
traces photos and screens leave (flat texture, glare, screen pixels, edges).

The models live in liveness_models/ (converted to ONNX, see the README there)
and run on ONNX Runtime, the same engine InsightFace uses.

Faces too small to judge (far from the camera) aren't checked: recognition
treats them as Unknown until the person comes closer.
"""
import os
import threading

import cv2
import numpy as np

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BACKEND_DIR, "liveness_models")

# (file, how much bigger than the face box the crop is). Both crops are resized
# to 80x80, matching how the models were trained.
MODEL_FILES = (
    ("minifasnet_v2_scale2.7.onnx", 2.7),
    ("minifasnet_v1se_scale4.0.onnx", 4.0),
)
INPUT_SIZE = 80
REAL_CLASS = 1  # the models output [fake (2D), real, fake (3D)]


class LivenessChecker:
    """Scores how likely a face is to be a real person (0-1), with MiniFASNet.

    Thresholds can be set in .env: LIVENESS_THRESHOLD (default 0.5) and
    LIVENESS_MIN_FACE_PX (default 80: faces smaller than this many pixels tall,
    in the full camera frame, are too small to judge).
    """

    def __init__(self, models_dir=MODELS_DIR):
        """Models load on first use, so the server starts instantly."""
        self.models_dir = models_dir
        self.threshold = float(os.environ.get("LIVENESS_THRESHOLD", "0.5"))
        self.min_face_px = float(os.environ.get("LIVENESS_MIN_FACE_PX", "80"))
        self._sessions = None
        self._lock = threading.Lock()

    def missing_files(self):
        """Model files that aren't in liveness_models/ (empty list = ready)."""
        return [f for f, _ in MODEL_FILES if not os.path.exists(os.path.join(self.models_dir, f))]

    def _load(self):
        """Open the ONNX models. Caller holds the lock."""
        if self._sessions is None:
            import onnxruntime as ort
            missing = self.missing_files()
            if missing:
                raise FileNotFoundError(f"liveness model files missing: {', '.join(missing)}")
            self._sessions = [
                (ort.InferenceSession(os.path.join(self.models_dir, f), providers=["CPUExecutionProvider"]), scale)
                for f, scale in MODEL_FILES
            ]
        return self._sessions

    def real_score(self, frame, box):
        """How likely the face in `box` (x, y, w, h in frame pixels) is a real person, 0-1."""
        with self._lock:
            sessions = self._load()
            total = 0.0
            for session, scale in sessions:
                patch = crop_face(frame, box, scale)
                # Same input the models were trained on: BGR, channels first,
                # raw 0-255 values (not divided by 255)
                x = patch.transpose(2, 0, 1)[np.newaxis].astype(np.float32)
                logits = session.run(None, {session.get_inputs()[0].name: x})[0][0]
                e = np.exp(logits - logits.max())
                total += float(e[REAL_CLASS] / e.sum())
            return total / len(sessions)


def crop_face(frame, box, scale):
    """Crop around the face, `scale` times the box size, kept inside the frame; resized to 80x80.

    Matches the original project's CropImage, so the models see faces the way they were trained.
    """
    src_h, src_w = frame.shape[:2]
    x, y, box_w, box_h = box
    scale = min((src_h - 1) / box_h, (src_w - 1) / box_w, scale)
    new_w, new_h = box_w * scale, box_h * scale
    cx, cy = x + box_w / 2, y + box_h / 2
    left, top, right, bottom = cx - new_w / 2, cy - new_h / 2, cx + new_w / 2, cy + new_h / 2
    # Slide the crop back inside the frame instead of cutting it off
    if left < 0:
        right -= left
        left = 0
    if top < 0:
        bottom -= top
        top = 0
    if right > src_w - 1:
        left -= right - src_w + 1
        right = src_w - 1
    if bottom > src_h - 1:
        top -= bottom - src_h + 1
        bottom = src_h - 1
    patch = frame[int(top):int(bottom) + 1, int(left):int(right) + 1]
    return cv2.resize(patch, (INPUT_SIZE, INPUT_SIZE))
