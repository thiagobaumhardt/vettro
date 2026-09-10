import { api } from "./client";

export const agendamentosApi = {
  listar: () => api.get("/agendamentos"),
  criar: (dados) => api.post("/agendamentos", dados),
  atualizar: (id, dados) => api.put(`/agendamentos/${id}`, dados),
  alterarStatus: (id, status) => api.patch(`/agendamentos/${id}/status`, { status }),
  reagendar: (id, data, hora) => api.patch(`/agendamentos/${id}/reagendar`, { data, hora: hora || null }),
  excluir: (id) => api.del(`/agendamentos/${id}`),
};
