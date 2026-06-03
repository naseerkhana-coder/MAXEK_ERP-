import { useEffect, useState } from "react";
import { api } from "../api";

function todayDdMmYyyy() {
  const d = new Date();
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

const PAYMENT_MODES = ["Cash", "Bank Transfer", "Cheque", "UPI"];

export default function Expenses() {
  const [projects, setProjects] = useState([]);
  const [clients, setClients] = useState([]);
  const [expenseHeads, setExpenseHeads] = useState([]);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({
    expense_date: todayDdMmYyyy(),
    expense_head: "",
    project_name: "",
    client_name: "",
    paid_to: "",
    amount: "",
    payment_mode: "Cash",
    remarks: "",
  });

  function load() {
    api
      .expensesList()
      .then((res) => setRows(res.data || []))
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    api.projects().then((res) => setProjects(res.data || [])).catch(() => {});
    api.clients().then((res) => setClients(res.data || [])).catch(() => {});
    api
      .expenseHeads()
      .then((res) => setExpenseHeads(res.data || []))
      .catch(() => {});
    load();
  }, []);

  async function save(e) {
    e.preventDefault();
    setError("");
    setMessage("");
    try {
      const res = await api.expensesCreate({
        ...form,
        amount: Number(form.amount) || 0,
      });
      setMessage(res.message || "Expense saved");
      setForm({ ...form, paid_to: "", amount: "", remarks: "" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div>
      <h2 className="page-title">Expenses</h2>
      {error && <div className="alert alert-error">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}

      <form className="card form-stack" onSubmit={save}>
        <h3>New expense</h3>
        <label>
          Date (DD/MM/YYYY)
          <input
            value={form.expense_date}
            onChange={(e) => setForm({ ...form, expense_date: e.target.value })}
            required
          />
        </label>
        <label>
          Expense head
          <select
            value={form.expense_head}
            onChange={(e) => setForm({ ...form, expense_head: e.target.value })}
            required
          >
            <option value="">Select head</option>
            {expenseHeads.map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
        </label>
        <label>
          Paid to
          <input
            value={form.paid_to}
            onChange={(e) => setForm({ ...form, paid_to: e.target.value })}
            placeholder="Vendor / person name"
          />
        </label>
        <div className="row-2">
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
            Client
            <select
              value={form.client_name}
              onChange={(e) => setForm({ ...form, client_name: e.target.value })}
            >
              <option value="">—</option>
              {clients.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="row-2">
          <label>
            Amount
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
              required
            />
          </label>
          <label>
            Payment mode
            <select
              value={form.payment_mode}
              onChange={(e) => setForm({ ...form, payment_mode: e.target.value })}
            >
              {PAYMENT_MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label>
          Remarks
          <input value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />
        </label>
        <button type="submit" className="btn-primary">
          Save expense
        </button>
      </form>

      <h3 className="section-title">Recent expenses</h3>
      <div className="list">
        {rows.map((r) => (
          <div key={r.expense_id} className="card">
            <strong>{r.expense_head}</strong>
            <p className="muted">
              {r.expense_id} · {r.expense_date} · ₹{Number(r.amount).toLocaleString("en-IN")}
            </p>
            <p className="muted">
              {r.project_name || "—"} · {r.paid_to || "—"} · {r.payment_mode}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
