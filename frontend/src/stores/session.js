import { reactive } from "vue";

import { api } from "@/api/client";
import { getToken, setToken } from "@/api/client";

export const session = reactive({
  usuario: null,
  carregando: true,
  autenticado: false,
  admin: false,
});

export async function carregarSessao() {
  session.carregando = true;
  if (!getToken()) {
    session.usuario = null;
    session.autenticado = false;
    session.admin = false;
    session.carregando = false;
    return;
  }
  try {
    const usuario = await api.get("/auth/me");
    session.usuario = usuario;
    session.autenticado = true;
    session.admin = usuario.papel === "admin";
  } catch {
    session.usuario = null;
    session.autenticado = false;
    session.admin = false;
  } finally {
    session.carregando = false;
  }
}

export function encerrarSessao() {
  setToken(null);
  session.usuario = null;
  session.autenticado = false;
  session.admin = false;
}
