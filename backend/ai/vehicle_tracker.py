"""Frame-to-frame vehicle tracking for speed estimation (v2).

Design
------
A lightweight IoU-based tracker. For each frame we receive vehicle bboxes
and match them to existing tracks by picking the highest-IoU track per
detection. Unmatched detections start a new track. Tracks that don't get
a match for N seconds are dropped.

From the last two centroid positions of a track we compute pixel velocity,
then convert to km/h using a user-provided calibration (pixels-per-meter).
Calibration is very rough but fine for a FYP demo — the point is to show
the system can surface a speed estimate and flag over-the-limit vehicles.

Thresholds / calibration are configurable via env vars:

    VLPR_PIXELS_PER_METER   (default: 50)     rough visual calibration
    VLPR_SPEED_LIMIT_KMH    (default: 60)     speed above this -> violation
    VLPR_SPEED_MIN_FRAMES   (default: 3)      need N frames before computing speed

Usage
-----
    from ai.vehicle_tracker import update_tracks

    tracks = update_tracks(
        session_id="abc",
        detections=[{"vehicle_type": "car", "bbox": [x1,y1,x2,y2]}, ...],
    )
    for t in tracks:
        if t["speed_kmh"] and t["speed_kmh"] > limit:
            ...  # emit over_speed violation
"""
from __future__ import annotations

import os
import time
import uuid
from collections import defaultdict
from threading import Lock
from typing import Optional

# ---- Config (env-overridable) ----
PIXELS_PER_METER = float(os.environ.get("VLPR_PIXELS_PER_METER", "50"))
SPEED_LIMIT_KMH = float(os.environ.get("VLPR_SPEED_LIMIT_KMH", "60"))
SPEED_MIN_FRAMES = int(os.environ.get("VLPR_SPEED_MIN_FRAMES", "3"))
TRACK_MAX_AGE_SEC = float(os.environ.get("VLPR_TRACK_MAX_AGE_SEC", "3.0"))
IOU_MATCH_THRESHOLD = float(os.environ.get("VLPR_IOU_MATCH_THRESHOLD", "0.3"))

# Internal state: session_id -> list of active tracks
# Each track: dict with keys: id, vehicle_type, positions, speed_kmh, last_seen
_sessions: dict[str, list[dict]] = defaultdict(list)
_lock = Lock()


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


def _centroid(bbox):
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def _compute_speed_kmh(positions: list[tuple[float, float, float]]) -> float:
    """positions = list of (x_px, y_px, timestamp). Uses the last two only."""
    if len(positions) < SPEED_MIN_FRAMES:
        return 0.0
    # Average over last few frames for stability
    recent = positions[-SPEED_MIN_FRAMES:]
    (x1, y1, t1) = recent[0]
    (x2, y2, t2) = recent[-1]
    dt = t2 - t1
    if dt <= 0:
        return 0.0
    dx, dy = x2 - x1, y2 - y1
    pixel_distance = (dx * dx + dy * dy) ** 0.5
    px_per_sec = pixel_distance / dt
    meters_per_sec = px_per_sec / max(PIXELS_PER_METER, 1.0)
    return meters_per_sec * 3.6  # m/s -> km/h


def update_tracks(
    session_id: Optional[str],
    detections: list[dict],
) -> list[dict]:
    """Advance the tracker for a session with this frame's detections.

    Returns augmented detection dicts with added keys:
        track_id, speed_kmh, is_over_speed
    """
    if not session_id:
        # No tracking without a session — just echo detections
        return [
            {**d, "track_id": None, "speed_kmh": 0.0, "is_over_speed": False}
            for d in detections
        ]

    now = time.monotonic()
    with _lock:
        # Expire old tracks
        tracks = _sessions.get(session_id, [])
        tracks = [t for t in tracks if (now - t["last_seen"]) <= TRACK_MAX_AGE_SEC]

        # Greedy IoU matching: for each detection, find best-IoU track
        # that hasn't been claimed by a higher-IoU detection yet.
        unclaimed = list(range(len(tracks)))
        matched: dict[int, int] = {}  # detection_idx -> track_idx

        # Sort detections by bbox area (bigger first, more confident)
        det_order = sorted(
            range(len(detections)),
            key=lambda i: -(
                (detections[i]["bbox"][2] - detections[i]["bbox"][0])
                * (detections[i]["bbox"][3] - detections[i]["bbox"][1])
            ),
        )

        for di in det_order:
            det = detections[di]
            best_j, best_score = -1, IOU_MATCH_THRESHOLD
            # First pass: IoU matching
            for j in unclaimed:
                if tracks[j]["vehicle_type"] != det["vehicle_type"]:
                    continue
                s = _iou(det["bbox"], tracks[j]["last_bbox"])
                if s > best_score:
                    best_j, best_score = j, s
            # Second pass: if no IoU match, fall back to centroid proximity
            # (handles fast-moving vehicles where boxes don't overlap frame-to-frame)
            if best_j < 0:
                dcx, dcy = _centroid(det["bbox"])
                # Accept if centroid is within half a bbox-diagonal
                d_diag = (
                    (det["bbox"][2] - det["bbox"][0]) ** 2
                    + (det["bbox"][3] - det["bbox"][1]) ** 2
                ) ** 0.5
                best_dist = d_diag * 0.6
                for j in unclaimed:
                    if tracks[j]["vehicle_type"] != det["vehicle_type"]:
                        continue
                    tcx, tcy = _centroid(tracks[j]["last_bbox"])
                    dist = ((dcx - tcx) ** 2 + (dcy - tcy) ** 2) ** 0.5
                    if dist < best_dist:
                        best_j, best_dist = j, dist
            if best_j >= 0:
                matched[di] = best_j
                unclaimed.remove(best_j)

        # Update matched tracks; create new tracks for unmatched detections
        augmented = []
        for di, det in enumerate(detections):
            cx, cy = _centroid(det["bbox"])
            if di in matched:
                t = tracks[matched[di]]
                t["positions"].append((cx, cy, now))
                t["last_bbox"] = list(det["bbox"])
                t["last_seen"] = now
                # Keep positions bounded
                if len(t["positions"]) > 20:
                    t["positions"] = t["positions"][-20:]
                t["speed_kmh"] = _compute_speed_kmh(t["positions"])
                track = t
            else:
                track = {
                    "id": uuid.uuid4().hex[:8],
                    "vehicle_type": det["vehicle_type"],
                    "positions": [(cx, cy, now)],
                    "last_bbox": list(det["bbox"]),
                    "last_seen": now,
                    "speed_kmh": 0.0,
                }
                tracks.append(track)

            augmented.append({
                **det,
                "track_id": track["id"],
                "speed_kmh": round(track["speed_kmh"], 1),
                "is_over_speed": track["speed_kmh"] > SPEED_LIMIT_KMH,
            })

        _sessions[session_id] = tracks
        return augmented


def get_session_tracks(session_id: str) -> list[dict]:
    """Debug helper: current active tracks for a session."""
    now = time.monotonic()
    with _lock:
        return [
            {
                "id": t["id"],
                "vehicle_type": t["vehicle_type"],
                "frames": len(t["positions"]),
                "speed_kmh": round(t["speed_kmh"], 1),
                "age_sec": round(now - t["last_seen"], 2),
            }
            for t in _sessions.get(session_id, [])
        ]


def clear_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)
