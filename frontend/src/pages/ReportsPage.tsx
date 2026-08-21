import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  Box, Card, Grid, Typography, Button, Alert,
  Table, TableBody, TableCell, TableHead, TableRow,
} from "@mui/material";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import DescriptionRoundedIcon from "@mui/icons-material/DescriptionRounded";
import PaidRoundedIcon from "@mui/icons-material/PaidRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import HourglassEmptyRoundedIcon from "@mui/icons-material/HourglassEmptyRounded";
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded";
import EventBusyRoundedIcon from "@mui/icons-material/EventBusyRounded";
import { api, formatMoney, monthLabel } from "../api";
import type { DashboardSummary, Invoice } from "../types";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import { SkeletonLines } from "../components/Skeleton";

export default function ReportsPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    Promise.all([
      api("/dashboard/summary").then((r) => (r.ok ? r.json() : null)),
      api("/invoices").then((r) => (r.ok ? r.json() : [])),
    ]).then(([s, inv]) => {
      if (s === null) setError(true);
      setSummary(s as DashboardSummary | null);
      setInvoices((inv as Invoice[]) || []);
    }).catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  function exportCsv() {
    const headers = ["Invoice Number", "Supplier", "Invoice Date", "Due Date", "GST", "Total", "Status", "Uploaded"];
    const rows = invoices.map((i) => [
      i.invoice_number, i.vendor, i.invoice_date, i.due_date, i.gst, i.total, i.status, i.created_at,
    ]);
    const csv = [headers, ...rows]
      .map((r) => r.map((c) => `"${String(c ?? "").replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "invoices.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loading) {
    return <Card variant="outlined" sx={{ p: 3 }}><SkeletonLines count={6} /></Card>;
  }

  const monthly = summary?.monthly_trend || [];
  interface Tile { label: string; value: string | number; icon: ReactNode; tone: "brand" | "green" | "amber" | "red" }
  const tiles: Tile[] = [
    { label: "Total Invoices", value: summary?.total_invoices ?? 0, icon: <DescriptionRoundedIcon fontSize="inherit" />, tone: "brand" },
    { label: "Total Amount", value: formatMoney(summary?.total_amount), icon: <PaidRoundedIcon fontSize="inherit" />, tone: "brand" },
    { label: "Paid", value: formatMoney(summary?.paid_amount), icon: <CheckCircleRoundedIcon fontSize="inherit" />, tone: "green" },
    { label: "Pending", value: formatMoney(summary?.pending_amount), icon: <HourglassEmptyRoundedIcon fontSize="inherit" />, tone: "amber" },
    { label: "Unpaid", value: formatMoney(summary?.unpaid_amount), icon: <WarningAmberRoundedIcon fontSize="inherit" />, tone: "red" },
  ];

  return (
    <Box>
      <PageHeader title="Reports" subtitle="Spending breakdowns and data export."
        actions={
          <Button variant="contained" startIcon={<DownloadRoundedIcon />}
            onClick={exportCsv} disabled={invoices.length === 0}>Export CSV</Button>
        } />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>Couldn't load report data. Try reloading the page.</Alert>
      )}

      <Grid container spacing={2} sx={{ mb: 2 }}>
        {tiles.map((t) => (
          <Grid key={t.label} size={{ xs: 6, sm: 4, md: 2.4 }}>
            <StatCard tone={t.tone} icon={t.icon} label={t.label} value={t.value} />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Monthly Breakdown</Typography>
            {monthly.length === 0 ? (
              <EmptyState icon={<EventBusyRoundedIcon fontSize="inherit" />} title="No data yet"
                message="Upload invoices to build reports." />
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow><TableCell>Month</TableCell><TableCell>Invoices</TableCell><TableCell>Spend</TableCell></TableRow>
                </TableHead>
                <TableBody>
                  {monthly.map((m) => (
                    <TableRow key={m.month}>
                      <TableCell sx={{ fontWeight: 600 }}>{monthLabel(m.month)}</TableCell>
                      <TableCell>{m.count}</TableCell>
                      <TableCell>{formatMoney(m.amount)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>By Status</Typography>
            <Table size="small">
              <TableHead>
                <TableRow><TableCell>Status</TableCell><TableCell>Invoices</TableCell></TableRow>
              </TableHead>
              <TableBody>
                {(summary?.status_distribution || []).map((s) => (
                  <TableRow key={s.status}>
                    <TableCell sx={{ fontWeight: 600, textTransform: "capitalize" }}>{s.status}</TableCell>
                    <TableCell>{s.count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
