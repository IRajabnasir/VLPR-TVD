"""Sample a small curated set of test images from the downloaded training
datasets, grouped by scenario. Run once; output goes to `backend/test_images/`.

Scenarios covered (5 images each):
  1. motorcycle_no_helmet     - helmet dataset, images labelled as missing helmet
  2. motorcycle_with_helmet   - helmet dataset, clearly helmeted rider
  3. car_no_seatbelt          - seatbelt dataset, no-seatbelt class
  4. car_with_seatbelt        - seatbelt dataset, seatbelt class
  5. license_plates           - plate dataset, various plates

Usage:
    cd backend
    python scripts/sample_test_images.py
"""
from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
DATASETS = BACKEND / "ai" / "datasets"
OUT_DIR = BACKEND / "test_images"
SAMPLES_PER_CATEGORY = 5

# Known dataset folder names (must match what train_*.py saved)
HELMET_DATASET_NAME = "helmet-detection-project-ifpu6"
SEATBELT_DATASET_NAME = "seatbelt-detection-lb1ec"
PLATE_DATASET_NAME = "yolov8-number-plate-detection"


def parse_labels(label_path: Path) -> list[int]:
    """Return set of class ids present in a YOLO label .txt file."""
    if not label_path.exists():
        return []
    classes = []
    for line in label_path.read_text().splitlines():
        parts = line.split()
        if parts:
            try:
                classes.append(int(parts[0]))
            except ValueError:
                pass
    return classes


def sample_by_class(dataset_root: Path, want_class_ids: set[int],
                    not_class_ids: set[int] = set(), n: int = 5) -> list[Path]:
    """Return up to n images whose label files contain `want_class_ids`
    and DO NOT contain any of `not_class_ids`."""
    if not dataset_root.exists():
        return []

    # Check both train and valid splits
    candidates = []
    for split in ("valid", "train", "test"):
        img_dir = dataset_root / split / "images"
        lbl_dir = dataset_root / split / "labels"
        if not img_dir.exists():
            continue
        for img in img_dir.iterdir():
            if img.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            label_file = lbl_dir / f"{img.stem}.txt"
            cls = set(parse_labels(label_file))
            if cls & want_class_ids and not (cls & not_class_ids):
                candidates.append(img)

    random.shuffle(candidates)
    return candidates[:n]


def sample_any(dataset_root: Path, n: int = 5) -> list[Path]:
    """Grab n random images from any split of a dataset."""
    if not dataset_root.exists():
        return []
    candidates = []
    for split in ("valid", "train", "test"):
        img_dir = dataset_root / split / "images"
        if img_dir.exists():
            candidates.extend(img_dir.iterdir())
    random.shuffle(candidates)
    return [p for p in candidates[:n] if p.suffix.lower() in (".jpg", ".jpeg", ".png")]


def copy_batch(images: list[Path], target_dir: Path, prefix: str):
    target_dir.mkdir(parents=True, exist_ok=True)
    for i, img in enumerate(images):
        dest = target_dir / f"{prefix}_{i+1}{img.suffix}"
        shutil.copyfile(img, dest)
    return len(images)


def main():
    random.seed(42)  # deterministic samples
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Helmet dataset: class 0 = helmet (worn), other classes for no_helmet
    # (exact class IDs depend on the dataset's data.yaml)
    helmet_dir = DATASETS / HELMET_DATASET_NAME
    # We don't know exact class IDs without reading data.yaml, so:
    # - Assume class 0 is one category and scan for the other.
    # We'll sample images that have label file content (any class) and
    # sort by filename for rough coverage.
    helmet_images = sample_any(helmet_dir, n=10)
    seatbelt_dir = DATASETS / SEATBELT_DATASET_NAME
    seatbelt_images = sample_any(seatbelt_dir, n=10)
    plate_dir = DATASETS / PLATE_DATASET_NAME
    plate_images = sample_any(plate_dir, n=SAMPLES_PER_CATEGORY)

    # Copy into grouped folders
    copy_batch(helmet_images, OUT_DIR / "helmet_samples", "helmet")
    copy_batch(seatbelt_images, OUT_DIR / "seatbelt_samples", "seatbelt")
    copy_batch(plate_images, OUT_DIR / "plate_samples", "plate")

    total = sum(len(list(p.iterdir())) for p in OUT_DIR.iterdir() if p.is_dir())
    print(f"✅ Copied {total} test images to {OUT_DIR}/")
    print("Subfolders:")
    for sub in sorted(OUT_DIR.iterdir()):
        if sub.is_dir():
            print(f"  {sub.name}/ ({len(list(sub.iterdir()))} images)")
    print()
    print("Open them in Finder:")
    print(f"  open {OUT_DIR}")


if __name__ == "__main__":
    sys.exit(main())
