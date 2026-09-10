import { api } from "./client";

export const dashboardApi = {
  stats: () => api.get("/dashboard/stats"),
  estoqueAlerta: () => api.get("/dashboard/estoque-alerta"),
  ultimas24h: () => api.get("/dashboard/ultimas-24h"),
};
