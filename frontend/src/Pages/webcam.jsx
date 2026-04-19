import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

export default function Webcam() {
  const videoRef = useRef(null);
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [stream, setStream] = useState(null);
  const [isOn, setIsOn] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  const startCamera = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720 },
        audio: false,
      });
      if (videoRef.current) videoRef.current.srcObject = mediaStream;
      setStream(mediaStream);
      setIsOn(true);
      setError("");
    } catch {
      setError("Camera access denied. Please allow camera permission.");
    }
  };

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      setStream(null);
      setIsOn(false);
    }
  };

  const detectHelmet = async () => {
    try {
      const video = videoRef.current;
      if (!video || !isOn) {
        alert("Please start the camera first.");
        return;
      }

      setIsDetecting(true);
      setLastResult(null);

      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);

      const blob = await new Promise((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", 0.9)
      );

      const form = new FormData();
      form.append("image", blob, "frame.jpg");

      const res = await api("/analyze/", { method: "POST", body: form });
      const data = await res.json();

      if (res.status === 200) {
        setLastResult({ ok: true, msg: data.message || "Helmet detected. No violation." });
      } else if (res.status === 201) {
        setLastResult({
          ok: false,
          msg: `No-helmet violation recorded. ID: ${data.id}, plate: ${data.vehicle_plate}`,
        });
        // Give the user 2s to read the result before jumping
        setTimeout(() => navigate("/violations"), 1500);
      } else {
        setLastResult({ ok: false, msg: JSON.stringify(data) });
      }
    } catch (e) {
      console.error(e);
      setLastResult({ ok: false, msg: "Error: " + e.message });
    } finally {
      setIsDetecting(false);
    }
  };

  useEffect(() => {
    return () => stopCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-100 via-white to-white px-6 py-10">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-extrabold text-slate-900">
            Live AI Surveillance Feed
          </h1>
          <p className="text-slate-600 mt-2 max-w-2xl">
            Real-time webcam stream integrated with AI-powered traffic monitoring
            and violation detection engine.
          </p>
        </div>

        <div className="relative bg-slate-900 rounded-2xl shadow-2xl overflow-hidden border border-slate-700">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/20 via-transparent to-amber-500/20 blur-2xl pointer-events-none" />

          <div className="absolute top-4 left-4 z-10">
            <span
              className={`px-4 py-1.5 rounded-full text-xs font-bold tracking-wide ${
                isOn
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-400/40"
                  : "bg-red-500/20 text-red-400 border border-red-400/40"
              }`}
            >
              {isOn ? "● LIVE FEED ACTIVE" : "● CAMERA OFFLINE"}
            </span>
          </div>

          <div className="aspect-video flex items-center justify-center bg-black">
            {error ? (
              <div className="text-center px-6">
                <p className="text-red-400 font-semibold mb-4">{error}</p>
                <button
                  onClick={startCamera}
                  className="px-6 py-3 bg-amber-500 text-black font-semibold rounded-lg hover:bg-amber-400 transition"
                >
                  Retry Camera Access
                </button>
              </div>
            ) : (
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className={`w-full h-full object-cover transition-opacity duration-500 ${
                  isOn ? "opacity-100" : "opacity-0"
                }`}
              />
            )}
          </div>

          <div className="flex items-center justify-between px-6 py-4 bg-slate-800 border-t border-slate-700">
            <div className="text-slate-300 text-sm">
              Resolution: <span className="font-semibold text-white">1280×720</span>
            </div>

            <div className="flex gap-4">
              <button
                onClick={detectHelmet}
                disabled={!isOn || isDetecting}
                className={`px-6 py-2.5 font-bold rounded-lg transition shadow ${
                  !isOn || isDetecting
                    ? "bg-slate-600 text-slate-300 cursor-not-allowed"
                    : "bg-amber-500 text-black hover:bg-amber-400"
                }`}
              >
                {isDetecting ? "Detecting..." : "Detect Helmet"}
              </button>

              {!isOn ? (
                <button
                  onClick={startCamera}
                  className="px-6 py-2.5 bg-emerald-500 text-black font-bold rounded-lg hover:bg-emerald-400 transition shadow"
                >
                  Start Camera
                </button>
              ) : (
                <button
                  onClick={stopCamera}
                  className="px-6 py-2.5 bg-red-500 text-white font-bold rounded-lg hover:bg-red-400 transition shadow"
                >
                  Stop Camera
                </button>
              )}
            </div>
          </div>
        </div>

        {lastResult && (
          <div
            className={`mt-6 rounded-xl border p-4 text-sm ${
              lastResult.ok
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-red-50 border-red-200 text-red-800"
            }`}
          >
            {lastResult.msg}
          </div>
        )}

        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            "Live Object Detection",
            "License Plate Recognition",
            "Violation Tracking Engine",
          ].map((item, i) => (
            <div
              key={i}
              className="bg-white rounded-xl border border-slate-200 shadow-sm p-5"
            >
              <p className="text-sm text-slate-500">AI Module</p>
              <h3 className="mt-1 text-lg font-semibold text-slate-900">{item}</h3>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
