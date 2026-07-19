import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { api, formatMoney } from "../api";
import StatCard from "../components/StatCard";
import StatusBadge from "../components/StatusBadge";
import EmptyState from "../components/EmptyState";
import Skeleton, { SkeletonLines } from "../components/Skeleton";

const CHART = {
  accent: "#14b8a6",
  bar: "#6366f1",
  grid: "rgba(148,163,184,0.18)",
  axis: "#94a3b8",
  status: { paid: "#10b981", pending: "#f59e0b", unpaid: "#ef4444" },
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function monthLabel(m) {
  if (!m || !m.includes("-")) return m || "";
  const [y, mm] = m.split("-");
  return `${MONTHS[Number(mm) - 1] || mm} '${y.slice(2)}`;
}

const tooltipStyle = {
  contentStyle: {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    color: "var(--text)",
    fontSize: 13,
  },
  labelStyle: { color: "var(--text-muted)" },
  itemStyle: { color: "var(--text)" },
};

export default function DashboardPage() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    Promise.all([
      api("/dashboard/summary").then((r) => (r.ok ? r.json() : null)),
      api("/invoices").then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([s, inv]) => {
        if (!alive) return;
        setSummary(s);
        setInvoices(inv || []);
      })
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, []);

  const today = new Date().toISOString().slice(0, 10);
  const overdue = invoices.filter(
    (i) => i.due_date && i.due_date < today && i.status !== "paid"
  );
  const recentUploads = [...invoices]
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
    .slice(0, 3);
  const recentInvoices = invoices.slice(0, 6);

  const monthly = summary?.monthly_trend || [];
  const monthlyData = monthly.map((m) => ({ ...m, label: monthLabel(m.month) }));
  const statusData = (summary?.status_distribution || []).map((s) => ({
    name: s.status,
    value: s.count,
  }));
  const supplierData = (summary?.top_suppliers || []).map((s) => ({
    name: s.vendor,
    amount: s.amount,
  }));

  return (
    <div className="page">
      <div className="page-head row-between">
        <div>
          <h1>Dashboard</h1>
          <p className="subtitle">An overview of your organization's invoices.</p>
        </div>
        <div className="quick-actions">
          <Link className="btn-primary" to="/invoices">Upload Invoice</Link>
          <Link className="btn-ghost" to="/suppliers">View Suppliers</Link>
          <Link className="btn-ghost" to="/reports">View Reports</Link>
        </div>
      </div>

      {/* Stat cards */}
      <div className="stat-grid">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div className="stat-card" key={i}><Skeleton height={52} /></div>
          ))
        ) : (
          <>
            <StatCard tone="brand" icon="📄" label="Total Invoices" value={summary?.total_invoices ?? 0} />
            <StatCard tone="indigo" icon="🏢" label="Total Suppliers" value={summary?.total_suppliers ?? 0} />
            <StatCard tone="brand" icon="💰" label="Total Amount" value={formatMoney(summary?.total_amount)} />
            <StatCard tone="green" icon="✅" label="Paid Amount" value={formatMoney(summary?.paid_amount)} />
            <StatCard tone="amber" icon="⏳" label="Pending Amount" value={formatMoney(summary?.pending_amount)} />
            <StatCard tone="red" icon="⚠️" label="Unpaid Invoices" value={summary?.unpaid_count ?? 0}
              hint={formatMoney(summary?.unpaid_amount) + " outstanding"} />
          </>
        )}
      </div>

      {/* Charts */}
      <div className="chart-grid">
        <div className="card chart-card">
          <h2>Monthly Invoice Trend</h2>
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
        </div>

        <div className="card chart-card">
          <h2>Monthly Spending</h2>
          {loading ? <Skeleton height={220} /> : monthlyData.length === 0 ? (
            <EmptyState icon="💸" title="No data yet" message="Upload invoices to see spending." />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={monthlyData} margin={{ top: 8, right: 8, bottom: 0, left: -4 }}>
                <CartesianGrid stroke={CHART.grid} vertical={false} />
                <XAxis dataKey="label" stroke={CHART.axis} fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke={CHART.axis} fontSize={12} tickLine={false} axisLine={false} width={64}
                  tickFormatter={(v) => formatMoney(v)} />
                <Tooltip {...tooltipStyle} formatter={(v) => formatMoney(v)} />
                <Bar dataKey="amount" name="Spend" fill={CHART.bar} radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card chart-card">
          <h2>Invoice Status Distribution</h2>
          {loading ? <Skeleton height={220} /> : statusData.length === 0 ? (
            <EmptyState icon="🥧" title="No data yet" message="Statuses appear once you have invoices." />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                  {statusData.map((entry) => (
                    <Cell key={entry.name} fill={CHART.status[entry.name] || CHART.axis} />
                  ))}
                </Pie>
                <Tooltip {...tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
          {!loading && statusData.length > 0 && (
            <div className="legend">
              {statusData.map((s) => (
                <span key={s.name} className="legend-item">
                  <span className="legend-dot" style={{ background: CHART.status[s.name] || CHART.axis }} />
                  {s.name} ({s.value})
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="card chart-card">
          <h2>Top Suppliers</h2>
          {loading ? <Skeleton height={220} /> : supplierData.length === 0 ? (
            <EmptyState icon="🏆" title="No suppliers yet" message="Top suppliers appear here." />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={supplierData} layout="vertical" margin={{ top: 4, right: 12, bottom: 0, left: 8 }}>
                <CartesianGrid stroke={CHART.grid} horizontal={false} />
                <XAxis type="number" stroke={CHART.axis} fontSize={12} tickLine={false} axisLine={false}
                  tickFormatter={(v) => formatMoney(v)} />
                <YAxis type="category" dataKey="name" stroke={CHART.axis} fontSize={11} width={110}
                  tickLine={false} axisLine={false} />
                <Tooltip {...tooltipStyle} formatter={(v) => formatMoney(v)} />
                <Bar dataKey="amount" name="Spend" fill={CHART.accent} radius={[0, 6, 6, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Recent invoices + notifications */}
      <div className="split-grid">
        <div className="card">
          <div className="card-head">
            <h2>Recent Invoices</h2>
            <Link className="link-plain" to="/invoices">View all →</Link>
          </div>
          {loading ? (
            <SkeletonLines count={5} />
          ) : recentInvoices.length === 0 ? (
            <EmptyState icon="📄" title="No invoices yet"
              message="Upload your first invoice to get started."
              action={<Link className="btn-primary" to="/invoices">Upload Invoice</Link>} />
          ) : (
            <div className="table-scroll">
              <table className="list-table">
                <thead>
                  <tr><th>Invoice #</th><th>Supplier</th><th>Amount</th><th>Status</th></tr>
                </thead>
                <tbody>
                  {recentInvoices.map((inv) => (
                    <tr key={inv.id} className="clickable" onClick={() => navigate(`/invoices/${inv.id}`)}>
                      <td className="cell-strong">{inv.invoice_number ?? "—"}</td>
                      <td>{inv.vendor ?? "—"}</td>
                      <td>{formatMoney(inv.total)}</td>
                      <td><StatusBadge status={inv.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-head"><h2>Notifications</h2></div>
          {loading ? (
            <SkeletonLines count={4} />
          ) : overdue.length === 0 && recentUploads.length === 0 ? (
            <EmptyState icon="🔔" title="You're all caught up" message="No overdue invoices." />
          ) : (
            <ul className="notif-list">
              {overdue.map((inv) => (
                <li key={`o-${inv.id}`} className="notif notif-warn" onClick={() => navigate(`/invoices/${inv.id}`)}>
                  <span className="notif-dot" />
                  <div>
                    <strong>Overdue:</strong> {inv.invoice_number} — {inv.vendor}
                    <span className="notif-sub">Due {inv.due_date} · {formatMoney(inv.total)}</span>
                  </div>
                </li>
              ))}
              {recentUploads.map((inv) => (
                <li key={`r-${inv.id}`} className="notif" onClick={() => navigate(`/invoices/${inv.id}`)}>
                  <span className="notif-dot notif-dot-ok" />
                  <div>
                    Uploaded {inv.invoice_number} — {inv.vendor}
                    <span className="notif-sub">{String(inv.created_at || "").slice(0, 16)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
