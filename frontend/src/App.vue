<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

import NavBar from "@/components/NavBar.vue";
import Toast from "@/components/Toast.vue";
import { session } from "@/stores/session";

const route = useRoute();
const mostrarNav = computed(() => !route.meta.publica && session.autenticado);
</script>

<template>
  <NavBar v-if="mostrarNav" />
  <router-view v-if="!session.carregando" />
  <Toast />
</template>
