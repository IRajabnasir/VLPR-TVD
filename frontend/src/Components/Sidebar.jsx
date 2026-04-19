import { NavLink, useNavigate } from "react-router-dom";
import Logo from "./Logo";
import { logout, getUser } from "../api";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: "📊" },
  { to: "/live-monitoring", label: "Live Monitoring", icon: "📹" },
  { to: "/violation-detection", label: "Violation Detection", icon: "🚦" },
  { to: "/violation-records", label: "Violation Records", icon: "📋" },
  { to: "/evidence", label: "Evidence Management", icon: "🗂️" },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const user = getUser();

  const onLogout = () => {
    if (!window.confirm("Are you sure you want to logout?")) return;
    logout();
    navigate("/login");
  };

  return (
    <aside className="w-64 shrink-0 bg-slate-900 text-slate-200 min-h-screen flex flex-col">
      <div className="px-5 py-5 border-b border-slate-800">
        <Logo variant="dark" />
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              [
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                isActive
                  ? "bg-blue-600 text-white font-semibold"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white",
              ].join(" ")
            }
            end
          >
            <span className="text-lg leading-none">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-slate-800">
        <div className="px-3 py-2 text-xs text-slate-400">
          Signed in as
          <div className="text-slate-100 font-semibold truncate">
            {user?.username || "admin"}
          </div>
        </div>
        <button
          onClick={onLogout}
          className="w-full mt-2 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-slate-800 hover:bg-red-600 text-sm font-medium transition-colors"
        >
          <span>🚪</span> Logout
        </button>
      </div>
    </aside>
  );
}
