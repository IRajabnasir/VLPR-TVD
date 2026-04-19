# VLPR-TVD — Vehicle License Plate Recognition & Traffic Violation Detection

Final Year Project · Department of Computer Science · University of Gujrat
Session: BSCS 2022–2026 · Advisor: Mr. Adeel Ahmed

A full-stack traffic intelligence system with **two detection flows**:

- **Motorcycles** → detect helmet violations + OCR the license plate.
- **Cars / trucks / buses** → detect seatbelt violations + OCR the license plate.

Built on Django REST Framework + YOLOv8 + EasyOCR, with a React + Vite + Tailwind
admin dashboard.

## Project Layout

```
FYP_Integrated/
├── backend/                      Django + DRF + YOLO inference
│   ├── ai/
│   │   ├── infer.py              dual motorcycle+car pipeline
│   │   ├── seatbelt_heuristic.py CV fallback when seatbelt.pt absent
│   │   ├── train_seatbelt.py     train seatbelt.pt from a Roboflow dataset
│   │   ├── models/               helmet.pt, license_plate.pt, (seatbelt.pt)
│   │   └── yolov8n.pt            COCO base model (vehicles + persons)
│   ├── config/                   Django project (settings, urls, asgi, wsgi)
│   ├── core/                     Main app (models, views, API, auth, stats)
│   ├── media/                    Violation evidence images (runtime)
│   ├── manage.py
│   └── requirements.txt
└── frontend/                     React 19 + Vite + Tailwind
    ├── src/
    │   ├── Components/           Sidebar, AdminLayout, Navbar, Logo, …
    │   ├── Pages/                Home, About, Contact, Login, Dashboard,
    │   │                         LiveMonitoring, ViolationDetection,
    │   │                         ViolationRecords, EvidenceManagement
    │   ├── api.js                Central API helper (JWT + auto-refresh)
    │   └── App.jsx
    └── package.json
```

## Prerequisites

* Python 3.10+
* Node 18+
* Optional: PostgreSQL 14+ (SQLite is used by default for dev)

## Backend — one-time setup

```bash
cd backend
python -m venv venv
source venv/bin/activate                # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                    # edit as needed
python manage.py migrate
python manage.py createsuperuser        # create your admin login
```

On first call to `/api/analyze/`, YOLO weights are loaded lazily:
`ai/yolov8n.pt`, `ai/models/helmet.pt`, `ai/models/license_plate.pt` must be
present (they're included in the repo). `ai/models/seatbelt.pt` is optional —
see "Seatbelt model" below.

### Run the backend

```bash
python manage.py runserver 8000
```

### API

All endpoints are under `/api/`. Everything except `/auth/login/` requires a
JWT in `Authorization: Bearer <access>`.

| Method | Path                   | Description |
|--------|------------------------|-------------|
| POST   | `/auth/login/`         | `{username, password}` → `{access, refresh}` |
| POST   | `/auth/refresh/`       | Refresh access token |
| GET    | `/auth/me/`            | Current user |
| POST   | `/analyze/`            | Multipart `image` upload → runs both flows, returns `{violations: [...]}` (possibly empty) |
| POST   | `/detections/`         | Manual violation creation (JSON body) |
| GET    | `/stats/`              | Dashboard aggregates |
| GET/POST/PATCH/DELETE | `/vehicles/`   | Vehicle CRUD |
| GET/POST/PATCH/DELETE | `/violations/` | Violation CRUD |
| POST   | `/violations/<id>/review/`  | Mark reviewed |
| POST   | `/violations/<id>/complete/`| Finalize |
| POST   | `/violations/<id>/reject/`  | Discard |

## Frontend — one-time setup

```bash
cd frontend
npm install
```

### Run the frontend

```bash
npm run dev
```

Vite serves at http://localhost:5173. Override the backend base URL with
`VITE_API_BASE` in `frontend/.env` if needed.

### Pages

Public routes (top-navbar layout):
- `/` — Home (hero + capabilities)
- `/about` — Project modules, tech stack, team info
- `/contact` — Contact form + team directory
- `/login` — Admin login

Authenticated routes (sidebar layout, auto-redirect if not logged in):
- `/dashboard` — Stats cards, lifecycle breakdown, recent alerts
- `/live-monitoring` — Camera feed only
- `/violation-detection` — Camera + manual/auto detection + live feed
- `/violation-records` — Full violation table with filters & actions
- `/evidence` — Gallery of evidence images with modal detail view

## Detection pipeline

### Motorcycle flow
1. YOLOv8n COCO detects motorcycles (class 3) + persons (class 0).
2. Riders = persons whose bbox overlaps the motorcycle bbox.
3. `helmet.pt` runs on each rider's head crop (top 35% of person bbox).
4. `license_plate.pt` runs on the motorcycle region; nearest plate by
   bbox-center distance is OCR'd with EasyOCR.
5. No helmet → Violation with `violation_type="no_helmet"`,
   `vehicle_type="motorcycle"`, plate + evidence image saved.

### Car / truck / bus flow
1. YOLOv8n COCO detects cars (2), buses (5), trucks (7).
2. Upper-front ~55% of the vehicle bbox = approximate driver cabin region.
3. **Seatbelt check** (best available path):
   - If `ai/models/seatbelt.pt` is present → trained YOLO model runs on the
     cabin region.
   - Otherwise → `seatbelt_heuristic.py` runs:
     (a) YOLOv8n-pose finds the driver's shoulder + hip keypoints,
     (b) Canny edges + Hough line transform looks for the diagonal belt
         signature between opposite shoulder and hip,
     (c) threshold on edge-density + matching-line count decides worn/not.
   - If neither is available → car flow is skipped gracefully.
4. Nearest license plate OCR'd.
5. No seatbelt → Violation with `violation_type="no_seatbelt"`,
   `vehicle_type="car" | "truck" | "bus"`.

## Seatbelt model

Two paths — pick whichever fits your deadline:

### Path A — Heuristic only (works NOW, no training)

Do nothing. The CV heuristic in `ai/seatbelt_heuristic.py` runs automatically
when `seatbelt.pt` isn't present. Accuracy is modest but it demos the full
pipeline end-to-end. First run will auto-download `yolov8n-pose.pt` (~6 MB).

### Path B — Train a real YOLO model

Gives you a real ML detector in ~1–2 hours on CPU or ~15 minutes on GPU.

```bash
# 1. Install the optional training dep
pip install roboflow

# 2. Sign up free at https://roboflow.com
#    Get your private API key: Settings -> Roboflow API
export ROBOFLOW_API_KEY=<your_key>

# 3. Train (downloads a public seatbelt dataset automatically)
cd backend
python -m ai.train_seatbelt --epochs 50

# 4. Restart Django — the new model is auto-loaded next /analyze/ call
```

The script writes `ai/models/seatbelt.pt`. To use your own dataset instead of
the default Roboflow one, pass `--data /path/to/data.yaml`.

## Database — PostgreSQL (optional)

Set in `backend/.env`:

```
DB_ENGINE=postgresql
DB_NAME=vlpr_tvd
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=5432
```

Then `python manage.py migrate`.

## End-to-end flow

1. `cd backend && python manage.py runserver` — API at http://127.0.0.1:8000.
2. `cd frontend && npm run dev` — React at http://localhost:5173.
3. Login with your admin credentials → redirected to `/dashboard`.
4. Sidebar → **Violation Detection** → Start Camera → either press "Detect
   Now" or enable auto-detect (e.g. every 3 seconds).
5. Point a motorcycle photo at the camera → helmet+plate violations appear.
   Point a car photo → seatbelt+plate violations appear.
6. **Violation Records** lists everything with search & filters, status
   actions (Review/Reject/Complete).
7. **Evidence Management** shows all captured evidence images in a gallery.

## Authentication

JWT via `djangorestframework-simplejwt`.
- Access tokens 8 h, refresh tokens 7 d.
- Stored in `localStorage`.
- `RequireAuth` guards all `/dashboard`, `/live-monitoring`,
  `/violation-detection`, `/violation-records`, `/evidence`.
- Frontend `api()` helper auto-attaches the access token and transparently
  refreshes on a 401.

## Violation lifecycle (state chart)

Matches the D1 state chart exactly:

```
  Idle  ──AI detects──▶  Detected  ──save──▶  Stored  ──admin opens──▶
  Reviewed  ──admin finalizes──▶  Completed
                               │
                               └─admin discards──▶  Rejected
```

Status values stored in DB: `detected`, `stored` (default on creation),
`reviewed`, `completed`, `rejected`.

## Known limitations

- Browser posts single frames to `/analyze/` — a periodic stream every N
  seconds (not a real WebSocket push) to avoid flooding CPU inference.
- OCR accuracy depends on plate clarity + lighting; we use the top-confidence
  candidate but expect imperfect reads.
- `ai/main.py` is a standalone Windows-oriented demo script
  (`cv2.CAP_DSHOW`). The web backend doesn't use it — `ai/infer.py` is.
- The seatbelt heuristic (Path A) is best-effort; Path B (trained model)
  is required for publication-grade accuracy.

## Team

- Rajab Nasir     — 22024119-188
- Muhammad Ali    — 22024119-189
- Muhammad Haseeb — 22024119-153

Advisor: **Mr. Adeel Ahmed**
