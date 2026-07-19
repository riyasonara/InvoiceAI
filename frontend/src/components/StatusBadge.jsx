// Colored pill for an invoice status. Falls back to "pending".
export default function StatusBadge({ status }) {
  const value = status || "pending";
  return <span className={`status-badge status-${value}`}>{value}</span>;
}
