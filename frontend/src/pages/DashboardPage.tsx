import { useEffect, useState } from "react";
import type { ReactNode } from "react";
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
import { api, formatMoney, monthLabel } from "../api";
import type { DashboardSummary, Invoice } from "../types";
import StatCard from "../components/StatCard";
import StatusBadge from "../components/StatusBadge";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";
import Skeleton, { SkeletonLines } from "../components/Skeleton";
import DescriptionRoundedIcon from "@mui/icons-material/DescriptionRounded";
import PaidRoundedIcon from "@mui/icons-material/PaidRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import HourglassEmptyRoundedIcon from "@mui/icons-material/HourglassEmptyRounded";
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded";
import TrendingUpRoundedIcon from "@mui/icons-material/TrendingUpRounded";
import PaymentsRoundedIcon from "@mui/icons-material/PaymentsRounded";
import PieChartOutlineRoundedIcon from "@mui/icons-material/PieChartOutlineRounded";
import EmojiEventsRoundedIcon from "@mui/icons-material/EmojiEventsRounded";
import TaskAltRoundedIcon from "@mui/icons-material/TaskAltRounded";

// Small uppercase section heading — groups the page into scannable bands
// instead of one undifferentiated pile of cards.
function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <Typography variant="overline" color="text.secondary"
      sx={{ display: "block", mb: 1.5, letterSpacing: "0.08em", fontWeight: 700 }}>
      {children}
    </Typography>
  );
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

  // IMPORTANT: with MUI cssVariables enabled, theme.palette.* returns the
  // DEFAULT (light) literal in JS, not the active scheme's value — so colors
  // read that way are wrong in dark mode (invisible axis text, white tooltip,
  // over-bright grid). theme.vars.palette.* are CSS variables that adapt to
  // the active scheme; use those for everything handed to Recharts/SVG.
  const pal = theme.vars ? theme.vars.palette : theme.palette;
  const CHART = {
    accent: pal.primary.main,
    bar: pal.primary.light,   // a lighter on-brand tone for the spending bars
    grid: pal.divider,
    axis: pal.text.primary,   // adapts per scheme → readable in light and dark
    cursor: pal.action.hover, // subtle hover tint instead of Recharts' grey box
    status: {
      paid: pal.success.main,
      pending: pal.warning.main,
      unpaid: pal.error.main,
    } as Record<string, string>,
  };
  const tooltipStyle = {
    contentStyle: {
      background: pal.background.paper,
      border: `1px solid ${pal.divider}`,
      borderRadius: 10,
      color: pal.text.primary,
      fontSize: 13,
    },
    labelStyle: { color: pal.text.secondary },
    itemStyle: { color: pal.text.primary },
  };

  const today = new Date().toISOString().slice(0, 10);
  const needsReview = summary?.needs_review ?? 0;
  const overdue = invoices.filter((i) => i.due_date && i.due_date < today && i.status !== "paid");
  const recentUploads = [...invoices]
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
    .slice(0, 3);
  const recentInvoices = invoices.slice(0, 6);

  // Last 12 data points only — keeps the trend about the recent business,
  // not skewed by one stray old invoice.
  const monthlyData = (summary?.monthly_trend || []).slice(-12).map((m) => ({ ...m, label: monthLabel(m.month, true) }));

  // Month-over-month spend direction for the headline card.
  const spendThis = summary?.spend_this_month ?? 0;
  const spendLast = summary?.spend_last_month ?? 0;
  let spendHint = "vs. last month";
  if (spendLast > 0) {
    const pct = Math.round(((spendThis - spendLast) / spendLast) * 100);
    spendHint = `${pct >= 0 ? "▲" : "▼"} ${Math.abs(pct)}% vs. last month`;
  } else if (spendThis > 0) {
    spendHint = "first month with spend";
  }
  const statusData = (summary?.status_distribution || []).map((s) => ({ name: s.status, value: s.count }));
  const supplierData = (summary?.top_suppliers || []).map((s) => ({ name: s.vendor, amount: s.amount }));

  return (
    <Box>
      <PageHeader title="Dashboard" subtitle="An overview of your organization's invoices."
        actions={<Button component={Link} to="/invoices" variant="contained">Upload Invoice</Button>} />

      {/* ---- Needs attention: the things that require the owner to act,
             first thing they see. ---- */}
      <SectionLabel>Needs attention</SectionLabel>
      <Grid container spacing={2} sx={{ mb: 4 }}>
        {loading
          ? Array.from({ length: 3 }).map((_, i) => (
              <Grid key={i} size={{ xs: 12, md: 4 }}>
                <Card variant="outlined" sx={{ p: 2 }}><Skeleton height={52} /></Card>
              </Grid>
            ))
          : (
            <>
              <Grid size={{ xs: 12, md: 4 }}>
                <StatCard tone={summary && summary.overdue_count > 0 ? "red" : "neutral"}
                  icon={<WarningAmberRoundedIcon fontSize="inherit" />} label="Overdue"
                  value={formatMoney(summary?.overdue_amount)}
                  hint={`${summary?.overdue_count ?? 0} invoice${summary?.overdue_count === 1 ? "" : "s"} past due`} />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <StatCard tone={summary && summary.due_week_count > 0 ? "amber" : "neutral"}
                  icon={<HourglassEmptyRoundedIcon fontSize="inherit" />} label="Due this week"
                  value={formatMoney(summary?.due_week_amount)}
                  hint={`${summary?.due_week_count ?? 0} invoice${summary?.due_week_count === 1 ? "" : "s"} coming due`} />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <StatCard tone={needsReview > 0 ? "amber" : "neutral"}
                  icon={<TaskAltRoundedIcon fontSize="inherit" />} label="Needs review"
                  value={needsReview}
                  hint={needsReview > 0 ? "AI figures to confirm" : "all confirmed"} />
              </Grid>
            </>
          )}
      </Grid>

      {/* ---- Money: the headline business numbers. ---- */}
      <SectionLabel>Money</SectionLabel>
      <Grid container spacing={2} sx={{ mb: 4 }}>
        {loading
          ? Array.from({ length: 3 }).map((_, i) => (
              <Grid key={i} size={{ xs: 12, md: 4 }}>
                <Card variant="outlined" sx={{ p: 2 }}><Skeleton height={52} /></Card>
              </Grid>
            ))
          : (
            <>
              <Grid size={{ xs: 12, md: 4 }}>
                <StatCard tone="brand" icon={<PaidRoundedIcon fontSize="inherit" />} label="Outstanding"
                  value={formatMoney(summary?.outstanding_amount)} hint="unpaid + pending" />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <StatCard tone="neutral" icon={<PaymentsRoundedIcon fontSize="inherit" />} label="Spend this month"
                  value={formatMoney(summary?.spend_this_month)} hint={spendHint} />
              </Grid>
              <Grid size={{ xs: 12, md: 4 }}>
                <StatCard tone="green" icon={<CheckCircleRoundedIcon fontSize="inherit" />} label="Paid"
                  value={formatMoney(summary?.paid_amount)} hint="all time" />
              </Grid>
            </>
          )}
      </Grid>

      {/* ---- Insights: charts ---- */}
      <SectionLabel>Insights</SectionLabel>
      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>Monthly Invoice Trend</Typography>
            {loading ? <Skeleton height={220} /> : monthlyData.length === 0 ? (
              <EmptyState icon={<TrendingUpRoundedIcon fontSize="inherit" />} title="No data yet" message="Upload invoices to see trends." />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={monthlyData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                  <CartesianGrid stroke={CHART.grid} vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: CHART.axis, fontSize: 12 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fill: CHART.axis, fontSize: 12 }} tickLine={false} axisLine={false} allowDecimals={false} />
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
              <EmptyState icon={<PaymentsRoundedIcon fontSize="inherit" />} title="No data yet" message="Upload invoices to see spending." />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={monthlyData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                  <CartesianGrid stroke={CHART.grid} vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: CHART.axis, fontSize: 12 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fill: CHART.axis, fontSize: 12 }} tickLine={false} axisLine={false} width={64} tickFormatter={(v) => formatMoney(v)} />
                  <Tooltip {...tooltipStyle} cursor={{ fill: CHART.cursor }} formatter={(value) => formatMoney(value as number)} />
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
              <EmptyState icon={<PieChartOutlineRoundedIcon fontSize="inherit" />} title="No data yet" message="Statuses appear once you have invoices." />
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
              <EmptyState icon={<EmojiEventsRoundedIcon fontSize="inherit" />} title="No suppliers yet" message="Top suppliers appear here." />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={supplierData} layout="vertical" margin={{ top: 4, right: 16, bottom: 8, left: 8 }}>
                  <CartesianGrid stroke={CHART.grid} horizontal={false} />
                  <XAxis type="number" tick={{ fill: CHART.axis, fontSize: 12 }} tickLine={false} axisLine={false} tickFormatter={(v) => formatMoney(v)} />
                  <YAxis type="category" dataKey="name" tick={{ fill: CHART.axis, fontSize: 11 }} width={110} tickLine={false} axisLine={false} />
                  <Tooltip {...tooltipStyle} cursor={{ fill: CHART.cursor }} formatter={(value) => formatMoney(value as number)} />
                  <Bar dataKey="amount" name="Spend" fill={CHART.accent} radius={[0, 6, 6, 0]} barSize={16} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </Grid>
      </Grid>

      {/* ---- Activity ---- */}
      <SectionLabel>Activity</SectionLabel>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Card variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" sx={{ mb: 1, justifyContent: "space-between", alignItems: "center" }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Recent Invoices</Typography>
              <Button component={Link} to="/invoices" size="small">View all</Button>
            </Stack>
            {loading ? <SkeletonLines count={5} /> : recentInvoices.length === 0 ? (
              <EmptyState icon={<DescriptionRoundedIcon fontSize="inherit" />} title="No invoices yet" message="Upload your first invoice to get started."
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
            {loading ? <SkeletonLines count={4} /> : needsReview === 0 && overdue.length === 0 && recentUploads.length === 0 ? (
              <EmptyState icon={<TaskAltRoundedIcon fontSize="inherit" />} title="You're all caught up" message="Nothing needs review." />
            ) : (
              <List disablePadding>
                {needsReview > 0 && (
                  <ListItemButton onClick={() => navigate("/invoices?review=1")} sx={{ borderRadius: 1, alignItems: "flex-start" }}>
                    <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: "warning.main", mt: 1, mr: 1.5, flexShrink: 0 }} />
                    <Box>
                      <Typography variant="body2"><b>{needsReview}</b> invoice{needsReview === 1 ? "" : "s"} need review</Typography>
                      <Typography variant="caption" color="text.secondary">AI-extracted — confirm the figures</Typography>
                    </Box>
                  </ListItemButton>
                )}
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
