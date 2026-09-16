<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

import NavBar from "@/components/NavBar.vue";
import TopBar from "@/components/TopBar.vue";
import Toast from "@/components/Toast.vue";
import { session } from "@/stores/session";

const route = useRoute();
const mostrarNav = computed(() => !route.meta.publica && session.autenticado);
</script>

<template>
  <template v-if="mostrarNav">
    <div class="app-shell">
      <NavBar />
      <div class="app-main">
        <TopBar />
        <main class="app-content">
          <router-view v-if="!session.carregando" />
        </main>
      </div>
    </div>
  </template>
  <router-view v-else-if="!session.carregando" />
  <Toast />
</template>
