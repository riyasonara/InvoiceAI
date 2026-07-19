import { useState, useEffect } from "react";
import "./App.css";

const API_URL = "http://localhost:8000";

// Every request goes through here so it ALWAYS sends the httpOnly cookie.
function api(path, options = {}) {
  return fetch(`${API_URL}${path}`, { credentials: "include", ...options });
}

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
  const [orgMode, setOrgMode] = useState("create"); // "create" | "join"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function readError(data) {
    if (Array.isArray(data.detail)) return data.detail[0]?.msg || "Invalid input.";
    return data.detail || "Something went wrong.";
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");

    // Build the request body. Register also carries the workspace choice.
    const body = { email, password };
    if (mode === "register") {
      if (orgMode === "create") body.organization_name = organizationName;
      else body.invite_code = inviteCode;
    }

    try {
      const res = await api(`/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();

      if (!res.ok) {
        setError(readError(data));
        return;
      }

      // /register doesn't set the cookie, so log in right after to start a session.
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
        onAuthenticated(data);
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
            ? "Log in to access your workspace."
            : "Start a workspace or join your team."}
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

          {!isLogin && (
            <>
              <div className="seg">
                <button
                  type="button"
                  className={orgMode === "create" ? "seg-btn active" : "seg-btn"}
                  onClick={() => setOrgMode("create")}
                >
                  Create workspace
                </button>
                <button
                  type="button"
                  className={orgMode === "join" ? "seg-btn active" : "seg-btn"}
                  onClick={() => setOrgMode("join")}
                >
                  Join with code
                </button>
              </div>

              {orgMode === "create" ? (
                <label className="field">
                  <span className="field-label">Organization name</span>
                  <input
                    type="text"
                    placeholder="Acme Inc"
                    value={organizationName}
                    onChange={(e) => setOrganizationName(e.target.value)}
                    required
                  />
                </label>
              ) : (
                <label className="field">
                  <span className="field-label">Invite code</span>
                  <input
                    type="text"
                    placeholder="Paste your team's invite code"
                    value={inviteCode}
                    onChange={(e) => setInviteCode(e.target.value)}
                    required
                  />
                </label>
              )}
            </>
          )}

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
  const [copied, setCopied] = useState(false);

  const org = user.organization;

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

  function copyInvite() {
    navigator.clipboard?.writeText(org.invite_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

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
        <div className="header-left">
          <Brand />
          <span className="workspace-pill">{org.name}</span>
        </div>
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

        <div className="invite-card">
          <div className="invite-text">
            <span className="invite-label">Invite teammates</span>
            <p className="invite-hint">Share this code so colleagues can join {org.name}.</p>
          </div>
          <div className="invite-code-box">
            <code>{org.invite_code}</code>
            <button type="button" className="copy-btn" onClick={copyInvite}>
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
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
            <h2>Workspace invoices</h2>
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
