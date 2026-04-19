import cv2
import os
import time
from datetime import datetime
from ultralytics import YOLO
import easyocr

# ==============================
# LOAD MODELS
# ==============================
vehicle_model = YOLO("yolov8n.pt")                 # COCO: person + motorcycle
helmet_model = YOLO("models/helmet.pt")            # Helmet detector
plate_model = YOLO("models/license_plate.pt")      # License plate detector

reader = easyocr.Reader(['en'], gpu=False)

# ==============================
# VIDEO / WEBCAM INPUT
# ==============================
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # stable on Windows

if not cap.isOpened():
    print("❌ Camera not opened")
    exit()

# ==============================
# FOLDERS
# ==============================
os.makedirs("violations", exist_ok=True)

# ==============================
# COOLDOWN (FIXED)
# ==============================
last_capture_time = 0
COOLDOWN_SECONDS = 5

print("🚦 Traffic Violation System Started")

# ==============================
# MAIN LOOP
# ==============================
while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Frame not received")
        break

    frame = cv2.resize(frame, (1280, 720))

    results = vehicle_model(frame)

    motorcycles = []
    persons = []

    # ------------------------------
    # Separate detections
    # ------------------------------
    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            if cls == 3:  # motorcycle
                motorcycles.append((x1, y1, x2, y2))
            elif cls == 0:  # person
                persons.append((x1, y1, x2, y2))

    # ------------------------------
    # Process motorcycles
    # ------------------------------
    for mx1, my1, mx2, my2 in motorcycles:
        cv2.rectangle(frame, (mx1, my1), (mx2, my2), (0, 255, 0), 2)
        cv2.putText(frame, "Motorcycle", (mx1, my1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        for px1, py1, px2, py2 in persons:

            # Check overlap (rider sitting on bike)
            overlap_x = max(0, min(px2, mx2) - max(px1, mx1))
            overlap_y = max(0, min(py2, my2) - max(py1, my1))
            if overlap_x == 0 or overlap_y == 0:
                continue

            # Rider box
            cv2.rectangle(frame, (px1, py1), (px2, py2), (255, 255, 0), 2)
            cv2.putText(frame, "Rider", (px1, py1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            # ------------------------------
            # Helmet detection on head region
            # ------------------------------
            head_y2 = py1 + int((py2 - py1) * 0.4)
            head_crop = frame[py1:head_y2, px1:px2]

            helmet_found = False
            helmet_results = helmet_model(head_crop, conf=0.2)

            for hr in helmet_results:
                for hbox in hr.boxes:
                    hx1, hy1, hx2, hy2 = map(int, hbox.xyxy[0])

                    # Map helmet box to original frame
                    hx1 += px1
                    hx2 += px1
                    hy1 += py1
                    hy2 += py1

                    cv2.rectangle(frame, (hx1, hy1), (hx2, hy2), (0, 0, 255), 2)
                    cv2.putText(frame, "Helmet", (hx1, hy1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                    helmet_found = True

            # ------------------------------
            # VIOLATION LOGIC (FIXED)
            # ------------------------------
            if not helmet_found:
                cv2.putText(frame, "NO HELMET", (px1, py2 + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                current_time = time.time()
                if current_time - last_capture_time > COOLDOWN_SECONDS:
                    last_capture_time = current_time

                    # ------------------------------
                    # LICENSE PLATE DETECTION
                    # ------------------------------
                    plate_text = "NOT READ"
                    plate_results = plate_model(frame, conf=0.3)

                    for pr in plate_results:
                        for pbox in pr.boxes:
                            lx1, ly1, lx2, ly2 = map(int, pbox.xyxy[0])
                            plate_img = frame[ly1:ly2, lx1:lx2]

                            if plate_img.size == 0:
                                continue

                            plate_img = cv2.resize(
                                plate_img, None, fx=2, fy=2,
                                interpolation=cv2.INTER_CUBIC
                            )
                            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)

                            ocr = reader.readtext(gray)
                            if ocr:
                                plate_text = ocr[0][1]

                            cv2.rectangle(frame, (lx1, ly1), (lx2, ly2),
                                          (255, 0, 0), 2)
                            break

                    # ------------------------------
                    # SAVE EVIDENCE
                    # ------------------------------
                    now = datetime.now()
                    filename = now.strftime("%Y%m%d_%H%M%S")
                    img_path = f"violations/{filename}.jpg"
                    cv2.imwrite(img_path, frame)

                    print("🚨 HELMET VIOLATION DETECTED")
                    print("Plate Number:", plate_text)
                    print("Time:", now)
                    print("Saved:", img_path)
                    print("-" * 40)

    # ------------------------------
    # DISPLAY
    # ------------------------------
    cv2.imshow("Traffic Monitoring System", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
