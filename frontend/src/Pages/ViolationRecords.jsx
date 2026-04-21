import { useEffect, useMemo, useState } from "react";
import AdminLayout from "../Components/AdminLayout";
import { api, mediaUrl } from "../api";

const STATUS_COLORS = {
  detected: "bg-purple-100 text-purple-700",
  stored: "bg-amber-100 text-amber-700",
  reviewed: "bg-blue-100 text-blue-700",
  completed: "bg-emerald-100 text-emerald-700",
  rejected: "bg-red-100 text-red-700",
};

const TYPE_LABELS = {
  no_helmet: "No Helmet",
  no_seatbelt: "No Seatbelt",
  red_light: "Red Light",
  over_speed: "Over Speed",
  illegal_parking: "Illegal Parking",
  other: "Other",
};

export default function ViolationRecords() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [query, setQuery] = useState("");

  const fetchData = async () => {
    try {
      const res = await api("/violations/");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setItems(Array.isArray(data) ? data : data.results || []);
      setErr("");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const i = setInterval(fetchData, 5000);
    return () => clearInterval(i);
  }, []);

  const filtered = useMemo(() => {
    return items.filter((v) => {
      if (filterType !== "all" && v.violation_type !== filterType) return false;
      if (filterStatus !== "all" && v.status !== filterStatus) return false;
      if (query) {
        const q = query.toLowerCase();
        if (
          !v.vehicle_plate?.toLowerCase().includes(q) &&
          !v.location?.toLowerCase().includes(q) &&
          !v.camera_name?.toLowerCase().includes(q)
        )
          return false;
      }
      return true;
    });
  }, [items, filterType, filterStatus, query]);

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
    <AdminLayout
      title="Violation Records"
      subtitle="All detected traffic violations — auto-refreshed every 5 seconds"
      actions={
        <button
          onClick={fetchData}
          className="px-3 py-2 text-sm rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold"
        >
          ↻ Refresh
        </button>
      }
    >
      {err && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-2">
          {err}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm mb-4 p-3 flex flex-wrap items-center gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search plate, location, camera…"
          className="flex-1 min-w-[200px] border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="border border-slate-300 rounded-lg px-2 py-2 text-sm"
        >
          <option value="all">All types</option>
          {Object.entries(TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="border border-slate-300 rounded-lg px-2 py-2 text-sm"
        >
          <option value="all">All statuses</option>
          {Object.keys(STATUS_COLORS).map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
        <span className="ml-auto text-xs text-slate-500">
          Showing {filtered.length} of {items.length}
        </span>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr className="border-b border-slate-200">
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider">
                  Evidence
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider">
                  Vehicle
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider">
                  Type
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider">
                  Violation
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider">
                  Location
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider">
                  Timestamp
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider">
                  Status
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && items.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-slate-500">
                    Loading…
                  </td>
                </tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-slate-500">
                    No violations match your filters.
                  </td>
                </tr>
              )}
              {filtered.map((v) => (
                <tr key={v.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    {v.evidence_url ? (
                      <a
                        href={mediaUrl(v.evidence_url)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <img
                          src={mediaUrl(v.evidence_url)}
                          alt="evidence"
                          className="w-20 h-14 object-cover rounded-md border border-slate-200 hover:shadow"
                        />
                      </a>
                    ) : (
                      <div className="w-20 h-14 bg-slate-100 rounded-md grid place-items-center text-slate-400 text-xs">
                        none
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div
                      className={`font-semibold ${
                        v.vehicle_plate === "UNKNOWN"
                          ? "text-slate-400 italic"
                          : "font-mono tracking-wider text-slate-900 bg-amber-50 inline-block px-2 rounded border border-amber-200"
                      }`}
                    >
                      {v.vehicle_plate === "UNKNOWN"
                        ? "Plate not readable"
                        : v.vehicle_plate}
                    </div>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">
                      #{v.id} · {v.camera_name || "—"}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs capitalize text-slate-700">
                    {v.vehicle_type || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-semibold text-slate-800">
                      {TYPE_LABELS[v.violation_type] || v.violation_type}
                    </span>
                    <div className="text-xs text-slate-500">
                      Fine: {v.fine_amount}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {v.location || "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {new Date(v.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider ${
                        STATUS_COLORS[v.status] || "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {v.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2 justify-end">
                      {["detected", "stored"].includes(v.status) && (
                        <>
                          <ActionButton
                            onClick={() => callAction(v.id, "review")}
                            color="blue"
                          >
                            Review
                          </ActionButton>
                          <ActionButton
                            onClick={() => callAction(v.id, "reject")}
                            color="red"
                          >
                            Reject
                          </ActionButton>
                        </>
                      )}
                      {v.status === "reviewed" && (
                        <>
                          <ActionButton
                            onClick={() => callAction(v.id, "complete")}
                            color="emerald"
                          >
                            Complete
                          </ActionButton>
                          <ActionButton
                            onClick={() => callAction(v.id, "reject")}
                            color="red"
                          >
                            Reject
                          </ActionButton>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AdminLayout>
  );
}

function ActionButton({ children, onClick, color }) {
  const map = {
    blue: "bg-blue-600 hover:bg-blue-500",
    red: "bg-red-600 hover:bg-red-500",
    emerald: "bg-emerald-600 hover:bg-emerald-500",
  };
  return (
    <button
      onClick={onClick}
      className={`text-xs px-2.5 py-1 text-white rounded font-semibold ${map[color]}`}
    >
      {children}
    </button>
  );
}
