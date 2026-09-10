import { api } from "./client";

export const servicosApi = {
  listar: () => api.get("/servicos"),
  criar: (dados) => api.post("/servicos", dados),
  atualizar: (id, dados) => api.put(`/servicos/${id}`, dados),
  excluir: (id) => api.del(`/servicos/${id}`),
};

export const cirurgiasCatApi = {
  listar: () => api.get("/cirurgias-cat"),
  criar: (dados) => api.post("/cirurgias-cat", dados),
  atualizar: (id, dados) => api.put(`/cirurgias-cat/${id}`, dados),
  excluir: (id) => api.del(`/cirurgias-cat/${id}`),
};
