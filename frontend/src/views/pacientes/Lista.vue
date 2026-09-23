<script setup>
import { onMounted, ref } from "vue";

import { pacientesApi } from "@/api/pacientes";
import { confirmar } from "@/stores/confirm";
import { toast } from "@/stores/toast";
import { especieEmoji } from "@/utils";

const lista = ref([]);
const busca = ref("");

async function carregar() {
  lista.value = await pacientesApi.listar(busca.value);
}

async function excluir(p) {
  if (!(await confirmar("Excluir este paciente e todos os seus dados?"))) return;
  try {
    await pacientesApi.excluir(p.id);
    toast("Paciente removido.");
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
      <h2 style="flex: 1">🐶 Pacientes Cadastrados</h2>
      <router-link class="btn btn-primary" to="/pacientes/novo">+ Novo Paciente</router-link>
    </div>
    <div class="card">
      <div class="search-bar">
        <input v-model="busca" placeholder="Buscar por animal ou tutor..." @input="carregar" />
      </div>
      <div class="table-wrap">
        <div v-if="!lista.length" class="empty"><span class="empty-icon">🐶</span>Nenhum paciente cadastrado.</div>
        <table v-else>
          <thead>
            <tr><th>Animal</th><th>Espécie</th><th>Tutor</th><th>Ações</th></tr>
          </thead>
          <tbody>
            <tr v-for="p in lista" :key="p.id">
              <td>
                <router-link :to="`/pacientes/${p.id}`" class="btn-link">{{ especieEmoji(p.especie) }} {{ p.nome }}</router-link>
              </td>
              <td>{{ p.especie }}{{ p.raca ? " · " + p.raca : "" }}</td>
              <td>{{ p.tutor ? p.tutor.nome : "—" }}</td>
              <td>
                <div class="td-actions">
                  <router-link class="btn btn-edit" :to="`/pacientes/${p.id}/editar`">Editar</router-link>
                  <button class="btn btn-danger" @click="excluir(p)">Excluir</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
