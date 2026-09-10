<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { dashboardApi } from "@/api/dashboard";
import { encerrarSessao, session } from "@/stores/session";

const router = useRouter();
const estoqueBaixoQtd = ref(0);

async function carregarAlerta() {
  try {
    const alerta = await dashboardApi.estoqueAlerta();
    estoqueBaixoQtd.value = alerta.zerados.length + alerta.baixos.length;
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
  <header @click="router.push({ name: 'inicio' })" title="Ir para o início">
    <div style="font-size: 2rem; flex-shrink: 0">🐾</div>
    <div style="flex: 1">
      <h1>VetDom</h1>
      <div class="sub">Sistema de Atendimento Veterinário a Domicílio</div>
    </div>
    <div v-if="session.usuario" style="text-align: right; font-size: 0.8rem" @click.stop>
      <div style="font-weight: 700">{{ session.usuario.nome }}</div>
      <div style="opacity: 0.75; margin-bottom: 4px">{{ session.admin ? "Admin" : "Veterinária" }}</div>
      <button class="btn btn-secondary" style="padding: 3px 10px; font-size: 0.72rem" @click="sair">Sair</button>
    </div>
  </header>

  <nav>
    <router-link to="/" exact-active-class="active">🏠 Início</router-link>
    <router-link to="/pacientes" active-class="active">🐶 Pacientes</router-link>
    <router-link to="/tutores" active-class="active">👤 Tutores</router-link>
    <router-link to="/servicos" active-class="active">💉 Serviços</router-link>
    <router-link to="/insumos" active-class="active"
      >📦 Insumos<span v-if="estoqueBaixoQtd > 0" class="nav-badge">{{ estoqueBaixoQtd }}</span></router-link
    >
    <router-link to="/agenda" active-class="active">📅 Agenda</router-link>
    <router-link to="/atendimentos" active-class="active">📋 Atendimentos</router-link>
    <router-link v-if="session.admin" to="/usuarios" active-class="active">🔑 Usuários</router-link>
  </nav>
</template>
