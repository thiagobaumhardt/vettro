<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { login } from "@/api/auth";
import { carregarSessao } from "@/stores/session";

const email = ref("");
const senha = ref("");
const erro = ref("");
const carregando = ref(false);
const router = useRouter();
const route = useRoute();

async function entrar() {
  erro.value = "";
  if (!email.value || !senha.value) {
    erro.value = "Informe e-mail e senha.";
    return;
  }
  carregando.value = true;
  try {
    await login(email.value.trim(), senha.value);
    await carregarSessao();
    router.push(route.query.redirect || { name: "inicio" });
  } catch (e) {
    erro.value = e.message || "Não foi possível entrar.";
  } finally {
    carregando.value = false;
  }
}
</script>

<template>
  <div class="login-wrap">
    <form class="login-card" @submit.prevent="entrar">
      <div style="font-size: 2.4rem; text-align: center; margin-bottom: 6px">🐾</div>
      <h1>Vettro</h1>
      <p class="sub">Entre com o e-mail e senha da clínica</p>
      <div v-if="erro" class="login-error">{{ erro }}</div>
      <div style="margin-bottom: 12px">
        <label>E-mail</label>
        <input v-model="email" type="email" autocomplete="username" placeholder="voce@clinica.com" />
      </div>
      <div>
        <label>Senha</label>
        <input v-model="senha" type="password" autocomplete="current-password" placeholder="••••••••" />
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" type="submit" :disabled="carregando">
          {{ carregando ? "Entrando..." : "Entrar" }}
        </button>
      </div>
    </form>
  </div>
</template>
