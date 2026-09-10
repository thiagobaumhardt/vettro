import { api } from "./client";

export const atendimentosApi = {
  listar: () => api.get("/atendimentos"),
  criar: (dados) => api.post("/atendimentos", dados),
  excluir: (id) => api.del(`/atendimentos/${id}`),
};
