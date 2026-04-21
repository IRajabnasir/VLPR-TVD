import { useEffect, useRef, useState } from "react";
import AdminLayout from "../Components/AdminLayout";
import { api } from "../api";

const LABELS = {
  no_helmet: "No Helmet",
  no_seatbelt: "No Seatbelt",
  red_light: "Red Light",
  over_speed: "Over Speed",
  illegal_parking: "Illegal Parking",
  other: "Other",
};

const MODES = {
  CAMERA: "camera",
  UPLOAD: "upload",
};

export default function ViolationDetection() {
  const videoRef = useRef(null);
  const fileInputRef = useRef(null);
  const [mode, setMode] = useState(MODES.UPLOAD); // default to upload (works everywhere)
  const [stream, setStream] = useState(null);
  const [isOn, setIsOn] = useState(false);
  const [error, setError] = useState("");

  // Upload-mode state
  const [uploadPreview, setUploadPreview] = useState(null); // data URL
  const [uploadBlob, setUploadBlob] = useState(null);       // raw blob to POST
  const [uploadName, setUploadName] = useState("");

  // Detection state
  const [autoDetect, setAutoDetect] = useState(false);
  const [intervalSec, setIntervalSec] = useState(3);
  const [isBusy, setIsBusy] = useState(false);
  const [feed, setFeed] = useState([]);
  const [stats, setStats] = useState({ frames: 0, violations: 0 });
  const [lastMessage, setLastMessage] = useState("");
  const [lastDebug, setLastDebug] = useState(null);
  const autoRef = useRef(null);

  // ---- Camera controls ----
  const startCamera = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720 },
        audio: false,
      });
      if (videoRef.current) videoRef.current.srcObject = s;
      setStream(s);
      setIsOn(true);
      setError("");
    } catch {
      setError("Camera access denied or no camera available.");
    }
  };

  const stopCamera = () => {
    setAutoDetect(false);
    if (stream) stream.getTracks().forEach((t) => t.stop());
    setStream(null);
    setIsOn(false);
  };

  // ---- Upload controls ----
  const handleFile = (file) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("Please select an image file (JPG, PNG, etc.).");
      return;
    }
    setError("");
    setUploadBlob(file);
    setUploadName(file.name);
    const reader = new FileReader();
    reader.onload = (e) => setUploadPreview(e.target.result);
    reader.readAsDataURL(file);
  };

  const onFileChange = (e) => handleFile(e.target.files?.[0]);

  const onDrop = (e) => {
    e.preventDefault();
    handleFile(e.dataTransfer.files?.[0]);
  };

  const onDragOver = (e) => e.preventDefault();

  const clearUpload = () => {
    setUploadBlob(null);
    setUploadPreview(null);
    setUploadName("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // ---- Analyze (works for both modes) ----
  const postBlob = async (blob, filename, locationLabel) => {
    const fd = new FormData();
    fd.append("image", blob, filename);
    fd.append("camera_name", mode === MODES.CAMERA ? "Browser Webcam" : "File Upload");
    fd.append("location", locationLabel);
    const res = await api("/analyze/", { method: "POST", body: fd });
    return await res.json();
  };

  const analyzeCameraFrame = async () => {
    const v = videoRef.current;
    if (!v || !isOn || isBusy) return;
    setIsBusy(true);
    try {
      const canvas = document.createElement("canvas");
      canvas.width = v.videoWidth || 1280;
      canvas.height = v.videoHeight || 720;
      canvas.getContext("2d").drawImage(v, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((r) => canvas.toBlob(r, "image/jpeg", 0.9));
      const data = await postBlob(blob, "frame.jpg", "Live Camera");
      handleResponse(data);
    } catch (e) {
      console.error(e);
      setLastMessage(`Error: ${e.message || e}`);
    } finally {
      setIsBusy(false);
    }
  };

  const analyzeUpload = async () => {
    if (!uploadBlob || isBusy) return;
    setIsBusy(true);
    try {
      const data = await postBlob(uploadBlob, uploadName || "upload.jpg", "Uploaded File");
      handleResponse(data);
    } catch (e) {
      console.error(e);
      setLastMessage(`Error: ${e.message || e}`);
    } finally {
      setIsBusy(false);
    }
  };

  const handleResponse = (data) => {
    const found = (data?.violations || []).length;
    setStats((s) => ({ frames: s.frames + 1, violations: s.violations + found }));
    if (found > 0) {
      setFeed((prev) =>
        [
          ...(data.violations || []).map((v) => ({ ...v, ts: new Date().toISOString() })),
          ...prev,
        ].slice(0, 12)
      );
      setLastMessage(`✅ ${found} violation${found > 1 ? "s" : ""} detected`);
    } else {
      setLastMessage(data?.message || "No violation detected in this frame.");
    }
    setLastDebug(data?.debug || null);
  };

  // Auto-detect (camera only)
  useEffect(() => {
    if (autoRef.current) {
      clearInterval(autoRef.current);
      autoRef.current = null;
    }
    if (mode === MODES.CAMERA && autoDetect && isOn) {
      autoRef.current = setInterval(analyzeCameraFrame, Math.max(1, intervalSec) * 1000);
    }
    return () => {
      if (autoRef.current) clearInterval(autoRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, autoDetect, isOn, intervalSec]);

  // Cleanup on unmount
  useEffect(() => () => stopCamera(), []); // eslint-disable-line react-hooks/exhaustive-deps

  // Stop camera when switching to upload mode
  useEffect(() => {
    if (mode === MODES.UPLOAD && isOn) stopCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const headerActions =
    mode === MODES.CAMERA ? (
      !isOn ? (
        <button
          onClick={startCamera}
          className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold shadow"
        >
          ▶ Start Camera
        </button>
      ) : (
        <button
          onClick={stopCamera}
          className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-semibold shadow"
        >
          ■ Stop
        </button>
      )
    ) : null;

  return (
    <AdminLayout
      title="Violation Detection"
      subtitle="AI-powered analysis — live webcam or uploaded image"
      actions={headerActions}
    >
      {/* Mode switcher */}
      <div className="mb-4 inline-flex rounded-xl bg-slate-200 p-1">
        <ModeTab
          active={mode === MODES.UPLOAD}
          onClick={() => setMode(MODES.UPLOAD)}
          icon="🖼️"
          label="Upload Image"
        />
        <ModeTab
          active={mode === MODES.CAMERA}
          onClick={() => setMode(MODES.CAMERA)}
          icon="📹"
          label="Live Camera"
        />
      </div>

      {error && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-2">
          {error}
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Main area — spans 2 cols */}
        <div className="lg:col-span-2 space-y-4">
          {mode === MODES.CAMERA ? (
            <CameraPanel
              videoRef={videoRef}
              isOn={isOn}
              error={error}
              onRetry={startCamera}
            />
          ) : (
            <UploadPanel
              preview={uploadPreview}
              uploadName={uploadName}
              fileInputRef={fileInputRef}
              onFileChange={onFileChange}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onClear={clearUpload}
            />
          )}

          {/* Controls strip */}
          <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm flex flex-wrap items-center gap-3">
            {mode === MODES.CAMERA ? (
              <>
                <button
                  onClick={analyzeCameraFrame}
                  disabled={!isOn || isBusy}
                  className={`px-4 py-2 rounded-lg text-sm font-semibold shadow ${
                    !isOn || isBusy
                      ? "bg-slate-200 text-slate-500 cursor-not-allowed"
                      : "bg-blue-600 hover:bg-blue-500 text-white"
                  }`}
                >
                  {isBusy ? "Analyzing…" : "📸 Detect Now"}
                </button>
                <label className="flex items-center gap-2 text-sm text-slate-700 ml-2">
                  <input
                    type="checkbox"
                    checked={autoDetect}
                    onChange={(e) => setAutoDetect(e.target.checked)}
                    disabled={!isOn}
                    className="w-4 h-4"
                  />
                  Auto-detect every
                  <input
                    type="number"
                    min={1}
                    max={30}
                    value={intervalSec}
                    onChange={(e) => setIntervalSec(Number(e.target.value))}
                    className="w-14 text-center border border-slate-300 rounded px-1 py-0.5"
                  />
                  s
                </label>
              </>
            ) : (
              <>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-800 text-sm font-semibold"
                >
                  📁 Choose Image
                </button>
                <button
                  onClick={analyzeUpload}
                  disabled={!uploadBlob || isBusy}
                  className={`px-4 py-2 rounded-lg text-sm font-semibold shadow ${
                    !uploadBlob || isBusy
                      ? "bg-slate-200 text-slate-500 cursor-not-allowed"
                      : "bg-blue-600 hover:bg-blue-500 text-white"
                  }`}
                >
                  {isBusy ? "Analyzing…" : "🔍 Run Detection"}
                </button>
                {uploadBlob && (
                  <button
                    onClick={clearUpload}
                    className="px-3 py-2 rounded-lg text-sm text-slate-600 hover:text-slate-900"
                  >
                    Clear
                  </button>
                )}
              </>
            )}

            <div className="ml-auto flex gap-5 text-sm">
              <Stat label="Frames" value={stats.frames} />
              <Stat label="Violations" value={stats.violations} color="text-red-600" />
            </div>
          </div>

          {lastMessage && (
            <div
              className={`rounded-lg px-4 py-3 text-sm ${
                lastMessage.startsWith("✅")
                  ? "bg-red-50 border border-red-200 text-red-800"
                  : lastMessage.startsWith("Error")
                  ? "bg-red-50 border border-red-200 text-red-800"
                  : "bg-emerald-50 border border-emerald-200 text-emerald-800"
              }`}
            >
              <div>{lastMessage}</div>
              {lastDebug && (
                <details className="mt-2 text-xs opacity-80">
                  <summary className="cursor-pointer font-semibold">
                    🔧 Show detection details
                  </summary>
                  <div className="mt-2 grid grid-cols-3 sm:grid-cols-6 gap-2">
                    <DebugStat label="Motorcycles" v={lastDebug.motorcycles} />
                    <DebugStat label="Cars" v={lastDebug.cars} />
                    <DebugStat label="Trucks" v={lastDebug.trucks} />
                    <DebugStat label="Buses" v={lastDebug.buses} />
                    <DebugStat label="Persons" v={lastDebug.persons} />
                    <DebugStat label="Plates" v={lastDebug.plates} />
                    <DebugStat label="Helmet worn" v={lastDebug.helmet_worn} />
                    <DebugStat label="Helmet NOT" v={lastDebug.helmet_not_worn} />
                    <DebugStat
                      label="Seatbelt mode"
                      v={lastDebug.seatbelt_mode}
                      isText
                    />
                  </div>
                  {lastDebug.notes?.length > 0 && (
                    <ul className="mt-2 list-disc list-inside space-y-0.5">
                      {lastDebug.notes.map((n, i) => (
                        <li key={i}>{n}</li>
                      ))}
                    </ul>
                  )}
                  {lastDebug.helmet_raw?.length > 0 && (
                    <div className="mt-3">
                      <div className="font-semibold text-[11px] uppercase tracking-wider">
                        Raw helmet model output
                        {lastDebug.helmet_conf_threshold != null && (
                          <span className="font-normal ml-1 text-slate-500">
                            (threshold: {lastDebug.helmet_conf_threshold})
                          </span>
                        )}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {lastDebug.helmet_raw.map((d, i) => {
                          const passes =
                            d.conf >= (lastDebug.helmet_conf_threshold ?? 0);
                          return (
                            <span
                              key={i}
                              className={`text-[10px] font-mono rounded px-1.5 py-0.5 ${
                                passes
                                  ? "bg-amber-100 text-amber-800"
                                  : "bg-slate-100 text-slate-500 line-through"
                              }`}
                              title={passes ? "counted" : "below threshold"}
                            >
                              {d.label} · {d.conf}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  {lastDebug.helmet_model_classes && (
                    <div className="mt-3 text-[11px]">
                      <span className="font-semibold">Helmet model knows:</span>{" "}
                      <span className="font-mono text-slate-600">
                        {lastDebug.helmet_model_classes.join(", ")}
                      </span>
                    </div>
                  )}
                  {lastDebug.plates_raw?.length > 0 && (
                    <div className="mt-3">
                      <div className="font-semibold text-[11px] uppercase tracking-wider">
                        All detected plates ({lastDebug.plates_raw.length})
                      </div>
                      <div className="mt-1 flex flex-wrap gap-2">
                        {lastDebug.plates_raw.map((p, i) => (
                          <div
                            key={i}
                            className="flex flex-col items-center bg-blue-50 border border-blue-200 rounded p-1"
                          >
                            {p.crop_url && (
                              <a
                                href={`http://127.0.0.1:8000${p.crop_url}`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                <img
                                  src={`http://127.0.0.1:8000${p.crop_url}`}
                                  alt={`plate ${i}`}
                                  className="h-8 border border-blue-300 rounded bg-white"
                                />
                              </a>
                            )}
                            <span
                              className="text-[9px] font-mono text-blue-800 mt-0.5"
                              title={`source: ${p.source}`}
                            >
                              📷 {p.conf} · {p.source}
                            </span>
                          </div>
                        ))}
                      </div>
                      <div className="text-[10px] text-slate-500 mt-1">
                        Every plate found in the frame. Only plates inside the
                        offending vehicle's bbox are OCR'd — others (e.g. from
                        other cars in view) are shown here but not used.
                      </div>
                    </div>
                  )}
                  {lastDebug.ocr_plates?.length > 0 && (
                    <div className="mt-3">
                      <div className="font-semibold text-[11px] uppercase tracking-wider">
                        OCR results ({lastDebug.ocr_plates.length})
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {lastDebug.ocr_plates.map((p, i) => (
                          <span
                            key={i}
                            className="text-[11px] font-mono rounded px-2 py-1 bg-emerald-100 text-emerald-900 font-bold"
                            title={`conf: ${p.conf} · ${p.violation_type} · ${p.vehicle_type}`}
                          >
                            🔤 {p.plate}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {lastDebug.ocr_candidates?.length > 0 && (
                    <div className="mt-3">
                      <div className="font-semibold text-[11px] uppercase tracking-wider">
                        All OCR attempts
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {lastDebug.ocr_candidates.map((c, i) => (
                          <span
                            key={i}
                            className={`text-[10px] font-mono rounded px-1.5 py-0.5 ${
                              c.accepted
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-slate-100 text-slate-500 line-through"
                            }`}
                            title={`variant: ${c.variant || "default"} · ${
                              c.accepted
                                ? "accepted"
                                : "rejected (low conf or bad format)"
                            }`}
                          >
                            {c.text} · {c.conf}
                            {c.variant && (
                              <span className="text-[9px] opacity-70 ml-1">
                                ({c.variant})
                              </span>
                            )}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {lastDebug.plate_match_log?.length > 0 && (
                    <div className="mt-3">
                      <div className="font-semibold text-[11px] uppercase tracking-wider">
                        Plate-to-vehicle matching
                      </div>
                      <div className="mt-1 space-y-1">
                        {lastDebug.plate_match_log.map((v, i) => (
                          <div
                            key={i}
                            className={`text-[10px] rounded px-2 py-1 ${
                              v.matched
                                ? "bg-emerald-50 border border-emerald-200"
                                : "bg-amber-50 border border-amber-200"
                            }`}
                          >
                            <span className="font-semibold capitalize">
                              {v.vehicle_type}
                            </span>{" "}
                            — {v.matched ? "plate matched ✓" : "no plate matched ✗"}
                            {v.checks?.length > 0 && (
                              <ul className="mt-1 ml-4 list-disc space-y-0.5 text-slate-600">
                                {v.checks.map((c, j) => (
                                  <li key={j} className="font-mono text-[9px]">
                                    plate #{c.plate_index} (conf {c.plate_conf}) —{" "}
                                    {c.result}
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {lastDebug.plate_crops?.length > 0 && (
                    <div className="mt-3">
                      <div className="font-semibold text-[11px] uppercase tracking-wider">
                        Plate crops sent to OCR
                      </div>
                      <div className="mt-1 flex flex-wrap gap-2">
                        {lastDebug.plate_crops.map((url, i) => (
                          <a
                            key={i}
                            href={`http://127.0.0.1:8000${url}`}
                            target="_blank"
                            rel="noreferrer"
                            title="Open full size"
                          >
                            <img
                              src={`http://127.0.0.1:8000${url}`}
                              alt="plate crop"
                              className="h-10 border border-slate-300 rounded bg-white hover:shadow-md transition"
                            />
                          </a>
                        ))}
                      </div>
                      <div className="text-[10px] text-slate-500 mt-1">
                        Click to open full size. If these look wrong or blurry,
                        OCR can't fix it — the plate detection cropped the wrong
                        region or the plate is too small.
                      </div>
                    </div>
                  )}
                </details>
              )}
            </div>
          )}
        </div>

        {/* Live feed sidebar */}
        <aside className="bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col max-h-[700px]">
          <div className="px-4 py-3 border-b border-slate-100">
            <h3 className="font-bold text-slate-900">Live Detections</h3>
            <p className="text-xs text-slate-500">Most recent first</p>
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {feed.length === 0 ? (
              <div className="p-6 text-center text-sm text-slate-500">
                No violations yet.
                <br />
                {mode === MODES.UPLOAD
                  ? "Upload an image and click Run Detection."
                  : "Start the camera and click Detect Now."}
              </div>
            ) : (
              feed.map((v, i) => (
                <div key={i} className="p-3 hover:bg-slate-50">
                  <div className="flex items-center justify-between">
                    <div className="font-mono text-xs text-slate-500">#{v.id}</div>
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-red-100 text-red-700">
                      {LABELS[v.violation_type] || v.violation_type}
                    </span>
                  </div>
                  <div className="mt-1 flex items-baseline justify-between">
                    <div
                      className={
                        v.vehicle_plate === "UNKNOWN"
                          ? "text-sm italic text-slate-400"
                          : "font-bold text-slate-900 font-mono tracking-wider"
                      }
                    >
                      {v.vehicle_plate === "UNKNOWN"
                        ? "Plate unreadable"
                        : v.vehicle_plate}
                    </div>
                    <div className="text-[10px] text-slate-500 capitalize">
                      {v.vehicle_type}
                    </div>
                  </div>
                  {v.evidence_url && (
                    <div className="mt-2">
                      <img
                        src={`http://127.0.0.1:8000${v.evidence_url}`}
                        alt="evidence"
                        className="w-full h-24 object-cover rounded-lg border border-slate-200"
                      />
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </aside>
      </div>
    </AdminLayout>
  );
}

function ModeTab({ active, onClick, icon, label }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
        active ? "bg-white text-slate-900 shadow" : "text-slate-600 hover:text-slate-800"
      }`}
    >
      <span className="mr-1">{icon}</span>
      {label}
    </button>
  );
}

function CameraPanel({ videoRef, isOn, error, onRetry }) {
  return (
    <div className="bg-slate-900 rounded-xl overflow-hidden border border-slate-800 shadow-xl relative">
      <div className="absolute top-3 left-3 z-10">
        <span
          className={`px-3 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase ${
            isOn
              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-400/40"
              : "bg-red-500/20 text-red-300 border border-red-400/40"
          }`}
        >
          ● {isOn ? "Detecting" : "Offline"}
        </span>
      </div>
      <div className="aspect-video grid place-items-center bg-black">
        {error ? (
          <div className="text-center p-6">
            <div className="text-red-400 font-semibold mb-3">{error}</div>
            <button
              onClick={onRetry}
              className="px-5 py-2 bg-amber-500 text-black font-semibold rounded-lg hover:bg-amber-400"
            >
              Retry
            </button>
          </div>
        ) : (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className={`w-full h-full object-cover transition-opacity duration-300 ${
              isOn ? "opacity-100" : "opacity-0"
            }`}
          />
        )}
        {!isOn && !error && (
          <div className="absolute inset-0 grid place-items-center text-slate-500 text-sm pointer-events-none">
            Camera is off. Click "Start Camera" to begin.
          </div>
        )}
      </div>
    </div>
  );
}

function UploadPanel({
  preview,
  uploadName,
  fileInputRef,
  onFileChange,
  onDrop,
  onDragOver,
  onClear,
}) {
  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      className="bg-slate-900 rounded-xl overflow-hidden border-2 border-dashed border-slate-700 hover:border-blue-500 transition shadow-xl relative"
    >
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={onFileChange}
        className="hidden"
      />
      <div className="aspect-video grid place-items-center bg-black">
        {preview ? (
          <>
            <img
              src={preview}
              alt="upload preview"
              className="w-full h-full object-contain"
            />
            <div className="absolute top-3 left-3 z-10 bg-slate-800/80 text-slate-200 text-xs rounded px-2 py-1 max-w-[70%] truncate">
              📄 {uploadName}
            </div>
            <button
              onClick={onClear}
              className="absolute top-3 right-3 z-10 bg-slate-800/80 hover:bg-red-600 text-white rounded-full w-7 h-7 grid place-items-center transition"
              title="Clear"
            >
              ×
            </button>
          </>
        ) : (
          <button
            onClick={() => fileInputRef.current?.click()}
            className="text-center p-10 w-full h-full flex flex-col items-center justify-center text-slate-400 hover:text-slate-200 transition"
          >
            <div className="text-6xl mb-3">🖼️</div>
            <div className="text-lg font-semibold text-slate-300">
              Click to choose or drop an image here
            </div>
            <div className="text-xs mt-2 text-slate-500">
              JPG, PNG, WebP — test with motorcycle or car photos
            </div>
          </button>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, color = "text-slate-900" }) {
  return (
    <div>
      <div className={`text-lg font-bold ${color}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
        {label}
      </div>
    </div>
  );
}

function DebugStat({ label, v, isText = false }) {
  const val = v === undefined || v === null ? "—" : v;
  return (
    <div className="bg-white/60 rounded px-2 py-1">
      <div className="text-[9px] uppercase tracking-wider text-slate-500">
        {label}
      </div>
      <div className={isText ? "text-xs font-semibold" : "text-sm font-bold"}>
        {val}
      </div>
    </div>
  );
}
