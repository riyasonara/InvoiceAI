import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  Box, Card, Grid, Typography, Button, TextField, Stack,
  ToggleButton, ToggleButtonGroup, Table, TableBody, TableCell, TableRow,
} from "@mui/material";
import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import { api, formatMoney, formatDate } from "../api";
import type { Invoice, InvoiceStatus } from "../types";
import StatusBadge from "../components/StatusBadge";
import { SkeletonLines } from "../components/Skeleton";

const STATUSES: InvoiceStatus[] = ["paid", "pending", "unpaid"];

export default function InvoiceDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [dueDate, setDueDate] = useState("");
  const [saving, setSaving] = useState(false);

  function load() {
    api(`/invoices/${id}`)
      .then((r) => {
        if (r.status === 404) { setNotFound(true); return null; }
        return r.ok ? r.json() : null;
      })
      .then((data: Invoice | null) => {
        if (data) { setInvoice(data); setDueDate(data.due_date || ""); }
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  async function patch(body: { status?: InvoiceStatus; due_date?: string }) {
    setSaving(true);
    try {
      const res = await api(`/invoices/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) setInvoice((await res.json()) as Invoice);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <Card variant="outlined" sx={{ p: 3 }}><SkeletonLines count={6} /></Card>;
  }
  if (notFound || !invoice) {
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

  const rows: [string, string][] = [
    ["Vendor", invoice.vendor ?? "—"],
    ["Invoice Number", invoice.invoice_number ?? "—"],
    ["Invoice Date", formatDate(invoice.invoice_date)],
    ["GST", formatMoney(invoice.gst)],
    ["Total", formatMoney(invoice.total)],
    ["Uploaded", String(invoice.created_at || "—").slice(0, 16)],
  ];

  return (
    <Box>
      <Stack direction="row" sx={{ mb: 3, justifyContent: "space-between", alignItems: "flex-start" }} spacing={2}>
        <Box>
          <Button startIcon={<ArrowBackRoundedIcon />} onClick={() => navigate(-1)} size="small" sx={{ mb: 1 }}>
            Back
          </Button>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>{invoice.vendor || "Invoice"}</Typography>
          <Typography color="text.secondary">Invoice {invoice.invoice_number}</Typography>
        </Box>
        <StatusBadge status={invoice.status} />
      </Stack>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 7 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Details</Typography>
            <Table size="small">
              <TableBody>
                {rows.map(([k, v]) => (
                  <TableRow key={k}>
                    <TableCell sx={{ color: "text.secondary", width: "45%", border: 0 }}>{k}</TableCell>
                    <TableCell sx={{ fontWeight: 500, border: 0 }}>{v}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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
