import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { login, isAuthenticated } from "../api";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (isAuthenticated()) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="relative min-h-[calc(100vh-80px)] bg-gradient-to-b from-slate-100 via-white to-white flex items-center justify-center px-6 overflow-hidden">
      {/* AMBIENT BACKGROUND GLOWS */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute top-[-120px] left-[-120px] w-[420px] h-[420px] bg-blue-300/20 rounded-full blur-[140px]" />
        <div className="absolute bottom-[-120px] right-[-120px] w-[420px] h-[420px] bg-indigo-300/20 rounded-full blur-[140px]" />
      </div>

      <div className="relative w-full max-w-5xl grid grid-cols-1 lg:grid-cols-2 bg-white/90 backdrop-blur rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
        {/* LEFT INFO PANEL */}
        <div className="hidden lg:flex flex-col justify-center bg-gradient-to-br from-slate-900 to-slate-800 text-white p-10 relative">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-transparent pointer-events-none" />
          <h2 className="relative text-3xl font-extrabold leading-tight">VLPR-TVD System</h2>
          <p className="relative mt-4 text-slate-300 text-base leading-relaxed">
            Secure access to the Vehicle License Plate Recognition and Traffic Violation
            Detection System.
          </p>
          <ul className="relative mt-6 space-y-3 text-sm text-slate-300">
            <li>• AI-powered license plate recognition</li>
            <li>• Real-time traffic violation monitoring</li>
            <li>• Secure role-based system access</li>
          </ul>
        </div>

        {/* RIGHT LOGIN FORM */}
        <div className="p-10 flex flex-col justify-center">
          <h3 className="text-2xl font-bold text-slate-900">Sign In</h3>
          <p className="mt-2 text-slate-600 text-sm">
            Enter your credentials to access the system
          </p>

          <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
            <div>
              <label className="block text-sm font-medium text-slate-700">Username or Email</label>
              <input
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                required
                className="mt-1 w-full px-4 py-3 border border-slate-300 rounded-lg text-sm
                  focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600
                  bg-white shadow-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">Password</label>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="mt-1 w-full px-4 py-3 border border-slate-300 rounded-lg text-sm
                  focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600
                  bg-white shadow-sm"
              />
            </div>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-3 bg-slate-900 text-white rounded-lg font-semibold
                hover:bg-slate-800 transition shadow-lg hover:shadow-xl disabled:opacity-60"
            >
              {submitting ? "Signing in..." : "Sign In"}
            </button>
          </form>

          <p className="mt-5 text-xs text-slate-500">
            Authorized personnel only. All activities are monitored.
          </p>
        </div>
      </div>
    </section>
  );
}
