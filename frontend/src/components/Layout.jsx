import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import Brand from "./Brand";

const icon = {
  dashboard: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" />
    </svg>
  ),
  invoices: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" />
      <path d="M9 13h6M9 17h6" />
    </svg>
  ),
  suppliers: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  reports: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="20" x2="12" y2="10" /><line x1="18" y1="20" x2="18" y2="4" /><line x1="6" y1="20" x2="6" y2="16" />
    </svg>
  ),
};

const NAV = [
  { to: "/", label: "Dashboard", end: true, key: "dashboard" },
  { to: "/invoices", label: "Invoices", key: "invoices" },
  { to: "/suppliers", label: "Suppliers", key: "suppliers" },
  { to: "/reports", label: "Reports", key: "reports" },
];

export default function Layout({ user, onLogout }) {
  const [open, setOpen] = useState(false);

  return (
    <div className={`layout${open ? " open" : ""}`}>
      <aside className="sidebar">
        <div className="sidebar-brand">
          <Brand />
        </div>
        <nav className="sidebar-nav">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => "nav-item" + (isActive ? " active" : "")}
              onClick={() => setOpen(false)}
            >
              <span className="nav-icon">{icon[item.key]}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="workspace-pill">{user.organization.name}</span>
        </div>
      </aside>

      {open && <div className="sidebar-scrim" onClick={() => setOpen(false)} />}

      <div className="layout-main">
        <header className="topbar">
          <button className="hamburger" onClick={() => setOpen((o) => !o)} aria-label="Toggle menu">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <div className="topbar-brand-mobile"><Brand /></div>
          <div className="topbar-right">
            <span className="user-email">{user.email}</span>
            <button type="button" className="logout" onClick={onLogout}>Log out</button>
          </div>
        </header>

        <main className="content">
          <Outlet context={{ user }} />
        </main>
      </div>
    </div>
  );
}
