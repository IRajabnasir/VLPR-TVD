// Central API helper. Handles base URL, JWT token, auth fetch, and login/logout.
//
// Usage:
//   import { api, login, logout, getUser, isAuthenticated } from "../api";
//   const res = await api("/violations/");
//   const data = await res.json();

const RAW_BASE = (import.meta.env && import.meta.env.VITE_API_BASE) || "http://127.0.0.1:8000";
export const API_BASE = RAW_BASE.replace(/\/+$/, "");
export const API_URL = `${API_BASE}/api`;

const TOKEN_KEY = "vlpr_access_token";
const REFRESH_KEY = "vlpr_refresh_token";
const USER_KEY = "vlpr_user";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function getUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function isAuthenticated() {
  return !!getToken();
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

export async function login(username, password) {
  const res = await fetch(`${API_URL}/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data.detail || `Login failed (HTTP ${res.status})`;
    throw new Error(msg);
  }

  localStorage.setItem(TOKEN_KEY, data.access);
  localStorage.setItem(REFRESH_KEY, data.refresh);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  return data.user;
}

export function mediaUrl(path) {
  if (!path) return "";
  if (/^https?:/.test(path)) return path;
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

// Authenticated fetch. Auto-attaches Bearer token, tries a refresh on 401.
export async function api(path, options = {}) {
  const url = path.startsWith("http") ? path : `${API_URL}${path.startsWith("/") ? "" : "/"}${path}`;
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  // Don't set Content-Type for FormData; let the browser add the boundary.
  if (!(options.body instanceof FormData) && !headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  let res = await fetch(url, { ...options, headers });
  if (res.status !== 401) return res;

  // Try a single refresh
  const refresh = getRefreshToken();
  if (!refresh) return res;

  const rr = await fetch(`${API_URL}/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!rr.ok) {
    logout();
    return res;
  }
  const rd = await rr.json();
  localStorage.setItem(TOKEN_KEY, rd.access);

  headers.set("Authorization", `Bearer ${rd.access}`);
  res = await fetch(url, { ...options, headers });
  return res;
}
