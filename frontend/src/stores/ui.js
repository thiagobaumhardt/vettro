import { reactive } from "vue";

const salvo = localStorage.getItem("vettro_sidebar_aberta");

export const ui = reactive({
  sidebarAberta: salvo === null ? true : salvo === "true",
});

export function alternarSidebar() {
  ui.sidebarAberta = !ui.sidebarAberta;
  localStorage.setItem("vettro_sidebar_aberta", String(ui.sidebarAberta));
}
