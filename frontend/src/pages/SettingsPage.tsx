import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Box, Card, Typography, Button, Alert, Stack, Chip } from "@mui/material";
import { api } from "../api";

interface GmailStatus {
  connected: boolean;
  configured: boolean;
  email?: string;
  connected_at?: string;
}

export default function SettingsPage() {
  const [status, setStatus] = useState<GmailStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [params] = useSearchParams();

  function load() {
    setLoading(true);
    api("/gmail/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setStatus(d as GmailStatus | null))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function connect() {
    const res = await api("/gmail/connect");
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Gmail integration is not available.");
      return;
    }
    // Send the browser to Google's consent screen.
    window.location.href = data.auth_url;
  }

  async function disconnect() {
    await api("/gmail/disconnect", { method: "POST" });
    load();
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700 }}>Settings</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Connect your email so invoices are imported automatically.
      </Typography>

      {params.get("gmail") === "connected" && (
        <Alert severity="success" sx={{ mb: 2 }}>Gmail connected successfully.</Alert>
      )}

      <Card variant="outlined" sx={{ p: 3, maxWidth: 560 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>Gmail</Typography>

        {loading ? (
          <Typography color="text.secondary">Loading…</Typography>
        ) : status && !status.configured ? (
          <Alert severity="info">
            Gmail integration isn't configured on the server yet
            (missing Google OAuth credentials).
          </Alert>
        ) : status?.connected ? (
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <Chip color="success" label="Connected" size="small" />
              <Typography>{status.email}</Typography>
            </Stack>
            <Box>
              <Button variant="outlined" color="error" onClick={disconnect}>Disconnect</Button>
            </Box>
          </Stack>
        ) : (
          <Stack spacing={2}>
            <Typography color="text.secondary">No Gmail account connected.</Typography>
            <Box>
              <Button variant="contained" onClick={connect}>Connect Gmail</Button>
            </Box>
          </Stack>
        )}
      </Card>
    </Box>
  );
}
