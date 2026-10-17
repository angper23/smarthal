"""Face detection + face embeddings for Register Resident.

Two interchangeable engines, picked with FACE_BACKEND in .env:
  insightface (default) — InsightFace buffalo_l (RetinaFace detector + ArcFace embeddings)
  opencv                — OpenCV YuNet detector + SFace embeddings

Both return L2-normalized embeddings compared by cosine similarity. Embeddings
from different engines can't be compared, so every stored embedding records
its engine's `model` name.

Models live in FACE_MODELS_DIR (default models/, gitignored) and are
downloaded on first use. Run `python faces.py` once to download them ahead of
time and check the engine works.
"""
import os
import threading
import urllib.request

import cv2
import numpy as np
from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# Photos are shrunk to this many pixels on the long side before detection.
# Detectors are tuned for faces well under this size; full 12 MP phone photos
# make some of them miss large faces entirely (seen in testing).
MAX_SIDE = 1280

OPENCV_MODELS = {
    "yunet.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "sface.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


def models_dir():
    """Folder holding the downloaded model files (FACE_MODELS_DIR, default models/)."""
    path = os.environ.get("FACE_MODELS_DIR", "models")
    return path if os.path.isabs(path) else os.path.join(BACKEND_DIR, path)


def decode_image(data):
    """Decode uploaded image bytes into a BGR array, shrunk to MAX_SIDE. None if not an image."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    scale = MAX_SIDE / max(img.shape[:2])
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return img


def cosine(a, b):
    """Cosine similarity of two embeddings: about 1 = same face, about 0 = unrelated."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


class InsightFaceEngine:
    """InsightFace buffalo_l. Most accurate in our first test; ~0.3 s per photo on an M2."""

    model = "insightface-buffalo_l"
    # How similar every capture angle must be to the front shot. Lenient on
    # purpose — turned-away angles score lower — it only has to catch a
    # different person stepping in mid-capture. Tune with real captures.
    consistency_threshold = 0.3
    # Live Feed: a camera face counts as a resident at or above this similarity
    # to their best-matching saved angle. In our tests the same person scored
    # 0.47-0.93 and different people 0.05-0.19. Override with RECOGNITION_THRESHOLD.
    match_threshold = 0.4

    def __init__(self):
        """Load (downloading on first run, ~280 MB) the detector and recognizer."""
        import warnings
        warnings.filterwarnings("ignore", module="insightface")
        from insightface.app import FaceAnalysis
        self._app = FaceAnalysis(
            name="buffalo_l",
            root=os.path.join(models_dir(), "insightface"),
            providers=["CPUExecutionProvider"],
            allowed_modules=["detection", "recognition"],
        )
        self._app.prepare(ctx_id=-1, det_size=(640, 640))

    def detect_faces(self, img):
        """Return (box, embedding) per face in the BGR image; box is (x, y, w, h) in pixels."""
        out = []
        for f in self._app.get(img):
            x1, y1, x2, y2 = (float(v) for v in f.bbox)
            out.append(((x1, y1, x2 - x1, y2 - y1), f.normed_embedding.astype(np.float32)))
        return out

    def embed_faces(self, img):
        """Return one normalized embedding per face found in the BGR image."""
        return [emb for _, emb in self.detect_faces(img)]


class OpenCVEngine:
    """OpenCV YuNet + SFace. ~7x faster than InsightFace, smaller safety margin in our first test."""

    model = "opencv-sface"
    consistency_threshold = 0.25
    # SFace's published cosine threshold for "same person"
    match_threshold = 0.363

    def __init__(self):
        """Load (downloading on first run, ~40 MB) the YuNet detector and SFace recognizer."""
        folder = models_dir()
        os.makedirs(folder, exist_ok=True)
        for name, url in OPENCV_MODELS.items():
            path = os.path.join(folder, name)
            if not os.path.exists(path):
                urllib.request.urlretrieve(url, path)
        self._det = cv2.FaceDetectorYN.create(os.path.join(folder, "yunet.onnx"), "", (320, 320), 0.8)
        self._rec = cv2.FaceRecognizerSF.create(os.path.join(folder, "sface.onnx"), "")

    def detect_faces(self, img):
        """Return (box, embedding) per face in the BGR image; box is (x, y, w, h) in pixels."""
        h, w = img.shape[:2]
        self._det.setInputSize((w, h))
        _, faces = self._det.detect(img)
        if faces is None:
            return []
        out = []
        for f in faces:
            emb = self._rec.feature(self._rec.alignCrop(img, f)).flatten().astype(np.float32)
            out.append((tuple(float(v) for v in f[:4]), emb / np.linalg.norm(emb)))
        return out

    def embed_faces(self, img):
        """Return one normalized embedding per face found in the BGR image."""
        return [emb for _, emb in self.detect_faces(img)]


ENGINES = {"insightface": InsightFaceEngine, "opencv": OpenCVEngine}


class LazyEngine:
    """Loads the configured engine on first use, so the server starts instantly
    and tests never need the real models. Calls are serialized with a lock —
    neither library promises thread safety, and the dev server is threaded."""

    def __init__(self, backend=None):
        """backend: 'insightface' or 'opencv' (default: FACE_BACKEND, else insightface)."""
        self.backend = (backend or os.environ.get("FACE_BACKEND") or "insightface").lower()
        if self.backend not in ENGINES:
            raise RuntimeError(f"FACE_BACKEND must be one of: {', '.join(ENGINES)}")
        self._engine = None
        self._lock = threading.Lock()

    def _get(self):
        """Return the loaded engine, loading it on first call. Caller holds the lock."""
        if self._engine is None:
            self._engine = ENGINES[self.backend]()
        return self._engine

    @property
    def model(self):
        """The model name stored next to each embedding."""
        return ENGINES[self.backend].model

    @property
    def consistency_threshold(self):
        """Minimum similarity between each angle and the front shot."""
        return ENGINES[self.backend].consistency_threshold

    @property
    def match_threshold(self):
        """Minimum similarity for a Live Feed face to count as a resident."""
        return ENGINES[self.backend].match_threshold

    def detect_faces(self, img):
        """Return (box, embedding) per face in the image."""
        with self._lock:
            return self._get().detect_faces(img)

    def embed_faces(self, img):
        """Return one normalized embedding per face in the image."""
        with self._lock:
            return self._get().embed_faces(img)

    def warm_up(self):
        """Load (and if needed download) the models now instead of on the first request."""
        with self._lock:
            self._get()


if __name__ == "__main__":
    import time
    engine = LazyEngine()
    start = time.time()
    engine.warm_up()
    print(f"{engine.backend}: models ready in {models_dir()} ({time.time() - start:.1f}s)")
    print("faces in a blank test image:", len(engine.embed_faces(np.zeros((480, 640, 3), np.uint8))))
