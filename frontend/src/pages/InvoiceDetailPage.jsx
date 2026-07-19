import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api, formatMoney, formatDate } from "../api";
import StatusBadge from "../components/StatusBadge";
import { SkeletonLines } from "../components/Skeleton";

const STATUSES = ["paid", "pending", "unpaid"];

export default function InvoiceDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState(null);
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
      .then((data) => {
        if (data) {
          setInvoice(data);
          setDueDate(data.due_date || "");
        }
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  async function patch(body) {
    setSaving(true);
    try {
      const res = await api(`/invoices/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) setInvoice(await res.json());
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="page"><div className="card"><SkeletonLines count={6} /></div></div>;
  }
  if (notFound || !invoice) {
    return (
      <div className="page">
        <div className="card">
          <h2>Invoice not found</h2>
          <p className="subtitle">It may have been removed, or belongs to another workspace.</p>
          <Link className="btn-primary" to="/invoices">Back to invoices</Link>
        </div>
      </div>
    );
  }

  const rows = [
    ["Vendor", invoice.vendor ?? "—"],
    ["Invoice Number", invoice.invoice_number ?? "—"],
    ["Invoice Date", formatDate(invoice.invoice_date)],
    ["GST", formatMoney(invoice.gst)],
    ["Total", formatMoney(invoice.total)],
    ["Uploaded", String(invoice.created_at || "—").slice(0, 16)],
  ];

  return (
    <div className="page">
      <div className="page-head row-between">
        <div>
          <button className="link-plain" onClick={() => navigate(-1)}>← Back</button>
          <h1>{invoice.vendor || "Invoice"}</h1>
          <p className="subtitle">Invoice {invoice.invoice_number}</p>
        </div>
        <StatusBadge status={invoice.status} />
      </div>

      <div className="detail-grid">
        <div className="card">
          <h2>Details</h2>
          <table className="kv-table">
            <tbody>
              {rows.map(([k, v]) => (
                <tr key={k}><td>{k}</td><td>{v}</td></tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h2>Manage</h2>
          <div className="field">
            <span className="field-label">Status</span>
            <div className="seg seg-inline">
              {STATUSES.map((s) => (
                <button key={s} disabled={saving}
                  className={invoice.status === s ? "seg-btn active" : "seg-btn"}
                  onClick={() => patch({ status: s })}>
                  {s[0].toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
          </div>

          <div className="field" style={{ marginTop: 18 }}>
            <span className="field-label">Due date</span>
            <div className="date-save">
              <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
              <button className="btn-primary" disabled={saving || dueDate === (invoice.due_date || "")}
                onClick={() => patch({ due_date: dueDate })}>
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
