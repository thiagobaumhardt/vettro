import { api } from "./client";

export const tutoresApi = {
  listar: (busca = "") => api.get(`/tutores${busca ? `?busca=${encodeURIComponent(busca)}` : ""}`),
  obter: (id) => api.get(`/tutores/${id}`),
  criar: (dados) => api.post("/tutores", dados),
  atualizar: (id, dados) => api.put(`/tutores/${id}`, dados),
  excluir: (id) => api.del(`/tutores/${id}`),
  pacientes: (id) => api.get(`/tutores/${id}/pacientes`),
  exportarDados: (id) => api.get(`/tutores/${id}/exportar`),
};
