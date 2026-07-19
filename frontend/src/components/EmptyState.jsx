// Friendly empty screen: icon, title, message, optional action button.
export default function EmptyState({ icon = "📄", title, message, action }) {
  return (
    <div className="empty-state">
      <div className="empty-icon" aria-hidden="true">{icon}</div>
      <h3 className="empty-title">{title}</h3>
      {message && <p className="empty-message">{message}</p>}
      {action}
    </div>
  );
}
