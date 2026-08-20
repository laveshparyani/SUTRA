"""ANPR core: ONNX plate detection + OCR, tuned for Indian registration plates.

Zero-GPU design: both models are small ONNX networks (YOLOv9-tiny detector,
CCT OCR) running on onnxruntime CPU — a few ms per frame on a modern CPU,
which is the whole edge-inference story for the 80k-camera scale plan.
"""

import logging
import re
import threading
from dataclasses import dataclass

import cv2
import numpy as np

from ..config import settings

log = logging.getLogger("sutra.anpr")

_detector = None
_recognizer = None
_load_lock = threading.Lock()


@dataclass
class PlateHit:
    text: str            # raw OCR output
    normalised: str      # corrected to Indian plate structure (best effort)
    valid_format: bool   # matches an Indian plate pattern after correction
    ocr_conf: float
    char_probs: list[float]  # per-character OCR probabilities (len == len(text))
    det_conf: float
    bbox: tuple[int, int, int, int]  # x1,y1,x2,y2 in frame coords
    crop: np.ndarray


def _load():
    global _detector, _recognizer
    if _detector is not None:
        return _detector, _recognizer
    with _load_lock:
        if _detector is None:
            from fast_plate_ocr import LicensePlateRecognizer
            from open_image_models import LicensePlateDetector

            log.info("loading ANPR models (first call downloads weights)...")
            _detector = LicensePlateDetector(detection_model=settings.plate_detector_model)
            _recognizer = LicensePlateRecognizer(settings.plate_ocr_model, device="cpu")
            log.info("ANPR models ready: %s + %s", settings.plate_detector_model, settings.plate_ocr_model)
    return _detector, _recognizer


# ---------------------------------------------------------------- Indian plates

# Standard: 2 state letters + 1-2 digit RTO + 1-3 series letters + 4 digits (GJ01AB1234)
# Bharat series: 2 digits + BH + 4 digits + 1-2 letters (22BH1234AB)
_STD = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}$")
_BH = re.compile(r"^\d{2}BH\d{4}[A-Z]{1,2}$")

_TO_DIGIT = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6", "T": "7"}
_TO_LETTER = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G", "7": "T", "4": "A"}

# valid Indian vehicle registration state/UT codes
_STATE_CODES = {
    "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA", "GJ", "HP", "HR",
    "JH", "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP", "MZ", "NL", "OD",
    "OR", "PB", "PY", "RJ", "SK", "TN", "TR", "TS", "UK", "UP", "WB",
}

# visually-confusable alternates for state-code repair (e.g. GI → GJ)
_LOOKALIKES = {
    "I": "J1T", "J": "I", "1": "IL", "L": "I", "O": "0DQ", "0": "OD", "D": "O0",
    "B": "8R", "8": "B", "G": "6C", "6": "G", "S": "5", "5": "S", "Z": "2", "2": "Z",
    "T": "1I", "A": "4", "4": "A", "H": "M", "M": "H", "K": "X", "V": "U", "U": "V",
}


def _fix_state_code(plate: str) -> str:
    """Repair an invalid leading state code using look-alike substitutions."""
    code = plate[:2]
    if code in _STATE_CODES or len(plate) < 2:
        return plate
    for i in (1, 0):  # second char is the more common OCR casualty
        for alt in _LOOKALIKES.get(code[i], ""):
            candidate = code[:i] + alt + code[i + 1:]
            if candidate in _STATE_CODES:
                return candidate + plate[2:]
    return plate


def is_valid_indian(plate: str) -> bool:
    """Shape-valid AND carries a real state code.

    The shape regex alone accepts impossible registrations like GI01D7553 —
    the structure-forcing pass can manufacture those, so the state code must
    be checked too or corrupted plates get stored as if they were confirmed.
    """
    if _BH.match(plate):
        return True
    return bool(_STD.match(plate)) and plate[:2] in _STATE_CODES


# confusion classes for fuzzy comparison: fold visually-identical chars together
_FOLD = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2",
                       "S": "5", "B": "8", "G": "6", "T": "7", "A": "4"})


def fold_plate(plate: str) -> str:
    """Collapse OCR-confusable characters so GJ01 == GJO1 == GJ0I."""
    return plate.upper().translate(_FOLD)


def levenshtein(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > 2:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def plate_similarity(read: str, target: str) -> str | None:
    """Classify a read against a watchlist plate: 'exact' | 'probable' | None.

    'probable' = identical after confusion-folding, or edit distance 1 —
    catches single-character OCR errors on genuine watchlist vehicles.
    """
    if read == target:
        return "exact"
    fr, ft = fold_plate(read), fold_plate(target)
    if fr == ft or levenshtein(fr, ft) <= 1:
        return "probable"
    return None


def normalise_plate(raw: str) -> tuple[str, bool]:
    """Best-effort correction of OCR confusions using Indian plate structure.

    Returns (normalised_plate, matches_known_format).
    """
    plate = "".join(ch for ch in raw.upper() if ch.isalnum())
    plate = _fix_state_code(plate)
    if is_valid_indian(plate):
        return plate, True
    if not 8 <= len(plate) <= 10:
        return plate, False

    # Force structure: [0:2]=letters, [-4:]=digits, middle = digits then letters
    chars = list(plate)
    for i in (0, 1):
        chars[i] = _TO_LETTER.get(chars[i], chars[i])
    for i in range(len(chars) - 4, len(chars)):
        chars[i] = _TO_DIGIT.get(chars[i], chars[i])
    middle = chars[2:-4]
    # RTO code first (1-2 digits), series letters after
    split = 2 if len(middle) >= 2 and middle[1].isdigit() or (len(middle) >= 2 and middle[1] in _TO_DIGIT) else 1
    split = min(split, len(middle))
    for i in range(split):
        middle[i] = _TO_DIGIT.get(middle[i], middle[i])
    for i in range(split, len(middle)):
        middle[i] = _TO_LETTER.get(middle[i], middle[i])
    # structure forcing can turn a digit into a bogus state letter (6I → GI),
    # so repair the code again on the rebuilt candidate before accepting it
    candidate = _fix_state_code("".join(chars[:2] + middle + chars[-4:]))
    if is_valid_indian(candidate):
        return candidate, True
    return plate, False


# ---------------------------------------------------------------- inference

def analyse_frame(frame: np.ndarray) -> list[PlateHit]:
    """Detect plates in a BGR frame and OCR each crop."""
    detector, recognizer = _load()
    hits: list[PlateHit] = []
    for det in detector.predict(frame):
        det_conf = float(getattr(det, "confidence", 0.0))
        if det_conf < settings.plate_det_min_conf:
            continue
        bb = det.bounding_box
        x1, y1, x2, y2 = (int(bb.x1), int(bb.y1), int(bb.x2), int(bb.y2))
        # small padding helps OCR
        h, w = frame.shape[:2]
        px, py = max(2, (x2 - x1) // 10), max(2, (y2 - y1) // 5)
        cx1, cy1 = max(0, x1 - px), max(0, y1 - py)
        cx2, cy2 = min(w, x2 + px), min(h, y2 + py)
        crop = frame[cy1:cy2, cx1:cx2]
        if crop.shape[0] < 12 or crop.shape[1] < 30:
            continue  # too small to read
        # far-away plates: upscale before OCR — CCTV wide shots yield 50-90px plates
        if crop.shape[1] < 140:
            scale = 160 / crop.shape[1]
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)

        preds = recognizer.run(crop, return_confidence=True)
        if not preds:
            continue
        pred = preds[0]  # PlatePrediction(plate, char_probs, region, region_prob)
        text = (pred.plate or "").strip().replace("_", "")
        # confidence over actual characters only (pad positions report ~1.0)
        probs = pred.char_probs[: len(text)] if len(text) else pred.char_probs
        ocr_conf = float(np.mean(probs)) if len(text) else 0.0
        if len(text) < 6:
            continue
        normalised, valid = normalise_plate(text)
        hits.append(
            PlateHit(
                text=text,
                normalised=normalised,
                valid_format=valid,
                ocr_conf=round(ocr_conf, 4),
                char_probs=[float(p) for p in probs][: len(text)],
                det_conf=round(det_conf, 4),
                bbox=(x1, y1, x2, y2),
                crop=crop,
            )
        )
    return hits


def vote_plate(reads: list[tuple[str, list[float]]]) -> tuple[str, float]:
    """Character-level majority vote over multiple reads of the same plate.

    Takes (text, char_probs) pairs; uses the majority read length, then picks
    each position's highest probability-weighted character. A vehicle crossing
    a frame yields 3-10 reads — voting recovers characters any single frame
    misread.
    """
    from collections import Counter, defaultdict

    if not reads:
        return "", 0.0
    lengths = Counter(len(t) for t, _ in reads if t)
    if not lengths:
        return "", 0.0
    length = lengths.most_common(1)[0][0]
    candidates = [(t, p) for t, p in reads if len(t) == length]
    voted = []
    confidences = []
    for i in range(length):
        scores: dict[str, float] = defaultdict(float)
        for text, probs in candidates:
            prob = probs[i] if i < len(probs) else 0.5
            scores[text[i]] += prob
        char, score = max(scores.items(), key=lambda kv: kv[1])
        voted.append(char)
        confidences.append(score / len(candidates))
    return "".join(voted), float(np.mean(confidences))
