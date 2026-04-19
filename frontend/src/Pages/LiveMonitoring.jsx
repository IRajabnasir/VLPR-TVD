import { useEffect, useRef, useState } from "react";
import AdminLayout from "../Components/AdminLayout";

export default function LiveMonitoring() {
  const videoRef = useRef(null);
  const [stream, setStream] = useState(null);
  const [error, setError] = useState("");
  const [isOn, setIsOn] = useState(false);
  const [resolution, setResolution] = useState("—");

  const start = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720 },
        audio: false,
      });
      if (videoRef.current) videoRef.current.srcObject = s;
      setStream(s);
      setIsOn(true);
      setError("");
      const track = s.getVideoTracks()[0];
      const settings = track.getSettings();
      setResolution(`${settings.width || "?"}×${settings.height || "?"}`);
    } catch {
      setError("Camera access denied. Please grant permission and retry.");
    }
  };

  const stop = () => {
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      setStream(null);
    }
    setIsOn(false);
    setResolution("—");
  };

  useEffect(() => () => stop(), []); // cleanup on unmount

  return (
    <AdminLayout
      title="Live Monitoring"
      subtitle="Watch the active traffic camera feed in real time"
      actions={
        !isOn ? (
          <button
            onClick={start}
            className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold shadow"
          >
            ▶ Start Camera
          </button>
        ) : (
          <button
            onClick={stop}
            className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-semibold shadow"
          >
            ■ Stop Camera
          </button>
        )
      }
    >
      <div className="bg-slate-900 rounded-xl overflow-hidden shadow-xl border border-slate-800 relative">
        <div className="absolute top-3 left-3 z-10">
          <span
            className={`px-3 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase ${
              isOn
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-400/40"
                : "bg-red-500/20 text-red-300 border border-red-400/40"
            }`}
          >
            ● {isOn ? "Live" : "Offline"}
          </span>
        </div>
        <div className="absolute top-3 right-3 z-10 text-xs text-slate-300 bg-slate-800/70 rounded px-2 py-1">
          {resolution}
        </div>

        <div className="aspect-video grid place-items-center bg-black">
          {error ? (
            <div className="text-center p-8">
              <div className="text-red-400 font-semibold mb-3">{error}</div>
              <button
                onClick={start}
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
              Camera is off. Click "Start Camera" to begin streaming.
            </div>
          )}
        </div>
      </div>

      <div className="mt-6 grid sm:grid-cols-3 gap-4">
        <InfoCard label="Feed Source" value="Browser Webcam" />
        <InfoCard label="Encoding" value="MJPEG / WebRTC" />
        <InfoCard
          label="Next Step"
          value="Go to Violation Detection to start automated analysis"
        />
      </div>
    </AdminLayout>
  );
}

function InfoCard({ label, value }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
      <div className="text-xs uppercase font-semibold tracking-wider text-slate-500">
        {label}
      </div>
      <div className="mt-1 text-sm font-semibold text-slate-800">{value}</div>
    </div>
  );
}
