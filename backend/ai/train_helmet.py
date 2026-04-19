"""Train a YOLOv8 helmet detection model to replace the broken `helmet.pt`.

The currently-shipped `helmet.pt` model was trained on a narrow dataset and
false-positives badly on bare-headed riders (and even on images with no
heads in frame). This script replaces it with a freshly trained model using
a much larger public helmet dataset from Roboflow.

Usage
-----
    # 1. Optional training deps (already in requirements.txt):
    #      pip install ultralytics roboflow

    # 2. Get a free Roboflow API key:
    #      https://app.roboflow.com -> Settings -> Roboflow API -> Private API Key
    export ROBOFLOW_API_KEY="<your_key>"

    # 3. Run the training script:
    cd backend
    python -m ai.train_helmet

    # Or point to an already-downloaded dataset:
    python -m ai.train_helmet --data /path/to/data.yaml --epochs 50

The script writes the trained weights to `backend/ai/models/helmet.pt`,
**replacing** the existing file (a backup is saved to
`backend/ai/models/helmet.pt.backup` the first time you run this).

Time budget
-----------
CPU (M1/M2 Mac):  ~45–90 minutes for 50 epochs on a 3k-image dataset.
GPU (CUDA):       ~10–15 minutes.

Dataset notes
-------------
The default Roboflow project is a popular public helmet detection dataset
with binary classes (helmet / no_helmet). If the specific project/version
below has become private or changed, browse Roboflow Universe for another
one and override with `--workspace --project --version`:

    https://universe.roboflow.com/search?q=helmet+detection
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

AI_DIR = Path(__file__).resolve().parent
MODELS_DIR = AI_DIR / "models"
DEFAULT_PROJECT_DIR = AI_DIR / "runs" / "helmet"


# ---------------------------------------------------------------------------
# Public Roboflow helmet dataset defaults (verified April 2026).
# "Helmet Detection Project" - 761 motorbike-focused images, binary classes.
# Browse: https://universe.roboflow.com/object-detection-using-yolov8/helmet-detection-project-ifpu6
# If this becomes unavailable, search https://universe.roboflow.com/search?q=class:helmet
# and override with --workspace / --project / --version.
DEFAULT_WORKSPACE = "object-detection-using-yolov8"
DEFAULT_PROJECT_NAME = "helmet-detection-project-ifpu6"
DEFAULT_VERSION = 1  # check the project page for the latest version if this fails
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
    """Back up the current helmet.pt the first time we train a new one."""
    existing = MODELS_DIR / "helmet.pt"
    backup = MODELS_DIR / "helmet.pt.backup"
    if existing.exists() and not backup.exists():
        shutil.copyfile(existing, backup)
        print(f"Backed up existing helmet.pt -> {backup}")


def train(data_yaml: Path, epochs: int, imgsz: int, project: Path, name: str):
    try:
        from ultralytics import YOLO
    except ImportError:
        raise SystemExit("ultralytics not installed. Run: pip install ultralytics")

    # Transfer-learn from the YOLOv8 nano base model (small + fast)
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
    dest = MODELS_DIR / "helmet.pt"
    shutil.copyfile(best, dest)
    print(f"\n✅ New helmet model saved to: {dest}")
    print("Restart Django and the inference pipeline will use it automatically.")
    return dest


def main():
    parser = argparse.ArgumentParser(description="Train YOLOv8 helmet detector")
    parser.add_argument("--data", help="Path to an existing YOLOv8 data.yaml (skips download)")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--name", default="helmet-v1")
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
