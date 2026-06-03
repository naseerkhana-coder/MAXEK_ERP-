import { useEffect, useState } from "react";
import { api } from "../api";
import { getUser } from "../auth";

export default function PayrollApprovals() {
  const user = getUser();
  const canApprove = ["Admin", "MD"].includes(user?.role);
  const [rows, setRows] = useState([]);
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  function load() {
    api
      .payrollPending()
      .then((res) => setRows(res.data || []))
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    load();
  }, []);

  async function act(action, payrollId) {
    setError("");
    setMessage("");
    try {
      if (action === "approve") await api.payrollApprove(payrollId, remarks);
      else if (action === "reject") await api.payrollReject(payrollId, remarks);
      else await api.payrollSendBack(payrollId, remarks);
      setMessage(`Payroll ${action} successful`);
      setRemarks("");
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (!canApprove) {
    return (
      <div>
        <h2 className="page-title">Payroll approval</h2>
        <div className="alert alert-error">Your role ({user?.role}) cannot approve payroll. MD/Admin only.</div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="page-title">Payroll approval</h2>
      <p className="muted">Pending MD approval</p>
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <label>
        Remarks (optional)
        <input value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="MD remarks" />
      </label>

      <div className="list">
        {rows.map((r) => (
          <div key={r.payroll_id} className="card">
            <strong>{r.employee_name}</strong>
            <p className="muted">
              {r.payroll_month} · Net Rs {Number(r.net_salary || 0).toLocaleString("en-IN")}
            </p>
            <p className="muted">
              Days: {r.worked_days} · OT: {r.total_ot_hours}h
            </p>
            <div className="btn-row">
              <button type="button" className="btn-primary" onClick={() => act("approve", r.payroll_id)}>
                Approve
              </button>
              <button type="button" className="btn-secondary" onClick={() => act("send-back", r.payroll_id)}>
                Send back
              </button>
              <button type="button" className="btn-danger" onClick={() => act("reject", r.payroll_id)}>
                Reject
              </button>
            </div>
          </div>
        ))}
        {rows.length === 0 && <p className="muted">No payroll waiting for approval.</p>}
      </div>
    </div>
  );
}
