import { ApiError, setToken } from "./client";

export async function login(email, senha) {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", senha);

  const res = await fetch("/api/auth/login", { method: "POST", body });
  if (!res.ok) {
    let detail = "E-mail ou senha inválidos.";
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, res.status);
  }
  const data = await res.json();
  setToken(data.access_token);
  return data.usuario;
}

export function logout() {
  setToken(null);
}
