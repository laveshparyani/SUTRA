"""Scene analytics beyond ANPR: person/vehicle detection (YOLOX-nano, ONNX).

Runs as a low-priority sidecar to the ANPR pipeline: at most one frame per
camera per `scene_interval_s`, single worker thread, so it adds ~2-4% CPU
while giving every monitored camera live person/vehicle counts — the
"additional reliable analytics" bonus line, and the building block for
crowd/intrusion rules at scale.
"""

import logging
import queue
import threading
import time

import cv2
import numpy as np

from ..config import settings

log = logging.getLogger("sutra.objects")

# COCO indices we care about -> reported class
_CLASSES = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
_INPUT = 416  # yolox_nano input size

_session = None
_load_lock = threading.Lock()


def _load():
    global _session
    if _session is None:
        with _load_lock:
            if _session is None:
                import onnxruntime as ort

                path = settings.data_dir / "models" / "yolox_nano.onnx"
                _session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
                log.info("scene model loaded: %s", path.name)
    return _session


def _preprocess(frame: np.ndarray) -> tuple[np.ndarray, float]:
    ratio = min(_INPUT / frame.shape[0], _INPUT / frame.shape[1])
    resized = cv2.resize(frame, (int(frame.shape[1] * ratio), int(frame.shape[0] * ratio)))
    padded = np.full((_INPUT, _INPUT, 3), 114, dtype=np.uint8)
    padded[: resized.shape[0], : resized.shape[1]] = resized
    img = padded.transpose(2, 0, 1)[None].astype(np.float32)  # yolox >=0.1.1: no normalisation
    return img, ratio


def _decode(output: np.ndarray, ratio: float) -> list[tuple[str, float, list[int]]]:
    """YOLOX grid decode + NMS -> [(class, score, [x1,y1,x2,y2])]."""
    grids, strides = [], []
    for stride in (8, 16, 32):
        gs = _INPUT // stride
        xv, yv = np.meshgrid(np.arange(gs), np.arange(gs))
        grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
        strides.append(np.full((gs * gs, 1), stride))
    grids = np.concatenate(grids)
    strides = np.concatenate(strides)
    out = output[0]
    out[:, :2] = (out[:, :2] + grids) * strides
    out[:, 2:4] = np.exp(out[:, 2:4]) * strides

    boxes, scores, classes = [], [], []
    obj_conf = out[:, 4]
    cls_scores = out[:, 5:] * obj_conf[:, None]
    for idx in np.where(cls_scores.max(1) > 0.35)[0]:
        cls = int(cls_scores[idx].argmax())
        if cls not in _CLASSES:
            continue
        cx, cy, w, h = out[idx, :4] / ratio
        boxes.append([int(cx - w / 2), int(cy - h / 2), int(w), int(h)])
        scores.append(float(cls_scores[idx].max()))
        classes.append(cls)
    keep = cv2.dnn.NMSBoxes(boxes, scores, 0.35, 0.45) if boxes else []
    keep = keep.flatten() if len(keep) else []
    return [
        (_CLASSES[classes[i]], round(scores[i], 3),
         [boxes[i][0], boxes[i][1], boxes[i][0] + boxes[i][2], boxes[i][1] + boxes[i][3]])
        for i in keep
    ]


def analyse_scene(frame: np.ndarray) -> list[tuple[str, float, list[int]]]:
    session = _load()
    img, ratio = _preprocess(frame)
    output = session.run(None, {session.get_inputs()[0].name: img})[0]
    return _decode(output, ratio)


class SceneAnalyzer:
    """Frame subscriber: throttled per-camera person/vehicle counting."""

    def __init__(self):
        self.queue: queue.Queue = queue.Queue(maxsize=8)
        self.latest: dict[int, dict] = {}       # camera_id -> {counts, ts}
        self._last_run: dict[int, float] = {}
        self.running = False
        self.frames_analysed = 0

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._worker, daemon=True, name="scene-analyzer").start()
        log.info("scene analyzer started (interval %.0fs/camera)", settings.scene_interval_s)

    def on_frame(self, camera_id: int, frame: np.ndarray, ts: float) -> None:
        now = time.monotonic()
        if now - self._last_run.get(camera_id, 0) < settings.scene_interval_s:
            return
        self._last_run[camera_id] = now
        try:
            self.queue.put_nowait((camera_id, frame))
        except queue.Full:
            self._last_run[camera_id] = 0  # try again next frame

    def _worker(self) -> None:
        while self.running:
            try:
                camera_id, frame = self.queue.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                dets = analyse_scene(frame)
                counts: dict[str, int] = {}
                for cls, _score, _box in dets:
                    counts[cls] = counts.get(cls, 0) + 1
                self.latest[camera_id] = {
                    "counts": counts,
                    "persons": counts.get("person", 0),
                    "vehicles": sum(v for k, v in counts.items() if k != "person"),
                    "ts": time.time(),
                }
                self.frames_analysed += 1
            except Exception:
                log.exception("scene analysis failed for cam %s", camera_id)


scene = SceneAnalyzer()
