<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { dashboardApi } from "@/api/dashboard";
import { encerrarSessao, session } from "@/stores/session";
import { alternarSidebar } from "@/stores/ui";

const router = useRouter();
const estoqueBaixoQtd = ref(0);
const menuAberto = ref(false);

const iniciais = computed(() => {
  const nome = session.usuario?.nome || "";
  return nome
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
});

async function carregarAlerta() {
  try {
    const alerta = await dashboardApi.estoqueAlerta();
    estoqueBaixoQtd.value = alerta.zerados.length + alerta.baixos.length + alerta.vencidos.length + alerta.vencendo.length;
  } catch {
    /* silencioso — não é crítico para a navegação */
  }
}

onMounted(carregarAlerta);

function sair() {
  encerrarSessao();
  router.push({ name: "login" });
}
</script>

<template>
  <header class="topbar">
    <button class="sidebar-toggle-btn" @click="alternarSidebar" title="Abrir/fechar menu">☰</button>

    <div class="topbar-search">
      <span class="ic">🔍</span>
      <input type="text" placeholder="Buscar paciente, tutor, atendimento..." />
    </div>

    <div class="topbar-spacer"></div>

    <router-link to="/insumos" class="topbar-bell" title="Estoque baixo">
      🔔
      <span v-if="estoqueBaixoQtd > 0" class="bell-badge">{{ estoqueBaixoQtd }}</span>
    </router-link>

    <div v-if="session.usuario" class="topbar-user" @click="menuAberto = !menuAberto">
      <div class="tu-avatar">{{ iniciais }}</div>
      <div class="tu-info">
        <div class="tu-name">{{ session.usuario.nome }}</div>
        <div class="tu-role">{{ session.admin ? "Admin" : "Veterinária" }}</div>
      </div>
      <div v-if="menuAberto" class="topbar-user-menu" @click.stop>
        <button @click="sair">Sair</button>
      </div>
    </div>
  </header>
</template>
