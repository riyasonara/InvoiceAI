import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box, Card, Typography, Button, TextField, Stack, Alert,
  ToggleButton, ToggleButtonGroup,
  Table, TableBody, TableCell, TableHead, TableRow,
} from "@mui/material";
import UploadFileRoundedIcon from "@mui/icons-material/UploadFileRounded";
import { api, formatMoney, formatDate } from "../api";
import type { Invoice } from "../types";
import StatusBadge from "../components/StatusBadge";
import EmptyState from "../components/EmptyState";
import { SkeletonLines } from "../components/Skeleton";

export default function InvoicesPage() {
  const navigate = useNavigate();

  // Upload state (unchanged logic from the original upload flow)
  const [file, setFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [justExtracted, setJustExtracted] = useState<Invoice | null>(null);

  // List + filter state
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  function loadInvoices() {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (status !== "all") params.set("status", status);
    if (fromDate) params.set("from_date", fromDate);
    if (toDate) params.set("to_date", toDate);
    const qs = params.toString();
    return api(`/invoices${qs ? `?${qs}` : ""}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setInvoices((data as Invoice[]) || []))
      .catch((err) => console.error("Failed to load invoices", err))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    const t = setTimeout(loadInvoices, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, status, fromDate, toDate]);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setUploadError("");
    setJustExtracted(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api("/extract", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) {
        setUploadError(data.detail || "Something went wrong while processing the file.");
        return;
      }
      setJustExtracted(data as Invoice);
      setFile(null);
      loadInvoices();
    } catch {
      setUploadError("Could not reach the server. Is the API running on port 8000?");
    } finally {
      setUploading(false);
    }
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700 }}>Invoices</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Upload, search, and manage your workspace invoices.
      </Typography>

      {/* Upload */}
      <Card variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ alignItems: { sm: "center" } }}>
          <Button component="label" variant="outlined" color="inherit" startIcon={<UploadFileRoundedIcon />}
            sx={{ flexGrow: 1, justifyContent: "flex-start", py: 1.5 }}>
            {file ? file.name : "Choose a PDF invoice…"}
            <input hidden type="file" accept="application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </Button>
          <Button variant="contained" onClick={handleUpload} disabled={!file || uploading}>
            {uploading ? "Extracting…" : "Extract Invoice"}
          </Button>
        </Stack>
      </Card>
      {uploadError && <Alert severity="error" sx={{ mb: 2 }}>{uploadError}</Alert>}
      {justExtracted && (
        <Alert severity="success" sx={{ mb: 2 }}>
          Extracted <b>{justExtracted.vendor}</b> — {justExtracted.invoice_number} ({formatMoney(justExtracted.total)})
        </Alert>
      )}

      {/* Filters */}
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} sx={{ mb: 2, alignItems: { md: "center" } }} useFlexGap>
        <TextField size="small" type="search" placeholder="Search supplier or invoice #…"
          value={search} onChange={(e) => setSearch(e.target.value)} sx={{ flexGrow: 1, minWidth: 220 }} />
        <ToggleButtonGroup value={status} exclusive size="small"
          onChange={(_, v) => v && setStatus(v)}>
          <ToggleButton value="all">All</ToggleButton>
          <ToggleButton value="paid">Paid</ToggleButton>
          <ToggleButton value="pending">Pending</ToggleButton>
          <ToggleButton value="unpaid">Unpaid</ToggleButton>
        </ToggleButtonGroup>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <TextField size="small" type="date" label="From" value={fromDate}
            onChange={(e) => setFromDate(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
          <TextField size="small" type="date" label="To" value={toDate}
            onChange={(e) => setToDate(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
        </Stack>
      </Stack>

      {/* Table */}
      <Card variant="outlined" sx={{ p: { xs: 1, sm: 2 } }}>
        {loading ? (
          <SkeletonLines count={6} />
        ) : invoices.length === 0 ? (
          <EmptyState icon="🔍" title="No invoices found"
            message="Try clearing filters, or upload an invoice above." />
        ) : (
          <Box sx={{ overflowX: "auto" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Invoice #</TableCell><TableCell>Supplier</TableCell><TableCell>Amount</TableCell>
                  <TableCell>Due Date</TableCell><TableCell>Status</TableCell><TableCell>Uploaded</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {invoices.map((inv) => (
                  <TableRow key={inv.id} hover onClick={() => navigate(`/invoices/${inv.id}`)} sx={{ cursor: "pointer" }}>
                    <TableCell sx={{ fontWeight: 600 }}>{inv.invoice_number ?? "—"}</TableCell>
                    <TableCell>{inv.vendor ?? "—"}</TableCell>
                    <TableCell>{formatMoney(inv.total)}</TableCell>
                    <TableCell>{formatDate(inv.due_date)}</TableCell>
                    <TableCell><StatusBadge status={inv.status} /></TableCell>
                    <TableCell>{formatDate(inv.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )}
      </Card>
    </Box>
  );
}
