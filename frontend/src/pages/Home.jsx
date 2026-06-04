import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { getUser } from "../auth";

const allModules = [
  { to: "/attendance", title: "Attendance", desc: "Mark daily attendance", icon: "🕒", roles: null },
  { to: "/payroll", title: "Payroll approval", desc: "MD approve / reject", icon: "💰", roles: ["Admin", "MD"] },
  { to: "/dpr", title: "DPR", desc: "Daily progress reports", icon: "📋", roles: null },
  { to: "/store", title: "Store request", desc: "Material requests", icon: "📦", roles: null },
  { to: "/expenses", title: "Expenses", desc: "Record site expenses", icon: "💸", roles: null },
];

export default function Home() {
  const user = getUser();
  const role = user?.role || "";
  const modules = allModules.filter((m) => !m.roles || m.roles.includes(role));
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .dashboard()
      .then((res) => setStats(res.data))
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div>
      <h2 className="page-title">Dashboard</h2>
      {error && <div className="alert alert-error">{error}</div>}

      {stats && (
        <div className="kpi-grid">
          <div className="kpi">
            <span>Employees</span>
            <strong>{stats.employees}</strong>
          </div>
          <div className="kpi">
            <span>Active projects</span>
            <strong>{stats.active_projects}</strong>
          </div>
          <div className="kpi">
            <span>Attendance today</span>
            <strong>{stats.attendance_today}</strong>
          </div>
          <div className="kpi">
            <span>Pending salary</span>
            <strong>{stats.pending_salary}</strong>
          </div>
        </div>
      )}

      <h3 className="section-title">Modules</h3>
      <div className="module-grid">
        {modules.map((m) => (
          <Link key={m.to} to={m.to} className="module-card">
            <span className="module-icon">{m.icon}</span>
            <strong>{m.title}</strong>
            <span className="muted">{m.desc}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
