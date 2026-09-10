import { api } from "./client";

export const anamneseApi = {
  listar: (pacienteId) => api.get(`/pacientes/${pacienteId}/anamnese`),
  criar: (pacienteId, dados) => api.post(`/pacientes/${pacienteId}/anamnese`, dados),
  excluir: (id) => api.del(`/anamnese/${id}`),
};

export const cirurgiasApi = {
  listar: (pacienteId) => api.get(`/pacientes/${pacienteId}/cirurgias`),
  criar: (pacienteId, dados) => api.post(`/pacientes/${pacienteId}/cirurgias`, dados),
  excluir: (id) => api.del(`/cirurgias/${id}`),
};

export const notasApi = {
  listar: (pacienteId) => api.get(`/pacientes/${pacienteId}/notas`),
  criar: (pacienteId, dados) => api.post(`/pacientes/${pacienteId}/notas`, dados),
  atualizar: (id, dados) => api.put(`/notas/${id}`, dados),
  excluir: (id) => api.del(`/notas/${id}`),
};

export const exemasApi = {
  listar: (pacienteId) => api.get(`/pacientes/${pacienteId}/exames`),
  anexar: (pacienteId, files) => {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    return api.postForm(`/pacientes/${pacienteId}/exames`, fd);
  },
  excluir: (id) => api.del(`/exames/${id}`),
};

export const fotosApi = {
  listar: (pacienteId) => api.get(`/pacientes/${pacienteId}/fotos`),
  anexar: (pacienteId, files) => {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    return api.postForm(`/pacientes/${pacienteId}/fotos`, fd);
  },
  excluir: (id) => api.del(`/fotos/${id}`),
};

export const cobrancasApi = {
  listar: (pacienteId) => api.get(`/pacientes/${pacienteId}/cobrancas`),
  criar: (pacienteId, dados) => api.post(`/pacientes/${pacienteId}/cobrancas`, dados),
  marcarPago: (id) => api.patch(`/cobrancas/${id}/pagar`),
  excluir: (id) => api.del(`/cobrancas/${id}`),
};
