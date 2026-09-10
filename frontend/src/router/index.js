import { createRouter, createWebHistory } from "vue-router";

import { carregarSessao, session } from "@/stores/session";

const routes = [
  { path: "/login", name: "login", component: () => import("@/views/Login.vue"), meta: { publica: true } },
  { path: "/", name: "inicio", component: () => import("@/views/Inicio.vue") },
  { path: "/tutores", name: "tutores", component: () => import("@/views/Tutores.vue") },
  { path: "/tutores/:id", name: "tutor-detalhe", component: () => import("@/views/TutorDetalhe.vue"), props: true },
  { path: "/pacientes", name: "pacientes", component: () => import("@/views/pacientes/Lista.vue") },
  { path: "/pacientes/novo", name: "paciente-novo", component: () => import("@/views/pacientes/Form.vue") },
  { path: "/pacientes/:id/editar", name: "paciente-editar", component: () => import("@/views/pacientes/Form.vue"), props: true },
  { path: "/pacientes/:id", name: "paciente-ficha", component: () => import("@/views/pacientes/Ficha.vue"), props: true },
  { path: "/servicos", name: "servicos", component: () => import("@/views/Servicos.vue") },
  { path: "/insumos", name: "insumos", component: () => import("@/views/Insumos.vue") },
  { path: "/agenda", name: "agenda", component: () => import("@/views/Agenda.vue") },
  { path: "/atendimentos", name: "atendimentos", component: () => import("@/views/Atendimentos.vue") },
  {
    path: "/usuarios",
    name: "usuarios",
    component: () => import("@/views/Usuarios.vue"),
    meta: { admin: true },
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

let sessaoCarregada = false;

router.beforeEach(async (to) => {
  if (!sessaoCarregada) {
    await carregarSessao();
    sessaoCarregada = true;
  }

  if (!to.meta.publica && !session.autenticado) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && session.autenticado) {
    return { name: "inicio" };
  }
  if (to.meta.admin && !session.admin) {
    return { name: "inicio" };
  }
  return true;
});
