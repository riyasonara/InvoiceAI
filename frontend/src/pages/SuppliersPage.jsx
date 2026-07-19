import { useEffect, useMemo, useState } from "react";
import { api, formatMoney, formatDate } from "../api";
import EmptyState from "../components/EmptyState";
import { SkeletonLines } from "../components/Skeleton";

export default function SuppliersPage() {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api("/invoices")
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setInvoices(d || []))
      .finally(() => setLoading(false));
  }, []);

  // Group invoices by supplier (vendor) → count, total spend, most recent invoice.
  const suppliers = useMemo(() => {
    const map = new Map();
    for (const inv of invoices) {
      const name = inv.vendor || "Unknown";
      const s = map.get(name) || { name, count: 0, total: 0, last: "" };
      s.count += 1;
      s.total += Number(inv.total) || 0;
      if (String(inv.invoice_date || "") > s.last) s.last = inv.invoice_date || "";
      map.set(name, s);
    }
    return [...map.values()].sort((a, b) => b.total - a.total);
  }, [invoices]);

  const filtered = suppliers.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="page">
      <div className="page-head">
        <h1>Suppliers</h1>
        <p className="subtitle">Every supplier across your workspace, ranked by total spend.</p>
      </div>

      <div className="toolbar">
        <input className="search-input" type="search" placeholder="Search suppliers…"
          value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      <div className="card">
        {loading ? (
          <SkeletonLines count={6} />
        ) : filtered.length === 0 ? (
          <EmptyState icon="🏢" title="No suppliers yet"
            message="Suppliers appear here once you upload invoices." />
        ) : (
          <div className="table-scroll">
            <table className="list-table">
              <thead>
                <tr><th>Supplier</th><th>Invoices</th><th>Total Spend</th><th>Latest Invoice</th></tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <tr key={s.name}>
                    <td className="cell-strong">{s.name}</td>
                    <td>{s.count}</td>
                    <td>{formatMoney(s.total)}</td>
                    <td>{formatDate(s.last)}</td>
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
