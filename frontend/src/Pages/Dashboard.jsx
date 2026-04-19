import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AdminLayout from "../Components/AdminLayout";
import { api } from "../api";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await api("/stats/");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setStats(data);
          setErr("");
        }
      } catch (e) {
        if (!cancelled) setErr(String(e.message || e));
      }
    };
    load();
    const id = setInterval(load, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const byStatus = (s) =>
    (stats?.by_status || []).find((x) => x.status === s)?.count ?? 0;

  const cards = [
    {
      label: "Total Violations",
      value: stats?.violations_total ?? "—",
      color: "from-blue-500 to-indigo-600",
      icon: "🚦",
    },
    {
      label: "Pending Review",
      value: byStatus("stored") + byStatus("detected"),
      color: "from-amber-500 to-orange-600",
      icon: "⏳",
    },
    {
      label: "Tracked Vehicles",
      value: stats?.vehicles_total ?? "—",
      color: "from-emerald-500 to-teal-600",
      icon: "🚗",
    },
    {
      label: "Active Cameras",
      value: stats?.cameras_total ?? "—",
      color: "from-violet-500 to-purple-600",
      icon: "📹",
    },
  ];

  return (
    <AdminLayout
      title="Dashboard"
      subtitle="Real-time traffic intelligence overview"
    >
      {err && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-2">
          {err}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        {cards.map((c, i) => (
          <div
            key={i}
            className="bg-white rounded-xl p-5 shadow-sm border border-slate-200 relative overflow-hidden"
          >
            <div
              className={`absolute -right-4 -top-4 w-20 h-20 rounded-full bg-gradient-to-br ${c.color} opacity-10`}
            />
            <div className="flex items-start justify-between relative">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  {c.label}
                </p>
                <h3 className="mt-2 text-3xl font-extrabold text-slate-900">
                  {c.value}
                </h3>
              </div>
              <div
                className={`w-10 h-10 rounded-lg bg-gradient-to-br ${c.color} text-white text-xl grid place-items-center shadow-md`}
              >
                {c.icon}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2 bg-white rounded-xl p-6 border border-slate-200 shadow-sm">
          <h2 className="text-base font-bold text-slate-900 mb-4">
            Violation Lifecycle
          </h2>
          <p className="text-xs text-slate-500 mb-5">
            Follows the state-chart: Detected → Stored → Reviewed → Completed
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {[
              { key: "detected", label: "Detected", color: "bg-purple-100 text-purple-700" },
              { key: "stored", label: "Stored", color: "bg-amber-100 text-amber-700" },
              { key: "reviewed", label: "Reviewed", color: "bg-blue-100 text-blue-700" },
              { key: "completed", label: "Completed", color: "bg-emerald-100 text-emerald-700" },
              { key: "rejected", label: "Rejected", color: "bg-red-100 text-red-700" },
            ].map((s) => (
              <div key={s.key} className="text-center">
                <div className={`py-3 rounded-lg ${s.color}`}>
                  <div className="text-2xl font-extrabold">{byStatus(s.key)}</div>
                </div>
                <div className="text-[10px] uppercase tracking-wider text-slate-500 mt-1 font-semibold">
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-sm">
          <h2 className="text-base font-bold text-slate-900 mb-4">
            Quick Actions
          </h2>
          <div className="space-y-2">
            <QuickLink to="/live-monitoring" icon="📹" text="Live Monitoring" />
            <QuickLink to="/violation-detection" icon="🚦" text="Start Detection" />
            <QuickLink to="/violation-records" icon="📋" text="View All Records" />
            <QuickLink to="/evidence" icon="🗂️" text="Evidence Library" />
          </div>
        </div>
      </div>

      {stats?.recent?.length > 0 && (
        <div className="bg-white rounded-xl p-6 border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-slate-900">Recent Alerts</h2>
            <Link
              to="/violation-records"
              className="text-xs font-semibold text-blue-600 hover:underline"
            >
              View all →
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-100">
                  <th className="pb-2">#</th>
                  <th className="pb-2">Plate</th>
                  <th className="pb-2">Type</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2 text-right">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {stats.recent.map((v) => (
                  <tr key={v.id} className="hover:bg-slate-50">
                    <td className="py-3 font-mono text-xs text-slate-500">
                      #{v.id}
                    </td>
                    <td className="py-3 font-semibold">{v.plate}</td>
                    <td className="py-3 text-slate-600">{v.type}</td>
                    <td className="py-3">
                      <StatusPill status={v.status} />
                    </td>
                    <td className="py-3 text-right text-xs text-slate-500">
                      {new Date(v.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}

function QuickLink({ to, icon, text }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 px-3 py-2 rounded-lg border border-slate-200 hover:border-blue-500 hover:bg-blue-50 transition text-sm font-semibold text-slate-700"
    >
      <span className="text-xl">{icon}</span> {text}
    </Link>
  );
}

function StatusPill({ status }) {
  const map = {
    detected: "bg-purple-100 text-purple-700",
    stored: "bg-amber-100 text-amber-700",
    reviewed: "bg-blue-100 text-blue-700",
    completed: "bg-emerald-100 text-emerald-700",
    rejected: "bg-red-100 text-red-700",
  };
  return (
    <span
      className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
        map[status] || "bg-slate-100 text-slate-700"
      }`}
    >
      {status}
    </span>
  );
}
