import { useState, useEffect } from "react";
import "./App.css";

const API_URL = "http://localhost:8000";

// Every request goes through here so it ALWAYS sends the httpOnly cookie.
// Without credentials:"include", the browser won't attach the cookie cross-origin.
function api(path, options = {}) {
  return fetch(`${API_URL}${path}`, { credentials: "include", ...options });
}

// Reusable brand mark (logo + wordmark), used on both the auth and app screens.
function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="2"
             strokeLinecap="round" strokeLinejoin="round">
          <path d="M5 2v20l2-1.5L9 22l2-1.5L13 22l2-1.5L17 22l2-1.5V2l-2 1.5L15 2l-2 1.5L11 2 9 3.5 7 2 5 3.5Z" />
          <path d="M9 8h6M9 12h6M9 16h4" />
        </svg>
      </span>
      <span className="brand-name">InvoiceAI</span>
    </div>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);

  // On load, ask "who am I?". The cookie (if present and valid) answers via /me.
  // This is how an httpOnly cookie "remembers" you across refreshes — the JS
  // never sees the token; it just asks the server whether the cookie is good.
  useEffect(() => {
    api("/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setAuthChecked(true));
  }, []);

  async function handleLogout() {
    await api("/logout", { method: "POST" });
    setUser(null);
  }

  if (!authChecked) {
    return (
      <div className="auth-page">
        <p className="loading">Loading…</p>
      </div>
    );
  }

  return user ? (
    <Dashboard user={user} onLogout={handleLogout} />
  ) : (
    <AuthScreen onAuthenticated={setUser} />
  );
}

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function readError(data) {
    // Login errors send { detail: "..." }; validation errors send
    // { detail: [{ msg, ... }] }. Handle both shapes.
    if (Array.isArray(data.detail)) return data.detail[0]?.msg || "Invalid input.";
    return data.detail || "Something went wrong.";
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await api(`/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();

      if (!res.ok) {
        setError(readError(data));
        return;
      }

      // /register creates the account but does NOT set the cookie. For a smooth
      // experience, log in automatically right after a successful registration.
      if (mode === "register") {
        const loginRes = await api("/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const loginData = await loginRes.json();
        if (!loginRes.ok) {
          setMode("login");
          setError("Account created — please log in.");
          return;
        }
        onAuthenticated(loginData);
      } else {
        onAuthenticated(data); // /login set the cookie and returned the user
      }
    } catch {
      setError("Could not reach the server. Is the API running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  const isLogin = mode === "login";

  return (
    <div className="auth-page">
      <div className="auth-card">
        <Brand />
        <h1 className="auth-title">{isLogin ? "Welcome back" : "Create your account"}</h1>
        <p className="auth-subtitle">
          {isLogin
            ? "Log in to access your invoices."
            : "Start extracting invoice data in seconds."}
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="field">
            <span className="field-label">Email</span>
            <input
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </label>

          <label className="field">
            <span className="field-label">Password</span>
            <input
              type="password"
              placeholder={isLogin ? "Your password" : "At least 8 characters"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isLogin ? "current-password" : "new-password"}
              required
            />
          </label>

          {error && <div className="error">{error}</div>}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Please wait…" : isLogin ? "Log in" : "Create account"}
          </button>
        </form>

        <p className="switch">
          {isLogin ? "Don't have an account?" : "Already have an account?"}{" "}
          <button
            type="button"
            className="link"
            onClick={() => {
              setMode(isLogin ? "register" : "login");
              setError("");
            }}
          >
            {isLogin ? "Sign up" : "Log in"}
          </button>
        </p>
      </div>
    </div>
  );
}

function Dashboard({ user, onLogout }) {
  const [file, setFile] = useState(null);
  const [invoice, setInvoice] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [invoices, setInvoices] = useState([]);

  async function loadInvoices() {
    try {
      const res = await api("/invoices");
      if (res.ok) setInvoices(await res.json());
    } catch (err) {
      console.error("Failed to load invoices", err);
    }
  }

  useEffect(() => {
    loadInvoices();
  }, []);

  async function handleUpload() {
    if (!file) return;

    setLoading(true);
    setError("");
    setInvoice(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await api("/extract", { method: "POST", body: formData });
      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || "Something went wrong while processing the file.");
        return;
      }

      setInvoice(data);
      loadInvoices();
    } catch {
      setError("Could not reach the server. Is the API running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <Brand />
        <div className="user-box">
          <span className="user-email">{user.email}</span>
          <button type="button" className="logout" onClick={onLogout}>
            Log out
          </button>
        </div>
      </header>

      <main className="app-main">
        <div className="page-head">
          <h1>Extract invoice data</h1>
          <p className="subtitle">Upload a PDF and let AI pull out the vendor, dates, and totals.</p>
        </div>

        <div className="upload-card">
          <label className="file-drop">
            <input
              type="file"
              accept="application/pdf"
              onChange={(e) => setFile(e.target.files[0])}
            />
            <span className="file-drop-text">
              {file ? file.name : "Choose a PDF invoice…"}
            </span>
          </label>
          <button
            className="btn-primary"
            onClick={handleUpload}
            disabled={!file || loading}
          >
            {loading ? "Extracting…" : "Extract Invoice"}
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        {invoice && (
          <div className="result-card">
            <h2>Extracted invoice</h2>
            <table>
              <tbody>
                <tr><td>Vendor</td><td>{invoice.vendor ?? "—"}</td></tr>
                <tr><td>Invoice Number</td><td>{invoice.invoice_number ?? "—"}</td></tr>
                <tr><td>Invoice Date</td><td>{invoice.invoice_date ?? "—"}</td></tr>
                <tr><td>GST</td><td>{invoice.gst ?? "—"}</td></tr>
                <tr><td>Total</td><td>{invoice.total ?? "—"}</td></tr>
              </tbody>
            </table>
          </div>
        )}

        <div className="list-card">
          <div className="list-head">
            <h2>Your invoices</h2>
            <span className="count-badge">{invoices.length}</span>
          </div>
          {invoices.length === 0 ? (
            <p className="empty">No invoices yet. Upload one above to get started.</p>
          ) : (
            <div className="table-scroll">
              <table className="list-table">
                <thead>
                  <tr>
                    <th>Vendor</th>
                    <th>Number</th>
                    <th>Date</th>
                    <th>GST</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id}>
                      <td className="cell-strong">{inv.vendor ?? "—"}</td>
                      <td>{inv.invoice_number ?? "—"}</td>
                      <td>{inv.invoice_date ?? "—"}</td>
                      <td>{inv.gst ?? "—"}</td>
                      <td>{inv.total ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
