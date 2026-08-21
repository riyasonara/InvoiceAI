import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  Box, Card, Typography, Button, Stack, Alert, Chip, TextField, IconButton, CircularProgress,
  Table, TableHead, TableBody, TableRow, TableCell, Divider, Tooltip,
} from "@mui/material";
import SyncRoundedIcon from "@mui/icons-material/SyncRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import ErrorRoundedIcon from "@mui/icons-material/ErrorRounded";
import HourglassEmptyRoundedIcon from "@mui/icons-material/HourglassEmptyRounded";
import RestartAltRoundedIcon from "@mui/icons-material/RestartAltRounded";
import { api } from "../api";
import type { EmailMessage, SyncResult, ProcessResult, EmailAttachment, ProcessingLog } from "../types";
import EmptyState from "../components/EmptyState";
import { SkeletonLines } from "../components/Skeleton";

// Icon + tone for each attachment status — a glance-able alternative to a
// text chip. "willRetry" (a failed attachment with a scheduled auto-retry)
// gets its own warning tone, distinct from a terminal failure.
function statusVisual(a: EmailAttachment): { icon: ReactNode; tone: "success" | "warning" | "error" | "disabled"; label: string } {
  if (a.status === "completed") return { icon: <CheckCircleRoundedIcon fontSize="small" />, tone: "success", label: "Extracted successfully" };
  if (a.status === "processing") return { icon: <SyncRoundedIcon fontSize="small" />, tone: "warning", label: "Processing…" };
  if (a.status === "pending") return { icon: <HourglassEmptyRoundedIcon fontSize="small" />, tone: "disabled", label: "Waiting to be processed" };
  const willRetry = !!a.next_retry_at;
  const at = (a.next_retry_at || "").slice(11, 16);
  return {
    icon: <ErrorRoundedIcon fontSize="small" />,
    tone: willRetry ? "warning" : "error",
    label: willRetry
      ? `Failed — retrying automatically around ${at} (attempt ${a.retry_count}/3)`
      : "Failed — no more automatic retries",
  };
}

// How often to poll while something's actually happening (a sync/process
// action in flight, or an attachment still pending/processing) — backs off
// to not polling at all once everything's settled.
const ACTIVE_POLL_MS = 3000;

export default function EmailsPage() {
  const [emails, setEmails] = useState<EmailMessage[]>([]);
  const [logs, setLogs] = useState<ProcessingLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<SyncResult | null>(null);
  const [processResult, setProcessResult] = useState<ProcessResult | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [retryingIds, setRetryingIds] = useState<Set<number>>(new Set());

  function load(silent = false) {
    if (!silent) setLoading(true);
    api("/emails")
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setEmails(d as EmailMessage[]))
      .finally(() => { if (!silent) setLoading(false); });
  }

  function loadLogs() {
    api("/processing/jobs")
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setLogs((d as ProcessingLog[]).slice(0, 8)));
  }

  useEffect(() => { load(); loadLogs(); }, []);

  const hasActive = emails.some((e) =>
    e.attachments.some((a) => a.status === "pending" || a.status === "processing"));

  // Polls only while there's something to watch: a sync/process action the
  // user just triggered, or attachments still mid-pipeline — e.g. from the
  // background auto-sync running on its own 5-minute schedule. Each
  // attachment's status is committed individually server-side as it
  // changes, so this picks up real progress, not just a fixed refresh.
  useEffect(() => {
    if (!hasActive && !syncing && !processing) return;
    const id = setInterval(() => { load(true); loadLogs(); }, ACTIVE_POLL_MS);
    return () => clearInterval(id);
  }, [hasActive, syncing, processing]);

  async function sync() {
    setSyncing(true);
    setError("");
    setResult(null);
    setProcessResult(null);
    try {
      const res = await api("/emails/sync", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Sync failed.");
        return;
      }
      setResult(data as SyncResult);
      load();
      loadLogs();
      // Automation: new attachments go straight into the pipeline.
      if ((data as SyncResult).new_attachments > 0) {
        await processPending();
      }
    } catch {
      setError("Could not reach the server. Is the API running on port 8000?");
    } finally {
      setSyncing(false);
    }
  }

  async function processPending() {
    setProcessing(true);
    setError("");
    setProcessResult(null);
    try {
      const res = await api("/processing/run", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Processing failed.");
        return;
      }
      setProcessResult(data as ProcessResult);
      load();
      loadLogs();
    } catch {
      setError("Could not reach the server. Is the API running on port 8000?");
    } finally {
      setProcessing(false);
    }
  }

  async function retryAttachment(attachmentId: number) {
    setRetryingIds((prev) => new Set(prev).add(attachmentId));
    setError("");
    try {
      const res = await api(`/processing/attachments/${attachmentId}/retry`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Retry failed.");
        return;
      }
      load();
      loadLogs();
    } catch {
      setError("Could not reach the server. Is the API running on port 8000?");
    } finally {
      setRetryingIds((prev) => { const next = new Set(prev); next.delete(attachmentId); return next; });
    }
  }

  const pendingCount = emails.reduce(
    (n, e) => n + e.attachments.filter((a) => a.status === "pending").length, 0
  );

  const q = search.toLowerCase();
  const filtered = emails.filter(
    (e) => (e.sender || "").toLowerCase().includes(q) || (e.subject || "").toLowerCase().includes(q)
  );

  return (
    <Box>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}
        sx={{ mb: 3, justifyContent: "space-between", alignItems: { sm: "flex-start" } }}>
        <Box>
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Typography variant="h4" sx={{ fontWeight: 700 }}>Emails</Typography>
            {(hasActive || syncing || processing) && (
              <Stack direction="row" spacing={0.75} sx={{
                alignItems: "center", px: 1, py: 0.25, borderRadius: 99,
                border: 1, borderColor: "info.main", color: "info.main",
              }}>
                <Box sx={{
                  width: 6, height: 6, borderRadius: "50%", bgcolor: "info.main",
                  animation: "pulse 1.4s ease-in-out infinite",
                  "@keyframes pulse": { "0%, 100%": { opacity: 1 }, "50%": { opacity: 0.3 } },
                }} />
                <Typography variant="caption" sx={{ fontWeight: 600 }}>Live</Typography>
              </Stack>
            )}
          </Stack>
          <Typography color="text.secondary">Invoices received through your connected inbox.</Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" color="inherit" startIcon={<SyncRoundedIcon />} onClick={sync} disabled={syncing || processing}>
            {syncing ? "Syncing…" : "Sync now"}
          </Button>
          <Button variant="contained" startIcon={<PlayArrowRoundedIcon />}
            onClick={processPending} disabled={processing || syncing || pendingCount === 0}>
            {processing ? "Processing…" : `Process (${pendingCount})`}
          </Button>
        </Stack>
      </Stack>

      {result && (
        <Alert severity="success" sx={{ mb: 2 }}>
          Synced — scanned {result.scanned}, {result.new_messages} new email(s), {result.new_attachments} attachment(s).
        </Alert>
      )}
      {processResult && (
        <Alert severity={processResult.failed > 0 ? "warning" : "success"} sx={{ mb: 2 }}>
          Processed {processResult.processed} attachment(s) — {processResult.completed} invoice(s) created, {processResult.failed} failed.
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}{" "}
          {error.toLowerCase().includes("connected") && <Link to="/settings">Connect Gmail in Settings</Link>}
        </Alert>
      )}

      <TextField size="small" type="search" placeholder="Search sender or subject…"
        value={search} onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 2, width: "100%", maxWidth: 360 }} />

      <Card variant="outlined" sx={{ p: { xs: 1, sm: 2 } }}>
        {loading ? (
          <SkeletonLines count={6} />
        ) : filtered.length === 0 ? (
          <EmptyState icon="📧" title="No emails yet"
            message="Click “Sync now” to pull invoices from your inbox — or connect Gmail first."
            action={<Button component={Link} to="/settings" variant="outlined">Go to Settings</Button>} />
        ) : (
          <Box sx={{ overflowX: "auto" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>From</TableCell><TableCell>Subject</TableCell>
                  <TableCell>Received</TableCell><TableCell>Attachments</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filtered.map((e) => (
                  <TableRow key={e.id} hover>
                    <TableCell sx={{ maxWidth: 180 }}>
                      <Typography variant="body2" noWrap>{e.sender ?? "—"}</Typography>
                    </TableCell>
                    <TableCell sx={{ maxWidth: 280 }}>
                      <Typography variant="body2" noWrap>{e.subject ?? "—"}</Typography>
                    </TableCell>
                    <TableCell>{(e.received_at || "").slice(0, 10) || "—"}</TableCell>
                    <TableCell>
                      <Stack spacing={0.5}>
                        {e.attachments.map((a) => (
                          <Chip key={a.id} size="small" variant="outlined" color="default"
                            label={a.filename ?? "file"} sx={{ maxWidth: 200, alignSelf: "flex-start" }}
                            {...(a.invoice_id
                              ? { component: Link, to: `/invoices/${a.invoice_id}`, clickable: true }
                              : {})} />
                        ))}
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Stack spacing={0.5}>
                        {e.attachments.map((a) => {
                          const { icon, tone, label } = statusVisual(a);
                          const canRetry = a.status === "failed";
                          const isRetrying = retryingIds.has(a.id);
                          return (
                            <Stack key={a.id} direction="row" spacing={0.5} sx={{ alignItems: "center", height: 32 }}>
                              <Tooltip title={label}>
                                <Box sx={{
                                  display: "flex",
                                  color: tone === "disabled" ? "text.disabled" : `${tone}.main`,
                                }}>
                                  {icon}
                                </Box>
                              </Tooltip>
                              <Tooltip title={canRetry ? "Retry now" : "Only failed attachments can be retried"}>
                                <span>
                                  <IconButton size="small" disabled={!canRetry || isRetrying}
                                    onClick={() => retryAttachment(a.id)} aria-label="Retry">
                                    {isRetrying
                                      ? <CircularProgress size={16} />
                                      : <RestartAltRoundedIcon fontSize="small" />}
                                  </IconButton>
                                </span>
                              </Tooltip>
                            </Stack>
                          );
                        })}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )}
      </Card>

      {logs.length > 0 && (
        <Card variant="outlined" sx={{ mt: 3, p: 2 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1.5 }}>Recent activity</Typography>
          <Stack divider={<Divider />} spacing={1}>
            {logs.map((log) => (
              <Stack key={log.id} direction="row" spacing={1.5}
                sx={{ alignItems: "flex-start", justifyContent: "space-between" }}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {log.step.replaceAll("_", " ")}
                  </Typography>
                  {log.message && (
                    <Typography variant="caption" color="text.secondary" noWrap
                      sx={{ display: "block", maxWidth: { xs: 220, sm: 480 } }}>
                      {log.message}
                    </Typography>
                  )}
                </Box>
                <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexShrink: 0 }}>
                  {log.status === "error" && <Chip size="small" color="error" label="error" />}
                  <Typography variant="caption" color="text.secondary">
                    {(log.created_at || "").slice(11, 16) || "—"}
                  </Typography>
                </Stack>
              </Stack>
            ))}
          </Stack>
        </Card>
      )}
    </Box>
  );
}
