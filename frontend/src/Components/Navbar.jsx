import { NavLink } from "react-router-dom";
import Logo from "./Logo";
import { isAuthenticated } from "../api";

export default function Navbar() {
  const authed = isAuthenticated();

  const links = [
    { name: "Home", path: "/" },
    { name: "About", path: "/about" },
    { name: "Contact", path: "/contact" },
  ];

  return (
    <nav className="sticky top-0 z-50 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 shadow-lg">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <Logo variant="dark" />

        <div className="hidden md:flex items-center gap-6 text-sm font-semibold text-slate-200">
          {links.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                isActive
                  ? "text-yellow-400 border-b-2 border-yellow-400 pb-1"
                  : "hover:text-yellow-300 transition"
              }
            >
              {item.name}
            </NavLink>
          ))}
        </div>

        <div className="flex items-center gap-3">
          {authed ? (
            <NavLink
              to="/dashboard"
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition"
            >
              Go to Dashboard
            </NavLink>
          ) : (
            <NavLink
              to="/login"
              className="px-4 py-2 rounded-lg bg-yellow-500 hover:bg-yellow-400 text-slate-900 text-sm font-bold transition"
            >
              Admin Login
            </NavLink>
          )}
        </div>
      </div>
    </nav>
  );
}
