import { api } from "./client";

export const usuariosApi = {
  listar: () => api.get("/usuarios"),
  criar: (dados) => api.post("/usuarios", dados),
  atualizar: (id, dados) => api.put(`/usuarios/${id}`, dados),
  excluir: (id) => api.del(`/usuarios/${id}`),
};
