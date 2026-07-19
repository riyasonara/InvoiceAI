export const API_URL = "http://localhost:8000";

// Every request includes credentials so the browser sends the httpOnly auth
// cookie. Centralised so no call site can forget it.
export function api(path, options = {}) {
  return fetch(`${API_URL}${path}`, { credentials: "include", ...options });
}

// Small helpers reused across pages.
export function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function formatDate(value) {
  if (!value) return "—";
  return String(value).slice(0, 10);
}
