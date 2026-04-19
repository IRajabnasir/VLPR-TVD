import { useEffect, useState } from "react";
import { api, mediaUrl } from "../api";

// Matches state chart: Idle -> Detected -> Stored -> Reviewed -> Completed (+ Rejected)
const STATUS_COLORS = {
  detected: "bg-purple-100 text-purple-700",
  stored: "bg-amber-100 text-amber-700",
  reviewed: "bg-blue-100 text-blue-700",
  completed: "bg-emerald-100 text-emerald-700",
  rejected: "bg-red-100 text-red-700",
};

export default function Violations() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        const res = await api("/violations/");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setItems(Array.isArray(data) ? data : data.results || []);
          setErr("");
        }
      } catch (e) {
        if (!cancelled) setErr(String(e.message || e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const callAction = async (id, action) => {
    try {
      const res = await api(`/violations/${id}/${action}/`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const updated = await res.json();
      setItems((prev) => prev.map((v) => (v.id === id ? updated : v)));
    } catch (e) {
      alert("Update failed: " + e.message);
    }
  };

  return (
    <div className="px-6 py-10 bg-slate-50 min-h-screen">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-slate-900 mb-2">Violations</h1>
        <p className="text-slate-600 mb-6">
          All detected traffic violations. Auto-refreshes every 5 seconds.
          Lifecycle follows the state chart: <strong>Detected → Stored → Reviewed → Completed</strong>.
        </p>

        {err && (
          <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
            {err}
          </div>
        )}

        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-slate-700">
              <tr>
                <th className="text-left px-4 py-3">ID</th>
                <th className="text-left px-4 py-3">Plate</th>
                <th className="text-left px-4 py-3">Type</th>
                <th className="text-left px-4 py-3">Camera</th>
                <th className="text-left px-4 py-3">Fine</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3">Evidence</th>
                <th className="text-left px-4 py-3">Created</th>
                <th className="text-left px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && items.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-slate-500">
                    Loading…
                  </td>
                </tr>
              )}
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-slate-500">
                    No violations yet.
                  </td>
                </tr>
              )}
              {items.map((v) => {
                const chipClass = STATUS_COLORS[v.status] || "bg-slate-100 text-slate-700";
                return (
                  <tr key={v.id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-xs">{v.id}</td>
                    <td className="px-4 py-3 font-semibold">{v.vehicle_plate}</td>
                    <td className="px-4 py-3">{v.violation_type}</td>
                    <td className="px-4 py-3 text-xs text-slate-600">
                      {v.camera_name || "-"}
                    </td>
                    <td className="px-4 py-3">{v.fine_amount}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold ${chipClass}`}
                      >
                        {v.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {v.evidence_url ? (
                        <a href={mediaUrl(v.evidence_url)} target="_blank" rel="noreferrer">
                          <img
                            src={mediaUrl(v.evidence_url)}
                            alt="evidence"
                            className="w-24 h-16 object-cover rounded border border-slate-200 hover:shadow"
                          />
                        </a>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {new Date(v.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        {["detected", "stored"].includes(v.status) && (
                          <>
                            <button
                              onClick={() => callAction(v.id, "review")}
                              className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-500"
                            >
                              Review
                            </button>
                            <button
                              onClick={() => callAction(v.id, "reject")}
                              className="text-xs px-2 py-1 bg-red-600 text-white rounded hover:bg-red-500"
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {v.status === "reviewed" && (
                          <>
                            <button
                              onClick={() => callAction(v.id, "complete")}
                              className="text-xs px-2 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-500"
                            >
                              Complete
                            </button>
                            <button
                              onClick={() => callAction(v.id, "reject")}
                              className="text-xs px-2 py-1 bg-red-600 text-white rounded hover:bg-red-500"
                            >
                              Reject
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
