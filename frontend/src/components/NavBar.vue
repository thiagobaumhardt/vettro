<script setup>
import { useRouter } from "vue-router";

import { session } from "@/stores/session";
import { alternarSidebar, ui } from "@/stores/ui";

const router = useRouter();
</script>

<template>
  <aside class="sidebar" :class="ui.sidebarAberta ? 'sidebar-open' : 'sidebar-closed'">
    <button class="sidebar-logo" @click="router.push({ name: 'inicio' })" title="Ir para o início">
      <span class="logo-text">VETTRO</span>
    </button>

    <nav class="sidebar-nav">
      <router-link to="/" exact-active-class="active"><span class="ic">🏠</span><span class="label">Início</span></router-link>
      <router-link to="/pacientes" active-class="active"><span class="ic">🐾</span><span class="label">Pacientes</span></router-link>
      <router-link to="/tutores" active-class="active"><span class="ic">👤</span><span class="label">Tutores</span></router-link>
      <router-link to="/agenda" active-class="active"><span class="ic">📅</span><span class="label">Agenda</span></router-link>
      <router-link to="/atendimentos" active-class="active"><span class="ic">📋</span><span class="label">Atendimentos</span></router-link>
      <router-link to="/servicos" active-class="active"><span class="ic">💉</span><span class="label">Serviços</span></router-link>
      <router-link to="/insumos" active-class="active"><span class="ic">📦</span><span class="label">Estoque</span></router-link>
      <router-link v-if="session.admin" to="/usuarios" active-class="active"
        ><span class="ic">🔑</span><span class="label">Usuários</span></router-link
      >
      <router-link v-if="session.admin" to="/auditoria" active-class="active"
        ><span class="ic">🛡️</span><span class="label">Auditoria</span></router-link
      >
    </nav>

    <div class="sidebar-footer">Cuidado, técnica<br />e bem-estar animal.</div>
  </aside>
  <div v-if="ui.sidebarAberta" class="sidebar-backdrop" @click="alternarSidebar"></div>
</template>
