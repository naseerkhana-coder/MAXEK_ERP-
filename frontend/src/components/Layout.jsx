import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearSession, getUser } from "../auth";
import { ERP_DISPLAY_NAME } from "../branding";

export default function Layout() {
  const navigate = useNavigate();
  const user = getUser();

  function logout() {
    clearSession();
    navigate("/login", { replace: true });
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <div className="app-title">{ERP_DISPLAY_NAME}</div>
          <div className="app-subtitle">
            {user?.full_name || user?.username} · {user?.role || "User"}
          </div>
        </div>
        <button type="button" className="btn-ghost" onClick={logout}>
          Logout
        </button>
      </header>

      <main className="app-main">
        <Outlet />
      </main>

      <nav className="bottom-nav">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
          Home
        </NavLink>
        <NavLink to="/attendance" className={({ isActive }) => (isActive ? "active" : "")}>
          Attendance
        </NavLink>
        <NavLink to="/payroll" className={({ isActive }) => (isActive ? "active" : "")}>
          Payroll
        </NavLink>
        <NavLink to="/dpr" className={({ isActive }) => (isActive ? "active" : "")}>
          DPR
        </NavLink>
        <NavLink to="/store" className={({ isActive }) => (isActive ? "active" : "")}>
          Store
        </NavLink>
        <NavLink to="/expenses" className={({ isActive }) => (isActive ? "active" : "")}>
          Expense
        </NavLink>
      </nav>
    </div>
  );
}
