import { useEffect, useState } from "react";
import { api, formatMoney } from "../api";
import EmptyState from "../components/EmptyState";
import { SkeletonLines } from "../components/Skeleton";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function monthLabel(m) {
  if (!m || !m.includes("-")) return m || "";
  const [y, mm] = m.split("-");
  return `${MONTHS[Number(mm) - 1] || mm} ${y}`;
}

export default function ReportsPage() {
  const [summary, setSummary] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api("/dashboard/summary").then((r) => (r.ok ? r.json() : null)),
      api("/invoices").then((r) => (r.ok ? r.json() : [])),
    ]).then(([s, inv]) => {
      setSummary(s);
      setInvoices(inv || []);
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
    return <div className="page"><div className="card"><SkeletonLines count={6} /></div></div>;
  }

  const monthly = summary?.monthly_trend || [];

  return (
    <div className="page">
      <div className="page-head row-between">
        <div>
          <h1>Reports</h1>
          <p className="subtitle">Spending breakdowns and data export.</p>
        </div>
        <button className="btn-primary" onClick={exportCsv} disabled={invoices.length === 0}>
          Export CSV
        </button>
      </div>

      <div className="report-tiles">
        <div className="card mini"><span className="stat-label">Total Invoices</span><span className="stat-value">{summary?.total_invoices ?? 0}</span></div>
        <div className="card mini"><span className="stat-label">Total Amount</span><span className="stat-value">{formatMoney(summary?.total_amount)}</span></div>
        <div className="card mini"><span className="stat-label">Paid</span><span className="stat-value">{formatMoney(summary?.paid_amount)}</span></div>
        <div className="card mini"><span className="stat-label">Pending</span><span className="stat-value">{formatMoney(summary?.pending_amount)}</span></div>
        <div className="card mini"><span className="stat-label">Unpaid</span><span className="stat-value">{formatMoney(summary?.unpaid_amount)}</span></div>
      </div>

      <div className="split-grid">
        <div className="card">
          <div className="card-head"><h2>Monthly Breakdown</h2></div>
          {monthly.length === 0 ? (
            <EmptyState icon="📅" title="No data yet" message="Upload invoices to build reports." />
          ) : (
            <div className="table-scroll">
              <table className="list-table">
                <thead><tr><th>Month</th><th>Invoices</th><th>Spend</th></tr></thead>
                <tbody>
                  {monthly.map((m) => (
                    <tr key={m.month}>
                      <td className="cell-strong">{monthLabel(m.month)}</td>
                      <td>{m.count}</td>
                      <td>{formatMoney(m.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-head"><h2>By Status</h2></div>
          <div className="table-scroll">
            <table className="list-table">
              <thead><tr><th>Status</th><th>Invoices</th></tr></thead>
              <tbody>
                {(summary?.status_distribution || []).map((s) => (
                  <tr key={s.status}>
                    <td className="cell-strong" style={{ textTransform: "capitalize" }}>{s.status}</td>
                    <td>{s.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
