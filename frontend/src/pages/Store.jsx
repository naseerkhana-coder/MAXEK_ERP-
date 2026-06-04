import { useEffect, useState } from "react";
import { api } from "../api";

function todayDdMmYyyy() {
  const d = new Date();
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

export default function Store() {
  const [projects, setProjects] = useState([]);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({
    project_name: "",
    item_name: "",
    quantity: 1,
    unit: "Nos",
    required_date: todayDdMmYyyy(),
    remarks: "",
  });

  function load() {
    api
      .materialsList()
      .then((res) => setRows(res.data || []))
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    api.projects().then((res) => setProjects(res.data || [])).catch(() => {});
    load();
  }, []);

  async function save(e) {
    e.preventDefault();
    setError("");
    setMessage("");
    try {
      const res = await api.materialsCreate({
        ...form,
        quantity: Number(form.quantity) || 1,
      });
      setMessage(res.message || "Request created");
      setForm({ ...form, item_name: "", remarks: "" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function setStatus(requestId, status) {
    setError("");
    try {
      await api.materialsUpdateStatus(requestId, status);
      setMessage(`Marked as ${status}`);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div>
      <h2 className="page-title">Store / Materials</h2>
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <form className="card form-stack" onSubmit={save}>
        <h3>New material request</h3>
        <label>
          Project
          <select
            value={form.project_name}
            onChange={(e) => setForm({ ...form, project_name: e.target.value })}
          >
            <option value="">—</option>
            {projects.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label>
          Item name
          <input
            value={form.item_name}
            onChange={(e) => setForm({ ...form, item_name: e.target.value })}
            required
          />
        </label>
        <div className="row-2">
          <label>
            Quantity
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={form.quantity}
              onChange={(e) => setForm({ ...form, quantity: e.target.value })}
              required
            />
          </label>
          <label>
            Unit
            <input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
          </label>
        </div>
        <label>
          Required date
          <input
            value={form.required_date}
            onChange={(e) => setForm({ ...form, required_date: e.target.value })}
          />
        </label>
        <label>
          Remarks
          <input value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />
        </label>
        <button type="submit" className="btn-primary">
          Submit request
        </button>
      </form>

      <h3 className="section-title">Requests</h3>
      <div className="list">
        {rows.map((r) => (
          <div key={r.request_id} className="card">
            <strong>{r.item_name}</strong>
            <p className="muted">
              {r.project_name || "—"} · {r.quantity} {r.unit} · {r.status}
            </p>
            {r.status === "Pending" && (
              <div className="btn-row">
                <button type="button" className="btn-primary" onClick={() => setStatus(r.request_id, "Approved")}>
                  Approve
                </button>
                <button type="button" className="btn-danger" onClick={() => setStatus(r.request_id, "Rejected")}>
                  Reject
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
