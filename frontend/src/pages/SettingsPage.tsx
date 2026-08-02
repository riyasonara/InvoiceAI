import { useEffect, useState } from "react";
import { useSearchParams, useOutletContext } from "react-router-dom";
import {
  Box, Card, Typography, Button, Alert, Stack, Chip, IconButton,
  ToggleButton, ToggleButtonGroup, Tooltip,
  Table, TableBody, TableCell, TableHead, TableRow,
} from "@mui/material";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import ContentCopyRoundedIcon from "@mui/icons-material/ContentCopyRounded";
import { api } from "../api";
import type { CurrentUser, Member, Role } from "../types";
import { SkeletonLines } from "../components/Skeleton";

interface GmailStatus {
  connected: boolean;
  configured: boolean;
  email?: string;
  connected_at?: string;
  last_synced_at?: string | null;
  auto_sync_seconds?: number;
}

export default function SettingsPage() {
  const { user } = useOutletContext<{ user: CurrentUser }>();
  const isAdmin = user.role === "admin";

  const [status, setStatus] = useState<GmailStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [members, setMembers] = useState<Member[]>([]);
  const [membersLoading, setMembersLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [params] = useSearchParams();

  function loadStatus() {
    setLoading(true);
    api("/gmail/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setStatus(d as GmailStatus | null))
      .finally(() => setLoading(false));
  }

  function loadMembers() {
    api("/organization/members")
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setMembers(d as Member[]))
      .finally(() => setMembersLoading(false));
  }

  useEffect(() => { loadStatus(); loadMembers(); }, []);

  async function connect() {
    const res = await api("/gmail/connect");
    const data = await res.json();
    if (!res.ok) {
      setError(data.detail || "Gmail integration is not available.");
      return;
    }
    window.location.href = data.auth_url;
  }

  async function disconnect() {
    await api("/gmail/disconnect", { method: "POST" });
    loadStatus();
  }

  function copyInvite() {
    if (!user.organization.invite_code) return;
    navigator.clipboard?.writeText(user.organization.invite_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  async function changeRole(memberId: number, role: Role) {
    setError("");
    const res = await api(`/organization/members/${memberId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    const data = await res.json();
    if (!res.ok) {
      setError(data.detail || "Could not change role.");
      return;
    }
    loadMembers();
  }

  async function removeMember(memberId: number, email: string) {
    if (!window.confirm(`Remove ${email} from this workspace?`)) return;
    setError("");
    const res = await api(`/organization/members/${memberId}`, { method: "DELETE" });
    if (!res.ok) {
      const data = await res.json();
      setError(data.detail || "Could not remove member.");
      return;
    }
    loadMembers();
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700 }}>Settings</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Manage your workspace, email connection, and teammates.
      </Typography>

      {params.get("gmail") === "connected" && (
        <Alert severity="success" sx={{ mb: 2 }}>Gmail connected successfully.</Alert>
      )}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>{error}</Alert>}

      <Stack spacing={2} sx={{ maxWidth: 720 }}>
        {/* Workspace + invite code (admins only — the code grants access) */}
        <Card variant="outlined" sx={{ p: 3 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>Workspace</Typography>
          <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: isAdmin ? 2 : 0 }}>
            <Typography>{user.organization.name}</Typography>
            <Chip size="small" label={`You: ${user.role}`} color={isAdmin ? "primary" : "default"} variant="outlined" />
          </Stack>

          {isAdmin && user.organization.invite_code && (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                Share this invite code so teammates can join. They join as members.
              </Typography>
              <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                <Box component="code" sx={{
                  px: 1.5, py: 1, borderRadius: 1, bgcolor: "action.hover",
                  fontFamily: "monospace", fontSize: 14, letterSpacing: "0.04em",
                }}>
                  {user.organization.invite_code}
                </Box>
                <Button size="small" startIcon={<ContentCopyRoundedIcon />} onClick={copyInvite}>
                  {copied ? "Copied!" : "Copy"}
                </Button>
              </Stack>
            </>
          )}
        </Card>

        {/* Gmail */}
        <Card variant="outlined" sx={{ p: 3 }}>
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
              <Typography variant="body2" color="text.secondary">
                {status.auto_sync_seconds && status.auto_sync_seconds > 0
                  ? `Auto-sync: every ${Math.round(status.auto_sync_seconds / 60)} min`
                  : "Auto-sync: off"}
                {status.last_synced_at &&
                  ` · Last synced ${String(status.last_synced_at).slice(0, 16).replace("T", " ")} UTC`}
              </Typography>
              {isAdmin ? (
                <Box><Button variant="outlined" color="error" onClick={disconnect}>Disconnect</Button></Box>
              ) : (
                <Typography variant="caption" color="text.secondary">
                  Only admins can change the email connection.
                </Typography>
              )}
            </Stack>
          ) : (
            <Stack spacing={2}>
              <Typography color="text.secondary">No Gmail account connected.</Typography>
              {isAdmin ? (
                <Box><Button variant="contained" onClick={connect}>Connect Gmail</Button></Box>
              ) : (
                <Typography variant="caption" color="text.secondary">
                  Ask an admin to connect your workspace inbox.
                </Typography>
              )}
            </Stack>
          )}
        </Card>

        {/* Members */}
        <Card variant="outlined" sx={{ p: 3 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>
            Members {!membersLoading && `(${members.length})`}
          </Typography>

          {membersLoading ? (
            <SkeletonLines count={3} />
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Email</TableCell>
                  <TableCell>Role</TableCell>
                  {isAdmin && <TableCell align="right">Actions</TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {members.map((m) => (
                  <TableRow key={m.id} hover>
                    <TableCell>
                      {m.email}
                      {m.id === user.id && (
                        <Typography component="span" variant="caption" color="text.secondary"> (you)</Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      {isAdmin ? (
                        <ToggleButtonGroup
                          size="small" exclusive value={m.role}
                          onChange={(_, v: Role | null) => v && v !== m.role && changeRole(m.id, v)}
                        >
                          <ToggleButton value="admin" sx={{ py: 0.25, px: 1 }}>Admin</ToggleButton>
                          <ToggleButton value="member" sx={{ py: 0.25, px: 1 }}>Member</ToggleButton>
                        </ToggleButtonGroup>
                      ) : (
                        <Chip size="small" label={m.role} variant="outlined"
                          color={m.role === "admin" ? "primary" : "default"} />
                      )}
                    </TableCell>
                    {isAdmin && (
                      <TableCell align="right">
                        <Tooltip title={m.id === user.id ? "You can't remove yourself" : "Remove from workspace"}>
                          <span>
                            <IconButton size="small" color="error" disabled={m.id === user.id}
                              onClick={() => removeMember(m.id, m.email)}>
                              <DeleteOutlineRoundedIcon fontSize="small" />
                            </IconButton>
                          </span>
                        </Tooltip>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      </Stack>
    </Box>
  );
}
