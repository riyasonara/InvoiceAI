import { useState } from "react";
import { api } from "../api";
import Brand from "../components/Brand";

export default function AuthScreen({ onAuthenticated }) {
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
          {isLogin ? "Log in to access your workspace." : "Start a workspace or join your team."}
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="field">
            <span className="field-label">Email</span>
            <input type="email" placeholder="you@company.com" value={email}
              onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
          </label>

          <label className="field">
            <span className="field-label">Password</span>
            <input type="password" placeholder={isLogin ? "Your password" : "At least 8 characters"}
              value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete={isLogin ? "current-password" : "new-password"} required />
          </label>

          {!isLogin && (
            <>
              <div className="seg">
                <button type="button" className={orgMode === "create" ? "seg-btn active" : "seg-btn"}
                  onClick={() => setOrgMode("create")}>Create workspace</button>
                <button type="button" className={orgMode === "join" ? "seg-btn active" : "seg-btn"}
                  onClick={() => setOrgMode("join")}>Join with code</button>
              </div>

              {orgMode === "create" ? (
                <label className="field">
                  <span className="field-label">Organization name</span>
                  <input type="text" placeholder="Acme Inc" value={organizationName}
                    onChange={(e) => setOrganizationName(e.target.value)} required />
                </label>
              ) : (
                <label className="field">
                  <span className="field-label">Invite code</span>
                  <input type="text" placeholder="Paste your team's invite code" value={inviteCode}
                    onChange={(e) => setInviteCode(e.target.value)} required />
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
          <button type="button" className="link"
            onClick={() => { setMode(isLogin ? "register" : "login"); setError(""); }}>
            {isLogin ? "Sign up" : "Log in"}
          </button>
        </p>
      </div>
    </div>
  );
}
