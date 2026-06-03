const TOKEN_KEY = "maxek_token";
const USER_KEY = "maxek_user";
const API_BASE_KEY = "maxek_api_base";

export function getApiBase() {
  return (
    localStorage.getItem(API_BASE_KEY) ||
    import.meta.env.VITE_API_BASE ||
    "http://72.61.224.204:8001"
  );
}

export function setApiBase(url) {
  localStorage.setItem(API_BASE_KEY, url.replace(/\/$/, ""));
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isLoggedIn() {
  return Boolean(getToken());
}
