import { useState } from "react";
import type { FormEvent } from "react";
import {
  Box, Card, Typography, TextField, Button, Alert, Link,
  ToggleButton, ToggleButtonGroup,
} from "@mui/material";
import { api } from "../api";
import type { CurrentUser } from "../types";
import Brand from "../components/Brand";

interface AuthScreenProps {
  onAuthenticated: (user: CurrentUser) => void;
}

export default function AuthScreen({ onAuthenticated }: AuthScreenProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [orgMode, setOrgMode] = useState<"create" | "join">("create");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function readError(data: { detail?: unknown }): string {
    if (Array.isArray(data.detail)) return data.detail[0]?.msg || "Invalid input.";
    return (data.detail as string) || "Something went wrong.";
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    const body: Record<string, string> = { email, password };
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
        onAuthenticated(loginData as CurrentUser);
      } else {
        onAuthenticated(data as CurrentUser);
      }
    } catch {
      setError("Could not reach the server. Is the API running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  const isLogin = mode === "login";

  return (
    <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", p: 2, bgcolor: "background.default" }}>
      <Card variant="outlined" sx={{ width: "100%", maxWidth: 420, p: 4 }}>
        <Brand />
        <Typography variant="h5" sx={{ fontWeight: 700, mt: 2.5 }}>
          {isLogin ? "Welcome back" : "Create your account"}
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          {isLogin ? "Log in to access your workspace." : "Start a workspace or join your team."}
        </Typography>

        <Box component="form" onSubmit={handleSubmit} sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            fullWidth size="small" required autoComplete="email" />
          <TextField label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
            fullWidth size="small" required autoComplete={isLogin ? "current-password" : "new-password"}
            helperText={isLogin ? undefined : "At least 8 characters"} />

          {!isLogin && (
            <>
              <ToggleButtonGroup value={orgMode} exclusive fullWidth size="small"
                onChange={(_, v: "create" | "join" | null) => v && setOrgMode(v)}>
                <ToggleButton value="create">Create workspace</ToggleButton>
                <ToggleButton value="join">Join with code</ToggleButton>
              </ToggleButtonGroup>
              {orgMode === "create" ? (
                <TextField label="Organization name" value={organizationName}
                  onChange={(e) => setOrganizationName(e.target.value)} fullWidth size="small" required />
              ) : (
                <TextField label="Invite code" value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)} fullWidth size="small" required />
              )}
            </>
          )}

          {error && <Alert severity="error">{error}</Alert>}

          <Button type="submit" variant="contained" size="large" disabled={loading}>
            {loading ? "Please wait…" : isLogin ? "Log in" : "Create account"}
          </Button>
        </Box>

        <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 2.5 }}>
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <Link component="button" type="button" underline="hover" sx={{ fontWeight: 600 }}
            onClick={() => { setMode(isLogin ? "register" : "login"); setError(""); }}>
            {isLogin ? "Sign up" : "Log in"}
          </Link>
        </Typography>
      </Card>
    </Box>
  );
}
