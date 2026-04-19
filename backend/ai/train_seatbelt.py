"""Train a YOLOv8 seatbelt detection model.

This script produces `backend/ai/models/seatbelt.pt`, which the inference
pipeline will automatically pick up on next restart (replacing the CV
heuristic).

Usage
-----
    # 1. Install training deps (already in requirements.txt):
    #      pip install ultralytics roboflow

    # 2. Get a free Roboflow API key from https://app.roboflow.com/
    #    (Settings -> Roboflow API -> Private API Key)
    export ROBOFLOW_API_KEY="<your_key>"

    # 3. Run the training script:
    python -m ai.train_seatbelt

    # Or point to an already-downloaded dataset:
    python -m ai.train_seatbelt --data /path/to/data.yaml --epochs 50

The script expects a dataset in standard YOLO format:
    data.yaml        # lists train/val image dirs and class names
    images/train/    # .jpg files
    images/val/
    labels/train/    # matching .txt YOLO label files
    labels/val/

Classes (in data.yaml `names:`) should include at least one of:
    "seatbelt" / "with_seatbelt" / "belt"  -> positive class
    "no_seatbelt" / "without_seatbelt"     -> negative class
(the inference pipeline normalises label names case-insensitively)

Time budget
-----------
On CPU (e.g. M1/M2 Mac): ~1-2 hours for 50 epochs on a 2k-image dataset.
On GPU (CUDA/T4/A100):   ~10-20 minutes.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

AI_DIR = Path(__file__).resolve().parent
MODELS_DIR = AI_DIR / "models"
DEFAULT_PROJECT = AI_DIR / "runs" / "seatbelt"


# ---------------------------------------------------------------------------
# Public Roboflow seatbelt dataset defaults (verified April 2026).
# "seatbelt-detection" by seatbelttraining - 3,489 images, YOLOv8+ compatible.
# Browse: https://universe.roboflow.com/seatbelttraining-7yh0f/seatbelt-detection-lb1ec
# If this becomes unavailable, search https://universe.roboflow.com/search?q=class:seatbelt
# and override with --workspace / --project / --version.
DEFAULT_WORKSPACE = "seatbelttraining-7yh0f"
DEFAULT_PROJECT_NAME = "seatbelt-detection-lb1ec"
DEFAULT_VERSION = 3  # check the project page for the latest version if this fails
# ---------------------------------------------------------------------------


def download_dataset(workspace: str, project_name: str, version: int) -> Path:
    """Download a YOLOv8-formatted dataset from Roboflow, return path to data.yaml."""
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
        raise SystemExit(
            "roboflow package missing. Run: pip install roboflow"
        )
    rf = Roboflow(api_key=api_key)
    project = rf.workspace(workspace).project(project_name)
    dataset = project.version(version).download("yolov8", location=str(AI_DIR / "datasets" / project_name))
    return Path(dataset.location) / "data.yaml"


def train(data_yaml: Path, epochs: int, imgsz: int, project: Path, name: str):
    """Run YOLOv8 training and copy best weights into the models folder."""
    try:
        from ultralytics import YOLO
    except ImportError:
        raise SystemExit("ultralytics not installed. Run: pip install ultralytics")

    model = YOLO("yolov8n.pt")  # transfer-learn from the nano base model
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        project=str(project),
        name=name,
        patience=15,
        verbose=True,
    )

    # Ultralytics saves best.pt here:
    best = project / name / "weights" / "best.pt"
    if not best.exists():
        print(f"⚠ best.pt not found at {best}. Training may have failed.")
        return None

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = MODELS_DIR / "seatbelt.pt"
    shutil.copyfile(best, dest)
    print(f"\n✅ Seatbelt model saved to: {dest}")
    print("Restart Django and the pipeline will use it automatically.")
    return dest


def main():
    parser = argparse.ArgumentParser(description="Train YOLOv8 seatbelt detector")
    parser.add_argument("--data", help="Path to an existing YOLOv8 data.yaml (skips download)")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--name", default="seatbelt-v1")
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
    train(data_yaml, args.epochs, args.imgsz, DEFAULT_PROJECT, args.name)


if __name__ == "__main__":
    sys.exit(main())
