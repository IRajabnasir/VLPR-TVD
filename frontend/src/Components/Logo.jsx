export default function Logo({ size = "md", variant = "dark", showText = true }) {
  const dims = size === "sm" ? 32 : size === "lg" ? 56 : 40;
  const titleText = variant === "dark" ? "text-white" : "text-slate-900";
  const subText = variant === "dark" ? "text-slate-300" : "text-slate-500";

  return (
    <div className="flex items-center gap-3 select-none">
      <div
        className="grid place-items-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white font-black shadow-lg ring-1 ring-white/10"
        style={{ width: dims, height: dims, fontSize: dims * 0.45 }}
      >
        V
      </div>
      {showText && (
        <div className="leading-tight">
          <div className={`font-extrabold tracking-wide ${titleText}`}>
            VLPR<span className="text-yellow-400">-TVD</span>
          </div>
          <div
            className={`text-[10px] uppercase tracking-[0.2em] ${subText}`}
          >
            Traffic Intelligence
          </div>
        </div>
      )}
    </div>
  );
}
