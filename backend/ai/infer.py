"""VLPR-TVD inference pipeline.

Two concurrent detection flows in a single frame:

 1. Motorcycle flow
    - Detect motorcycles (YOLOv8 COCO class 3)
    - Find rider person(s) overlapping the motorcycle
    - Run `helmet.pt` on the rider's head region
    - Run `license_plate.pt` on the motorcycle region and OCR with EasyOCR
    - If rider has NO helmet -> emit a no_helmet violation with the plate

 2. Car flow
    - Detect cars/trucks/buses (YOLOv8 COCO classes 2, 5, 7)
    - Run `seatbelt.pt` on the driver-side windshield region (upper-front)
    - Run `license_plate.pt` on the car region and OCR
    - If driver has NO seatbelt -> emit a no_seatbelt violation with the plate
    - If seatbelt.pt is not present, this flow is skipped gracefully.

Public API: `analyze_image(image_path)` returns a list[dict]. Each dict has:
    {
      "violation_type": "no_helmet" | "no_seatbelt",
      "vehicle_type":   "motorcycle" | "car" | "truck" | "bus",
      "plate_number":   "<OCR result or 'UNKNOWN'>",
      "evidence_url":   "/media/violations/<uuid>.jpg",
      "confidence":     float,
    }

Missing model weights are handled gracefully - a warning is logged and that
flow is skipped, rather than throwing.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

import cv2

logger = logging.getLogger(__name__)

# --- Paths ---------------------------------------------------------------
AI_DIR = Path(__file__).resolve().parent
BACKEND_DIR = AI_DIR.parent
MEDIA_DIR = BACKEND_DIR / "media" / "violations"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

BASE_WEIGHTS = AI_DIR / "yolov8n.pt"          # COCO base model (vehicles + persons)
HELMET_WEIGHTS = AI_DIR / "models" / "helmet.pt"
PLATE_WEIGHTS = AI_DIR / "models" / "license_plate.pt"
SEATBELT_WEIGHTS = AI_DIR / "models" / "seatbelt.pt"  # may be missing - stub-ok

# Label sets
HELMET_WORN = {"with helmet", "helmet", "with_helmet", "withhelmet", "helmeted"}
HELMET_NOT_WORN = {"no helmet", "without helmet", "no_helmet", "nohelmet", "without_helmet"}
SEATBELT_WORN = {"seatbelt", "with seatbelt", "with_seatbelt", "belt", "buckled"}
SEATBELT_NOT_WORN = {"no seatbelt", "no_seatbelt", "without seatbelt", "without_seatbelt", "unbuckled"}

# COCO class IDs (yolov8n.pt)
COCO_PERSON = 0
COCO_CAR = 2
COCO_MOTORCYCLE = 3
COCO_BUS = 5
COCO_TRUCK = 7


# --- Lazy loaders --------------------------------------------------------
_base_model = None
_helmet_model = None
_plate_model = None
_seatbelt_model = None
_ocr_reader = None


def _load_yolo(path: Path, required: bool = False):
    if not path.exists():
        msg = f"weights missing: {path}"
        if required:
            raise FileNotFoundError(msg)
        logger.warning("%s (skipping)", msg)
        return None
    try:
        from ultralytics import YOLO
    except ImportError:
        msg = "ultralytics not installed; `pip install ultralytics`"
        if required:
            raise
        logger.warning("%s (skipping)", msg)
        return None
    logger.info("Loading YOLO weights: %s", path)
    return YOLO(str(path))


def _get_base_model():
    global _base_model
    if _base_model is None:
        _base_model = _load_yolo(BASE_WEIGHTS, required=False)
    return _base_model


def _get_helmet_model():
    global _helmet_model
    if _helmet_model is None:
        _helmet_model = _load_yolo(HELMET_WEIGHTS, required=False)
    return _helmet_model


def _get_plate_model():
    global _plate_model
    if _plate_model is None:
        _plate_model = _load_yolo(PLATE_WEIGHTS, required=False)
    return _plate_model


def _get_seatbelt_model():
    """Lazy-loaded. Returns None if seatbelt.pt is not provided."""
    global _seatbelt_model
    if _seatbelt_model is None:
        _seatbelt_model = _load_yolo(SEATBELT_WEIGHTS, required=False)
    return _seatbelt_model


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            logger.info("Loading EasyOCR reader (cpu)")
            _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        except Exception as e:
            logger.warning("EasyOCR init failed: %s (OCR disabled)", e)
            _ocr_reader = False
    return _ocr_reader if _ocr_reader else None


# --- Geometry helpers ----------------------------------------------------
def _iou(a, b) -> float:
    """Intersection-over-union of two [x1,y1,x2,y2] boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    aarea = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    barea = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = aarea + barea - inter
    return inter / union if union > 0 else 0.0


def _overlap_ratio(inner, outer) -> float:
    """How much of `inner` falls inside `outer` (0..1)."""
    ix1, iy1 = max(inner[0], outer[0]), max(inner[1], outer[1])
    ix2, iy2 = min(inner[2], outer[2]), min(inner[3], outer[3])
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    inner_area = max(1, (inner[2] - inner[0]) * (inner[3] - inner[1]))
    return inter / inner_area


def _center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _dist(a, b):
    cax, cay = _center(a)
    cbx, cby = _center(b)
    return ((cax - cbx) ** 2 + (cay - cby) ** 2) ** 0.5


def _clip(img, box, pad: int = 0):
    h, w = img.shape[:2]
    x1 = max(0, int(box[0]) - pad)
    y1 = max(0, int(box[1]) - pad)
    x2 = min(w, int(box[2]) + pad)
    y2 = min(h, int(box[3]) + pad)
    if x2 <= x1 or y2 <= y1:
        return None
    return img[y1:y2, x1:x2]


# --- Primitive detectors -------------------------------------------------
def _detect_base(img):
    """Returns dict with lists of [x1,y1,x2,y2,conf] for person/motorcycle/car-like."""
    model = _get_base_model()
    result = {"person": [], "motorcycle": [], "car": [], "truck": [], "bus": []}
    if model is None:
        return result
    res = model(img, conf=0.25, verbose=False)
    for r in res:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = [float(v) for v in box.xyxy[0]]
            if cls_id == COCO_PERSON:
                result["person"].append(xyxy + [conf])
            elif cls_id == COCO_MOTORCYCLE:
                result["motorcycle"].append(xyxy + [conf])
            elif cls_id == COCO_CAR:
                result["car"].append(xyxy + [conf])
            elif cls_id == COCO_TRUCK:
                result["truck"].append(xyxy + [conf])
            elif cls_id == COCO_BUS:
                result["bus"].append(xyxy + [conf])
    return result


def _detect_plates(img):
    """Returns list of [x1,y1,x2,y2,conf] for license plates."""
    model = _get_plate_model()
    if model is None:
        return []
    out = []
    res = model(img, conf=0.2, verbose=False)
    for r in res:
        for box in r.boxes:
            xyxy = [float(v) for v in box.xyxy[0]]
            out.append(xyxy + [float(box.conf[0])])
    return out


def _ocr_plate(img, plate_box) -> tuple[str, float]:
    crop = _clip(img, plate_box, pad=2)
    if crop is None or crop.size == 0:
        return "UNKNOWN", 0.0
    crop = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    reader = _get_ocr_reader()
    if reader is None:
        return "UNKNOWN", 0.0
    detections = reader.readtext(gray)
    if not detections:
        return "UNKNOWN", 0.0
    detections.sort(key=lambda d: d[2], reverse=True)
    text = detections[0][1].strip().upper().replace(" ", "")
    conf = float(detections[0][2])
    # Strip non-alphanumerics - plates are alpha+digit only
    clean = "".join(ch for ch in text if ch.isalnum())
    return (clean or "UNKNOWN"), conf


HELMET_CONF_THRESHOLD = 0.45  # require at least this confidence to count a class

def _check_helmet(head_crop, raw_out: Optional[list] = None) -> tuple[bool, bool]:
    """Returns (worn_detected, not_worn_detected).

    If `raw_out` is a list, each detection's (label, confidence) tuple is
    appended to it for diagnostic reporting. Only detections above
    HELMET_CONF_THRESHOLD contribute to the worn/not_worn signal — this
    filters out borderline false positives from a weak model.
    """
    model = _get_helmet_model()
    if model is None or head_crop is None or head_crop.size == 0:
        return (False, False)
    res = model(head_crop, verbose=False)
    worn = not_worn = False
    for r in res:
        for box in r.boxes:
            label = model.names[int(box.cls[0])].lower().strip()
            conf = float(box.conf[0])
            if raw_out is not None:
                raw_out.append({"label": label, "conf": round(conf, 3)})
            if conf < HELMET_CONF_THRESHOLD:
                continue
            if label in HELMET_WORN:
                worn = True
            elif label in HELMET_NOT_WORN:
                not_worn = True
    return (worn, not_worn)


def _check_seatbelt(cabin_crop) -> tuple[bool, bool]:
    """Returns (worn_detected, not_worn_detected).

    Preference order:
      1. Trained YOLO model at models/seatbelt.pt  (best accuracy)
      2. Heuristic pose-based detector             (works without training)
      3. Give up: (False, False) = inconclusive, no violation raised
    """
    if cabin_crop is None or cabin_crop.size == 0:
        return (False, False)

    model = _get_seatbelt_model()
    if model is not None:
        res = model(cabin_crop, verbose=False)
        worn = not_worn = False
        for r in res:
            for box in r.boxes:
                label = model.names[int(box.cls[0])].lower().strip()
                if label in SEATBELT_WORN:
                    worn = True
                elif label in SEATBELT_NOT_WORN:
                    not_worn = True
        return (worn, not_worn)

    # Fallback: heuristic detector using pose keypoints + edge analysis
    try:
        from ai.seatbelt_heuristic import check_seatbelt as _heur
        return _heur(cabin_crop)
    except Exception as e:
        logger.debug("seatbelt heuristic unavailable (%s)", e)
        return (False, False)


# --- Pipeline helpers ----------------------------------------------------
def _nearest_plate(target_box, plates):
    """Pick the plate whose center is closest to target_box."""
    if not plates:
        return None
    return min(plates, key=lambda p: _dist(target_box[:4], p[:4]))


def _head_region(person_box):
    """Top ~30% of a person bbox - rough approximation of head area."""
    x1, y1, x2, y2 = person_box[:4]
    h = y2 - y1
    return [x1, y1, x2, y1 + h * 0.35]


def _cabin_region(car_box):
    """Upper-front ~45% of a car bbox - approximation of driver-side windshield."""
    x1, y1, x2, y2 = car_box[:4]
    h = y2 - y1
    return [x1, y1, x2, y1 + h * 0.55]


def _save_evidence(img, annot_box=None, label: str = "") -> str:
    """Save the frame (optionally with an annotation box) and return the public URL."""
    out = img.copy()
    if annot_box is not None:
        x1, y1, x2, y2 = [int(v) for v in annot_box[:4]]
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 0, 255), 2)
        if label:
            cv2.putText(out, label, (x1, max(0, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    filename = f"{uuid.uuid4().hex}.jpg"
    save_path = MEDIA_DIR / filename
    cv2.imwrite(str(save_path), out)
    return f"/media/violations/{filename}"


# --- Public API ----------------------------------------------------------
def analyze_image(image_path: Path, debug: Optional[dict] = None) -> list[dict]:
    """Run both detection flows and return a list of violations (possibly empty).

    If a `debug` dict is passed, it will be populated with diagnostic info:
        motorcycles, cars, trucks, buses, persons, plates, helmet_worn,
        helmet_not_worn, seatbelt_mode, notes (list of string messages).
    """
    if debug is None:
        debug = {}
    debug.setdefault("notes", [])

    img = cv2.imread(str(image_path))
    if img is None:
        logger.warning("analyze_image: cannot read %s", image_path)
        debug["notes"].append("Could not read image file")
        return []

    violations: list[dict] = []

    detections = _detect_base(img)
    plates = _detect_plates(img)

    # Populate debug counts
    debug.update({
        "motorcycles": len(detections["motorcycle"]),
        "cars": len(detections["car"]),
        "trucks": len(detections["truck"]),
        "buses": len(detections["bus"]),
        "persons": len(detections["person"]),
        "plates": len(plates),
    })
    if _get_base_model() is None:
        debug["notes"].append("yolov8n.pt base model not loaded")
    if _get_helmet_model() is None:
        debug["notes"].append("helmet.pt not loaded")
    else:
        debug["helmet_model_classes"] = list(_get_helmet_model().names.values())
    if _get_plate_model() is None:
        debug["notes"].append("license_plate.pt not loaded")

    helmet_worn_count = 0
    helmet_not_worn_count = 0
    raw_helmet_detections = []  # all detections, for debug
    debug["helmet_conf_threshold"] = HELMET_CONF_THRESHOLD

    # ---------- Motorcycle flow ----------
    for moto in detections["motorcycle"]:
        candidate_riders = [
            p for p in detections["person"]
            if _overlap_ratio(p[:4], moto[:4]) > 0.2
            or _iou(p[:4], moto[:4]) > 0.08
        ]
        if not candidate_riders:
            candidate_riders = sorted(
                detections["person"],
                key=lambda p: _dist(p[:4], moto[:4]),
            )[:1]

        any_no_helmet = False
        any_worn = False
        for rider in candidate_riders:
            head = _head_region(rider)
            head_crop = _clip(img, head, pad=5)
            worn, not_worn = _check_helmet(head_crop, raw_out=raw_helmet_detections)
            any_worn = any_worn or worn
            any_no_helmet = any_no_helmet or not_worn

        # Fallback: if no rider matched at all, run helmet.pt on the whole
        # motorcycle bbox (useful for tight motorcycle-only crops).
        if not candidate_riders:
            moto_crop = _clip(img, moto, pad=10)
            worn, not_worn = _check_helmet(moto_crop, raw_out=raw_helmet_detections)
            any_worn, any_no_helmet = worn, not_worn

        if any_worn:
            helmet_worn_count += 1
        if any_no_helmet:
            helmet_not_worn_count += 1

        # Emit violation only on explicit no-helmet signal (avoid false
        # positives when the helmet model is simply silent).
        if any_no_helmet:
            plate_box = _nearest_plate(moto, plates)
            plate_number, conf = ("UNKNOWN", 0.0)
            if plate_box is not None:
                plate_number, conf = _ocr_plate(img, plate_box)
            url = _save_evidence(img, moto, "NO HELMET")
            violations.append({
                "violation_type": "no_helmet",
                "vehicle_type": "motorcycle",
                "plate_number": plate_number,
                "evidence_url": url,
                "confidence": conf,
            })

    # ---------- Lenient whole-image helmet fallback ----------
    # If base detector missed the motorcycle entirely (e.g. tight rider-only
    # crop, odd angle), run helmet.pt on the whole image as a last resort.
    if not detections["motorcycle"]:
        worn, not_worn = _check_helmet(img, raw_out=raw_helmet_detections)
        if worn:
            helmet_worn_count += 1
        if not_worn:
            helmet_not_worn_count += 1
            # Emit as motorcycle/no_helmet even though we couldn't classify
            # the vehicle - most no-helmet detections are motorcyclists.
            plate_box = _nearest_plate([0, 0, img.shape[1], img.shape[0]], plates)
            plate_number, conf = ("UNKNOWN", 0.0)
            if plate_box is not None:
                plate_number, conf = _ocr_plate(img, plate_box)
            h, w = img.shape[:2]
            url = _save_evidence(img, [0, 0, w, h], "NO HELMET (fallback)")
            violations.append({
                "violation_type": "no_helmet",
                "vehicle_type": "motorcycle",
                "plate_number": plate_number,
                "evidence_url": url,
                "confidence": conf,
            })
            debug["notes"].append("Triggered whole-image helmet fallback")

    debug["helmet_worn"] = helmet_worn_count
    debug["helmet_not_worn"] = helmet_not_worn_count
    # Sort raw detections by confidence desc, keep top 10 for debug
    raw_helmet_detections.sort(key=lambda d: d["conf"], reverse=True)
    debug["helmet_raw"] = raw_helmet_detections[:10]

    # ---------- Car/Truck/Bus flow (seatbelt) ----------
    has_trained_seatbelt = _get_seatbelt_model() is not None
    has_pose_heuristic = False
    if not has_trained_seatbelt:
        try:
            from ai.seatbelt_heuristic import _get_pose_model
            has_pose_heuristic = _get_pose_model() is not None
        except Exception:
            has_pose_heuristic = False

    if has_trained_seatbelt:
        debug["seatbelt_mode"] = "trained_model"
    elif has_pose_heuristic:
        debug["seatbelt_mode"] = "pose_heuristic"
    else:
        debug["seatbelt_mode"] = "disabled"
        debug["notes"].append(
            "Seatbelt detection disabled (no seatbelt.pt and pose model unavailable)"
        )

    seatbelt_enabled = has_trained_seatbelt or has_pose_heuristic
    if seatbelt_enabled:
        car_like = []
        for k in ("car", "truck", "bus"):
            for b in detections[k]:
                car_like.append((k, b))

        seatbelt_not_worn_count = 0
        for vtype, vbox in car_like:
            cabin = _cabin_region(vbox)
            cabin_crop = _clip(img, cabin, pad=5)
            worn, not_worn = _check_seatbelt(cabin_crop)
            if not_worn:
                seatbelt_not_worn_count += 1
                plate_box = _nearest_plate(vbox, plates)
                plate_number, conf = ("UNKNOWN", 0.0)
                if plate_box is not None:
                    plate_number, conf = _ocr_plate(img, plate_box)
                url = _save_evidence(img, vbox, "NO SEATBELT")
                violations.append({
                    "violation_type": "no_seatbelt",
                    "vehicle_type": vtype,
                    "plate_number": plate_number,
                    "evidence_url": url,
                    "confidence": conf,
                })
        debug["seatbelt_not_worn"] = seatbelt_not_worn_count
        if car_like and seatbelt_not_worn_count == 0:
            debug["notes"].append(
                "Car(s) detected but seatbelt check inconclusive — the driver "
                "probably isn't visible in this angle (heuristic needs the "
                "driver's torso visible through the windshield)"
            )

    logger.info(
        "analyze_image: motorcycles=%d cars=%d persons=%d plates=%d "
        "helmet_worn=%d helmet_not_worn=%d violations=%d",
        debug["motorcycles"], debug["cars"], debug["persons"], debug["plates"],
        debug["helmet_worn"], debug["helmet_not_worn"], len(violations),
    )
    return violations


# --- Backwards-compatible single-result wrapper --------------------------
def analyze_image_first(image_path: Path) -> Optional[dict]:
    """Legacy shim: return only the first violation or None."""
    results = analyze_image(image_path)
    return results[0] if results else None
