"""Train a YOLOv8 license plate detection model to replace the existing `license_plate.pt`.

The currently-shipped `license_plate.pt` model detects plates but frequently
misses them in busy scenes, falls back to low confidence, and the system
occasionally picks the wrong vehicle's plate. This script retrains a fresh
plate detector on a much larger public dataset (5,750 images) so we get
more reliable plate detections across diverse vehicles, angles, and lighting.

Usage
-----
    # 1. Install optional training deps (already in requirements.txt):
    #      pip install ultralytics roboflow

    # 2. Get a free Roboflow API key:
    #      https://app.roboflow.com -> Settings -> Roboflow API -> Private API Key
    export ROBOFLOW_API_KEY="<your_key>"

    # 3. Run the training script:
    cd backend
    python -m ai.train_plate

    # Or point to an already-downloaded dataset:
    python -m ai.train_plate --data /path/to/data.yaml --epochs 50

The script writes trained weights to `backend/ai/models/license_plate.pt`,
replacing the existing file (a backup is saved to
`backend/ai/models/license_plate.pt.backup` the first time).

Time budget
-----------
CPU (M1/M2 Mac):  ~60-120 minutes for 50 epochs on ~5.7k images.
GPU (CUDA):       ~10-20 minutes.

Alternative datasets
--------------------
If the default project becomes unavailable, browse:
  https://universe.roboflow.com/search?q=class:%22license+plate%22
Pick one with a YOLOv8 export and at least 2k training images, then override:
  python -m ai.train_plate --workspace X --project Y --version Z
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

AI_DIR = Path(__file__).resolve().parent
MODELS_DIR = AI_DIR / "models"
DEFAULT_PROJECT_DIR = AI_DIR / "runs" / "plate"


# ---------------------------------------------------------------------------
# Public Roboflow license plate dataset defaults (verified April 2026).
# "YOLOv8 number plate detection" by ML - 5,750 images, single class.
# Browse: https://universe.roboflow.com/ml-sdznj/yolov8-number-plate-detection
# For a larger alternative (~24k images): VNLP Dataset.
# Override with --workspace / --project / --version as needed.
DEFAULT_WORKSPACE = "ml-sdznj"
DEFAULT_PROJECT_NAME = "yolov8-number-plate-detection"
DEFAULT_VERSION = 1  # check the project page if this fails
# ---------------------------------------------------------------------------


def download_dataset(workspace: str, project_name: str, version: int) -> Path:
    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        raise SystemExit(
            "ROBOFLOW_API_KEY not set.\n"
            "  1. Sign up free at https://roboflow.com\n"
            "  2. Get your key: Settings -> Roboflow API -> Private API Key\n"
            "  3. export ROBOFLOW_API_KEY=<key>"
        )
    try:
        from roboflow import Roboflow
    except ImportError:
        raise SystemExit("roboflow package missing. Run: pip install roboflow")
    rf = Roboflow(api_key=api_key)
    project = rf.workspace(workspace).project(project_name)
    location = AI_DIR / "datasets" / project_name
    dataset = project.version(version).download("yolov8", location=str(location))
    return Path(dataset.location) / "data.yaml"


def backup_existing():
    """Back up the current license_plate.pt the first time we train a new one."""
    existing = MODELS_DIR / "license_plate.pt"
    backup = MODELS_DIR / "license_plate.pt.backup"
    if existing.exists() and not backup.exists():
        shutil.copyfile(existing, backup)
        print(f"Backed up existing license_plate.pt -> {backup}")


def train(data_yaml: Path, epochs: int, imgsz: int, project: Path, name: str):
    try:
        from ultralytics import YOLO
    except ImportError:
        raise SystemExit("ultralytics not installed. Run: pip install ultralytics")

    # Transfer-learn from YOLOv8 nano
    model = YOLO("yolov8n.pt")
    model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        project=str(project),
        name=name,
        patience=15,
        verbose=True,
    )

    best = project / name / "weights" / "best.pt"
    if not best.exists():
        print(f"⚠ best.pt not found at {best}. Training may have failed.")
        return None

    backup_existing()
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = MODELS_DIR / "license_plate.pt"
    shutil.copyfile(best, dest)
    print(f"\n✅ New plate model saved to: {dest}")
    print("Restart Django and the inference pipeline will use it automatically.")
    return dest


def main():
    parser = argparse.ArgumentParser(description="Train YOLOv8 license plate detector")
    parser.add_argument("--data", help="Path to an existing YOLOv8 data.yaml (skips download)")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--name", default="plate-v1")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--project", default=DEFAULT_PROJECT_NAME)
    parser.add_argument("--version", type=int, default=DEFAULT_VERSION)
    args = parser.parse_args()

    if args.data:
        data_yaml = Path(args.data)
        if not data_yaml.exists():
            raise SystemExit(f"--data path not found: {data_yaml}")
    else:
        print(f"Downloading dataset: {args.workspace}/{args.project}/v{args.version}")
        data_yaml = download_dataset(args.workspace, args.project, args.version)
        print(f"  -> {data_yaml}")

    print(f"Training {args.epochs} epochs on {data_yaml}")
    train(data_yaml, args.epochs, args.imgsz, DEFAULT_PROJECT_DIR, args.name)


if __name__ == "__main__":
    sys.exit(main())
