const BASE = import.meta.env.DEV ? "/api" : "https://your-backend-project.vercel.app/api"; 

function getToken() {
  return localStorage.getItem("token");
}

async function request(path, { method = "GET", body, form, isForm = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!isForm && body) headers["Content-Type"] = "application/json";

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: isForm ? form : body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  signup: (username, password, role = "user") =>
    request("/signup", { method: "POST", body: { username, password, role } }),

  login: (username, password) => {
    const form = new URLSearchParams();
    form.set("username", username);
    form.set("password", password);
    return request("/login", { method: "POST", isForm: true, form });
  },

  me: () => request("/me"),

  analyze: (file, view) => {
    const form = new FormData();
    form.append("file", file);
    form.append("view", view);
    return request("/analyze", { method: "POST", isForm: true, form });
  },

  myDeliveries: () => request("/deliveries"),
  deliveryDetail: (id) => request(`/deliveries/${id}`),
  coachDeliveries: () => request("/coach/deliveries"),
  coachUsers: () => request("/coach/users"),
  deleteDelivery: (id) => request(`/deliveries/${id}`, { method: "DELETE" }),
  renameDelivery: (id, name) =>
  request(`/deliveries/${id}/rename`, {
    method: "PATCH",
    body: { name },
  }),
};

export function fileUrl(relativePath) {
  if (!relativePath) return null;
  return `/files/${relativePath}`;
}
