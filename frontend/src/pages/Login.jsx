import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { getApiBase, isLoggedIn, setApiBase, setSession } from "../auth";
import { ERP_DISPLAY_NAME } from "../branding";

export default function Login() {
  const navigate = useNavigate();
  if (isLoggedIn()) navigate("/", { replace: true });

  const [apiBase, setApiBaseInput] = useState(getApiBase());
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      setApiBase(apiBase.trim());
      const res = await api.login(username.trim(), password);
      setSession(res.token, {
        user_id: res.user_id,
        full_name: res.full_name,
        role: res.role,
        username,
      });
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <form className="card" onSubmit={onSubmit}>
        <h1>{ERP_DISPLAY_NAME}</h1>
        <p className="muted">Mobile app — sign in</p>

        <label>
          API server
          <input
            type="url"
            value={apiBase}
            onChange={(e) => setApiBaseInput(e.target.value)}
            placeholder="http://72.61.224.204:8001"
            required
          />
        </label>
        <p className="hint">
          Production VPS: http://72.61.224.204:8001 · Same Wi‑Fi PC: http://YOUR_PC_IP:8001 · Emulator:
          http://10.0.2.2:8001
        </p>

        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>

        {error && <div className="alert alert-error">{error}</div>}

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? "Signing in…" : "Login"}
        </button>
      </form>
    </div>
  );
}
