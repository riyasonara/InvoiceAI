import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, formatMoney, formatDate } from "../api";
import StatusBadge from "../components/StatusBadge";
import EmptyState from "../components/EmptyState";
import { SkeletonLines } from "../components/Skeleton";

const STATUSES = ["all", "paid", "pending", "unpaid"];

export default function InvoicesPage() {
  const navigate = useNavigate();

  // Upload state (unchanged logic from the original upload flow)
  const [file, setFile] = useState(null);
  const [uploadError, setUploadError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [justExtracted, setJustExtracted] = useState(null);

  // List + filter state
  const [invoices, setInvoices] = useState([]);
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
      .then((data) => setInvoices(data || []))
      .catch((err) => console.error("Failed to load invoices", err))
      .finally(() => setLoading(false));
  }

  // Reload when filters change (debounced so typing doesn't spam the API).
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
      setJustExtracted(data);
      setFile(null);
      loadInvoices();
    } catch {
      setUploadError("Could not reach the server. Is the API running on port 8000?");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <h1>Invoices</h1>
        <p className="subtitle">Upload, search, and manage your workspace invoices.</p>
      </div>

      {/* Upload */}
      <div className="card upload-card">
        <label className="file-drop">
          <input type="file" accept="application/pdf"
            onChange={(e) => setFile(e.target.files[0])} />
          <span className="file-drop-text">{file ? file.name : "Choose a PDF invoice…"}</span>
        </label>
        <button className="btn-primary" onClick={handleUpload} disabled={!file || uploading}>
          {uploading ? "Extracting…" : "Extract Invoice"}
        </button>
      </div>
      {uploadError && <div className="error">{uploadError}</div>}
      {justExtracted && (
        <div className="banner-ok">
          ✓ Extracted <strong>{justExtracted.vendor}</strong> — {justExtracted.invoice_number} ({formatMoney(justExtracted.total)})
        </div>
      )}

      {/* Filters */}
      <div className="toolbar">
        <input className="search-input" type="search" placeholder="Search supplier or invoice #…"
          value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="seg seg-inline">
          {STATUSES.map((s) => (
            <button key={s} className={status === s ? "seg-btn active" : "seg-btn"}
              onClick={() => setStatus(s)}>{s === "all" ? "All" : s[0].toUpperCase() + s.slice(1)}</button>
          ))}
        </div>
        <div className="date-range">
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} aria-label="From date" />
          <span>–</span>
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} aria-label="To date" />
        </div>
      </div>

      {/* Table */}
      <div className="card">
        {loading ? (
          <SkeletonLines count={6} />
        ) : invoices.length === 0 ? (
          <EmptyState icon="🔍" title="No invoices found"
            message="Try clearing filters, or upload an invoice above." />
        ) : (
          <div className="table-scroll">
            <table className="list-table">
              <thead>
                <tr>
                  <th>Invoice #</th><th>Supplier</th><th>Amount</th>
                  <th>Due Date</th><th>Status</th><th>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id} className="clickable" onClick={() => navigate(`/invoices/${inv.id}`)}>
                    <td className="cell-strong">{inv.invoice_number ?? "—"}</td>
                    <td>{inv.vendor ?? "—"}</td>
                    <td>{formatMoney(inv.total)}</td>
                    <td>{formatDate(inv.due_date)}</td>
                    <td><StatusBadge status={inv.status} /></td>
                    <td>{formatDate(inv.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
