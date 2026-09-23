import { api } from "./client";

export const insumosApi = {
  listar: () => api.get("/insumos"),
  criar: (dados) => api.post("/insumos", dados),
  atualizar: (id, dados) => api.put(`/insumos/${id}`, dados),
  excluir: (id) => api.del(`/insumos/${id}`),
  repor: (id, qtd) => api.patch(`/insumos/${id}/repor`, { qtd }),
  buscarPorCodigo: (codigo) => api.get(`/insumos/codigo/${encodeURIComponent(codigo)}`),
  importarXml: (arquivo) => {
    const fd = new FormData();
    fd.append("arquivo", arquivo);
    return api.postForm("/insumos/importar-xml", fd);
  },
};
