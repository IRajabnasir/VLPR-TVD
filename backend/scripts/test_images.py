"""Batch image tester for the VLPR-TVD pipeline.

Runs any number of images through the full detection pipeline WITHOUT
needing Django or the frontend to be running. Prints a concise colored
summary per image plus a final pass/fail table.

Usage
-----
    # Single image
    python scripts/test_images.py path/to/image.jpg

    # Multiple images (shell glob)
    python scripts/test_images.py ~/Downloads/*.jpg

    # Whole directory
    python scripts/test_images.py test_images/

    # With expectations from filename hints:
    #   "motorcycle_no_helmet_*.jpg"  -> expect no_helmet violation
    #   "*_with_helmet*.jpg"          -> expect NO violation
    #   "car_no_seatbelt_*.jpg"       -> expect no_seatbelt violation
    #   "*_with_seatbelt*.jpg"        -> expect NO violation
    # The script auto-reports pass/fail vs the hint in filenames.

    # JSON output (pipe into jq or save):
    python scripts/test_images.py test_images/ --json > results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make backend/ importable so `from ai.infer import ...` works
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ANSI colors (fallback to no colors if not a TTY)
if sys.stdout.isatty():
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
else:
    GREEN = RED = YELLOW = BLUE = MAGENTA = CYAN = BOLD = DIM = RESET = ""


def expected_from_filename(name: str) -> str | None:
    """Infer expected outcome from filename conventions."""
    n = name.lower()
    if "with_helmet" in n or "helmet_worn" in n or "with-helmet" in n:
        return "none"
    if "no_helmet" in n or "without_helmet" in n or "no-helmet" in n:
        return "no_helmet"
    if "with_seatbelt" in n or "seatbelt_worn" in n or "with-seatbelt" in n:
        return "none"
    if "no_seatbelt" in n or "without_seatbelt" in n or "no-seatbelt" in n:
        return "no_seatbelt"
    return None  # unknown / user will eyeball


def gather_images(args: list[str]) -> list[Path]:
    """Expand args (files, globs, dirs) into a flat list of image paths."""
    out = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
                out.extend(sorted(p.rglob(ext)))
        elif p.exists():
            out.append(p)
        else:
            # try shell-style glob
            out.extend(sorted(Path().glob(a)))
    return [p for p in out if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]


def format_violation(v: dict) -> str:
    plate = v.get("plate_number", "UNKNOWN")
    vtype = v.get("vehicle_type", "?")
    viol = v.get("violation_type", "?")
    conf = v.get("confidence", 0.0)
    return f"{vtype}/{viol} plate={plate} (ocr_conf={conf:.2f})"


def pretty_print(path: Path, violations: list[dict], debug: dict, expected: str | None):
    name = path.name
    print(f"\n{BOLD}{CYAN}▶ {name}{RESET}  {DIM}({path}){RESET}")

    # Counts
    print(
        f"  {DIM}Detections:{RESET} "
        f"motorcycles={debug.get('motorcycles', 0)} "
        f"cars={debug.get('cars', 0)} "
        f"trucks={debug.get('trucks', 0)} "
        f"buses={debug.get('buses', 0)} "
        f"persons={debug.get('persons', 0)} "
        f"plates={debug.get('plates', 0)}"
    )

    # Helmet summary
    hw = debug.get("helmet_worn", 0)
    hnw = debug.get("helmet_not_worn", 0)
    print(f"  {DIM}Helmet:{RESET} worn={hw} not_worn={hnw}")

    # Seatbelt mode
    mode = debug.get("seatbelt_mode", "?")
    snw = debug.get("seatbelt_not_worn", 0)
    print(f"  {DIM}Seatbelt:{RESET} mode={mode} not_worn={snw}")

    # Plate match log
    for v in debug.get("plate_match_log", []):
        vt = v.get("vehicle_type", "?")
        matched = "✓" if v.get("matched") else "✗"
        col = GREEN if v.get("matched") else YELLOW
        print(f"  {DIM}Plate matching:{RESET} {col}{vt} {matched}{RESET}")
        for c in v.get("checks", []):
            col_c = GREEN if "matched" in c.get("result", "") else DIM
            print(
                f"    {col_c}plate#{c.get('plate_index')} "
                f"conf={c.get('plate_conf')} → {c.get('result')}{RESET}"
            )

    # Violations
    if violations:
        print(f"  {GREEN}Violations ({len(violations)}):{RESET}")
        for v in violations:
            print(f"    • {format_violation(v)}")
    else:
        print(f"  {YELLOW}Violations: none{RESET}")

    # Unconditional OCR results (if --ocr-all-plates)
    if debug.get("unconditional_ocr"):
        print(f"  {MAGENTA}All-plates OCR:{RESET}")
        for r in debug["unconditional_ocr"]:
            text = r["ocr_text"]
            col = GREEN if text != "UNKNOWN" else DIM
            print(
                f"    {col}plate#{r['plate_index']} det={r['detection_conf']} "
                f"src={r['source']} → {text} (ocr_conf={r['ocr_conf']}){RESET}"
            )

    # Pass/fail vs expectation
    if expected is not None:
        actual_types = {v.get("violation_type") for v in violations}
        if expected == "none":
            ok = len(violations) == 0
        else:
            ok = expected in actual_types
        tag = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(
            f"  {DIM}Expected:{RESET} {expected}  "
            f"{DIM}Actual:{RESET} {','.join(actual_types) or 'none'}  "
            f"[{tag}]"
        )
        return ok
    return None


def main():
    parser = argparse.ArgumentParser(description="Batch-test the VLPR-TVD pipeline")
    parser.add_argument("paths", nargs="+", help="image files, directories, or globs")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--quiet", action="store_true", help="only show summary line per image")
    parser.add_argument(
        "--ocr-all-plates", action="store_true",
        help="OCR every detected plate, even if no violation fired. "
             "Useful for testing OCR on close-up plate images.",
    )
    args = parser.parse_args()

    images = gather_images(args.paths)
    if not images:
        print(f"{RED}No images found in:{RESET} {args.paths}")
        return 1

    # Delayed imports so --help works even without the ML deps loaded
    from ai.infer import analyze_image, _detect_plates, _ocr_plate
    import cv2

    results = []
    print(f"{BOLD}Testing {len(images)} image(s) through the full pipeline...{RESET}")
    if args.ocr_all_plates:
        print(f"{DIM}(--ocr-all-plates: every detected plate will be OCR'd){RESET}")

    pass_count = fail_count = unknown_count = 0

    for img_path in images:
        debug = {}
        try:
            violations = analyze_image(img_path, debug=debug)
        except Exception as e:
            print(f"{RED}ERROR on {img_path.name}: {e}{RESET}")
            results.append({"image": str(img_path), "error": str(e)})
            continue

        # Optional: OCR every detected plate regardless of violation
        if args.ocr_all_plates:
            img = cv2.imread(str(img_path))
            if img is not None:
                plates = _detect_plates(img)
                debug.setdefault("unconditional_ocr", [])
                for i, p in enumerate(plates):
                    text, conf = _ocr_plate(img, p)
                    debug["unconditional_ocr"].append({
                        "plate_index": i,
                        "detection_conf": round(p[4], 3),
                        "source": p[5] if len(p) > 5 else "?",
                        "ocr_text": text,
                        "ocr_conf": round(conf, 3),
                    })

        expected = expected_from_filename(img_path.name)
        result = {
            "image": str(img_path),
            "expected": expected,
            "violations": violations,
            "debug": debug,
        }
        results.append(result)

        if args.json:
            continue

        ok = pretty_print(img_path, violations, debug, expected)
        if ok is True:
            pass_count += 1
        elif ok is False:
            fail_count += 1
        else:
            unknown_count += 1

    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return 0

    # Final summary
    total = len(images)
    print()
    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{BOLD}Summary:{RESET} {total} image(s) processed")
    if pass_count or fail_count:
        print(
            f"  {GREEN}✓ {pass_count} passed{RESET}  "
            f"{RED}✗ {fail_count} failed{RESET}  "
            f"{DIM}? {unknown_count} no expectation{RESET}"
        )
    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
