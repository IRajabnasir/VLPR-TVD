"""Heuristic seatbelt detector.

Used as a fallback when a trained `seatbelt.pt` YOLO model isn't available.

Approach
--------
1. Run YOLOv8-pose on the car cabin crop to find the driver's keypoints.
   COCO-pose keypoints used:
     5 = left_shoulder, 6 = right_shoulder
    11 = left_hip, 12 = right_hip
2. A seat belt, when worn, runs diagonally from one shoulder to the opposite
   hip. We sample a narrow band along that virtual line and check for a
   strong, coherent edge signature (Canny + HoughLinesP whose angles match
   the expected belt angle).
3. If the edge density / line count along that diagonal is above a threshold
   we say "seatbelt worn", otherwise we say "no seatbelt".

This is obviously not as accurate as a properly trained model, but it works
out-of-the-box with no dataset / training time, and fails gracefully (never
raises). The output shape mirrors the ML path so the pipeline code doesn't
care which one is active.

Return contract (same as the ML path):
    (worn: bool, not_worn: bool)

If we can't even find a driver, we return (False, False) which the pipeline
treats as "inconclusive, don't raise a violation".
"""
from __future__ import annotations

import logging
import math
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

AI_DIR = Path(__file__).resolve().parent
POSE_WEIGHTS = AI_DIR / "yolov8n-pose.pt"   # auto-downloaded by ultralytics on first run

# COCO-pose keypoint indices
KP_L_SHOULDER = 5
KP_R_SHOULDER = 6
KP_L_HIP = 11
KP_R_HIP = 12

# Tuning knobs. These numbers come from experimenting with a mix of
# daytime in-car photos. Consider these rough starting points - retune
# for your exact camera angle / lighting if needed.
EDGE_DENSITY_THRESHOLD = 0.06     # fraction of diag-band pixels that are Canny edges
MIN_DIAGONAL_LINES = 1            # Hough lines at belt-like angles needed to confirm
BAND_WIDTH_FRAC = 0.12            # width of the diagonal sample band as fraction of torso width
BELT_ANGLE_TOL_DEG = 25           # how close a Hough line's angle must be to the shoulder-hip axis


_pose_model = None


def _get_pose_model():
    """Lazy-load yolov8n-pose. Returns None if ultralytics or weights can't be had."""
    global _pose_model
    if _pose_model is None:
        try:
            from ultralytics import YOLO
            # ultralytics auto-downloads yolov8n-pose.pt on first call if missing.
            _pose_model = YOLO("yolov8n-pose.pt")
            logger.info("Loaded YOLOv8-pose for seatbelt heuristic")
        except Exception as e:
            logger.warning("pose model unavailable (%s); seatbelt heuristic disabled", e)
            _pose_model = False
    return _pose_model if _pose_model else None


def _pick_driver(keypoints_list):
    """Pick the largest-torso person - usually the driver in a dash/front shot."""
    best = None
    best_area = 0
    for kps in keypoints_list:
        if kps is None or len(kps) < 13:
            continue
        ls, rs = kps[KP_L_SHOULDER], kps[KP_R_SHOULDER]
        lh, rh = kps[KP_L_HIP], kps[KP_R_HIP]
        # require shoulders and at least one hip to be visible (conf > 0.3 implicit via non-zero)
        if min(ls[2] if len(ls) > 2 else 0, rs[2] if len(rs) > 2 else 0) < 0.3:
            continue
        shoulder_width = abs(ls[0] - rs[0])
        torso_height = max(abs(ls[1] - lh[1]) if len(lh) > 2 and lh[2] > 0.3 else 0,
                           abs(rs[1] - rh[1]) if len(rh) > 2 and rh[2] > 0.3 else 0)
        area = shoulder_width * torso_height
        if area > best_area:
            best_area = area
            best = kps
    return best


def _sample_diagonal_band(edges: np.ndarray, p1, p2, band_px: int):
    """Return the mean edge-density in a band of width `band_px` centred on the p1->p2 line."""
    h, w = edges.shape[:2]
    x1, y1 = int(p1[0]), int(p1[1])
    x2, y2 = int(p2[0]), int(p2[1])
    # Build a mask that's 1 inside the band, 0 outside.
    mask = np.zeros_like(edges, dtype=np.uint8)
    cv2.line(mask, (x1, y1), (x2, y2), 255, band_px)
    band_area = int(np.count_nonzero(mask))
    if band_area == 0:
        return 0.0
    edge_hits = int(np.count_nonzero(cv2.bitwise_and(edges, mask)))
    return edge_hits / band_area


def _count_matching_hough_lines(edges: np.ndarray, target_angle_deg: float) -> int:
    """Count Hough line segments whose orientation matches the target diagonal."""
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=40,
        minLineLength=20,
        maxLineGap=5,
    )
    if lines is None:
        return 0
    count = 0
    for line in lines:
        x1, y1, x2, y2 = line[0]
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            continue
        angle = math.degrees(math.atan2(dy, dx))
        # Normalise to [-90, 90]
        if angle > 90:
            angle -= 180
        if angle < -90:
            angle += 180
        if abs(angle - target_angle_deg) <= BELT_ANGLE_TOL_DEG:
            count += 1
    return count


def check_seatbelt(cabin_crop) -> tuple[bool, bool]:
    """Return (worn_detected, not_worn_detected) for a driver-cabin image crop.

    (False, False) means "inconclusive" - no driver found or signal unusable.
    """
    if cabin_crop is None or cabin_crop.size == 0:
        return (False, False)

    model = _get_pose_model()
    if model is None:
        return (False, False)

    try:
        results = model(cabin_crop, verbose=False, conf=0.25)
    except Exception as e:
        logger.warning("pose inference failed: %s", e)
        return (False, False)

    # Collect keypoints from all detected persons
    all_kps = []
    for r in results:
        if r.keypoints is None:
            continue
        # keypoints.data shape: (num_persons, 17, 3) where last dim is (x, y, conf)
        try:
            data = r.keypoints.data.cpu().numpy()
        except Exception:
            data = np.asarray(r.keypoints.data)
        for person in data:
            all_kps.append(person.tolist())

    driver = _pick_driver(all_kps)
    if driver is None:
        return (False, False)

    ls = driver[KP_L_SHOULDER]
    rs = driver[KP_R_SHOULDER]
    lh = driver[KP_L_HIP]
    rh = driver[KP_R_HIP]

    # Choose the more confident shoulder/hip diagonal.
    # Belt typically runs from the driver's LEFT shoulder to RIGHT hip (left-hand drive)
    # but we try both combinations and pick the one with the stronger signal.
    candidates = []
    if (len(ls) > 2 and ls[2] > 0.3) and (len(rh) > 2 and rh[2] > 0.3):
        candidates.append((ls[:2], rh[:2]))
    if (len(rs) > 2 and rs[2] > 0.3) and (len(lh) > 2 and lh[2] > 0.3):
        candidates.append((rs[:2], lh[:2]))

    if not candidates:
        return (False, False)

    gray = cv2.cvtColor(cabin_crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(gray, 60, 160)

    best_density = 0.0
    best_line_count = 0
    shoulder_width = max(1.0, abs(ls[0] - rs[0]) if len(rs) > 2 else 60)
    band_px = max(4, int(BAND_WIDTH_FRAC * shoulder_width))

    for p1, p2 in candidates:
        density = _sample_diagonal_band(edges, p1, p2, band_px)
        angle = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
        if angle > 90:
            angle -= 180
        if angle < -90:
            angle += 180
        line_count = _count_matching_hough_lines(edges, angle)
        if density > best_density:
            best_density = density
            best_line_count = line_count

    logger.debug(
        "seatbelt heuristic: density=%.3f line_count=%d (thr=%.2f / %d)",
        best_density, best_line_count, EDGE_DENSITY_THRESHOLD, MIN_DIAGONAL_LINES,
    )

    worn = (
        best_density >= EDGE_DENSITY_THRESHOLD
        and best_line_count >= MIN_DIAGONAL_LINES
    )
    # "Inconclusive" (neither strong yes nor strong no) is reported as not_worn
    # only if the signal is clearly weak. Otherwise leave both False so we
    # don't raise spurious violations.
    not_worn = (
        best_density < EDGE_DENSITY_THRESHOLD * 0.5
        and best_line_count == 0
    )
    return (worn, not_worn)
