import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  Box, Card, Grid, Typography, Button, TextField, Stack, Alert, Chip,
  ToggleButton, ToggleButtonGroup,
} from "@mui/material";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import { api } from "../api";
import type { Invoice, InvoiceStatus } from "../types";
import StatusBadge from "../components/StatusBadge";
import PageHeader from "../components/PageHeader";
import { SkeletonLines } from "../components/Skeleton";

const STATUSES: InvoiceStatus[] = ["paid", "pending", "unpaid"];

// The AI-extracted fields a reviewer may need to correct.
interface DetailsForm {
  vendor: string;
  invoice_number: string;
  invoice_date: string;
  gst: string;
  total: string;
}

function toForm(inv: Invoice): DetailsForm {
  return {
    vendor: inv.vendor ?? "",
    invoice_number: inv.invoice_number ?? "",
    invoice_date: inv.invoice_date ?? "",
    gst: inv.gst == null ? "" : String(inv.gst),
    total: inv.total == null ? "" : String(inv.total),
  };
}

export default function InvoiceDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [dueDate, setDueDate] = useState("");
  const [form, setForm] = useState<DetailsForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function load() {
    setLoading(true);
    setNotFound(false);
    setLoadError(false);
    api(`/invoices/${id}`)
      .then((r) => {
        if (r.status === 404) { setNotFound(true); return null; }
        if (!r.ok) { setLoadError(true); return null; }
        return r.json();
      })
      .then((data: Invoice | null) => {
        if (data) { setInvoice(data); setDueDate(data.due_date || ""); setForm(toForm(data)); }
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  // Single PATCH helper. On success it swaps in the server's copy (so
  // `reviewed`, re-formatted money, etc. all reflect reality); on a 409
  // (vendor/number collision) it surfaces the detail.
  async function patch(body: Record<string, unknown>) {
    setSaving(true);
    setError("");
    try {
      const res = await api(`/invoices/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "Could not save."); return false; }
      setInvoice(data as Invoice);
      setForm(toForm(data as Invoice));
      return true;
    } catch {
      setError("Could not reach the server.");
      return false;
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <Card variant="outlined" sx={{ p: 3 }}><SkeletonLines count={6} /></Card>;
  }
  if (loadError) {
    return (
      <Card variant="outlined" sx={{ p: 3 }}>
        <Typography variant="h6">Couldn't load this invoice</Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Something went wrong reaching the server. Try again.
        </Typography>
        <Button variant="contained" onClick={load}>Retry</Button>
      </Card>
    );
  }
  if (notFound || !invoice || !form) {
    return (
      <Card variant="outlined" sx={{ p: 3 }}>
        <Typography variant="h6">Invoice not found</Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          It may have been removed, or belongs to another workspace.
        </Typography>
        <Button component={Link} to="/invoices" variant="contained">Back to invoices</Button>
      </Card>
    );
  }

  const original = toForm(invoice);
  const dirty = (Object.keys(form) as (keyof DetailsForm)[]).some((k) => form[k] !== original[k]);

  function field(label: string, key: keyof DetailsForm, type = "text") {
    return (
      <TextField label={label} size="small" fullWidth type={type}
        value={form![key]} onChange={(e) => setForm({ ...form!, [key]: e.target.value })}
        slotProps={type === "date" ? { inputLabel: { shrink: true } } : undefined} />
    );
  }

  function saveDetails() {
    // Send only what changed; blank numeric fields are left unchanged (the
    // API treats null as "don't touch"), so clearing a total isn't supported
    // here — a reviewer corrects a wrong value, not deletes it.
    const body: Record<string, unknown> = {};
    if (form!.vendor !== original.vendor) body.vendor = form!.vendor;
    if (form!.invoice_number !== original.invoice_number) body.invoice_number = form!.invoice_number;
    if (form!.invoice_date !== original.invoice_date) body.invoice_date = form!.invoice_date;
    if (form!.gst !== original.gst) body.gst = form!.gst === "" ? null : form!.gst;
    if (form!.total !== original.total) body.total = form!.total === "" ? null : form!.total;
    patch(body);
  }

  return (
    <Box>
      <PageHeader title={invoice.vendor || "Invoice"} subtitle={`Invoice ${invoice.invoice_number}`}
        onBack={() => navigate(-1)}
        actions={
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            {invoice.reviewed && (
              <Chip size="small" color="success" variant="outlined"
                icon={<CheckCircleRoundedIcon />} label="Reviewed" />
            )}
            <StatusBadge status={invoice.status} />
          </Stack>
        } />

      {!invoice.reviewed && (
        <Alert severity="warning" sx={{ mb: 2 }}
          action={
            <Button color="inherit" size="small" disabled={saving}
              onClick={() => patch({ reviewed: true })}>
              {saving ? "Saving…" : "Mark as reviewed"}
            </Button>
          }>
          These figures were extracted by AI and haven't been reviewed. Check the details, correct anything wrong, then mark it reviewed.
        </Alert>
      )}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>{error}</Alert>}

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 7 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2 }}>Details</Typography>
            <Stack spacing={2}>
              {field("Vendor", "vendor")}
              {field("Invoice number", "invoice_number")}
              {field("Invoice date", "invoice_date", "date")}
              <Stack direction="row" spacing={2}>
                {field("GST", "gst")}
                {field("Total", "total")}
              </Stack>
              <Typography variant="caption" color="text.secondary">
                Uploaded {String(invoice.created_at || "—").slice(0, 16)}
              </Typography>
              <Box>
                <Button variant="contained" disabled={saving || !dirty} onClick={saveDetails}>
                  {saving ? "Saving…" : "Save changes"}
                </Button>
              </Box>
            </Stack>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 5 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 2 }}>Manage</Typography>

            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>Status</Typography>
            <ToggleButtonGroup value={invoice.status} exclusive size="small" disabled={saving}
              onChange={(_, v: InvoiceStatus | null) => v && patch({ status: v })} sx={{ mb: 3 }}>
              {STATUSES.map((s) => (
                <ToggleButton key={s} value={s} sx={{ textTransform: "capitalize" }}>{s}</ToggleButton>
              ))}
            </ToggleButtonGroup>

            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>Due date</Typography>
            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
              <TextField size="small" type="date" value={dueDate}
                onChange={(e) => setDueDate(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
              <Button variant="contained" disabled={saving || dueDate === (invoice.due_date || "")}
                onClick={() => patch({ due_date: dueDate })}>
                {saving ? "Saving…" : "Save"}
              </Button>
            </Stack>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
