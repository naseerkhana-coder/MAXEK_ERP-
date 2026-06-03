import { useEffect, useState } from "react";

import { api } from "../api";



function todayDdMmYyyy() {

  const d = new Date();

  const dd = String(d.getDate()).padStart(2, "0");

  const mm = String(d.getMonth() + 1).padStart(2, "0");

  const yyyy = d.getFullYear();

  return `${dd}/${mm}/${yyyy}`;

}



const emptyForm = () => ({

  attendance_date: todayDdMmYyyy(),

  project_name: "",

  status: "Present",

  in_time: "08:00",

  out_time: "17:00",

  break_hours: 1,

  remarks: "",

});



export default function Attendance() {

  const [employees, setEmployees] = useState([]);

  const [projects, setProjects] = useState([]);

  const [statuses, setStatuses] = useState(["Present", "Absent", "Leave", "Half Day"]);

  const [employeeId, setEmployeeId] = useState("");

  const [rows, setRows] = useState([]);

  const [editId, setEditId] = useState(null);

  const [form, setForm] = useState(emptyForm());

  const [message, setMessage] = useState("");

  const [error, setError] = useState("");

  const [loading, setLoading] = useState(false);



  useEffect(() => {

    Promise.all([api.employees(), api.projects(), api.attendanceStatuses()])

      .then(([empRes, projRes, statRes]) => {

        setEmployees(empRes.data || []);

        setProjects(projRes.data || []);

        if (statRes.data?.length) setStatuses(statRes.data);

        if (empRes.data?.length) setEmployeeId(empRes.data[0].employee_id);

      })

      .catch((err) => setError(err.message));

  }, []);



  function loadList() {

    if (!employeeId) return;

    setLoading(true);

    api

      .attendanceList(employeeId)

      .then((res) => setRows(res.data || []))

      .catch((err) => setError(err.message))

      .finally(() => setLoading(false));

  }



  useEffect(() => {

    loadList();

  }, [employeeId]);



  function startEdit(row) {

    setEditId(row.id);

    setForm({

      attendance_date: row.attendance_date || todayDdMmYyyy(),

      project_name: row.project_name || "",

      status: row.status || "Present",

      in_time: row.in_time || "",

      out_time: row.out_time || "",

      break_hours: row.break_hours ?? 0,

      remarks: row.remarks || "",

    });

    setMessage("");

    setError("");

    window.scrollTo({ top: 0, behavior: "smooth" });

  }



  function cancelEdit() {

    setEditId(null);

    setForm(emptyForm());

  }



  async function save(e) {

    e.preventDefault();

    setError("");

    setMessage("");

    const payload = {

      ...form,

      break_hours: Number(form.break_hours) || 0,

    };

    try {

      if (editId) {

        await api.attendanceUpdate(editId, payload);

        setMessage("Timesheet updated");

      } else {

        await api.attendanceCreate({ employee_id: employeeId, ...payload });

        setMessage("Attendance saved");

      }

      cancelEdit();

      loadList();

    } catch (err) {

      setError(err.message);

    }

  }



  async function removeRow(id) {

    if (!window.confirm("Delete this timesheet entry?")) return;

    setError("");

    try {

      await api.attendanceDelete(id);

      if (editId === id) cancelEdit();

      setMessage("Timesheet deleted");

      loadList();

    } catch (err) {

      setError(err.message);

    }

  }



  return (

    <div>

      <h2 className="page-title">Attendance</h2>

      {error && <div className="alert alert-error">{error}</div>}

      {message && <div className="alert alert-success">{message}</div>}



      <div className="card">

        <label>

          Employee

          <select

            value={employeeId}

            onChange={(e) => {

              setEmployeeId(e.target.value);

              cancelEdit();

            }}

          >

            {employees.map((e) => (

              <option key={e.employee_id} value={e.employee_id}>

                {e.employee_name} ({e.employee_id})

              </option>

            ))}

          </select>

        </label>

      </div>



      <form className="card form-stack" onSubmit={save}>

        <h3>{editId ? `Edit timesheet #${editId}` : "New entry"}</h3>

        {editId && (

          <button type="button" className="btn-secondary" onClick={cancelEdit}>

            Cancel edit

          </button>

        )}

        <label>

          Date (DD/MM/YYYY)

          <input

            value={form.attendance_date}

            onChange={(e) => setForm({ ...form, attendance_date: e.target.value })}

            required

          />

        </label>

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

          Status

          <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>

            {statuses.map((s) => (

              <option key={s} value={s}>

                {s}

              </option>

            ))}

          </select>

        </label>

        <div className="row-2">

          <label>

            In time

            <input value={form.in_time} onChange={(e) => setForm({ ...form, in_time: e.target.value })} />

          </label>

          <label>

            Out time

            <input value={form.out_time} onChange={(e) => setForm({ ...form, out_time: e.target.value })} />

          </label>

        </div>

        <label>

          Break hours

          <input

            type="number"

            min="0"

            step="0.5"

            value={form.break_hours}

            onChange={(e) => setForm({ ...form, break_hours: e.target.value })}

          />

        </label>

        <label>

          Remarks

          <input value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />

        </label>

        <button type="submit" className="btn-primary">

          {editId ? "Update timesheet" : "Save attendance"}

        </button>

      </form>



      <h3 className="section-title">Recent</h3>

      {loading && <p className="muted">Loading…</p>}

      <div className="list">

        {rows.map((r) => (

          <div key={r.id} className={`list-item list-item-actions ${editId === r.id ? "active" : ""}`}>

            <div>

              <strong>{r.attendance_date}</strong>

              <span>

                {r.status} · {r.project_name || "—"} · {r.total_hours}h

                {r.attendance_category ? ` · ${r.attendance_category}` : ""}

              </span>

            </div>

            <div className="btn-row compact">

              <button type="button" className="btn-secondary" onClick={() => startEdit(r)}>

                Edit

              </button>

              <button type="button" className="btn-danger" onClick={() => removeRow(r.id)}>

                Delete

              </button>

            </div>

          </div>

        ))}

        {!loading && rows.length === 0 && <p className="muted">No records yet.</p>}

      </div>

    </div>

  );

}

