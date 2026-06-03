import { clearSession, getApiBase, getToken } from "./auth";

async function request(path, options = {}) {
  const base = getApiBase();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${base}${path}`, { ...options, headers });
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (res.status === 401) {
    clearSession();
    throw new Error("Session expired. Please login again.");
  }
  if (!res.ok) {
    const detail = body?.detail || body?.message || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

export const api = {
  health: () => request("/api/health"),
  login: (username, password) =>
    request("/api/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  dashboard: () => request("/api/dashboard"),
  employees: () => request("/api/employees"),
  projects: () => request("/api/projects"),
  attendanceStatuses: () => request("/api/attendance/statuses"),
  attendanceList: (employeeId) =>
    request(`/api/attendance?employee_id=${encodeURIComponent(employeeId)}`),
  attendanceGet: (id) => request(`/api/attendance/${id}`),
  attendanceCreate: (payload) =>
    request("/api/attendance", { method: "POST", body: JSON.stringify(payload) }),
  attendanceUpdate: (id, payload) =>
    request(`/api/attendance/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  attendanceDelete: (id) =>
    request(`/api/attendance/${id}`, { method: "DELETE" }),
  payrollPending: () => request("/api/payroll?workflow_status=Submitted%20to%20MD"),
  payrollApprove: (id, remarks) =>
    request(`/api/payroll/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify({ remarks }),
    }),
  payrollReject: (id, remarks) =>
    request(`/api/payroll/${encodeURIComponent(id)}/reject`, {
      method: "POST",
      body: JSON.stringify({ remarks }),
    }),
  payrollSendBack: (id, remarks) =>
    request(`/api/payroll/${encodeURIComponent(id)}/send-back`, {
      method: "POST",
      body: JSON.stringify({ remarks }),
    }),
  dprList: () => request("/api/dpr"),
  dprCreate: (payload) =>
    request("/api/dpr", { method: "POST", body: JSON.stringify(payload) }),
  materialsList: () => request("/api/materials"),
  materialsCreate: (payload) =>
    request("/api/materials", { method: "POST", body: JSON.stringify(payload) }),
  materialsUpdateStatus: (requestId, status) =>
    request(`/api/materials/${encodeURIComponent(requestId)}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
  expenseHeads: () => request("/api/expense-heads"),
  clients: () => request("/api/clients"),
  expensesList: () => request("/api/expenses"),
  expensesCreate: (payload) =>
    request("/api/expenses", { method: "POST", body: JSON.stringify(payload) }),
};
