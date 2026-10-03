// Env-driven so production points at the deployed API; falls back to the
// local backend in dev. Set VITE_API_URL at build time for production.
export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Every request includes credentials so the browser sends the httpOnly auth
// cookie. Centralised so no call site can forget it.
export function api(path: string, options: RequestInit = {}): Promise<Response> {
  return fetch(`${API_URL}${path}`, { credentials: "include", ...options });
}

// Small helpers reused across pages.
export function formatMoney(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return String(value).slice(0, 10);
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// "2026-01" -> "Jan 2026" (short: "Jan '26", for tighter chart axis labels).
export function monthLabel(value: string, short = false): string {
  if (!value || !value.includes("-")) return value || "";
  const [y, mm] = value.split("-");
  const month = MONTHS[Number(mm) - 1] || mm;
  return short ? `${month} '${y.slice(2)}` : `${month} ${y}`;
}
