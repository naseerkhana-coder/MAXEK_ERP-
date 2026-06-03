import { useEffect, useState } from "react";
import { api } from "../api";

function todayDdMmYyyy() {
  const d = new Date();
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

export default function Dpr() {
  const [projects, setProjects] = useState([]);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({
    project_name: "",
    dpr_date: todayDdMmYyyy(),
    progress_quantity: 0,
    remarks: "",
  });

  function load() {
    api
      .dprList()
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
      const res = await api.dprCreate({
        ...form,
        progress_quantity: Number(form.progress_quantity) || 0,
      });
      setMessage(res.message || "DPR saved");
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div>
      <h2 className="page-title">DPR</h2>
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <form className="card form-stack" onSubmit={save}>
        <h3>Quick DPR entry</h3>
        <label>
          Project
          <select
            value={form.project_name}
            onChange={(e) => setForm({ ...form, project_name: e.target.value })}
            required
          >
            <option value="">Select project</option>
            {projects.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label>
          Date (DD/MM/YYYY)
          <input
            value={form.dpr_date}
            onChange={(e) => setForm({ ...form, dpr_date: e.target.value })}
            required
          />
        </label>
        <label>
          Progress quantity
          <input
            type="number"
            min="0"
            step="0.01"
            value={form.progress_quantity}
            onChange={(e) => setForm({ ...form, progress_quantity: e.target.value })}
          />
        </label>
        <label>
          Remarks
          <input value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />
        </label>
        <button type="submit" className="btn-primary">
          Submit DPR
        </button>
      </form>

      <h3 className="section-title">Recent DPRs</h3>
      <div className="list">
        {rows.map((r) => (
          <div key={r.dpr_id} className="list-item">
            <strong>{r.project_name}</strong>
            <span>
              {r.dpr_date} · Qty {r.progress_quantity} · {r.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
