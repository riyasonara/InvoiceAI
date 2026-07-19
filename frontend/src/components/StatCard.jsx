// A single dashboard metric card: icon, label, value, optional accent tone.
export default function StatCard({ label, value, icon, tone = "default", hint }) {
  return (
    <div className={`stat-card tone-${tone}`}>
      <div className="stat-icon" aria-hidden="true">{icon}</div>
      <div className="stat-body">
        <span className="stat-label">{label}</span>
        <span className="stat-value">{value}</span>
        {hint && <span className="stat-hint">{hint}</span>}
      </div>
    </div>
  );
}
