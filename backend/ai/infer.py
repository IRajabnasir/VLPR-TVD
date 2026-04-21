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

# Label sets — stored in NORMALIZED form (lowercase, hyphens/spaces/underscores
# all collapsed to a single "_"). Use `_normalize_label()` when comparing.
HELMET_WORN = {"helmet", "with_helmet", "withhelmet", "helmeted"}
HELMET_NOT_WORN = {"no_helmet", "nohelmet", "without_helmet"}
SEATBELT_WORN = {"seatbelt", "with_seatbelt", "belt", "buckled"}
SEATBELT_NOT_WORN = {"no_seatbelt", "without_seatbelt", "unbuckled"}


def _normalize_label(label: str) -> str:
    """Normalize a model's class label so hyphen/space/underscore variants
    all match the same entry in the WORN/NOT_WORN sets."""
    return label.lower().strip().replace("-", "_").replace(" ", "_")

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


_tesseract_available = None

def _tesseract_enabled() -> bool:
    """Check if pytesseract + tesseract binary are installed and callable."""
    global _tesseract_available
    if _tesseract_available is None:
        try:
            import pytesseract
            # Force a no-op call to confirm the binary exists
            pytesseract.get_tesseract_version()
            _tesseract_available = True
            logger.info("Tesseract OCR fallback enabled")
        except Exception as e:
            logger.info("Tesseract not available (%s) — EasyOCR only", e)
            _tesseract_available = False
    return _tesseract_available


def _ocr_tesseract(img_gray) -> tuple[str, float]:
    """Run Tesseract on a preprocessed grayscale image. Returns (text, conf).

    Uses psm=7 (single line of text) and a restricted char whitelist. Returns
    ("", 0.0) on any failure.
    """
    if not _tesseract_enabled():
        return ("", 0.0)
    try:
        import pytesseract
        config = (
            "--psm 7 "
            "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )
        # image_to_data returns conf per-word; take the max-conf word
        data = pytesseract.image_to_data(
            img_gray, config=config, output_type=pytesseract.Output.DICT
        )
        best_text, best_conf = "", 0.0
        for i, t in enumerate(data.get("text", [])):
            if not t:
                continue
            try:
                c = float(data["conf"][i]) / 100.0
            except (ValueError, KeyError):
                continue
            if c > best_conf:
                best_conf = c
                best_text = t
        return (best_text, best_conf)
    except Exception as e:
        logger.debug("Tesseract OCR failed: %s", e)
        return ("", 0.0)


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


PLATE_LABELS = {"license_plate", "plate", "licenseplate", "numberplate", "number_plate"}


def _dedupe_boxes(boxes, iou_threshold: float = 0.5):
    """Greedy NMS: keep highest-conf box, drop boxes with IoU > threshold against any kept box."""
    if not boxes:
        return []
    sorted_boxes = sorted(boxes, key=lambda b: b[4], reverse=True)
    kept = []
    for b in sorted_boxes:
        if all(_iou(b[:4], k[:4]) < iou_threshold for k in kept):
            kept.append(b)
    return kept


def _detect_plates(img):
    """Detect license plate bboxes using every available model, merged + deduped.

    Sources (best-effort, each is optional):
      1. `license_plate.pt` (dedicated plate detector)
      2. `helmet.pt` - the new multi-class model also knows `license_plate`
         (typically better on motorbike scenes, mAP50 ~0.94)

    Returns a list of `[x1, y1, x2, y2, conf, source]` where source is one
    of "plate_model" | "helmet_model" for debug reporting.
    """
    all_plates = []

    plate_model = _get_plate_model()
    if plate_model is not None:
        res = plate_model(img, conf=0.15, verbose=False)
        for r in res:
            for box in r.boxes:
                xyxy = [float(v) for v in box.xyxy[0]]
                all_plates.append(xyxy + [float(box.conf[0]), "plate_model"])

    helmet_model = _get_helmet_model()
    if helmet_model is not None:
        class_names = {_normalize_label(n) for n in helmet_model.names.values()}
        # Only query helmet model if it actually has a plate class (new-style)
        if class_names & PLATE_LABELS:
            res = helmet_model(img, conf=0.15, verbose=False)
            for r in res:
                for box in r.boxes:
                    label = _normalize_label(helmet_model.names[int(box.cls[0])])
                    if label in PLATE_LABELS:
                        xyxy = [float(v) for v in box.xyxy[0]]
                        all_plates.append(xyxy + [float(box.conf[0]), "helmet_model"])

    # IoU-dedupe so overlapping detections from both models don't double-count
    # (we only need x1,y1,x2,y2,conf for dedup; keep the 'source' separately)
    boxes_for_dedupe = [b[:5] for b in all_plates]
    kept_indices = []
    if boxes_for_dedupe:
        sorted_idx = sorted(range(len(all_plates)), key=lambda i: all_plates[i][4], reverse=True)
        kept = []
        for i in sorted_idx:
            box = boxes_for_dedupe[i]
            if all(_iou(box[:4], k[:4]) < 0.5 for k in kept):
                kept.append(box)
                kept_indices.append(i)
    return [all_plates[i] for i in kept_indices]


OCR_MIN_CONF = 0.20
OCR_MIN_LENGTH = 4     # plates shorter than this are almost certainly noise
OCR_MAX_LENGTH = 20    # relaxed from 12 — multi-text plates (PUNJAB LEE 24 6059)
                       # concatenate to longer strings; stopword-strip cleans them
OCR_PAD_PX = 4         # pad the plate crop a few pixels for OCR
PLATE_CROPS_DIR = BACKEND_DIR / "media" / "plates"
PLATE_CROPS_DIR.mkdir(parents=True, exist_ok=True)

# Words that frequently appear on plates as decoration/jurisdiction labels
# but are NOT part of the plate number itself. Strip them from OCR output.
# All entries must be UPPERCASE.
OCR_STOPWORDS = {
    # Pakistani jurisdictions / labels
    "PUNJAB", "SINDH", "KPK", "KP", "BALOCHISTAN", "ICT", "ISLAMABAD",
    "PAKISTAN", "PAK", "GILGIT", "BALTISTAN", "KASHMIR", "AJK",
    # Pakistani military / corporate
    "NAVY", "ARMY", "AIR", "AIRFORCE", "FORCE", "ARMED",
    "DEFENCE", "DEFENSE", "BAHRIA", "DHA", "CANT", "CANTT",
    "FOUNDATION", "GOVT", "GOVERNMENT",
    # Indian jurisdictions / labels
    "BHARAT", "INDIA", "POLICE",
    # Stock-photo/watermark noise sometimes cropped with plates
    "POWER", "BRAKE", "BREAK", "KEEP", "DISTANCE", "STOCK", "IMAGE",
    "PHOTO", "ALAMY", "GETTY",
}


def _strip_stopwords(text: str) -> str:
    """Remove OCR_STOPWORDS from a text blob. Longest words removed first
    so e.g. 'ISLAMABAD' is matched before 'ISL'.
    """
    if not text:
        return text
    # Split into alpha-only runs and digit-only runs; strip whole-word matches
    result = text
    for word in sorted(OCR_STOPWORDS, key=len, reverse=True):
        result = result.replace(word, "")
    return result


def _preprocess_variants(crop_bgr) -> list[tuple[str, "np.ndarray"]]:
    """Return a list of (name, processed_image) variants for OCR.

    Different preprocessing works better on different plates:
      - Original gray       : baseline
      - CLAHE + sharpen     : handles low contrast
      - Otsu binarisation   : crisp black/white, great for clean plates
      - Adaptive threshold  : handles uneven lighting
      - Bilateral denoise   : removes speckle without killing edges
      - Inverted            : for dark plates with light text
    """
    variants = []
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    variants.append(("gray", gray))

    # CLAHE + sharpen
    try:
        clahe_img = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        blur = cv2.GaussianBlur(clahe_img, (0, 0), 1.5)
        sharp = cv2.addWeighted(clahe_img, 1.5, blur, -0.5, 0)
        variants.append(("clahe_sharp", sharp))
    except Exception:
        pass

    # Otsu binarisation
    try:
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(("otsu", otsu))
    except Exception:
        pass

    # Adaptive threshold (Gaussian)
    try:
        adaptive = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 3
        )
        variants.append(("adaptive", adaptive))
    except Exception:
        pass

    # Bilateral denoise
    try:
        bi = cv2.bilateralFilter(gray, 9, 75, 75)
        variants.append(("bilateral", bi))
    except Exception:
        pass

    # Inverted (for dark plates with light text)
    try:
        inverted = cv2.bitwise_not(gray)
        variants.append(("inverted", inverted))
    except Exception:
        pass

    return variants


def _ocr_plate(img, plate_box, debug_ocr: Optional[list] = None,
               debug_crops: Optional[list] = None) -> tuple[str, float]:
    """OCR a plate crop with multi-variant preprocessing.

    Runs EasyOCR across several preprocessing variants and picks the best
    acceptable read. If `debug_ocr` is a list, each candidate (text, conf,
    accepted, variant) is appended. If `debug_crops` is a list, the saved
    plate-crop URL is appended.
    """
    crop = _clip(img, plate_box, pad=OCR_PAD_PX)
    if crop is None or crop.size == 0:
        return "UNKNOWN", 0.0

    # Save the raw plate crop so the user can SEE what's being OCR'd
    if debug_crops is not None:
        try:
            fn = f"{uuid.uuid4().hex}.jpg"
            cv2.imwrite(str(PLATE_CROPS_DIR / fn), crop)
            debug_crops.append(f"/media/plates/{fn}")
        except Exception as e:
            logger.debug("failed to save plate crop: %s", e)

    # Adaptive upscaling: aim for ~400px wide
    h_orig, w_orig = crop.shape[:2]
    target_w = 400
    fx = max(2.0, min(6.0, target_w / max(1, w_orig)))
    crop = cv2.resize(crop, None, fx=fx, fy=fx, interpolation=cv2.INTER_CUBIC)

    reader = _get_ocr_reader()
    if reader is None:
        return "UNKNOWN", 0.0

    def _clean(s: str) -> str:
        s = s.strip().upper().replace(" ", "")
        s = "".join(ch for ch in s if ch.isalnum())
        # Remove jurisdiction/decoration words like PUNJAB, ICT, ISLAMABAD
        return _strip_stopwords(s)

    def _acceptable(text: str, conf: float) -> bool:
        if conf < OCR_MIN_CONF:
            return False
        if not (OCR_MIN_LENGTH <= len(text) <= OCR_MAX_LENGTH):
            return False
        has_alpha = any(c.isalpha() for c in text)
        has_digit = any(c.isdigit() for c in text)
        return has_alpha and has_digit

    all_candidates = []  # (text, conf, variant_name)

    for variant_name, variant_img in _preprocess_variants(crop):
        try:
            detections = reader.readtext(
                variant_img,
                allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            )
        except Exception as e:
            logger.debug("OCR variant %s failed: %s", variant_name, e)
            continue
        if not detections:
            continue

        # Single-best (highest conf) read
        best = max(detections, key=lambda d: d[2])
        all_candidates.append((_clean(best[1]), float(best[2]), variant_name))

        # Concatenated reads left-to-right (handles multi-segment plates)
        if len(detections) > 1:
            sorted_lr = sorted(detections, key=lambda d: d[0][0][0])
            concat = "".join(d[1] for d in sorted_lr)
            avg_conf = sum(d[2] for d in sorted_lr) / len(sorted_lr)
            all_candidates.append((_clean(concat), float(avg_conf), f"{variant_name}+concat"))

    # Record all candidates to debug
    if debug_ocr is not None:
        for text, conf, variant in all_candidates:
            debug_ocr.append({
                "text": text or "(empty)",
                "conf": round(conf, 3),
                "variant": variant,
                "accepted": False,
            })

    # Pick best acceptable
    ok = [(t, c, v) for (t, c, v) in all_candidates if _acceptable(t, c)]

    # If EasyOCR didn't produce anything acceptable, fall back to Tesseract
    if not ok and _tesseract_enabled():
        for variant_name, variant_img in _preprocess_variants(crop):
            text, conf = _ocr_tesseract(variant_img)
            cleaned = _clean(text)
            if debug_ocr is not None:
                debug_ocr.append({
                    "text": cleaned or "(empty)",
                    "conf": round(conf, 3),
                    "variant": f"tesseract+{variant_name}",
                    "accepted": False,
                })
            if _acceptable(cleaned, conf):
                ok.append((cleaned, conf, f"tesseract+{variant_name}"))

    if not ok:
        return "UNKNOWN", 0.0

    ok.sort(key=lambda tcv: (tcv[1], len(tcv[0])), reverse=True)
    picked_text, picked_conf, picked_variant = ok[0]

    if debug_ocr is not None:
        for entry in debug_ocr:
            if entry["text"] == picked_text and entry["variant"] == picked_variant:
                entry["accepted"] = True
                break

    return picked_text, picked_conf


HELMET_CONF_THRESHOLD = 0.55  # raised 0.40→0.55 to cut false positives
                              # (scarves, airbags, random objects triggering "helmet")

# Labels the trained model uses for "rider detected" (the anchor for no_helmet).
RIDER_LABELS = {"motorcyclist", "rider", "person"}


def _check_helmet(head_crop, raw_out: Optional[list] = None) -> tuple[bool, bool]:
    """Returns (worn_detected, not_worn_detected).

    Handles two common helmet-model styles:

    A. Binary classifier (old style): outputs "with helmet" / "without helmet"
       labels. Maps directly to worn / not_worn.

    B. Detection model (new style, our current helmet.pt): outputs `helmet`,
       `motorcyclist`, and optionally `license_plate` boxes. Interpretation:
         - At least one `helmet` above threshold  -> worn = True
         - `motorcyclist` present but no `helmet` -> not_worn = True
         - Neither                                -> both False (inconclusive)

    Only detections above HELMET_CONF_THRESHOLD contribute; raw detections are
    captured in `raw_out` for diagnostic reporting either way.
    """
    model = _get_helmet_model()
    if model is None or head_crop is None or head_crop.size == 0:
        return (False, False)
    res = model(head_crop, verbose=False)

    helmet_hits = 0
    rider_hits = 0
    explicit_worn = False
    explicit_not_worn = False

    for r in res:
        for box in r.boxes:
            raw_label = model.names[int(box.cls[0])]
            label = _normalize_label(raw_label)
            conf = float(box.conf[0])
            if raw_out is not None:
                raw_out.append({"label": raw_label, "conf": round(conf, 3)})
            if conf < HELMET_CONF_THRESHOLD:
                continue

            # Style A: binary classifier labels
            if label in HELMET_WORN and label != "helmet":
                explicit_worn = True
                continue
            if label in HELMET_NOT_WORN:
                explicit_not_worn = True
                continue

            # Style B: detection model labels
            if label == "helmet":
                helmet_hits += 1
            elif label in RIDER_LABELS:
                rider_hits += 1

    # Combine both styles into (worn, not_worn)
    worn = explicit_worn or helmet_hits > 0
    not_worn = explicit_not_worn or (rider_hits > 0 and helmet_hits == 0)
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
                label = _normalize_label(model.names[int(box.cls[0])])
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
def _best_plate_for_vehicle(vehicle_box, plates, match_log: Optional[list] = None):
    """Pick the plate that actually belongs to `vehicle_box`.

    The user's rule: a plate may only be assigned to a vehicle if it is
    INSIDE that vehicle's bounding box. We never fall back to a nearby plate
    from a different vehicle — recording the wrong plate is worse than
    recording UNKNOWN.

    Matching rules (most permissive first, checked in order):
      1. Plate centre lies inside the expanded vehicle bbox
         (expansion = 8% on each side, to catch plates clipped at bike edges)
      2. At least 25% of the plate's area overlaps the expanded bbox
         (handles plates that straddle the vehicle's bbox boundary)

    Within the matched set, we return the highest-confidence plate.

    If `match_log` is a list, an entry is appended for each plate considered,
    stating whether it matched and on which rule.
    """
    if not plates:
        return None

    vx1, vy1, vx2, vy2 = vehicle_box[:4]
    v_w = max(1.0, vx2 - vx1)
    v_h = max(1.0, vy2 - vy1)

    pad_x = v_w * 0.08
    pad_y = v_h * 0.08
    ex1, ey1 = vx1 - pad_x, vy1 - pad_y
    ex2, ey2 = vx2 + pad_x, vy2 + pad_y
    expanded = [ex1, ey1, ex2, ey2]

    inside, overlapping = [], []
    for idx, p in enumerate(plates):
        pcx = (p[0] + p[2]) / 2
        pcy = (p[1] + p[3]) / 2
        centre_in = (ex1 <= pcx <= ex2) and (ey1 <= pcy <= ey2)
        overlap = _overlap_ratio(p[:4], expanded)

        if centre_in:
            inside.append(p)
            result = "matched (centre inside)"
        elif overlap >= 0.25:
            overlapping.append(p)
            result = f"matched (overlap {overlap:.2f})"
        else:
            result = f"rejected (overlap {overlap:.2f}, centre outside)"

        if match_log is not None:
            match_log.append({
                "plate_index": idx,
                "plate_conf": round(p[4], 3),
                "result": result,
            })

    if inside:
        return max(inside, key=lambda p: p[4])
    if overlapping:
        return max(overlapping, key=lambda p: p[4])
    return None


# Back-compat alias (old name used elsewhere)
_nearest_plate = _best_plate_for_vehicle


def _head_region(person_box):
    """Full person bbox - the new helmet model needs enough context to also
    detect the `motorcyclist` class (which needs torso + head in view).
    A too-tight head crop would only let helmet presence trigger, never
    the 'rider without helmet' signal.
    """
    x1, y1, x2, y2 = person_box[:4]
    return [x1, y1, x2, y2]


def _rider_region(person_box, moto_box):
    """Union of a rider's person bbox and the motorcycle bbox.

    This gives the helmet detection model the full scene (head + torso + bike)
    so it can confidently fire both its `motorcyclist` and `helmet` classes.
    """
    return [
        min(person_box[0], moto_box[0]),
        min(person_box[1], moto_box[1]),
        max(person_box[2], moto_box[2]),
        max(person_box[3], moto_box[3]),
    ]


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
    # Per-plate debug details (box, confidence, which model found it)
    # Also save each detected plate crop to disk so the user can SEE them all
    # and visually confirm which one belongs to the violating vehicle.
    all_detected_plate_crops = []
    plates_raw_entries = []
    for idx, p in enumerate(plates):
        entry = {
            "conf": round(p[4], 3),
            "source": p[5] if len(p) > 5 else "unknown",
            "index": idx,
        }
        crop_all = _clip(img, p[:4], pad=2)
        if crop_all is not None and crop_all.size > 0:
            try:
                fn = f"{uuid.uuid4().hex}.jpg"
                cv2.imwrite(str(PLATE_CROPS_DIR / fn), crop_all)
                entry["crop_url"] = f"/media/plates/{fn}"
                all_detected_plate_crops.append(entry["crop_url"])
            except Exception:
                pass
        plates_raw_entries.append(entry)
    debug["plates_raw"] = plates_raw_entries
    debug["all_detected_plate_crops"] = all_detected_plate_crops
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
    ocr_candidates = []  # every OCR attempt, for debug
    plate_crops = []  # URLs of saved plate crops for visual debug
    plate_match_log = []  # per-vehicle plate matching decisions, for debug

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
            # Pass the rider+bike region so the new detection model has enough
            # context to fire both `motorcyclist` and `helmet` classes.
            region = _rider_region(rider, moto)
            region_crop = _clip(img, region, pad=10)
            worn, not_worn = _check_helmet(region_crop, raw_out=raw_helmet_detections)
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
            vehicle_match = {"vehicle_type": "motorcycle", "checks": []}
            plate_box = _best_plate_for_vehicle(moto, plates, match_log=vehicle_match["checks"])
            vehicle_match["matched"] = plate_box is not None
            plate_match_log.append(vehicle_match)
            plate_number, conf = ("UNKNOWN", 0.0)
            if plate_box is not None:
                plate_number, conf = _ocr_plate(
                    img, plate_box,
                    debug_ocr=ocr_candidates, debug_crops=plate_crops,
                )
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
            plate_box = _best_plate_for_vehicle([0, 0, img.shape[1], img.shape[0]], plates)
            plate_number, conf = ("UNKNOWN", 0.0)
            if plate_box is not None:
                plate_number, conf = _ocr_plate(
                    img, plate_box,
                    debug_ocr=ocr_candidates, debug_crops=plate_crops,
                )
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
                vehicle_match = {"vehicle_type": vtype, "checks": []}
                plate_box = _best_plate_for_vehicle(vbox, plates, match_log=vehicle_match["checks"])
                vehicle_match["matched"] = plate_box is not None
                plate_match_log.append(vehicle_match)
                plate_number, conf = ("UNKNOWN", 0.0)
                if plate_box is not None:
                    plate_number, conf = _ocr_plate(
                        img, plate_box,
                        debug_ocr=ocr_candidates, debug_crops=plate_crops,
                    )
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

    # All OCR attempts (including rejected ones) for deep diagnostics
    debug["ocr_candidates"] = ocr_candidates[-40:]
    # Plate-crop image URLs (so frontend can show exactly what was sent to OCR)
    debug["plate_crops"] = plate_crops
    # Per-vehicle plate matching decisions (for visibility on UI)
    debug["plate_match_log"] = plate_match_log

    # Aggregate the final plate read(s) that ended up in violations (all flows)
    debug["ocr_plates"] = [
        {
            "plate": v["plate_number"],
            "conf": round(v.get("confidence", 0), 3),
            "vehicle_type": v.get("vehicle_type", ""),
            "violation_type": v.get("violation_type", ""),
        }
        for v in violations
        if v.get("plate_number") and v["plate_number"] != "UNKNOWN"
    ]

    logger.info(
        "analyze_image: motorcycles=%d cars=%d persons=%d plates=%d "
        "helmet_worn=%d helmet_not_worn=%d violations=%d ocr_reads=%d",
        debug["motorcycles"], debug["cars"], debug["persons"], debug["plates"],
        debug["helmet_worn"], debug["helmet_not_worn"], len(violations),
        len(debug["ocr_plates"]),
    )
    return violations


# --- Backwards-compatible single-result wrapper --------------------------
def analyze_image_first(image_path: Path) -> Optional[dict]:
    """Legacy shim: return only the first violation or None."""
    results = analyze_image(image_path)
    return results[0] if results else None
