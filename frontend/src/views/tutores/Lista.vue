<script setup>
import { onMounted, ref } from "vue";

import { tutoresApi } from "@/api/tutores";
import { confirmar } from "@/stores/confirm";
import { toast } from "@/stores/toast";

const lista = ref([]);
const busca = ref("");

async function carregar() {
  lista.value = await tutoresApi.listar(busca.value);
}

async function excluir(t) {
  if (!(await confirmar("Excluir este tutor?"))) return;
  try {
    await tutoresApi.excluir(t.id);
    toast("Tutor removido.");
    carregar();
  } catch (e) {
    toast(e.message, false);
  }
}

onMounted(carregar);
</script>

<template>
  <div class="tab" style="padding-top: 20px">
    <div class="pac-subpage-header">
      <h2 style="flex: 1">👤 Tutores Cadastrados</h2>
      <router-link class="btn btn-primary" to="/tutores/novo">+ Novo Tutor</router-link>
    </div>
    <div class="card">
      <div class="search-bar">
        <input v-model="busca" placeholder="Buscar por nome ou telefone..." @input="carregar" />
      </div>
      <div class="table-wrap">
        <div v-if="!lista.length" class="empty"><span class="empty-icon">👤</span>Nenhum tutor cadastrado.</div>
        <table v-else>
          <thead>
            <tr><th>Nome</th><th>Telefone</th><th>E-mail</th><th>Como conheceu</th><th>Ações</th></tr>
          </thead>
          <tbody>
            <tr v-for="t in lista" :key="t.id">
              <td><router-link :to="`/tutores/${t.id}`" class="btn-link">{{ t.nome }}</router-link></td>
              <td>{{ t.tel }}</td>
              <td>{{ t.email || "—" }}</td>
              <td>{{ t.como_conheceu || "—" }}</td>
              <td>
                <div class="td-actions">
                  <router-link class="btn btn-edit" :to="`/tutores/${t.id}/editar`">Editar</router-link>
                  <button class="btn btn-danger" @click="excluir(t)">Excluir</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
