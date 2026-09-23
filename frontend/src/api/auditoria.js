import { api } from "./client";

export const auditoriaApi = {
  listar: (entidade = "") => api.get(`/auditoria${entidade ? `?entidade=${encodeURIComponent(entidade)}` : ""}`),
};
