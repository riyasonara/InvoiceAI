import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Box, Grid, Card, Typography, Button, Stack,
  Table, TableBody, TableCell, TableHead, TableRow, List, ListItemButton,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { api, formatMoney } from "../api";
import type { DashboardSummary, Invoice } from "../types";
import StatCard from "../components/StatCard";
import StatusBadge from "../components/StatusBadge";
import EmptyState from "../components/EmptyState";
import Skeleton, { SkeletonLines } from "../components/Skeleton";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function monthLabel(m: string): string {
  if (!m || !m.includes("-")) return m || "";
  const [y, mm] = m.split("-");
  return `${MONTHS[Number(mm) - 1] || mm} '${y.slice(2)}`;
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const theme = useTheme();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    Promise.all([
      api("/dashboard/summary").then((r) => (r.ok ? r.json() : null)),
      api("/invoices").then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([s, inv]) => {
        if (!alive) return;
        setSummary(s as DashboardSummary | null);
        setInvoices((inv as Invoice[]) || []);
      })
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, []);

  const CHART = {
    accent: theme.palette.primary.main,
    bar: "#6366f1",
    grid: theme.palette.divider,
    axis: theme.palette.text.secondary,
    status: {
      paid: theme.palette.success.main,
      pending: theme.palette.warning.main,
      unpaid: theme.palette.error.main,
    } as Record<string, string>,
  };
  const tooltipStyle = {
    contentStyle: {
      background: theme.palette.background.paper,
      border: `1px solid ${theme.palette.divider}`,
      borderRadius: 10,
      color: theme.palette.text.primary,
      fontSize: 13,
    },
    labelStyle: { color: theme.palette.text.secondary },
    itemStyle: { color: theme.palette.text.primary },
  };

  const today = new Date().toISOString().slice(0, 10);
  const overdue = invoices.filter((i) => i.due_date && i.due_date < today && i.status !== "paid");
  const recentUploads = [...invoices]
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
    .slice(0, 3);
  const recentInvoices = invoices.slice(0, 6);

  const monthlyData = (summary?.monthly_trend || []).map((m) => ({ ...m, label: monthLabel(m.month) }));
  const statusData = (summary?.status_distribution || []).map((s) => ({ name: s.status, value: s.count }));
  const supplierData = (summary?.top_suppliers || []).map((s) => ({ name: s.vendor, amount: s.amount }));

  return (
    <Box>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}
        sx={{ mb: 3, justifyContent: "space-between", alignItems: { sm: "flex-start" } }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>Dashboard</Typography>
          <Typography color="text.secondary">An overview of your organization's invoices.</Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
          <Button component={Link} to="/invoices" variant="contained">Upload Invoice</Button>
          <Button component={Link} to="/suppliers" variant="outlined" color="inherit">View Suppliers</Button>
          <Button component={Link} to="/reports" variant="outlined" color="inherit">View Reports</Button>
        </Stack>
      </Stack>

      {/* Stat cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {loading
          ? Array.from({ length: 6 }).map((_, i) => (
              <Grid key={i} size={{ xs: 12, sm: 6, md: 4 }}>
                <Card variant="outlined" sx={{ p: 2 }}><Skeleton height={52} /></Card>
              </Grid>
            ))
          : (
            <>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}><StatCard tone="brand" icon="📄" label="Total Invoices" value={summary?.total_invoices ?? 0} /></Grid>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}><StatCard tone="indigo" icon="🏢" label="Total Suppliers" value={summary?.total_suppliers ?? 0} /></Grid>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}><StatCard tone="brand" icon="💰" label="Total Amount" value={formatMoney(summary?.total_amount)} /></Grid>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}><StatCard tone="green" icon="✅" label="Paid Amount" value={formatMoney(summary?.paid_amount)} /></Grid>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}><StatCard tone="amber" icon="⏳" label="Pending Amount" value={formatMoney(summary?.pending_amount)} /></Grid>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}><StatCard tone="red" icon="⚠️" label="Unpaid Invoices" value={summary?.unpaid_count ?? 0} hint={`${formatMoney(summary?.unpaid_amount)} outstanding`} /></Grid>
            </>
          )}
      </Grid>

      {/* Email automation tiles */}
      {!loading && summary?.email_stats && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid size={{ xs: 6, md: 3 }}><StatCard tone="indigo" icon="📥" label="Emails Synced Today" value={summary.email_stats.synced_today} /></Grid>
          <Grid size={{ xs: 6, md: 3 }}><StatCard tone="green" icon="📨" label="Imported from Email" value={summary.email_stats.imported} /></Grid>
          <Grid size={{ xs: 6, md: 3 }}><StatCard tone="red" icon="❌" label="Processing Errors" value={summary.email_stats.errors} /></Grid>
          <Grid size={{ xs: 6, md: 3 }}><StatCard tone="amber" icon="🕓" label="Pending Queue" value={summary.email_stats.pending} /></Grid>
        </Grid>
      )}

      {/* Charts */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Monthly Invoice Trend</Typography>
            {loading ? <Skeleton height={220} /> : monthlyData.length === 0 ? (
              <EmptyState icon="📈" title="No data yet" message="Upload invoices to see trends." />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={monthlyData} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                  <CartesianGrid stroke={CHART.grid} vertical={false} />
                  <XAxis dataKey="label" stroke={CHART.axis} fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke={CHART.axis} fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip {...tooltipStyle} />
                  <Line type="monotone" dataKey="count" name="Invoices" stroke={CHART.accent} strokeWidth={2.5} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Monthly Spending</Typography>
            {loading ? <Skeleton height={220} /> : monthlyData.length === 0 ? (
              <EmptyState icon="💸" title="No data yet" message="Upload invoices to see spending." />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={monthlyData} margin={{ top: 8, right: 8, bottom: 0, left: -4 }}>
                  <CartesianGrid stroke={CHART.grid} vertical={false} />
                  <XAxis dataKey="label" stroke={CHART.axis} fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke={CHART.axis} fontSize={12} tickLine={false} axisLine={false} width={64} tickFormatter={(v) => formatMoney(v)} />
                  <Tooltip {...tooltipStyle} formatter={(value) => formatMoney(value as number)} />
                  <Bar dataKey="amount" name="Spend" fill={CHART.bar} radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Invoice Status Distribution</Typography>
            {loading ? <Skeleton height={220} /> : statusData.length === 0 ? (
              <EmptyState icon="🥧" title="No data yet" message="Statuses appear once you have invoices." />
            ) : (
              <>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                      {statusData.map((entry) => (
                        <Cell key={entry.name} fill={CHART.status[entry.name] || CHART.axis} />
                      ))}
                    </Pie>
                    <Tooltip {...tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
                <Stack direction="row" spacing={2} useFlexGap sx={{ justifyContent: "center", flexWrap: "wrap" }}>
                  {statusData.map((s) => (
                    <Stack key={s.name} direction="row" spacing={0.5} sx={{ alignItems: "center" }}>
                      <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: CHART.status[s.name] || CHART.axis }} />
                      <Typography variant="caption" color="text.secondary" sx={{ textTransform: "capitalize" }}>{s.name} ({s.value})</Typography>
                    </Stack>
                  ))}
                </Stack>
              </>
            )}
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Top Suppliers</Typography>
            {loading ? <Skeleton height={220} /> : supplierData.length === 0 ? (
              <EmptyState icon="🏆" title="No suppliers yet" message="Top suppliers appear here." />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={supplierData} layout="vertical" margin={{ top: 4, right: 12, bottom: 0, left: 8 }}>
                  <CartesianGrid stroke={CHART.grid} horizontal={false} />
                  <XAxis type="number" stroke={CHART.axis} fontSize={12} tickLine={false} axisLine={false} tickFormatter={(v) => formatMoney(v)} />
                  <YAxis type="category" dataKey="name" stroke={CHART.axis} fontSize={11} width={110} tickLine={false} axisLine={false} />
                  <Tooltip {...tooltipStyle} formatter={(value) => formatMoney(value as number)} />
                  <Bar dataKey="amount" name="Spend" fill={CHART.accent} radius={[0, 6, 6, 0]} barSize={16} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </Grid>
      </Grid>

      {/* Recent invoices + notifications */}
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" sx={{ mb: 1, justifyContent: "space-between", alignItems: "center" }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Recent Invoices</Typography>
              <Button component={Link} to="/invoices" size="small">View all</Button>
            </Stack>
            {loading ? <SkeletonLines count={5} /> : recentInvoices.length === 0 ? (
              <EmptyState icon="📄" title="No invoices yet" message="Upload your first invoice to get started."
                action={<Button component={Link} to="/invoices" variant="contained">Upload Invoice</Button>} />
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow><TableCell>Invoice #</TableCell><TableCell>Supplier</TableCell><TableCell>Amount</TableCell><TableCell>Status</TableCell></TableRow>
                </TableHead>
                <TableBody>
                  {recentInvoices.map((inv) => (
                    <TableRow key={inv.id} hover onClick={() => navigate(`/invoices/${inv.id}`)} sx={{ cursor: "pointer" }}>
                      <TableCell sx={{ fontWeight: 600 }}>{inv.invoice_number ?? "—"}</TableCell>
                      <TableCell>{inv.vendor ?? "—"}</TableCell>
                      <TableCell>{formatMoney(inv.total)}</TableCell>
                      <TableCell><StatusBadge status={inv.status} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Notifications</Typography>
            {loading ? <SkeletonLines count={4} /> : overdue.length === 0 && recentUploads.length === 0 ? (
              <EmptyState icon="🔔" title="You're all caught up" message="No overdue invoices." />
            ) : (
              <List disablePadding>
                {overdue.map((inv) => (
                  <ListItemButton key={`o-${inv.id}`} onClick={() => navigate(`/invoices/${inv.id}`)} sx={{ borderRadius: 1, alignItems: "flex-start" }}>
                    <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: "error.main", mt: 1, mr: 1.5, flexShrink: 0 }} />
                    <Box>
                      <Typography variant="body2"><b>Overdue:</b> {inv.invoice_number} — {inv.vendor}</Typography>
                      <Typography variant="caption" color="text.secondary">Due {inv.due_date} · {formatMoney(inv.total)}</Typography>
                    </Box>
                  </ListItemButton>
                ))}
                {recentUploads.map((inv) => (
                  <ListItemButton key={`r-${inv.id}`} onClick={() => navigate(`/invoices/${inv.id}`)} sx={{ borderRadius: 1, alignItems: "flex-start" }}>
                    <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: "success.main", mt: 1, mr: 1.5, flexShrink: 0 }} />
                    <Box>
                      <Typography variant="body2">Uploaded {inv.invoice_number} — {inv.vendor}</Typography>
                      <Typography variant="caption" color="text.secondary">{String(inv.created_at || "").slice(0, 16)}</Typography>
                    </Box>
                  </ListItemButton>
                ))}
              </List>
            )}
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
