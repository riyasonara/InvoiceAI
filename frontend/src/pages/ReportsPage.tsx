import { useEffect, useState } from "react";
import {
  Box, Card, Grid, Typography, Button, Stack,
  Table, TableBody, TableCell, TableHead, TableRow,
} from "@mui/material";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import { api, formatMoney } from "../api";
import type { DashboardSummary, Invoice } from "../types";
import EmptyState from "../components/EmptyState";
import { SkeletonLines } from "../components/Skeleton";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function monthLabel(m: string): string {
  if (!m || !m.includes("-")) return m || "";
  const [y, mm] = m.split("-");
  return `${MONTHS[Number(mm) - 1] || mm} ${y}`;
}

export default function ReportsPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api("/dashboard/summary").then((r) => (r.ok ? r.json() : null)),
      api("/invoices").then((r) => (r.ok ? r.json() : [])),
    ]).then(([s, inv]) => {
      setSummary(s as DashboardSummary | null);
      setInvoices((inv as Invoice[]) || []);
    }).finally(() => setLoading(false));
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
  const tiles: [string, string | number][] = [
    ["Total Invoices", summary?.total_invoices ?? 0],
    ["Total Amount", formatMoney(summary?.total_amount)],
    ["Paid", formatMoney(summary?.paid_amount)],
    ["Pending", formatMoney(summary?.pending_amount)],
    ["Unpaid", formatMoney(summary?.unpaid_amount)],
  ];

  return (
    <Box>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}
        sx={{ mb: 3, justifyContent: "space-between", alignItems: { sm: "flex-start" } }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>Reports</Typography>
          <Typography color="text.secondary">Spending breakdowns and data export.</Typography>
        </Box>
        <Button variant="contained" startIcon={<DownloadRoundedIcon />}
          onClick={exportCsv} disabled={invoices.length === 0}>Export CSV</Button>
      </Stack>

      <Grid container spacing={2} sx={{ mb: 2 }}>
        {tiles.map(([label, value]) => (
          <Grid key={label} size={{ xs: 6, sm: 4, md: 2.4 }}>
            <Card variant="outlined" sx={{ p: 2 }}>
              <Typography variant="body2" color="text.secondary">{label}</Typography>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>{value}</Typography>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Monthly Breakdown</Typography>
            {monthly.length === 0 ? (
              <EmptyState icon="📅" title="No data yet" message="Upload invoices to build reports." />
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
