import { api } from "./client";

export const pacientesApi = {
  listar: (busca = "") => api.get(`/pacientes${busca ? `?busca=${encodeURIComponent(busca)}` : ""}`),
  obter: (id) => api.get(`/pacientes/${id}`),
  criar: (dados) => api.post("/pacientes", dados),
  atualizar: (id, dados) => api.put(`/pacientes/${id}`, dados),
  excluir: (id) => api.del(`/pacientes/${id}`),
  atualizarFoto: (id, fotoPerfil) => api.put(`/pacientes/${id}/foto`, { foto_perfil: fotoPerfil }),
};
