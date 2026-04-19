import { useEffect, useMemo, useState } from "react";
import AdminLayout from "../Components/AdminLayout";
import { api, mediaUrl } from "../api";

const TYPE_LABELS = {
  no_helmet: "No Helmet",
  no_seatbelt: "No Seatbelt",
  red_light: "Red Light",
};

export default function EvidenceManagement() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [activeType, setActiveType] = useState("all");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api("/violations/");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          const list = Array.isArray(data) ? data : data.results || [];
          setItems(list.filter((v) => v.evidence_url));
        }
      } catch (e) {
        if (!cancelled) setErr(String(e.message || e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    if (activeType === "all") return items;
    return items.filter((v) => v.violation_type === activeType);
  }, [items, activeType]);

  return (
    <AdminLayout
      title="Evidence Management"
      subtitle="Browse all evidence images captured by the system"
    >
      {err && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-2">
          {err}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-xl p-3 mb-4 flex flex-wrap gap-2">
        <FilterChip
          active={activeType === "all"}
          onClick={() => setActiveType("all")}
          label={`All (${items.length})`}
        />
        {Object.entries(TYPE_LABELS).map(([k, label]) => {
          const n = items.filter((v) => v.violation_type === k).length;
          if (n === 0) return null;
          return (
            <FilterChip
              key={k}
              active={activeType === k}
              onClick={() => setActiveType(k)}
              label={`${label} (${n})`}
            />
          );
        })}
      </div>

      {loading ? (
        <div className="text-center text-slate-500 py-10">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="bg-white border border-dashed border-slate-300 rounded-xl p-10 text-center text-slate-500">
          No evidence images yet. Run detection to start capturing evidence.
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {filtered.map((v) => (
            <button
              key={v.id}
              onClick={() => setSelected(v)}
              className="group bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm hover:shadow-lg hover:border-blue-400 transition text-left"
            >
              <div className="aspect-video bg-slate-900">
                <img
                  src={mediaUrl(v.evidence_url)}
                  alt="evidence"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
              </div>
              <div className="p-3">
                <div className="flex items-center justify-between">
                  <div className="font-semibold text-slate-900 text-sm">
                    {v.vehicle_plate}
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-red-100 text-red-700">
                    {TYPE_LABELS[v.violation_type] || v.violation_type}
                  </span>
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {new Date(v.created_at).toLocaleString()}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm grid place-items-center p-4"
          onClick={() => setSelected(null)}
        >
          <div
            className="bg-white rounded-2xl max-w-3xl w-full overflow-hidden shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="bg-black">
              <img
                src={mediaUrl(selected.evidence_url)}
                alt="evidence"
                className="w-full max-h-[70vh] object-contain"
              />
            </div>
            <div className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs font-mono text-slate-500">
                    #{selected.id}
                  </div>
                  <div className="text-2xl font-extrabold text-slate-900">
                    {selected.vehicle_plate}
                  </div>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-red-100 text-red-700">
                  {TYPE_LABELS[selected.violation_type] || selected.violation_type}
                </span>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <Info label="Vehicle Type" value={selected.vehicle_type || "—"} />
                <Info label="Camera" value={selected.camera_name || "—"} />
                <Info label="Location" value={selected.location || "—"} />
                <Info label="Status" value={selected.status} />
                <Info label="Fine Amount" value={selected.fine_amount} />
                <Info
                  label="Timestamp"
                  value={new Date(selected.created_at).toLocaleString()}
                />
              </dl>
              <div className="mt-5 flex justify-end gap-2">
                <a
                  href={mediaUrl(selected.evidence_url)}
                  target="_blank"
                  rel="noreferrer"
                  className="px-4 py-2 rounded-lg border border-slate-300 hover:bg-slate-100 text-sm font-semibold"
                >
                  Open Image
                </a>
                <button
                  onClick={() => setSelected(null)}
                  className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  );
}

function FilterChip({ active, onClick, label }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full text-xs font-semibold transition ${
        active
          ? "bg-blue-600 text-white"
          : "bg-slate-100 text-slate-700 hover:bg-slate-200"
      }`}
    >
      {label}
    </button>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <dt className="text-xs uppercase font-semibold tracking-wider text-slate-500">
        {label}
      </dt>
      <dd className="text-sm font-semibold text-slate-800 mt-0.5">{value}</dd>
    </div>
  );
}
